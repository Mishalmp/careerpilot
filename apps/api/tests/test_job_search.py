"""Finding jobs beyond a few company boards: free job feeds, searches by place and way of working,
a daily list of up to 100, and interview questions ranked by how many pages ask them.
# covers: coverage (feeds), search conditions (India cities, abroad, remote), scale (quick items),
# interview preparation kept current and ranked
"""

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient

from careerpilot.core.search import SearchHit
from careerpilot.modules.discovery.adapters import (
    board_url,
    parse_arbeitnow,
    parse_himalayas,
    parse_remoteok,
    parse_remotive,
    parse_weworkremotely,
)
from careerpilot.modules.discovery.enums import BoardKind
from careerpilot.modules.research import service as research_service
from tests.fakes import FakeLlm, FakeSearch, FakeWeb, run_worker
from tests.test_apply_api import GOOD_JD, build, job, policy, profile, queue, wire
from tests.test_research_api import item, reply

DISCOVERY = "/api/v1/discovery"
JSON = "application/json"


# --- the free feeds -----------------------------------------------------------------------------


def test_remoteok_skips_its_legal_notice_and_reads_jobs() -> None:
    raw = json.dumps(
        [
            {"legal": "API Terms of Service: link back"},
            {
                "id": "1137700",
                "position": "Backend Engineer",
                "company": "Acme",
                "location": "Worldwide",
                "url": "https://remoteok.com/remote-jobs/1137700",
                "apply_url": "https://remoteok.com/remote-jobs/1137700",
                "date": "2026-11-06T13:47:40+00:00",
                "description": "<p>Build <b>APIs</b> in Python.</p>",
            },
            {"id": "2", "position": "No link"},
        ]
    )
    (found,) = parse_remoteok(raw)
    assert (found.external_id, found.title, found.company, found.location) == (
        "1137700",
        "Backend Engineer",
        "Acme",
        "Worldwide",
    )
    assert found.remote is True and "Build APIs in Python." in (found.description or "")
    assert found.published_on is not None and found.published_on.year == 2026


def test_remotive_reads_the_place_a_candidate_must_be_in() -> None:
    raw = json.dumps(
        {
            "00-warning": "x",
            "jobs": [
                {
                    "id": 7,
                    "url": "https://remotive.com/remote-jobs/software-dev/x-7",
                    "title": "Python Developer",
                    "company_name": "Globex",
                    "candidate_required_location": "USA",
                    "publication_date": "2026-11-06T08:51:01",
                    "description": "<p>Python</p>",
                }
            ],
        }
    )
    (found,) = parse_remotive(raw)
    assert (found.company, found.location, found.remote) == ("Globex", "USA", True)


def test_arbeitnow_epoch_seconds_become_the_right_date_and_escaped_html_becomes_text() -> None:
    raw = json.dumps(
        {
            "data": [
                {
                    "slug": "data-eng-1",
                    "company_name": "Mews",
                    "title": "Data Engineer",
                    "remote": False,
                    "url": "https://www.arbeitnow.com/jobs/companies/mews/data-eng-1",
                    "location": "Berlin",
                    "created_at": 1794077723,
                    "description": "&lt;p&gt;Help &lt;strong&gt;us&lt;/strong&gt;&lt;/p&gt;",
                }
            ]
        }
    )
    (found,) = parse_arbeitnow(raw)
    assert found.remote is False and found.location == "Berlin"
    assert found.published_on is not None and found.published_on.year == 2026  # not 1970
    assert "Help us" in (found.description or "") and "<" not in (found.description or "")


def test_himalayas_without_restrictions_means_worldwide() -> None:
    raw = json.dumps(
        {
            "jobs": [
                {
                    "title": "Engineer",
                    "companyName": "A",
                    "locationRestrictions": [],
                    "applicationLink": "https://himalayas.app/companies/a/jobs/1",
                    "guid": "https://himalayas.app/companies/a/jobs/1",
                    "pubDate": 1794079244,
                },
                {
                    "title": "Engineer 2",
                    "companyName": "B",
                    "locationRestrictions": ["United States", "Canada"],
                    "applicationLink": "https://himalayas.app/companies/b/jobs/2",
                    "guid": "https://himalayas.app/companies/b/jobs/2",
                },
            ]
        }
    )
    jobs = parse_himalayas(raw)
    assert [j.location for j in jobs] == ["Worldwide", "United States, Canada"]


def test_weworkremotely_rss_splits_the_company_from_the_title() -> None:
    raw = (
        "<rss><channel><item><title>Squarespace: Staff Software Engineer</title>"
        "<region>Anywhere in the World</region><link>https://weworkremotely.com/jobs/1</link>"
        "<guid>https://weworkremotely.com/jobs/1</guid>"
        "<pubDate>Thu, 06 Nov 2026 10:00:00 +0000</pubDate>"
        "<description>&lt;p&gt;Hello&lt;/p&gt;</description></item></channel></rss>"
    )
    (found,) = parse_weworkremotely(raw)
    assert (found.company, found.title, found.location) == (
        "Squarespace",
        "Staff Software Engineer",
        "Anywhere in the World",
    )
    assert found.published_on is not None and found.published_on.month == 11


def test_each_feed_has_one_fixed_address() -> None:
    assert board_url(BoardKind.REMOTEOK, "all") == "https://remoteok.com/api"
    assert board_url(BoardKind.REMOTIVE, "all") == "https://remotive.com/api/remote-jobs"
    assert board_url(BoardKind.REMOTIVE, "software-dev").endswith("?category=software-dev")
    assert board_url(BoardKind.ARBEITNOW, "all").startswith("https://www.arbeitnow.com/")
    assert board_url(BoardKind.WEWORKREMOTELY, "all").endswith("remote-programming-jobs.rss")


# --- searches by place and way of working -------------------------------------------------------


def gh(*jobs: tuple[int, str, str]) -> tuple[str, str]:
    rows = [
        {
            "id": i,
            "title": t,
            "absolute_url": f"https://job-boards.greenhouse.io/acme/jobs/{i}",
            "location": {"name": place},
        }
        for i, t, place in jobs
    ]
    return json.dumps({"jobs": rows}), JSON


GH = "boards-api.greenhouse.io/v1/boards/acme/jobs"


async def follow(api: AsyncClient) -> str:
    made = await api.post(
        f"{DISCOVERY}/sources",
        json={"kind": "greenhouse", "board": "acme", "company_name": "Acme"},
    )
    assert made.status_code == 201, made.text
    return made.json()["id"]


async def test_a_search_keeps_only_listings_in_your_places_and_ways_of_working(
    app: FastAPI, api: AsyncClient
) -> None:
    app.state.fetcher = FakeWeb(
        {
            GH: gh(
                (1, "Backend Engineer", "Bangalore, India"),
                (2, "Backend Engineer", "Pune, India"),
                (3, "Backend Engineer", "Berlin, Germany"),
                (4, "Backend Engineer", "Hyderabad (Hybrid)"),
                (5, "Backend Engineer", "Springfield"),
            )
        }
    ).fetcher()
    source = await follow(api)
    made = await api.post(
        f"{DISCOVERY}/searches",
        json={
            "name": "India on site",
            "regions": ["India"],
            "cities": ["Bengaluru", "Hyderabad"],
            "work_modes": ["Hybrid", "Onsite"],
        },
    )
    assert made.status_code == 201, made.text
    run = (await api.post(f"{DISCOVERY}/sources/{source}/run")).json()
    assert (run["listed"], run["kept"], run["new"], run["outside_search"]) == (5, 2, 2, 3)
    assert sum(run["left_out"].values()) == 3
    titles = {c["location"] for c in (await api.get(f"{DISCOVERY}/candidates")).json()["items"]}
    assert titles == {"Bangalore, India", "Hyderabad (Hybrid)"}


async def test_without_any_search_nothing_is_filtered_and_a_disabled_search_does_not_count(
    app: FastAPI, api: AsyncClient
) -> None:
    app.state.fetcher = FakeWeb(
        {GH: gh((1, "Engineer", "Berlin"), (2, "Engineer", "Pune"))}
    ).fetcher()
    source = await follow(api)
    assert (await api.post(f"{DISCOVERY}/sources/{source}/run")).json()["kept"] == 2
    search = (
        await api.post(
            f"{DISCOVERY}/searches",
            json={"name": "x", "regions": ["India"], "work_modes": ["Onsite"], "enabled": False},
        )
    ).json()
    app.state.fetcher = FakeWeb(
        {GH: gh((3, "Engineer", "Delhi"), (4, "Engineer", "Rome"))}
    ).fetcher()
    assert (await api.post(f"{DISCOVERY}/sources/{source}/run")).json()["kept"] == 2  # disabled
    await api.patch(f"{DISCOVERY}/searches/{search['id']}", json={"enabled": True})
    app.state.fetcher = FakeWeb(
        {GH: gh((5, "Engineer", "Noida"), (6, "Engineer", "Rome"))}
    ).fetcher()
    assert (await api.post(f"{DISCOVERY}/sources/{source}/run")).json()["kept"] == 1  # Noida only


async def test_searches_are_validated_listed_edited_deleted_and_private(
    api: AsyncClient, other_api: AsyncClient
) -> None:
    for bad in (
        {"name": "x", "regions": [], "work_modes": ["Remote"]},
        {"name": "x", "regions": ["India"], "work_modes": []},
        {"name": "x", "regions": ["Atlantis"], "work_modes": ["Remote"]},
        {"name": "", "regions": ["India"], "work_modes": ["Remote"]},
        {"name": "x", "regions": ["India"], "work_modes": ["Remote"], "cities": ["c"] * 16},
    ):
        assert (await api.post(f"{DISCOVERY}/searches", json=bad)).status_code == 422, bad
    made = (
        await api.post(
            f"{DISCOVERY}/searches",
            json={"name": "Abroad remote", "regions": ["Europe", "USA"], "work_modes": ["Remote"]},
        )
    ).json()
    edited = (
        await api.patch(f"{DISCOVERY}/searches/{made['id']}", json={"cities": ["London"]})
    ).json()
    assert edited["cities"] == ["London"] and edited["regions"] == ["Europe", "USA"]
    assert [s["name"] for s in (await api.get(f"{DISCOVERY}/searches")).json()] == ["Abroad remote"]
    assert (await other_api.get(f"{DISCOVERY}/searches")).json() == []
    assert (await other_api.delete(f"{DISCOVERY}/searches/{made['id']}")).status_code == 404
    assert (await other_api.patch(f"{DISCOVERY}/searches/{made['id']}", json={})).status_code == 404
    assert (await api.delete(f"{DISCOVERY}/searches/{made['id']}")).status_code == 204
    assert (await api.get(f"{DISCOVERY}/searches")).json() == []


async def test_a_feed_job_keeps_its_own_company_and_says_which_feed_listed_it(
    app: FastAPI, api: AsyncClient
) -> None:
    feed = json.dumps(
        [
            {"legal": "terms"},
            {
                "id": "9",
                "position": "Python Developer",
                "company": "Initech",
                "location": "Worldwide",
                "url": "https://remoteok.com/remote-jobs/9",
                "date": "2026-11-06T10:00:00+00:00",
                "description": "<p>Python and FastAPI</p>",
            },
        ]
    )
    app.state.fetcher = FakeWeb({"remoteok.com/api": (feed, JSON)}).fetcher()
    made = await api.post(
        f"{DISCOVERY}/sources",
        json={"kind": "remoteok", "board": "all", "company_name": "RemoteOK"},
    )
    assert made.status_code == 201, made.text
    await api.post(f"{DISCOVERY}/sources/{made.json()['id']}/run")
    (candidate,) = (await api.get(f"{DISCOVERY}/candidates")).json()["items"]
    assert (candidate["company_name"], candidate["via"]) == ("Initech", "RemoteOK")
    accepted = await api.post(f"{DISCOVERY}/candidates/{candidate['id']}/accept")
    assert accepted.status_code == 200
    tracked = (await api.get(f"/api/v1/jobs/{accepted.json()['job_id']}")).json()
    assert tracked["company"]["name"] == "Initech" and "FastAPI" in tracked["jd_text"]
    assert tracked["work_mode"] == "Remote"


# --- the apply list: searches, quick items, up to 100 a day ---------------------------------------


async def test_the_apply_list_only_takes_jobs_that_fit_your_searches(
    app: FastAPI, api: AsyncClient, content: Path
) -> None:
    policy(content, "daily_limit: 10\nmin_match_score: 50\n")
    wire(app, FakeSearch([]))
    await profile(api)
    await api.post(
        f"{DISCOVERY}/searches",
        json={"name": "Pune", "regions": ["India"], "cities": ["Pune"], "work_modes": ["Onsite"]},
    )
    pune = await job(
        api, "Python Backend Developer", "Punecorp", jd_text=GOOD_JD, location_text="Pune, India"
    )
    berlin = await job(
        api,
        "Python Backend Developer",
        "Berlincorp",
        jd_text=GOOD_JD,
        location_text="Berlin, Germany",
    )
    unstated = await job(api, "Python Backend Developer", "Nowhere", jd_text=GOOD_JD)
    await build(app, api)
    listed = {i["job_id"] for i in (await queue(api))["items"]}
    assert pune in listed and unstated in listed  # no place stated: nothing to judge
    assert berlin not in listed


async def test_beyond_the_deep_limit_jobs_are_listed_quickly_and_can_be_researched_on_demand(
    app: FastAPI, api: AsyncClient, content: Path
) -> None:
    policy(content, "daily_limit: 5\ndeep_limit: 1\nmin_match_score: 50\n")
    search = FakeSearch([])
    wire(app, search)
    await profile(api)
    for n in range(3):
        await job(api, "Python Backend Developer", f"Co{n}", jd_text=GOOD_JD)
    await build(app, api)
    items = (await queue(api))["items"]
    assert sorted(i["deep"] for i in items) == [False, False, True]
    quick = next(i for i in items if not i["deep"])
    assert any("Not researched on the web yet" in n for n in quick["notes"])
    assert quick["pay"]["level"] == "posted"  # what the post says is still read
    searches_before = len(search.queries)
    done = await api.post(f"/api/v1/apply/items/{quick['id']}/research")
    assert done.status_code == 200, done.text
    assert done.json()["deep"] is True and len(search.queries) > searches_before
    assert not any("Not researched" in n for n in done.json()["notes"])


async def test_the_daily_limit_can_be_a_hundred_and_no_higher(
    app: FastAPI, api: AsyncClient, content: Path
) -> None:
    await profile(api)
    policy(content, "daily_limit: 100\n")
    assert (await api.get("/api/v1/apply/queue")).json()["policy"]["daily_limit"] == 100
    policy(content, "daily_limit: 101\n")
    assert (await api.get("/api/v1/apply/queue")).json()["policy_problems"]


async def test_researching_another_users_item_is_not_found(
    app: FastAPI, api: AsyncClient, other_api: AsyncClient, content: Path
) -> None:
    policy(content, "daily_limit: 2\nmin_match_score: 50\n")
    wire(app, FakeSearch([]))
    await profile(api)
    await job(api, "Python Backend Developer", "Acme", jd_text=GOOD_JD)
    await build(app, api)
    (mine,) = (await queue(api))["items"]
    assert (await other_api.post(f"/api/v1/apply/items/{mine['id']}/research")).status_code == 404


# --- interview questions ranked by how many pages ask them -----------------------------------------

QUESTION = "What is a database transaction?"
PAGE_ONE = "Interviewers often ask: What is a database transaction? Also revise caching strategies."
PAGE_TWO = "A classic question is: What is a database transaction? Candidates should know ACID."
PAGE_THREE = "Another guide only covers: How do you design a rate limiter for an API?"


def two_pages_ask_the_same_question() -> FakeLlm:
    return FakeLlm(
        replies=[
            reply(
                item("question", "transactions", QUESTION, QUESTION),
                item(
                    "question",
                    "caching",
                    "What is caching strategies?",
                    "revise caching strategies",
                ),
            ),
            reply(item("question", "transactions", QUESTION, QUESTION)),
            reply(
                item(
                    "question",
                    "rate limiting",
                    "How do you design a rate limiter for an API?",
                    "How do you design a rate limiter for an API?",
                )
            ),
        ]
    )


async def test_a_question_found_on_several_pages_is_counted_once_and_ranked_first(
    app: FastAPI, api: AsyncClient
) -> None:
    hits = [
        SearchHit("Guide one", "https://one.example.com/interviews", ""),
        SearchHit("Guide two", "https://two.example.org/questions", ""),
        SearchHit("Guide three", "https://three.example.net/design", ""),
    ]
    app.state.search = FakeSearch(hits)
    app.state.llm = two_pages_ask_the_same_question()
    app.state.fetcher = FakeWeb(
        {
            "one.example.com/interviews": PAGE_ONE,
            "two.example.org/questions": PAGE_TWO,
            "three.example.net/design": PAGE_THREE,
        }
    ).fetcher()
    created = await api.post(
        "/api/v1/jobs", json={"company_name": "Acme", "title": "Backend Developer"}
    )
    job_id = created.json()["job"]["id"] if "job" in created.json() else created.json()["id"]
    assert (await api.post("/api/v1/research/runs", json={"job_id": job_id})).status_code == 202
    assert await run_worker(app)

    found = (await api.get("/api/v1/research/findings")).json()["items"]
    assert next(f["mentions"] for f in found) == 2 and len(found) == 3  # not four: one was merged
    top = found[0]
    assert top["text"] == QUESTION
    assert {s["url"] for s in top["more_sources"]} == {"https://two.example.org/questions"}
    assert all(f["mentions"] == 1 for f in found[1:])


async def test_the_same_page_never_counts_twice(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID
) -> None:
    from careerpilot.modules.research import repository

    app.state.search = FakeSearch([SearchHit("One", "https://one.example.com/a", "")])
    app.state.llm = FakeLlm(reply(item("question", "t", QUESTION, QUESTION)))
    app.state.fetcher = FakeWeb({"one.example.com/a": PAGE_ONE}).fetcher()
    created = await api.post(
        "/api/v1/jobs", json={"company_name": "Acme", "title": "Backend Developer"}
    )
    job_id = created.json()["job"]["id"] if "job" in created.json() else created.json()["id"]
    await api.post("/api/v1/research/runs", json={"job_id": job_id})
    await run_worker(app)
    async with app.state.sessionmaker() as db:
        counted = await repository.add_mention(
            db, owner_id, _key(), url="https://one.example.com/a", title="One"
        )
        assert counted is False  # the page that found it is not a second source


def _key() -> str:
    from careerpilot.modules.research import rules

    return rules.dedupe_key("question", QUESTION)


# --- keeping interview preparation current ----------------------------------------------------------


async def live_jobs(api: AsyncClient, how_many: int) -> None:
    for n in range(how_many):
        made = await api.post(
            "/api/v1/jobs",
            json={"company_name": f"Live{n}", "title": "Backend Developer"},
        )
        data = made.json()
        application = data.get("job", data)["application"]
        moved = await api.post(
            f"/api/v1/applications/{application['id']}/status",
            json={"status": "Shortlisted", "expected_version": application["version"]},
        )
        assert moved.status_code == 200, moved.text


async def test_live_applications_are_researched_again_every_week_a_few_a_day(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID
) -> None:
    await live_jobs(api, 5)
    now = datetime.now(UTC)
    keyed = app.state.settings.model_copy(
        update={"anthropic_api_key": "sk-test", "search_provider": "searxng"}
    )

    async def refresh(settings: Any, at: datetime) -> int:
        async with app.state.sessionmaker() as db:
            return await research_service.refresh_due(db, owner_id, settings, now=at)

    assert await refresh(app.state.settings, now) == 0  # no model key and no search: nothing
    assert await refresh(keyed, now) == 3  # a few a day, not all five
    assert await refresh(keyed, now) == 2  # the other two; the first three were just researched
    assert await refresh(keyed, now) == 0  # all looked at this week
    assert await refresh(keyed, now + timedelta(days=8)) == 3  # a week later, again
