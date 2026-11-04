"""Import rows from the Job_Hunt_Tracker workbook (sheet "Tracker") into jobs and applications.

Idempotent: a job already present (same fingerprint) is left alone, so running it twice
changes nothing. Columns with no home yet (scores, verification, ratings, intel) are listed in
the result instead of being silently dropped.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.tracker import enums, service
from careerpilot.modules.tracker.schemas import ApplicationInit, JobCreate

SHEET = "Tracker"

_JOB_COLUMNS = {
    "Company": "company_name",
    "Role": "title",
    "Date Found": "found_on",
    "Posted Date": "posted_on",
    "Region": "region",
    "Office Location": "location_text",
    "Work Mode": "work_mode",
    "Job Type": "job_type",
    "Hiring From India?": "hiring_from_india",
    "Pay Currency": "currency",
    "Salary Package (As Posted)": "salary_text",
    "Est. CTC (LPA, INR)": "est_ctc_lpa",
    "Visa / Relocation": "visa",
    "Job Description (link)": "jd_url",
    "JD Summary": "jd_summary",
    "Apply Link": "apply_url",
    "Company Careers Page": "careers_url",
    "Portal Used": "source",
}
_APPLICATION_COLUMNS = {
    "Status": "status",
    "Applied On": "applied_on",
    "Next Follow-up": "next_followup_on",
    "Mode 1: Job Portal": "portal_mode",
    "Mode 2: Company Site": "site_mode",
    "Mode 3: Email": "email_mode",
    "Resume Used": "resume_version",
    "Notes": "notes",
}
_ENUM_FIELDS: dict[str, type[StrEnum]] = {
    "region": enums.Region,
    "work_mode": enums.WorkMode,
    "job_type": enums.JobType,
    "hiring_from_india": enums.HiringFromIndia,
    "currency": enums.Currency,
    "visa": enums.Visa,
    "source": enums.Portal,
    "status": enums.Status,
    "portal_mode": enums.PortalMode,
    "site_mode": enums.PortalMode,
    "email_mode": enums.EmailMode,
}
_DATE_FIELDS = {"found_on", "posted_on", "applied_on", "next_followup_on"}
# Computed or bookkeeping columns that are expected to be skipped.
_SKIP_QUIETLY = {"#", "12+ LPA?", "Last Updated", "Modes Done"}


@dataclass
class RowError:
    row: int
    message: str


@dataclass
class ImportResult:
    created: int = 0
    already_present: int = 0
    errors: list[RowError] = field(default_factory=lambda: [])
    ignored_columns: list[str] = field(default_factory=lambda: [])


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        value = value.strip()
    return None if value in ("", None) else value


def _convert(name: str, value: Any) -> Any:
    if name in _ENUM_FIELDS:
        enum_cls = _ENUM_FIELDS[name]
        match = next((m for m in enum_cls if m.value.casefold() == str(value).casefold()), None)
        if match is None:
            allowed = ", ".join(m.value for m in enum_cls)
            raise ValueError(f"{name}: '{value}' is not one of: {allowed}")
        return match
    if name in _DATE_FIELDS:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value))
        except ValueError as exc:
            raise ValueError(f"{name}: '{value}' is not a date (use YYYY-MM-DD)") from exc
    if name == "est_ctc_lpa":
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name}: '{value}' is not a number") from exc
    return str(value)


async def import_workbook(
    db: AsyncSession, owner_id: uuid.UUID, path: Path, *, today: date
) -> ImportResult:
    workbook = load_workbook(path, read_only=True, data_only=True)
    if SHEET not in workbook.sheetnames:
        raise ValueError(f"The workbook has no '{SHEET}' sheet.")
    rows = workbook[SHEET].iter_rows(values_only=True)
    headers = [str(h).strip() if h is not None else "" for h in next(rows)]

    result = ImportResult()
    known = set(_JOB_COLUMNS) | set(_APPLICATION_COLUMNS) | _SKIP_QUIETLY
    result.ignored_columns = [h for h in headers if h and h not in known]

    for number, row in enumerate(rows, start=2):
        cells = {h: _clean(v) for h, v in zip(headers, row, strict=False) if h}
        if not cells.get("Company") and not cells.get("Role"):
            continue
        try:
            job_fields = {
                _JOB_COLUMNS[h]: _convert(_JOB_COLUMNS[h], v)
                for h, v in cells.items()
                if h in _JOB_COLUMNS and v is not None
            }
            app_fields = {
                _APPLICATION_COLUMNS[h]: _convert(_APPLICATION_COLUMNS[h], v)
                for h, v in cells.items()
                if h in _APPLICATION_COLUMNS and v is not None
            }
            outcome = await service.create_job(
                db,
                owner_id,
                JobCreate(**job_fields),
                today=today,
                init=ApplicationInit(**app_fields),
            )
        except (ValueError, ValidationError) as exc:
            result.errors.append(RowError(number, _first_message(exc)))
            continue
        if outcome.created:
            result.created += 1
        else:
            result.already_present += 1
    workbook.close()
    return result


def _first_message(exc: ValueError | ValidationError) -> str:
    if isinstance(exc, ValidationError):
        first = exc.errors()[0]
        where = ".".join(str(part) for part in first["loc"])
        return f"{where}: {first['msg']}"
    return str(exc)
