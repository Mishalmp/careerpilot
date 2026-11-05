"""Job-board discovery: parsers, the inbox, re-running without duplicates, refused addresses."""

import json
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from careerpilot.modules.discovery.adapters import (
    AdapterError,
    board_url,
    parse_ashby,
    parse_greenhouse,
    parse_lever,
)
from careerpilot.modules.discovery.enums import BoardKind
from careerpilot.modules.discovery.service import matches
from tests.fakes import FakeWeb, Redirect

DISCOVERY = "/api/v1/discovery"
JSON = "application/json"
GH = "boards-api.greenhouse.io/v1/boards/acme/jobs"
LEVER = "api.lever.co/v0/postings/acme?mode=json"
ASHBY = "api.ashbyhq.com/posting-api/job-board/acme"


def greenhouse(*jobs: dict[str, Any]) -> tuple[str, str]:
    return json.dumps({"jobs": list(jobs)}), JSON


def gh_job(job_id: int, title: str, location: str = "Bengaluru") -> dict[str, Any]:
    return {
        "id": job_id,
        "title": title,
        "absolute_url": f"https://job-boards.greenhouse.io/acme/jobs/{job_id}",
        "location": {"name": location},
        "first_published": "2026-10-20T10:00:00-04:00",
    }


# --- parsers -------------------------------------------------------------------------------


def test_greenhouse_entries_without_an_id_title_or_link_are_skipped() -> None:
    raw = json.dumps(
        {
            "jobs": [
                gh_job(1, "Backend Engineer"),
                {"id": 2, "title": "No link"},
                {"title": "No id", "absolute_url": "https://x.example/1"},
                {"id": 3, "title": "Bad link", "absolute_url": "javascript:alert(1)"},
                "not an object",
            ]
        }
    )
    jobs = parse_greenhouse(raw)
    assert [(j.external_id, j.title, j.location) for j in jobs] == [
        ("1", "Backend Engineer", "Bengaluru")
    ]
    assert jobs[0].published_on is not None and jobs[0].description is None


def test_lever_entries_carry_their_description_and_remote_flag() -> None:
    raw = json.dumps(
        [
            {
                "id": "abc",
                "text": "Data Engineer",
                "hostedUrl": "https://jobs.lever.co/acme/abc",
                "applyUrl": "https://jobs.lever.co/acme/abc/apply",
                "categories": {"location": "Remote - India"},
                "descriptionPlain": "Build pipelines.",
                "createdAt": 1760000000000,
                "workplaceType": "remote",
            },
            {"id": "bad", "text": "Missing url"},
        ]
    )
    (job,) = parse_lever(raw)
    assert job.remote and job.description == "Build pipelines." and job.location == "Remote - India"
    assert job.apply_url == "https://jobs.lever.co/acme/abc/apply" and job.published_on is not None


def test_ashby_skips_unlisted_postings() -> None:
    raw = json.dumps(
        {
            "jobs": [
                {
                    "id": "1",
                    "title": "A",
                    "jobUrl": "https://jobs.ashbyhq.com/acme/1",
                    "isRemote": True,
                    "isListed": True,
                },
                {
                    "id": "2",
                    "title": "B",
                    "jobUrl": "https://jobs.ashbyhq.com/acme/2",
                    "isListed": False,
                },
            ]
        }
    )
    jobs = parse_ashby(raw)
    assert [j.external_id for j in jobs] == ["1"] and jobs[0].remote


@pytest.mark.parametrize("parser", [parse_greenhouse, parse_lever, parse_ashby])
@pytest.mark.parametrize("raw", ["", "{broken", '"a string"', '{"jobs": "nope"}', "42"])
def test_unreadable_boards_raise_a_clear_error(parser: Any, raw: str) -> None:
    with pytest.raises(AdapterError):
        parser(raw)


@pytest.mark.parametrize(
    "token", ["", "a/b", "../x", "a b", "acme?x=1", "acme#", "a" * 81, "-acme", "ac\nme"]
)
def test_a_board_name_cannot_change_the_address(token: str) -> None:
    with pytest.raises(AdapterError):
        board_url(BoardKind.GREENHOUSE, token)


def test_each_board_address_stays_on_its_providers_host() -> None:
    assert (
        board_url(BoardKind.GREENHOUSE, "acme")
        == "https://boards-api.greenhouse.io/v1/boards/acme/jobs"
    )
    assert (
        board_url(BoardKind.LEVER, "ac.me-1_x")
        == "https://api.lever.co/v0/postings/ac.me-1_x?mode=json"
    )
    assert (
        board_url(BoardKind.ASHBY, "acme") == "https://api.ashbyhq.com/posting-api/job-board/acme"
    )


def test_title_filters() -> None:
    assert matches("Senior Backend Engineer", [], [])
    assert matches("Senior Backend Engineer", ["backend", "data"], [])
    assert not matches("Sales Manager", ["backend", "data"], [])
    assert not matches("Senior Backend Engineer", ["backend"], ["senior"])
    assert matches("Data Engineer", [], ["sales"])


# --- the API -------------------------------------------------------------------------------


async def add_source(api: AsyncClient, kind: str = "greenhouse", **fields: Any) -> dict[str, Any]:
    body = {"kind": kind, "board": "acme", "company_name": "Acme Robotics", **fields}
    response = await api.post(f"{DISCOVERY}/sources", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def serve(app: FastAPI, pages: dict[str, Any]) -> FakeWeb:
    web = FakeWeb(pages)
    app.state.fetcher = web.fetcher()
    return web


async def inbox(api: AsyncClient, status: str = "new") -> list[dict[str, Any]]:
    return (await api.get(f"{DISCOVERY}/candidates", params={"status": status})).json()["items"]


async def test_requires_login(client: AsyncClient) -> None:
    assert (await client.get(f"{DISCOVERY}/sources")).status_code == 401
    assert (await client.get(f"{DISCOVERY}/candidates")).status_code == 401


async def test_another_owner_cannot_see_run_or_change_anything(
    app: FastAPI, api: AsyncClient, other_api: AsyncClient
) -> None:
    serve(app, {GH: greenhouse(gh_job(1, "Backend Engineer"))})
    source = await add_source(api)
    await api.post(f"{DISCOVERY}/sources/{source['id']}/run")
    candidate = (await inbox(api))[0]

    assert (await other_api.get(f"{DISCOVERY}/sources")).json() == []
    assert (await other_api.get(f"{DISCOVERY}/candidates")).json()["items"] == []
    assert (await other_api.post(f"{DISCOVERY}/sources/{source['id']}/run")).status_code == 404
    assert (
        await other_api.patch(f"{DISCOVERY}/sources/{source['id']}", json={"enabled": False})
    ).status_code == 404
    assert (await other_api.delete(f"{DISCOVERY}/sources/{source['id']}")).status_code == 404
    assert (
        await other_api.post(f"{DISCOVERY}/candidates/{candidate['id']}/accept")
    ).status_code == 404
    assert (
        await other_api.post(f"{DISCOVERY}/candidates/{candidate['id']}/dismiss")
    ).status_code == 404


async def test_sources_are_validated_and_not_added_twice(api: AsyncClient) -> None:
    await add_source(api)
    again = await api.post(
        f"{DISCOVERY}/sources", json={"kind": "greenhouse", "board": "acme", "company_name": "Acme"}
    )
    assert again.status_code == 409
    assert (await add_source(api, kind="lever"))["kind"] == "lever"  # same name, other provider
    for bad in ({"board": "a/b"}, {"board": ""}, {"kind": "workday"}, {"include": ["x"] * 11}):
        body = {"kind": "ashby", "board": "other", "company_name": "X", **bad}
        assert (await api.post(f"{DISCOVERY}/sources", json=body)).status_code == 422


async def test_running_a_board_fills_the_inbox_and_running_again_adds_nothing(
    app: FastAPI, api: AsyncClient
) -> None:
    serve(app, {GH: greenhouse(gh_job(1, "Backend Engineer"), gh_job(2, "Data Engineer"))})
    source = await add_source(api)

    first = (await api.post(f"{DISCOVERY}/sources/{source['id']}/run")).json()
    assert first == {"listed": 2, "kept": 2, "new": 2}
    second = (await api.post(f"{DISCOVERY}/sources/{source['id']}/run")).json()
    assert second == {"listed": 2, "kept": 2, "new": 0}
    assert len(await inbox(api)) == 2

    listed = (await api.get(f"{DISCOVERY}/sources")).json()[0]
    assert listed["new_count"] == 2 and listed["last_listed"] == 2 and listed["last_error"] is None


async def test_a_new_posting_appears_and_old_decisions_survive_a_rerun(
    app: FastAPI, api: AsyncClient
) -> None:
    web = serve(app, {GH: greenhouse(gh_job(1, "Backend Engineer"), gh_job(2, "Data Engineer"))})
    source = await add_source(api)
    await api.post(f"{DISCOVERY}/sources/{source['id']}/run")
    by_title = {c["title"]: c for c in await inbox(api)}
    await api.post(f"{DISCOVERY}/candidates/{by_title['Data Engineer']['id']}/dismiss")

    web.pages[GH] = greenhouse(
        gh_job(1, "Backend Engineer"), gh_job(2, "Data Engineer"), gh_job(3, "Platform Engineer")
    )
    rerun = (await api.post(f"{DISCOVERY}/sources/{source['id']}/run")).json()
    assert rerun["new"] == 1
    assert sorted(c["title"] for c in await inbox(api)) == ["Backend Engineer", "Platform Engineer"]
    assert [c["title"] for c in await inbox(api, "dismissed")] == [
        "Data Engineer"
    ]  # stays dismissed

    assert (
        await api.post(f"{DISCOVERY}/candidates/{by_title['Data Engineer']['id']}/restore")
    ).status_code == 204
    assert len(await inbox(api)) == 3


async def test_a_posting_that_leaves_the_board_is_marked_not_listed(
    app: FastAPI, api: AsyncClient
) -> None:
    web = serve(app, {GH: greenhouse(gh_job(1, "Backend Engineer"), gh_job(2, "Data Engineer"))})
    source = await add_source(api)
    await api.post(f"{DISCOVERY}/sources/{source['id']}/run")
    web.pages[GH] = greenhouse(gh_job(1, "Backend Engineer"))
    await api.post(f"{DISCOVERY}/sources/{source['id']}/run")
    listed = {c["title"]: c["listed"] for c in await inbox(api)}
    assert listed == {"Backend Engineer": True, "Data Engineer": False}


async def test_the_inbox_says_how_many_there_are_in_total(app: FastAPI, api: AsyncClient) -> None:
    from careerpilot.modules.discovery import repository

    serve(app, {GH: greenhouse(*(gh_job(n, f"Engineer {n}") for n in range(1, 6)))})
    source = await add_source(api)
    await api.post(f"{DISCOVERY}/sources/{source['id']}/run")
    original = repository.CANDIDATE_LIMIT
    repository.CANDIDATE_LIMIT = 3
    try:
        body = (await api.get(f"{DISCOVERY}/candidates")).json()
    finally:
        repository.CANDIDATE_LIMIT = original
    assert len(body["items"]) == 3 and body["total"] == 5
    only = await api.get(f"{DISCOVERY}/candidates", params={"source_id": source["id"]})
    assert only.json()["total"] == 5


async def test_keyword_filters_decide_what_reaches_the_inbox(
    app: FastAPI, api: AsyncClient
) -> None:
    serve(
        app,
        {
            GH: greenhouse(
                gh_job(1, "Backend Engineer"),
                gh_job(2, "Senior Backend Engineer"),
                gh_job(3, "Account Executive"),
            )
        },
    )
    source = await add_source(api, include=["engineer"], exclude=["senior"])
    result = (await api.post(f"{DISCOVERY}/sources/{source['id']}/run")).json()
    assert result == {"listed": 3, "kept": 1, "new": 1}
    assert [c["title"] for c in await inbox(api)] == ["Backend Engineer"]


async def test_lever_and_ashby_boards_work_the_same_way(app: FastAPI, api: AsyncClient) -> None:
    serve(
        app,
        {
            LEVER: (
                json.dumps(
                    [
                        {
                            "id": "l1",
                            "text": "SRE",
                            "hostedUrl": "https://jobs.lever.co/acme/l1",
                            "descriptionPlain": "Keep it up.",
                        }
                    ]
                ),
                JSON,
            ),
            ASHBY: (
                json.dumps(
                    {
                        "jobs": [
                            {
                                "id": "a1",
                                "title": "ML Engineer",
                                "jobUrl": "https://jobs.ashbyhq.com/acme/a1",
                                "isRemote": True,
                            }
                        ]
                    }
                ),
                JSON,
            ),
        },
    )
    lever, ashby = await add_source(api, "lever"), await add_source(api, "ashby")
    assert (await api.post(f"{DISCOVERY}/sources/{lever['id']}/run")).json()["new"] == 1
    assert (await api.post(f"{DISCOVERY}/sources/{ashby['id']}/run")).json()["new"] == 1
    assert {c["title"]: c["remote"] for c in await inbox(api)} == {
        "SRE": False,
        "ML Engineer": True,
    }


# --- failures ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pages", "expected"),
    [
        ({}, "404"),  # no such board
        ({GH: ("{broken", JSON)}, "valid JSON"),
        ({GH: ('{"jobs": "x"}', JSON)}, "unexpected shape"),
        ({GH: ("<html>nope</html>", "text/html")}, "valid JSON"),
    ],
)
async def test_a_board_that_cannot_be_read_is_reported_and_remembered(
    app: FastAPI, api: AsyncClient, pages: dict[str, Any], expected: str
) -> None:
    serve(app, pages)
    source = await add_source(api)
    response = await api.post(f"{DISCOVERY}/sources/{source['id']}/run")
    assert response.status_code == 502 and expected in response.json()["detail"]
    shown = (await api.get(f"{DISCOVERY}/sources")).json()[0]
    assert expected in shown["last_error"] and shown["last_run_at"] is not None


async def test_a_board_that_redirects_to_a_blocked_site_is_refused(
    app: FastAPI, api: AsyncClient
) -> None:
    web = serve(app, {GH: Redirect("https://www.linkedin.com/company/acme/jobs")})
    source = await add_source(api)
    response = await api.post(f"{DISCOVERY}/sources/{source['id']}/run")
    assert response.status_code == 502 and "automated access" in response.json()["detail"]
    assert not any("linkedin" in request for request in web.requests)


async def test_a_board_that_redirects_to_an_internal_address_is_refused(
    app: FastAPI, api: AsyncClient
) -> None:
    serve(app, {GH: Redirect("http://169.254.169.254/latest/meta-data/")})
    source = await add_source(api)
    response = await api.post(f"{DISCOVERY}/sources/{source['id']}/run")
    assert response.status_code == 502 and "public address" in response.json()["detail"]


async def test_an_oversized_board_is_refused_not_half_read(app: FastAPI, api: AsyncClient) -> None:
    serve(app, {GH: greenhouse(gh_job(1, "Backend Engineer"))})
    from careerpilot.modules.discovery import adapters

    original = adapters.BOARD_MAX_BYTES
    adapters.BOARD_MAX_BYTES = 20
    try:
        source = await add_source(api)
        response = await api.post(f"{DISCOVERY}/sources/{source['id']}/run")
    finally:
        adapters.BOARD_MAX_BYTES = original
    assert response.status_code == 502 and "8 MB" in response.json()["detail"]
    assert await inbox(api) == []


# --- accepting into the tracker ------------------------------------------------------------


async def test_accepting_creates_one_tracker_job_with_the_listing_details(
    app: FastAPI, api: AsyncClient
) -> None:
    serve(
        app,
        {
            LEVER: (
                json.dumps(
                    [
                        {
                            "id": "l1",
                            "text": "Data Engineer",
                            "hostedUrl": "https://jobs.lever.co/acme/l1",
                            "categories": {"location": "Remote - India"},
                            "descriptionPlain": "Build pipelines with Python and dbt.",
                            "workplaceType": "remote",
                        }
                    ]
                ),
                JSON,
            )
        },
    )
    source = await add_source(api, "lever")
    await api.post(f"{DISCOVERY}/sources/{source['id']}/run")
    candidate = (await inbox(api))[0]

    accepted = (await api.post(f"{DISCOVERY}/candidates/{candidate['id']}/accept")).json()
    assert accepted["already_tracked"] is False
    job = (await api.get(f"/api/v1/jobs/{accepted['job_id']}")).json()
    assert job["company"]["name"] == "Acme Robotics" and job["title"] == "Data Engineer"
    assert job["work_mode"] == "Remote" and job["jd_url"] == "https://jobs.lever.co/acme/l1"
    assert (
        job["jd_text"] == "Build pipelines with Python and dbt."
        and job["application"]["status"] == "New"
    )

    # Accepting again, or re-running the board, never makes a second job.
    again = (await api.post(f"{DISCOVERY}/candidates/{candidate['id']}/accept")).json()
    assert again == {"job_id": accepted["job_id"], "already_tracked": True}
    await api.post(f"{DISCOVERY}/sources/{source['id']}/run")
    assert (await api.get("/api/v1/jobs")).json()["items"].__len__() == 1
    assert await inbox(api) == [] and len(await inbox(api, "accepted")) == 1


async def test_a_job_you_already_track_is_recognised_not_duplicated(
    app: FastAPI, api: AsyncClient
) -> None:
    serve(app, {GH: greenhouse(gh_job(1, "Backend Engineer", "Bengaluru"))})
    source = await add_source(api)
    await api.post(f"{DISCOVERY}/sources/{source['id']}/run")
    candidate = (await inbox(api))[0]
    # The same posting was added by hand earlier (same company, title, place and apply link).
    manual = await api.post(
        "/api/v1/jobs",
        json={
            "company_name": "Acme Robotics",
            "title": "Backend Engineer",
            "location_text": "Bengaluru",
            "apply_url": "https://job-boards.greenhouse.io/acme/jobs/1",
        },
    )
    accepted = (await api.post(f"{DISCOVERY}/candidates/{candidate['id']}/accept")).json()
    assert accepted["already_tracked"] is True and accepted["job_id"] == manual.json()["id"]
    assert len((await api.get("/api/v1/jobs")).json()["items"]) == 1


async def test_greenhouse_descriptions_are_fetched_only_when_you_accept(
    app: FastAPI, api: AsyncClient
) -> None:
    detail = json.dumps(
        {"content": "&lt;p&gt;Own the &lt;b&gt;ingestion&lt;/b&gt; service.&lt;/p&gt;"}
    )
    web = serve(
        app,
        {
            GH: greenhouse(gh_job(7, "Backend Engineer")),
            "boards-api.greenhouse.io/v1/boards/acme/jobs/7": (detail, JSON),
        },
    )
    source = await add_source(api)
    await api.post(f"{DISCOVERY}/sources/{source['id']}/run")
    assert not any(request.endswith("/jobs/7") for request in web.requests)

    candidate = (await inbox(api))[0]
    accepted = (await api.post(f"{DISCOVERY}/candidates/{candidate['id']}/accept")).json()
    job = (await api.get(f"/api/v1/jobs/{accepted['job_id']}")).json()
    assert job["jd_text"] == "Own the ingestion service."


async def test_an_accepted_listing_cannot_be_dismissed(app: FastAPI, api: AsyncClient) -> None:
    serve(app, {GH: greenhouse(gh_job(1, "Backend Engineer"))})
    source = await add_source(api)
    await api.post(f"{DISCOVERY}/sources/{source['id']}/run")
    candidate = (await inbox(api))[0]
    await api.post(f"{DISCOVERY}/candidates/{candidate['id']}/accept")
    assert (await api.post(f"{DISCOVERY}/candidates/{candidate['id']}/dismiss")).status_code == 409


async def test_deleting_a_source_removes_its_unaccepted_listings_but_keeps_tracked_jobs(
    app: FastAPI, api: AsyncClient
) -> None:
    serve(app, {GH: greenhouse(gh_job(1, "Backend Engineer"), gh_job(2, "Data Engineer"))})
    source = await add_source(api)
    await api.post(f"{DISCOVERY}/sources/{source['id']}/run")
    await api.post(f"{DISCOVERY}/candidates/{(await inbox(api))[0]['id']}/accept")
    assert (await api.delete(f"{DISCOVERY}/sources/{source['id']}")).status_code == 204
    assert await inbox(api) == [] and len((await api.get("/api/v1/jobs")).json()["items"]) == 1
