"""The daily apply list end to end, with a fake search service and fake web.
# covers: the assisted daily apply list (docs/phase-7/11, tasks A07-A14): chosen by your policy,
# every part labelled with its source, held back on hard evidence, decided only by you, and no way
# to submit an application
"""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient

from careerpilot.core.clock import today_in
from careerpilot.core.search import SearchHit
from careerpilot.modules.apply import service as apply_service
from careerpilot.worker import schedule_due
from tests.fakes import FakeSearch, FakeWeb, run_worker

BASE = "/api/v1/apply"
JOBS = "/api/v1/jobs"
GOOD_JD = (
    "Python FastAPI PostgreSQL. Salary 12-18 LPA. Our interview process has two rounds: "
    "a coding test and a technical discussion with the team."
)


def policy(content: Path, text: str) -> None:
    (content / "private" / "apply-policy.yaml").write_text(text, encoding="utf-8")


def wire(
    app: FastAPI, search: FakeSearch | None = None, pages: dict[str, Any] | None = None
) -> None:
    app.state.search = search
    app.state.llm = None
    app.state.fetcher = FakeWeb(pages or {}).fetcher()


async def profile(api: AsyncClient) -> None:
    response = await api.patch(
        "/api/v1/profile",
        json={
            "skills": ["Python", "FastAPI", "PostgreSQL"],
            "role_titles": ["Python Backend Developer"],
        },
    )
    assert response.status_code == 200, response.text


async def job(api: AsyncClient, title: str, company: str, **fields: Any) -> str:
    body = {
        "company_name": company,
        "title": title,
        "apply_url": f"https://{company.lower()}.example/apply",
        **fields,
    }
    response = await api.post(JOBS, json=body)
    assert response.status_code in (200, 201), response.text
    data = response.json()
    return data["job"]["id"] if "job" in data else data["id"]


async def build(app: FastAPI, api: AsyncClient) -> None:
    response = await api.post(f"{BASE}/build")
    assert response.status_code == 202, response.text
    assert await run_worker(app)


async def rebuild(app: FastAPI, owner_id: uuid.UUID, minutes: int = 5) -> None:
    """Another build later the same day (the button only queues one per minute)."""
    later = datetime.now(UTC) + timedelta(minutes=minutes)
    async with app.state.sessionmaker() as db:
        assert await apply_service.request_build(db, owner_id, app.state.settings, now=later)
    assert await run_worker(app)


async def queue(api: AsyncClient) -> dict[str, Any]:
    response = await api.get(f"{BASE}/queue")
    assert response.status_code == 200, response.text
    return response.json()


async def setup_basic(app: FastAPI, api: AsyncClient, content: Path) -> dict[str, str]:
    policy(content, "daily_limit: 3\nmin_match_score: 50\n")
    wire(app, FakeSearch([]))
    await profile(api)
    return {
        "good": await job(api, "Python Backend Developer", "Acme", jd_text=GOOD_JD),
        "ok": await job(api, "Python Developer", "Globex", jd_text="Python and Docker."),
        "off": await job(api, "Marketing Manager", "Initech", jd_text="SEO and brand."),
        "nolink": await job(
            api,
            "Python Backend Developer",
            "Hooli",
            jd_text=GOOD_JD,
            apply_url=None,
        ),
    }


# --- before anything is built ---------------------------------------------------------------


async def test_building_needs_a_cv_profile_and_says_so(
    app: FastAPI, api: AsyncClient, content: Path
) -> None:
    response = await api.post(f"{BASE}/build")
    assert response.status_code == 409
    assert "Profile" in response.json()["detail"]


async def test_a_wrong_policy_file_is_reported_not_ignored(
    app: FastAPI, api: AsyncClient, content: Path
) -> None:
    await profile(api)
    policy(content, "daily_limit: 99\nauto_submit: true\n")
    response = await api.post(f"{BASE}/build")
    assert response.status_code == 422
    assert "daily_limit" in response.json()["detail"] and "auto_submit" in response.json()["detail"]
    shown = await queue(api)
    assert shown["policy_problems"]  # the page can tell you what to fix


# --- building and reading -----------------------------------------------------------------------


async def test_the_list_picks_the_best_matches_and_labels_everything(
    app: FastAPI, api: AsyncClient, content: Path
) -> None:
    ids = await setup_basic(app, api, content)
    await build(app, api)
    shown = await queue(api)
    by_job = {i["job_id"]: i for i in shown["items"]}
    assert set(by_job) == {ids["good"], ids["ok"]}  # not the marketing job, not the no-link one
    best = by_job[ids["good"]]
    assert best["match_score"] == 100 and best["status"] == "ready"
    assert any("3 of the 3 skills" in r for r in best["reasons"])
    assert next(i["job_id"] for i in shown["items"]) == ids["good"]  # best first
    # Pay and interview information come from the post itself, with the words they came from.
    assert best["pay"]["level"] == "posted" and best["pay"]["low"] == 1_200_000
    assert "12-18 LPA" in best["pay"]["evidence"][0]["quote"]
    assert best["interview"]["level"] == "posted"
    assert "two rounds" in best["interview"]["points"][0]["quote"]
    # The job with nothing found says what was tried instead of leaving a blank.
    other = by_job[ids["ok"]]
    assert other["pay"]["level"] is None and len(other["pay"]["tried"]) == 4
    assert other["company_check"]["verdict"] == "not_checked"
    assert shown["ready_count"] == 2
    assert "never submits" in shown["notice"]


async def test_the_daily_limit_holds_and_building_twice_adds_nothing(
    app: FastAPI, api: AsyncClient, content: Path, owner_id: uuid.UUID
) -> None:
    await setup_basic(app, api, content)
    policy(content, "daily_limit: 1\nmin_match_score: 50\n")
    await build(app, api)
    assert len((await queue(api))["items"]) == 1
    await rebuild(app, owner_id)
    assert len((await queue(api))["items"]) == 1  # still one: the limit is per day


async def test_a_job_is_never_listed_twice_after_you_skip_it(
    app: FastAPI, api: AsyncClient, content: Path, owner_id: uuid.UUID
) -> None:
    await setup_basic(app, api, content)
    policy(content, "daily_limit: 1\nmin_match_score: 50\n")
    await build(app, api)
    (first,) = (await queue(api))["items"]
    assert (await api.post(f"{BASE}/items/{first['id']}/skip", json={})).status_code == 200
    policy(content, "daily_limit: 2\nmin_match_score: 50\n")
    await rebuild(app, owner_id)
    jobs = [i["job_id"] for i in (await queue(api))["items"]]
    assert len(jobs) == 2 and len(set(jobs)) == 2  # the skipped one stays; another is added
    assert first["job_id"] in jobs


async def test_the_web_fills_in_what_the_post_does_not_say(
    app: FastAPI, api: AsyncClient, content: Path
) -> None:
    policy(content, "min_match_score: 50\n")
    search = FakeSearch(
        answers={
            "Python Developer Acme job": [
                SearchHit(
                    "Python Developer - Acme | Naukri",
                    "https://jobs.example.net/acme-python",
                    "Acme is hiring a Python Developer. Salary 10 - 14 LPA.",
                )
            ]
        }
    )
    wire(app, search)
    await profile(api)
    job_id = await job(api, "Python Developer", "Acme", jd_text="Python and FastAPI.")
    await build(app, api)
    (item,) = (await queue(api))["items"]
    assert item["job_id"] == job_id
    assert item["pay"]["level"] == "same_job_elsewhere"
    assert item["pay"]["evidence"][0]["url"] == "https://jobs.example.net/acme-python"
    assert [x["host"] for x in item["also_listed"]] == ["jobs.example.net"]
    assert len(search.queries) <= 5


async def test_a_red_flag_holds_a_job_back_and_says_why(
    app: FastAPI, api: AsyncClient, content: Path
) -> None:
    policy(content, "daily_limit: 1\nmin_match_score: 50\n")
    wire(app, FakeSearch([]))
    await profile(api)
    bad = await job(
        api,
        "Python Backend Developer",
        "Shady",
        jd_text="Python FastAPI PostgreSQL. Pay a registration fee of Rs 5000 to confirm.",
    )
    good = await job(api, "Python Developer", "Fine", jd_text="Python FastAPI PostgreSQL.")
    await build(app, api)
    items = {i["job_id"]: i for i in (await queue(api))["items"]}
    assert items[bad]["status"] == "blocked"
    assert "asks for money" in items[bad]["decision_note"]
    assert items[good]["status"] == "ready"  # a held-back job does not use up the day's limit


# --- deciding -------------------------------------------------------------------------------


async def tracker(api: AsyncClient, job_id: str) -> dict[str, Any]:
    return (await api.get(f"{JOBS}/{job_id}")).json()["application"]


async def test_approve_then_applied_moves_the_job_through_the_tracker(
    app: FastAPI, api: AsyncClient, content: Path
) -> None:
    ids = await setup_basic(app, api, content)
    await build(app, api)
    item = next(i for i in (await queue(api))["items"] if i["job_id"] == ids["good"])
    item_id = item["id"]

    early = await api.post(f"{BASE}/items/{item_id}/applied", json={})
    assert early.status_code == 409  # approve first

    approved = await api.post(f"{BASE}/items/{item_id}/approve", json={"note": "looks right"})
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    assert (await tracker(api, ids["good"]))["status"] == "Shortlisted"

    done = await api.post(f"{BASE}/items/{item_id}/applied", json={})
    assert done.json()["status"] == "applied"
    application = await tracker(api, ids["good"])
    assert application["status"] == "Applied - Pending"
    expected = today_in(app.state.settings.timezone) + timedelta(days=7)
    assert application["next_followup_on"] == expected.isoformat()

    again = await api.post(f"{BASE}/items/{item_id}/approve", json={})
    assert again.status_code == 409  # a decision is made once


async def test_skipping_leaves_the_tracker_alone(
    app: FastAPI, api: AsyncClient, content: Path
) -> None:
    ids = await setup_basic(app, api, content)
    await build(app, api)
    item = next(i for i in (await queue(api))["items"] if i["job_id"] == ids["good"])
    skipped = await api.post(f"{BASE}/items/{item['id']}/skip", json={"note": "not now"})
    assert skipped.json()["status"] == "skipped"
    assert (await tracker(api, ids["good"]))["status"] == "New"
    assert (await queue(api))["ready_count"] == 1


async def test_a_held_back_job_can_still_be_approved_by_you(
    app: FastAPI, api: AsyncClient, content: Path
) -> None:
    policy(content, "min_match_score: 50\n")
    wire(app, FakeSearch([]))
    await profile(api)
    bad = await job(
        api,
        "Python Backend Developer",
        "Shady",
        jd_text="Python FastAPI PostgreSQL. Pay a registration fee of Rs 5000 to confirm.",
    )
    await build(app, api)
    (item,) = (await queue(api))["items"]
    assert item["status"] == "blocked"
    approved = await api.post(f"{BASE}/items/{item['id']}/approve", json={})
    assert approved.status_code == 200  # your decision, with the warning in front of you
    assert (await tracker(api, bad))["status"] == "Shortlisted"


# --- owners and the missing submit action --------------------------------------------------------


async def test_one_owner_cannot_see_or_decide_anothers_list(
    app: FastAPI, api: AsyncClient, other_api: AsyncClient, content: Path
) -> None:
    await setup_basic(app, api, content)
    await build(app, api)
    (first, *_) = (await queue(api))["items"]
    assert (await queue(other_api))["items"] == []
    for action in ("approve", "applied", "skip"):
        response = await other_api.post(f"{BASE}/items/{first['id']}/{action}", json={})
        assert response.status_code == 404
    assert (await queue(api))["ready_count"] == 2  # untouched


async def test_the_list_needs_a_signed_in_user(client: AsyncClient) -> None:
    assert (await client.get(f"{BASE}/queue")).status_code == 401
    assert (await client.post(f"{BASE}/build")).status_code in (401, 403)


async def test_there_is_no_way_to_submit_or_send_an_application(app: FastAPI) -> None:
    paths = {
        (path, method.upper())
        for path, methods in app.openapi()["paths"].items()
        if "/apply" in path
        for method in methods
    }
    assert paths == {
        (f"{BASE}/queue", "GET"),
        (f"{BASE}/build", "POST"),
        (f"{BASE}/items/{{item_id}}/approve", "POST"),
        (f"{BASE}/items/{{item_id}}/applied", "POST"),
        (f"{BASE}/items/{{item_id}}/skip", "POST"),
    }
    assert not any(word in path for path, _ in paths for word in ("submit", "send", "auto"))


# --- scheduling -----------------------------------------------------------------------------


async def test_the_daily_build_is_queued_once_a_day_and_only_for_users_with_a_profile(
    app: FastAPI, api: AsyncClient, other_api: AsyncClient
) -> None:
    settings = app.state.settings.model_copy(
        update={"apply_hour": 0, "discovery_hour": 23, "digest_hour": 23, "backup_key": None}
    )
    now = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)
    sm = app.state.sessionmaker
    assert await schedule_due(sm, settings, now) == 0  # nobody has a profile yet
    await profile(api)
    assert await schedule_due(sm, settings, now) == 1  # only the user with a profile
    assert await schedule_due(sm, settings, now) == 0  # once per day
    disabled = settings.model_copy(update={"apply_enabled": False})
    assert await schedule_due(sm, disabled, now + timedelta(days=1)) == 0
