"""Interview intel end to end: sources, quote-checked extraction, peers, access rules."""

import json
from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient

from tests.fakes import FakeLlm, FakeWeb

JOBS = "/api/v1/jobs"

BLOG = (
    "How we hire engineers at Fabrikam. First there is a 30 minute recruiter call. "
    "Then a take-home coding test in Python that should take about two hours. "
    "The final round is a system design conversation about a multi-tenant service. "
) * 2
PASTED = (
    "Interview experience, 2026. The coding test was about SQL window functions and I was asked "
    "to explain the difference between RANK and DENSE_RANK. System design covered rate limiting."
)


def extraction(*items: dict[str, str]) -> str:
    return json.dumps({"items": list(items)})


def item(
    kind: str, key: str, quote: str, text: str = "Something the source says."
) -> dict[str, str]:
    return {"kind": kind, "key": key, "text": text, "quote": quote}


async def new_job(api: AsyncClient, company: str = "Fabrikam Cloud") -> dict[str, Any]:
    response = await api.post(
        JOBS, json={"company_name": company, "title": "Backend Engineer", "jd_text": "Python role."}
    )
    return response.json()


def base(job: dict[str, Any]) -> str:
    return f"{JOBS}/{job['id']}/intel"


async def test_requires_login(client: AsyncClient) -> None:
    nothing = "00000000-0000-0000-0000-000000000000"
    assert (await client.get(f"{JOBS}/{nothing}/intel")).status_code == 401


async def test_another_owner_cannot_see_or_change_intel(
    app: FastAPI, api: AsyncClient, other_api: AsyncClient
) -> None:
    app.state.llm = None
    job = await new_job(api)
    created = await api.post(f"{base(job)}/sources", json={"label": "My notes", "text": PASTED})
    source_id = created.json()["source"]["id"]
    assert (await other_api.get(base(job))).status_code == 404
    assert (
        await other_api.post(f"{base(job)}/sources", json={"label": "x", "text": PASTED})
    ).status_code == 404
    assert (await other_api.delete(f"{base(job)}/sources/{source_id}")).status_code == 404
    assert len((await api.get(base(job))).json()["sources"]) == 1


async def test_a_source_without_a_model_is_kept_unread(app: FastAPI, api: AsyncClient) -> None:
    app.state.llm = None
    job = await new_job(api)
    body = (await api.post(f"{base(job)}/sources", json={"label": "Notes", "text": PASTED})).json()
    assert body["kept"] == 0 and body["source"]["kind"] == "pasted"
    assert (await api.get(base(job))).json()["ai_available"] is False
    assert (
        await api.post(f"{base(job)}/sources/{body['source']['id']}/extract")
    ).status_code == 409


async def test_only_facts_whose_quote_is_in_the_source_are_kept(
    app: FastAPI, api: AsyncClient
) -> None:
    llm = FakeLlm(
        extraction(
            item(
                "round",
                "coding test",
                "The coding test was about SQL window functions",
            ),
            item("question", "sql", "explain the difference between RANK and DENSE_RANK"),
            item("topic", "system design", "System design covered rate limiting"),
            item(
                "question",
                "sql",
                "asked to explain the difference between RANK and DENSE_RANK and ROW_NUMBER",
            ),
            item("tip", "process", "Practise on a whiteboard for three weeks"),  # invented
            item("topic", "go", ""),  # no quote
        )
    )
    app.state.llm = llm
    job = await new_job(api)
    body = (await api.post(f"{base(job)}/sources", json={"label": "Notes", "text": PASTED})).json()
    assert body["kept"] == 3 and body["dropped"] == 3
    assert "<source>" in llm.calls[0]["user"] and "untrusted" in llm.calls[0]["system"]

    intel = (await api.get(base(job))).json()
    assert [q["quote"] for q in intel["brief"]["likely_questions"]] == [
        "explain the difference between RANK and DENSE_RANK"
    ]
    assert {t["key"] for t in intel["brief"]["topics"]} == {"sql", "system design"}
    assert intel["brief"]["needs_more_sources"] is True
    assert "prediction" in intel["note"]


async def test_a_fetched_page_is_read_through_the_safe_fetcher(
    app: FastAPI, api: AsyncClient
) -> None:
    app.state.fetcher = FakeWeb({"blog.fabrikam.example/hiring": f"<p>{BLOG}</p>"}).fetcher()
    app.state.llm = FakeLlm(
        extraction(item("round", "recruiter call", "a 30 minute recruiter call"))
    )
    job = await new_job(api)
    url = f"{base(job)}/sources"

    ok = await api.post(
        url,
        json={
            "label": "Hiring blog",
            "url": "https://blog.fabrikam.example/hiring",
            "published_on": "2026-03-01",
        },
    )
    assert (
        ok.status_code == 201
        and ok.json()["source"]["kind"] == "fetched"
        and ok.json()["kept"] == 1
    )

    for bad in ("https://www.glassdoor.com/Interview/x", "https://nowhere.example/x"):
        assert (await api.post(url, json={"label": "x", "url": bad})).status_code == 422
    assert (await api.post(url, json={"label": "x"})).status_code == 422
    assert (
        await api.post(url, json={"label": "x", "url": "javascript:alert(1)"})
    ).status_code == 422


async def test_texts_about_another_company_are_marked_inferred(
    app: FastAPI, api: AsyncClient
) -> None:
    app.state.llm = FakeLlm(extraction(item("topic", "sql", "SQL window functions")))
    job = await new_job(api)
    await api.post(
        f"{base(job)}/sources",
        json={"label": "Peer write-up", "text": PASTED, "about_company": "Contoso"},
    )
    intel = (await api.get(base(job))).json()
    assert intel["sources"][0]["inferred"] is True
    topic = intel["brief"]["topics"][0]
    assert topic["inferred_only"] is True
    # A peer's own sources never count as sources about this company.
    assert intel["brief"]["own_recent_sources"] == 0


async def test_corroboration_raises_reliability_and_sources_can_be_deleted(
    app: FastAPI, api: AsyncClient
) -> None:
    app.state.llm = FakeLlm(extraction(item("topic", "sql", "SQL window functions")))
    job = await new_job(api)
    first = (
        await api.post(
            f"{base(job)}/sources",
            json={"label": "A", "text": PASTED, "published_on": "2026-05-01"},
        )
    ).json()
    alone = (await api.get(base(job))).json()["brief"]["topics"][0]["reliability"]
    await api.post(
        f"{base(job)}/sources",
        json={"label": "B", "text": PASTED + " Again.", "published_on": "2026-06-01"},
    )
    topic = (await api.get(base(job))).json()["brief"]["topics"][0]
    assert topic["sources"] == 2 and topic["reliability"] > alone

    assert (await api.delete(f"{base(job)}/sources/{first['source']['id']}")).status_code == 204
    assert (await api.delete(f"{base(job)}/sources/{first['source']['id']}")).status_code == 404
    assert len((await api.get(base(job))).json()["sources"]) == 1


async def test_peer_and_question_suggestions_are_labelled_and_need_a_model(
    app: FastAPI, api: AsyncClient
) -> None:
    job = await new_job(api)
    app.state.llm = None
    assert (await api.post(f"{base(job)}/peers")).status_code == 409

    app.state.llm = FakeLlm(
        json.dumps(
            {
                "peers": [
                    {"name": "Contoso", "why": "Similar size."},
                    {"name": "Fabrikam Cloud", "why": "itself"},
                ]
            }
        )
    )
    peers = (await api.post(f"{base(job)}/peers")).json()
    assert [p["name"] for p in peers["peers"]] == ["Contoso"]  # never itself
    assert "not facts" in peers["note"]

    app.state.llm = FakeLlm(
        json.dumps(
            {
                "questions": [
                    "How does the team handle on-call?",
                    "What does a good first quarter look like?",
                    "How are services deployed here?",
                ]
            }
        )
    )
    asked = (await api.post(f"{base(job)}/questions-to-ask")).json()
    assert len(asked["questions"]) == 3
