"""From a followed board to the daily list, and saying why when the list is empty.
# covers: the feed-to-list pipeline (docs/phase-7/14): listings that fit your searches reach the
# tracker by themselves, the list is built from them, and every empty result has a written reason
"""

import uuid
from pathlib import Path

from fastapi import FastAPI
from httpx import AsyncClient

from tests.fakes import FakeSearch, FakeWeb, run_worker
from tests.test_apply_api import BASE, build, policy, profile, queue
from tests.test_discovery import DISCOVERY, GH, add_source, gh_job, greenhouse

TASKS = "/api/v1/tasks"


async def latest_task(api: AsyncClient, kind: str) -> dict[str, object]:
    listing = (await api.get(TASKS)).json()["items"]
    return next(t for t in listing if t["kind"] == kind)


async def results_of(api: AsyncClient, kind: str) -> list[str]:
    task = await latest_task(api, kind)
    detail = (await api.get(f"{TASKS}/{task['id']}")).json()
    return [e["message"] for e in detail["events"] if e["level"] == "result"]


def wire(app: FastAPI, pages: dict[str, object]) -> None:
    app.state.search = FakeSearch([])
    app.state.llm = None
    app.state.fetcher = FakeWeb(pages).fetcher()  # type: ignore[arg-type]


async def read_board(app: FastAPI, api: AsyncClient, source_id: str) -> None:
    queued = await api.post(f"{DISCOVERY}/sources/{source_id}/run")
    assert queued.status_code == 200, queued.text


async def test_listings_that_fit_reach_the_list_without_accepting_them_by_hand(
    app: FastAPI, api: AsyncClient, content: Path
) -> None:
    policy(content, "daily_limit: 5\nmin_match_score: 40\nauto_add_limit: 10\n")
    wire(
        app,
        {
            GH: greenhouse(
                gh_job(1, "Python Backend Developer", "Bengaluru"),
                gh_job(2, "Python Developer", "Remote - India"),
                gh_job(3, "Marketing Manager", "Bengaluru"),
            )
        },
    )
    await profile(api)
    source = await add_source(api)
    await read_board(app, api, source["id"])
    assert (await api.get("/api/v1/jobs")).json()["items"] == []  # nothing in the tracker yet

    await build(app, api)
    items = (await queue(api))["items"]
    titles = {i["title"] for i in items}
    assert {"Python Backend Developer", "Python Developer"} <= titles
    assert "Marketing Manager" not in titles  # below the match minimum, so not listed
    tracker = (await api.get("/api/v1/jobs")).json()["items"]
    assert len(tracker) == 2  # the marketing job stayed waiting: its title does not match the CV

    lines = await results_of(api, "apply_queue")
    assert any(line.startswith("Copied 2 new listings") for line in lines)
    assert any(
        "1 stayed waiting because their title does not match your CV" in line for line in lines
    )
    waiting = (await api.get(f"{DISCOVERY}/candidates", params={"status": "new"})).json()["items"]
    assert [c["title"] for c in waiting] == ["Marketing Manager"]  # still there for you to judge


async def test_auto_add_can_be_turned_off_and_is_capped(
    app: FastAPI, api: AsyncClient, content: Path
) -> None:
    policy(content, "daily_limit: 5\nauto_add_limit: 1\n")
    wire(app, {GH: greenhouse(gh_job(1, "Python Developer"), gh_job(2, "Python Engineer"))})
    await profile(api)
    source = await add_source(api)
    await read_board(app, api, source["id"])
    await build(app, api)
    assert len((await api.get("/api/v1/jobs")).json()["items"]) == 1  # the cap held

    policy(content, "daily_limit: 5\nauto_add_limit: 0\n")
    await api.post(f"{BASE}/build")  # same minute: not queued again, so build another way
    assert len((await api.get("/api/v1/jobs")).json()["items"]) == 1


async def test_an_empty_tracker_says_what_to_do_not_just_nothing(
    app: FastAPI, api: AsyncClient, content: Path
) -> None:
    policy(content, "daily_limit: 5\nauto_add_limit: 0\n")
    wire(app, {})
    await profile(api)
    await build(app, api)
    data = await queue(api)
    assert data["items"] == []
    joined = " ".join(data["last_build"])
    assert "0 open job(s)" in joined and "Follow job boards" in joined


async def test_jobs_the_policy_refuses_are_counted_with_reasons(
    app: FastAPI, api: AsyncClient, content: Path
) -> None:
    policy(content, "daily_limit: 5\nauto_add_limit: 0\nregions: [India]\n")
    wire(app, {})
    await profile(api)
    for title, region in (("Python Developer", "Europe"), ("Python Engineer", "USA")):
        response = await api.post(
            "/api/v1/jobs",
            json={
                "company_name": f"Co {title}",
                "title": title,
                "region": region,
                "apply_url": f"https://{uuid.uuid4().hex}.example/apply",
            },
        )
        assert response.status_code == 201, response.text
    await build(app, api)
    joined = " ".join((await queue(api))["last_build"])
    assert "2 outside the regions in your policy" in joined


async def test_a_board_read_records_what_was_kept_and_why_the_rest_was_not(
    app: FastAPI, api: AsyncClient
) -> None:
    wire(
        app,
        {
            GH: greenhouse(
                gh_job(1, "Python Developer", "Bengaluru"),
                gh_job(2, "Python Engineer", "Berlin"),
                gh_job(3, "Python Lead", "Berlin"),
            )
        },
    )
    made = await api.post(
        f"{DISCOVERY}/searches",
        json={
            "name": "India on site",
            "regions": ["India"],
            "cities": ["Bengaluru"],
            "work_modes": ["Onsite", "Hybrid"],
        },
    )
    assert made.status_code == 201, made.text
    source = await add_source(api)
    run = (await api.post(f"{DISCOVERY}/sources/{source['id']}/run")).json()
    assert run["kept"] == 1 and run["outside_search"] == 2 and sum(run["left_out"].values()) == 2

    shown = next(
        s for s in (await api.get(f"{DISCOVERY}/sources")).json() if s["id"] == source["id"]
    )
    assert shown["last_kept"] == 1 and sum(shown["left_out"].values()) == 2


async def test_the_scheduled_discovery_task_writes_its_outcome_into_the_history(
    app: FastAPI, api: AsyncClient
) -> None:
    wire(app, {GH: greenhouse(gh_job(1, "Python Developer", "Berlin"))})
    made = await api.post(
        f"{DISCOVERY}/searches",
        json={"name": "India remote", "regions": ["India"], "work_modes": ["Remote"]},
    )
    assert made.status_code == 201, made.text
    await add_source(api)
    from datetime import UTC, datetime

    from careerpilot.worker import schedule_due

    settings = app.state.settings.model_copy(
        update={"apply_hour": 23, "discovery_hour": 0, "digest_hour": 23, "backup_key": None}
    )
    now = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)
    assert await schedule_due(app.state.sessionmaker, settings, now) >= 1
    while await run_worker(app):
        pass
    lines = await results_of(api, "discover")
    assert any("1 jobs listed, 0 fit your searches" in line for line in lines)
    task = await latest_task(api, "discover")
    detail = (await api.get(f"{TASKS}/{task['id']}")).json()
    assert any(
        e["level"] == "warning" and "add an 'India: remote'" in e["message"]
        for e in detail["events"]
    )


# --- the checked list of company boards ---------------------------------------------------------


def test_the_real_suggested_boards_file_is_valid_and_has_no_repeats() -> None:
    from careerpilot.core.config import REPO_ROOT
    from careerpilot.modules.discovery.suggestions import load_suggestions

    boards = load_suggestions(REPO_ROOT / "content")
    assert len(boards) >= 30
    assert len({b.key for b in boards}) == len(boards)
    assert any("india" in b.tags for b in boards) and any("remote" in b.tags for b in boards)


async def test_suggested_boards_are_followed_once_and_only_from_the_checked_list(
    app: FastAPI, api: AsyncClient, other_api: AsyncClient
) -> None:
    listing = (await api.get(f"{DISCOVERY}/suggestions")).json()
    assert listing and all(not b["followed"] for b in listing)
    keys = [b["key"] for b in listing[:3]]

    done = (await api.post(f"{DISCOVERY}/suggestions/follow", json={"keys": keys})).json()
    assert done == {"added": 3, "already": 0}
    again = (await api.post(f"{DISCOVERY}/suggestions/follow", json={"keys": keys})).json()
    assert again == {"added": 0, "already": 3}
    followed = {
        b["key"] for b in (await api.get(f"{DISCOVERY}/suggestions")).json() if b["followed"]
    }
    assert followed == set(keys)
    sources = (await api.get(f"{DISCOVERY}/sources")).json()
    assert {f"{s['kind']}/{s['board']}" for s in sources} == set(keys)

    unknown = await api.post(
        f"{DISCOVERY}/suggestions/follow", json={"keys": ["greenhouse/not-listed"]}
    )
    assert unknown.status_code == 422
    assert (await api.post(f"{DISCOVERY}/suggestions/follow", json={"keys": []})).status_code == 422

    mine_only = (await other_api.get(f"{DISCOVERY}/suggestions")).json()
    assert all(not b["followed"] for b in mine_only)  # another owner's choices are not shared
