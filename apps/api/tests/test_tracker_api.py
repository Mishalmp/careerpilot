import csv
import io
from typing import Any

import pytest
from httpx import AsyncClient

JOBS = "/api/v1/jobs"


async def add_job(api: AsyncClient, **overrides: Any) -> dict[str, Any]:
    body = {"company_name": "Acme", "title": "Backend Engineer", **overrides}
    response = await api.post(JOBS, json=body)
    assert response.status_code in (200, 201), response.text
    return response.json()


async def detail(api: AsyncClient, job: dict[str, Any]) -> dict[str, Any]:
    response = await api.get(f"{JOBS}/{job['id']}")
    assert response.status_code == 200, response.text
    return response.json()


async def move(api: AsyncClient, job: dict[str, Any], status: str, **extra: Any):
    """Change status using the application's current version, like the UI does."""
    current = await detail(api, job)
    application = current["application"]
    return await api.post(
        f"/api/v1/applications/{application['id']}/status",
        json={"status": status, "expected_version": application["version"], **extra},
    )


async def test_requires_login(client: AsyncClient) -> None:
    assert (await client.get(JOBS)).status_code == 401
    created = await client.post(JOBS, json={"company_name": "A", "title": "B"})
    assert created.status_code == 401


async def test_create_job_starts_as_new(api: AsyncClient) -> None:
    response = await api.post(JOBS, json={"company_name": "Acme", "title": "Backend Engineer"})
    assert response.status_code == 201
    job = response.json()
    assert job["company"]["name"] == "Acme"
    assert job["application"]["status"] == "New"
    assert job["application"]["version"] == 1
    assert job["found_on"] is not None


async def test_adding_the_same_job_twice_returns_the_existing_one(api: AsyncClient) -> None:
    first = await api.post(JOBS, json={"company_name": "Acme Pvt Ltd", "title": "Backend Engineer"})
    again = await api.post(JOBS, json={"company_name": "ACME", "title": "backend  engineer"})
    assert first.status_code == 201
    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    assert len((await api.get(JOBS)).json()["items"]) == 1


@pytest.mark.parametrize("field", ["apply_url", "jd_url", "careers_url"])
@pytest.mark.parametrize("bad", ["javascript:alert(1)", "ftp://example.com/x", "not a url"])
async def test_links_must_be_http(api: AsyncClient, field: str, bad: str) -> None:
    response = await api.post(JOBS, json={"company_name": "A", "title": "B", field: bad})
    assert response.status_code == 422


async def test_list_filters(api: AsyncClient) -> None:
    await add_job(
        api,
        company_name="Alpha",
        title="Python Dev",
        region="India",
        work_mode="Remote",
        est_ctc_lpa=12,
    )
    await add_job(
        api,
        company_name="Beta",
        title="Go Dev",
        region="Europe",
        work_mode="Onsite",
        est_ctc_lpa=30,
    )
    await add_job(
        api, company_name="Gamma_100%", title="Java Dev", region="India", work_mode="Hybrid"
    )

    async def titles(**params: Any) -> set[str]:
        response = await api.get(JOBS, params=params)
        assert response.status_code == 200
        return {item["title"] for item in response.json()["items"]}

    assert await titles(region="India") == {"Python Dev", "Java Dev"}
    assert await titles(work_mode="Onsite") == {"Go Dev"}
    assert await titles(min_ctc=20) == {"Go Dev"}
    assert await titles(q="beta") == {"Go Dev"}
    assert await titles(q="python") == {"Python Dev"}
    assert await titles(q="100%") == {"Java Dev"}  # % is matched literally, not as a wildcard
    assert await titles(q="%") == {"Java Dev"}
    assert await titles(status="New") == {"Python Dev", "Go Dev", "Java Dev"}
    assert await titles(status="Shortlisted") == set()


async def test_keyset_pagination_visits_every_job_once_newest_first(api: AsyncClient) -> None:
    created = [(await add_job(api, title=f"Role {n}"))["id"] for n in range(5)]
    seen: list[str] = []
    cursor = None
    pages = 0
    while True:
        params: dict[str, Any] = {"limit": 2}
        if cursor:
            params["cursor"] = cursor
        page = (await api.get(JOBS, params=params)).json()
        seen += [item["id"] for item in page["items"]]
        pages += 1
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert pages == 3
    assert seen == list(reversed(created))


async def test_bad_cursor_is_rejected(api: AsyncClient) -> None:
    assert (await api.get(JOBS, params={"cursor": "garbage"})).status_code == 400


async def test_full_pipeline_records_history(api: AsyncClient) -> None:
    job = await add_job(api)
    for status in [
        "Shortlisted",
        "Applied - Pending",
        "Technical Round",
        "HR Round",
        "Offer Received",
        "Offer Accepted",
    ]:
        response = await move(api, job, status, next_followup_on="2030-01-01")
        assert response.status_code == 200, response.text

    final = await detail(api, job)
    assert final["application"]["status"] == "Offer Accepted"
    assert final["application"]["version"] == 7
    assert final["application"]["applied_on"] is not None
    assert final["application"]["next_followup_on"] is None  # finished: no follow-up pending
    assert [e["to_status"] for e in final["events"]] == [
        "New",
        "Shortlisted",
        "Applied - Pending",
        "Technical Round",
        "HR Round",
        "Offer Received",
        "Offer Accepted",
    ]
    assert final["events"][0]["type"] == "created"
    assert final["events"][1]["from_status"] == "New"


async def test_skipping_a_stage_needs_a_note(api: AsyncClient) -> None:
    job = await add_job(api)
    refused = await move(api, job, "Offer Received")
    assert refused.status_code == 422
    assert refused.json()["code"] == "note_required"
    assert (await detail(api, job))["application"]["status"] == "New"  # nothing changed
    allowed = await move(api, job, "Offer Received", note="Offer came through a referral")
    assert allowed.status_code == 200
    assert allowed.json()["events"][-1]["note"] == "Offer came through a referral"


async def test_stale_version_is_a_conflict(api: AsyncClient) -> None:
    job = await add_job(api)
    application = (await detail(api, job))["application"]
    url = f"/api/v1/applications/{application['id']}/status"
    first = await api.post(url, json={"status": "Shortlisted", "expected_version": 1})
    stale = await api.post(url, json={"status": "Applied - Pending", "expected_version": 1})
    assert first.status_code == 200
    assert stale.status_code == 409
    assert (await detail(api, job))["application"]["status"] == "Shortlisted"


async def test_reopening_a_rejected_application(api: AsyncClient) -> None:
    job = await add_job(api)
    assert (await move(api, job, "Applied - Pending")).status_code == 200
    assert (await move(api, job, "Rejected")).status_code == 200
    plain = await move(api, job, "Applied - Pending")
    assert plain.json()["code"] == "reopen_required"
    reopened = await move(api, job, "Applied - Pending", reopen=True, note="Role reopened")
    assert reopened.status_code == 200
    assert reopened.json()["events"][-1]["type"] == "reopened"


async def test_status_change_moves_the_job_to_the_top(api: AsyncClient) -> None:
    older = await add_job(api, title="Older")
    await add_job(api, title="Newer")
    first = (await api.get(JOBS)).json()["items"][0]["title"]
    assert first == "Newer"
    await move(api, older, "Shortlisted")
    assert (await api.get(JOBS)).json()["items"][0]["title"] == "Older"


async def test_followups_due_excludes_finished_applications(api: AsyncClient) -> None:
    due = await add_job(api, title="Due")
    later = await add_job(api, title="Later")
    done = await add_job(api, title="Done")
    await move(api, due, "Applied - Pending", next_followup_on="2000-01-01")
    await move(api, later, "Applied - Pending", next_followup_on="2999-01-01")
    await move(api, done, "Applied - Pending", next_followup_on="2000-01-01")
    await move(api, done, "Rejected")
    response = await api.get(JOBS, params={"followup_due": True})
    assert [item["title"] for item in response.json()["items"]] == ["Due"]


async def test_another_owner_cannot_see_or_change_anything(
    api: AsyncClient, other_api: AsyncClient
) -> None:
    job = await add_job(api)
    application_id = (await detail(api, job))["application"]["id"]
    assert (await other_api.get(JOBS)).json()["items"] == []
    assert (await other_api.get(f"{JOBS}/{job['id']}")).status_code == 404
    assert (await other_api.delete(f"{JOBS}/{job['id']}")).status_code == 404
    patch = await other_api.patch(f"/api/v1/applications/{application_id}", json={"notes": "x"})
    assert patch.status_code == 404
    status_change = await other_api.post(
        f"/api/v1/applications/{application_id}/status",
        json={"status": "Shortlisted", "expected_version": 1},
    )
    assert status_change.status_code == 404
    assert (await detail(api, job))["application"]["status"] == "New"


async def test_state_changing_calls_need_the_csrf_header(api: AsyncClient) -> None:
    job = await add_job(api)
    csrf = api.headers.pop("X-CSRF-Token")
    assert (await api.delete(f"{JOBS}/{job['id']}")).status_code == 403
    api.headers["X-CSRF-Token"] = csrf
    assert (await api.delete(f"{JOBS}/{job['id']}")).status_code == 204


async def test_update_job_and_application_fields(api: AsyncClient) -> None:
    job = await add_job(api)
    patched = await api.patch(f"{JOBS}/{job['id']}", json={"est_ctc_lpa": 15.5, "region": "India"})
    assert patched.status_code == 200
    assert patched.json()["est_ctc_lpa"] == 15.5

    application_id = patched.json()["application"]["id"]
    app_patch = await api.patch(
        f"/api/v1/applications/{application_id}",
        json={"notes": "Referred by a friend", "portal_mode": "Done"},
    )
    assert app_patch.json()["application"]["notes"] == "Referred by a friend"
    assert app_patch.json()["application"]["portal_mode"] == "Done"

    cleared = await api.patch(f"{JOBS}/{job['id']}", json={"est_ctc_lpa": None})
    assert cleared.json()["est_ctc_lpa"] is None
    assert (await api.patch(f"{JOBS}/{job['id']}", json={"title": None})).status_code == 422


async def test_contacts_need_a_source_when_published(api: AsyncClient) -> None:
    job = await add_job(api)
    url = f"{JOBS}/{job['id']}/contacts"
    no_source = await api.post(url, json={"name": "HR", "kind": "published_business"})
    assert no_source.status_code == 422
    bad_email = await api.post(url, json={"name": "HR", "kind": "recruiter", "email": "nope"})
    assert bad_email.status_code == 422

    ok = await api.post(
        url,
        json={
            "name": "Careers desk",
            "kind": "published_business",
            "email": "careers@acme.example",
            "source_url": "https://acme.example/contact",
        },
    )
    assert ok.status_code == 201
    contacts = (await detail(api, job))["contacts"]
    assert [c["name"] for c in contacts] == ["Careers desk"]
    assert (await api.delete(f"/api/v1/contacts/{ok.json()['id']}")).status_code == 204
    assert (await detail(api, job))["contacts"] == []


async def test_delete_job(api: AsyncClient) -> None:
    job = await add_job(api)
    assert (await api.delete(f"{JOBS}/{job['id']}")).status_code == 204
    assert (await api.get(f"{JOBS}/{job['id']}")).status_code == 404
    assert (await api.get(JOBS)).json()["items"] == []


async def test_csv_export_neutralises_spreadsheet_formulas(api: AsyncClient) -> None:
    await add_job(api, title='=HYPERLINK("http://evil.example","click")', company_name="Safe Co")
    response = await api.get(f"{JOBS}/export.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0][:3] == ["Company", "Role", "Status"]
    assert rows[1][0] == "Safe Co"
    assert rows[1][1].startswith("'=")
