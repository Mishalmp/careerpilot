"""The CV-derived profile and its use in research.
# covers: REQ-28 (dynamic from the CV; nothing hard-coded), owner isolation
"""

from fastapi import FastAPI
from httpx import AsyncClient

from careerpilot.modules.research import rules
from tests.test_research_api import PAGES, FakeSearch, hits, job, setup, start

BASE = "/api/v1/profile"
CV = """
Mishal MP - Software Engineer
Senior Python Full Stack Developer at Acme (2022 - present). 4+ years of professional experience.
Built REST APIs with FastAPI and Django, PostgreSQL and Docker; React and TypeScript front ends.
Also worked as Python Full Stack Developer at Beta Ltd. Open to SDE and Software Developer roles.
"""


async def test_a_new_user_has_an_empty_profile(api: AsyncClient) -> None:
    body = (await api.get(BASE)).json()
    assert body == {
        "has_cv": False,
        "skills": [],
        "role_titles": [],
        "years_experience": None,
        "updated_at": None,
    }


async def test_analysing_a_cv_fills_skills_titles_and_years(api: AsyncClient) -> None:
    body = (await api.put(f"{BASE}/cv", json={"text": CV})).json()
    assert body["has_cv"] is True
    assert {"python", "fastapi", "django", "docker", "react", "typescript"} <= set(body["skills"])
    assert "Python Full Stack Developer" in body["role_titles"]
    assert "Software Developer" in body["role_titles"]
    assert "SDE" in body["role_titles"]
    assert body["years_experience"] == 4
    assert (await api.get(BASE)).json()["skills"] == body["skills"]


async def test_the_owner_can_correct_what_was_read_and_analysing_again_starts_over(
    api: AsyncClient,
) -> None:
    await api.put(f"{BASE}/cv", json={"text": CV})
    edited = (
        await api.patch(
            BASE,
            json={
                "skills": ["Python", "python", " Go Lang ", "Kafka"],
                "role_titles": ["Data Engineer"],
                "years_experience": 3,
            },
        )
    ).json()
    assert edited["skills"] == ["Python", "Go Lang", "Kafka"]
    assert edited["role_titles"] == ["Data Engineer"]
    assert edited["years_experience"] == 3
    only_years = (await api.patch(BASE, json={"years_experience": None})).json()
    assert only_years["skills"] == edited["skills"]  # only what was sent changes
    assert only_years["years_experience"] is None
    again = (await api.put(f"{BASE}/cv", json={"text": CV})).json()
    assert "Kafka" not in again["skills"]


async def test_the_cv_text_can_be_forgotten_and_is_never_returned(api: AsyncClient) -> None:
    await api.put(f"{BASE}/cv", json={"text": CV})
    assert "Acme" not in (await api.get(BASE)).text  # the text is stored, never echoed
    assert (await api.delete(f"{BASE}/cv")).status_code == 204
    after = (await api.get(BASE)).json()
    assert after["has_cv"] is False
    assert after["skills"]  # the derived lists stay until edited


async def test_input_limits(api: AsyncClient) -> None:
    assert (await api.put(f"{BASE}/cv", json={"text": "short"})).status_code == 422
    assert (await api.put(f"{BASE}/cv", json={"text": "x" * 60_001})).status_code == 422
    assert (await api.patch(BASE, json={"skills": ["x"] * 61})).status_code == 422
    assert (await api.patch(BASE, json={"years_experience": 99})).status_code == 422


async def test_profiles_belong_to_their_owner(api: AsyncClient, other_api: AsyncClient) -> None:
    await api.put(f"{BASE}/cv", json={"text": CV})
    assert (await other_api.get(BASE)).json()["skills"] == []
    await other_api.patch(BASE, json={"skills": ["rust"]})
    assert "rust" not in (await api.get(BASE)).json()["skills"]


async def test_signed_out_requests_are_refused(client: AsyncClient) -> None:
    assert (await client.get(BASE)).status_code == 401
    assert (await client.put(f"{BASE}/cv", json={"text": CV})).status_code in (401, 403)


def test_the_plan_uses_your_top_skills_and_stays_bounded() -> None:
    plan = rules.plan_queries(
        "Backend Developer", "Acme", skills=["python", "fastapi", "docker", "react"]
    )
    assert any(q.startswith("python interview questions") for q in plan)
    assert any(q.startswith("docker interview questions") for q in plan)
    assert not any(q.startswith("react interview questions") for q in plan)  # only the top three
    assert len(plan) <= rules.MAX_QUERIES
    assert plan[0] == "Backend Developer interview questions"
    assert rules.plan_queries("Backend Developer", "Acme") == rules.plan_queries(
        "Backend Developer", "Acme", skills=[]
    )


async def test_a_research_run_searches_for_the_profile_skills(
    app: FastAPI, api: AsyncClient
) -> None:
    from tests.fakes import FakeLlm

    await api.put(f"{BASE}/cv", json={"text": CV})
    search = FakeSearch(hits())
    setup(app, search=search, llm=FakeLlm('{"items": []}'), pages=PAGES)
    await start(api, await job(api))
    from tests.test_research_api import run_worker

    await run_worker(app)
    assert any(
        q.startswith("django interview questions") or q.startswith("docker interview questions")
        for q in search.queries
    )
