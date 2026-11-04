import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from openpyxl import Workbook

from careerpilot.modules.tracker import importer
from careerpilot.modules.tracker.importer import ImportResult

HEADERS = [
    "#",
    "Company",
    "Role",
    "Region",
    "Work Mode",
    "Status",
    "Applied On",
    "Est. CTC (LPA, INR)",
    "Apply Link",
    "JD Match % (0-100)",
    "Notes",
]
TODAY = date(2026, 11, 5)


def make_workbook(path: Path, rows: list[list[object]], *, sheet: str = "Tracker") -> Path:
    workbook = Workbook()
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.title = sheet
    worksheet.append(HEADERS)
    for row in rows:
        worksheet.append(row)
    workbook.save(path)
    return path


ROWS: list[list[object]] = [
    [
        1,
        "Acme",
        "Backend Dev",
        "India",
        "Remote",
        "Applied - Pending",
        date(2026, 11, 1),
        14,
        "https://acme.example/jobs/1",
        80,
        "from naukri",
    ],
    [
        2,
        "ACME Pvt Ltd",
        "backend dev",
        "India",
        None,
        None,
        None,
        None,
        "https://acme.example/jobs/1",
        None,
        None,
    ],
    [3, "BadCo", "Role", "Atlantis", None, None, None, None, None, None, None],
    [4, "NoUrl Inc", "Role", None, None, None, None, None, "javascript:alert(1)", None, None],
    [5, "Numbers", "Role", None, None, None, None, "lots", None, None, None],
    [None] * len(HEADERS),
]


async def run_import(app: FastAPI, owner_id: uuid.UUID, path: Path) -> ImportResult:
    async with app.state.sessionmaker() as db:
        return await importer.import_workbook(db, owner_id, path, today=TODAY)


async def test_import_creates_rows_reports_problems_and_ignored_columns(
    app: FastAPI, owner_id: uuid.UUID, api: AsyncClient, tmp_path: Path
) -> None:
    result = await run_import(app, owner_id, make_workbook(tmp_path / "t.xlsx", ROWS))

    assert result.created == 1
    assert result.already_present == 1  # row 3 is the same job as row 2
    assert [e.row for e in result.errors] == [4, 5, 6]
    assert "Atlantis" in result.errors[0].message
    assert "http" in result.errors[1].message
    assert "number" in result.errors[2].message
    assert result.ignored_columns == ["JD Match % (0-100)"]  # "#" is skipped quietly

    jobs = (await api.get("/api/v1/jobs")).json()["items"]
    assert len(jobs) == 1
    job = jobs[0]
    assert job["application"]["status"] == "Applied - Pending"
    assert job["application"]["applied_on"] == "2026-11-01"
    assert job["application"]["notes"] == "from naukri"
    assert job["est_ctc_lpa"] == 14.0
    assert job["found_on"] == TODAY.isoformat()


async def test_importing_twice_changes_nothing(
    app: FastAPI, owner_id: uuid.UUID, api: AsyncClient, tmp_path: Path
) -> None:
    path = make_workbook(tmp_path / "t.xlsx", ROWS)
    await run_import(app, owner_id, path)
    again = await run_import(app, owner_id, path)
    assert again.created == 0
    assert again.already_present == 2
    assert len((await api.get("/api/v1/jobs")).json()["items"]) == 1


async def test_import_rejects_a_workbook_without_the_tracker_sheet(
    app: FastAPI, owner_id: uuid.UUID, tmp_path: Path
) -> None:
    path = make_workbook(tmp_path / "t.xlsx", [], sheet="Other")
    with pytest.raises(ValueError, match="no 'Tracker' sheet"):
        await run_import(app, owner_id, path)


async def test_today_combines_pipeline_followups_and_prep(api: AsyncClient) -> None:
    empty = (await api.get("/api/v1/today")).json()
    assert {p["status"]: p["count"] for p in empty["pipeline"]}["New"] == 0
    assert len(empty["pipeline"]) == 16
    assert empty["due_followups"] == []
    assert empty["prep"]["phase"] == "not_configured"

    job = (await api.post("/api/v1/jobs", json={"company_name": "Acme", "title": "Dev"})).json()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    await api.post(
        f"/api/v1/applications/{job['application']['id']}/status",
        json={"status": "Applied - Pending", "expected_version": 1, "next_followup_on": yesterday},
    )
    data = (await api.get("/api/v1/today")).json()
    counts = {p["status"]: p["count"] for p in data["pipeline"]}
    assert counts["Applied - Pending"] == 1 and counts["New"] == 0
    assert [j["title"] for j in data["due_followups"]] == ["Dev"]


async def test_today_needs_login(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/today")).status_code == 401
