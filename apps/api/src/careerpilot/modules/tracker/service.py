import base64
import csv
import io
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.errors import ProblemError
from careerpilot.modules.tracker import repository
from careerpilot.modules.tracker.enums import EventType, Status
from careerpilot.modules.tracker.filters import JobFilters
from careerpilot.modules.tracker.identity import job_fingerprint, normalize_company
from careerpilot.modules.tracker.models import Application, Contact, Job
from careerpilot.modules.tracker.schemas import (
    ApplicationInit,
    ApplicationUpdate,
    CompanyUpdate,
    ContactCreate,
    JobCreate,
    JobUpdate,
    StatusChange,
)
from careerpilot.modules.tracker.workflow import (
    STAGE,
    TERMINAL,
    InvalidTransition,
    check_transition,
)

MAX_PAGE = 200
_APPLIED_STAGE = 1


def _not_found(what: str) -> ProblemError:
    return ProblemError(404, "Not found", f"{what} not found.")


def _money(fields: dict[str, Any]) -> dict[str, Any]:
    if fields.get("est_ctc_lpa") is not None:
        fields["est_ctc_lpa"] = Decimal(str(fields["est_ctc_lpa"]))
    return fields


@dataclass(frozen=True)
class CreateResult:
    job: Job
    created: bool


async def create_job(
    db: AsyncSession,
    owner_id: uuid.UUID,
    data: JobCreate,
    *,
    today: date,
    init: ApplicationInit | None = None,
) -> CreateResult:
    """Create a job and its application. Entering the same job twice returns the existing one."""
    init = init or ApplicationInit()
    company = await repository.get_or_create_company(
        db, owner_id, data.company_name, normalize_company(data.company_name)
    )
    fingerprint = job_fingerprint(data.company_name, data.title, data.location_text, data.apply_url)
    fields = _money(data.model_dump(exclude={"company_name"}))
    fields["found_on"] = fields["found_on"] or today
    job_id = await repository.insert_job_if_new(db, owner_id, company.id, fingerprint, **fields)

    if job_id is None:
        existing_id = await repository.find_job_id_by_fingerprint(db, owner_id, fingerprint)
        existing = await repository.get_job(db, owner_id, existing_id) if existing_id else None
        if existing is None:  # it was deleted between the conflict and the lookup
            raise ProblemError(409, "Changed elsewhere", "Please try adding the job again.")
        return CreateResult(existing, created=False)

    application = repository.add_application(db, owner_id, job_id, **init.model_dump())
    await db.flush()
    repository.add_event(db, application.id, EventType.CREATED, None, init.status, None)
    await db.commit()
    job = await repository.get_job(db, owner_id, job_id)
    if job is None:
        raise RuntimeError("job missing right after it was created")
    return CreateResult(job, created=True)


def encode_cursor(job: Job) -> str:
    return base64.urlsafe_b64encode(f"{job.updated_at.isoformat()}|{job.id}".encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        stamp, raw_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        return datetime.fromisoformat(stamp), uuid.UUID(raw_id)
    except ValueError as exc:
        raise ProblemError(400, "Invalid cursor") from exc


async def list_jobs(
    db: AsyncSession,
    owner_id: uuid.UUID,
    filters: JobFilters,
    *,
    cursor: str | None,
    limit: int,
) -> tuple[Sequence[Job], str | None]:
    limit = max(1, min(limit, MAX_PAGE))
    after = decode_cursor(cursor) if cursor else None
    rows = await repository.list_jobs(db, owner_id, filters, after=after, limit=limit + 1)
    page = rows[:limit]
    return page, encode_cursor(page[-1]) if len(rows) > limit else None


async def get_job(db: AsyncSession, owner_id: uuid.UUID, job_id: uuid.UUID) -> Job:
    job = await repository.get_job(db, owner_id, job_id, detail=True)
    if job is None:
        raise _not_found("Job")
    return job


async def update_job(
    db: AsyncSession, owner_id: uuid.UUID, job_id: uuid.UUID, data: JobUpdate
) -> Job:
    job = await repository.get_job(db, owner_id, job_id)
    if job is None:
        raise _not_found("Job")
    for field, value in _money(data.model_dump(exclude_unset=True)).items():
        setattr(job, field, value)
    await db.commit()
    return await get_job(db, owner_id, job_id)


async def delete_job(db: AsyncSession, owner_id: uuid.UUID, job_id: uuid.UUID) -> None:
    if not await repository.delete_job(db, owner_id, job_id):
        raise _not_found("Job")
    await db.commit()


async def change_status(
    db: AsyncSession,
    owner_id: uuid.UUID,
    application_id: uuid.UUID,
    change: StatusChange,
    *,
    today: date,
) -> Job:
    # The row lock makes "check the version, then write" atomic if two clients race.
    application = await repository.get_application_for_update(db, owner_id, application_id)
    if application is None:
        raise _not_found("Application")
    if change.expected_version != application.version:
        await db.rollback()
        raise ProblemError(
            409, "Changed elsewhere", "This application was updated. Reload and try again."
        )
    try:
        event_type = check_transition(
            application.status, change.status, note=change.note, reopen=change.reopen
        )
    except InvalidTransition as exc:
        await db.rollback()
        raise ProblemError(422, "Status change not allowed", exc.message, code=exc.code) from exc

    previous = application.status
    application.status = change.status
    application.version += 1
    if STAGE.get(change.status, 0) >= _APPLIED_STAGE and application.applied_on is None:
        application.applied_on = today
    if change.status in TERMINAL:
        application.next_followup_on = None
    elif change.next_followup_on is not None:
        application.next_followup_on = change.next_followup_on
    repository.add_event(db, application.id, event_type, previous, change.status, change.note)
    await repository.touch_job(db, application.job_id)
    job_id = application.job_id
    await db.commit()
    return await get_job(db, owner_id, job_id)


async def update_application(
    db: AsyncSession, owner_id: uuid.UUID, application_id: uuid.UUID, data: ApplicationUpdate
) -> Job:
    application = await repository.get_application_for_update(db, owner_id, application_id)
    if application is None:
        raise _not_found("Application")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(application, field, value)
    job_id = application.job_id
    await repository.touch_job(db, job_id)
    await db.commit()
    return await get_job(db, owner_id, job_id)


async def update_company(
    db: AsyncSession, owner_id: uuid.UUID, job_id: uuid.UUID, data: CompanyUpdate
) -> Job:
    job = await get_job(db, owner_id, job_id)
    for field in data.model_fields_set:
        setattr(job.company, field, getattr(data, field))
    await repository.touch_job(db, job_id)
    await db.commit()
    return await get_job(db, owner_id, job_id)


async def add_contact(
    db: AsyncSession, owner_id: uuid.UUID, job_id: uuid.UUID, data: ContactCreate
) -> Contact:
    job = await repository.get_job(db, owner_id, job_id)
    if job is None:
        raise _not_found("Job")
    contact = repository.add_contact(db, owner_id, job.company_id, **data.model_dump())
    await db.commit()
    await db.refresh(contact)
    return contact


async def delete_contact(db: AsyncSession, owner_id: uuid.UUID, contact_id: uuid.UUID) -> None:
    if not await repository.delete_contact(db, owner_id, contact_id):
        raise _not_found("Contact")
    await db.commit()


@dataclass(frozen=True)
class TrackerSnapshot:
    counts: dict[Status, int]
    due_followups: Sequence[Job]


async def snapshot(db: AsyncSession, owner_id: uuid.UUID, today: date) -> TrackerSnapshot:
    return TrackerSnapshot(
        counts=await repository.status_counts(db, owner_id),
        due_followups=await repository.due_followups(db, owner_id, today, limit=10),
    )


_CSV_COLUMNS = (
    "Company",
    "Role",
    "Status",
    "Applied On",
    "Next Follow-up",
    "Region",
    "Office Location",
    "Work Mode",
    "Job Type",
    "Pay Currency",
    "Salary Package (As Posted)",
    "Est. CTC (LPA, INR)",
    "Visa / Relocation",
    "Job Description (link)",
    "Apply Link",
    "Posted Date",
    "Date Found",
    "Notes",
)


def _safe_cell(value: object) -> str:
    """Stop a spreadsheet from running a cell that starts like a formula (CSV injection)."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


async def export_csv(db: AsyncSession, owner_id: uuid.UUID) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(_CSV_COLUMNS)
    cursor: str | None = None
    while True:
        jobs, cursor = await list_jobs(db, owner_id, JobFilters(), cursor=cursor, limit=MAX_PAGE)
        for job in jobs:
            app: Application = job.application
            writer.writerow(
                _safe_cell(value)
                for value in (
                    job.company.name,
                    job.title,
                    app.status.value,
                    app.applied_on,
                    app.next_followup_on,
                    job.region,
                    job.location_text,
                    job.work_mode,
                    job.job_type,
                    job.currency,
                    job.salary_text,
                    job.est_ctc_lpa,
                    job.visa,
                    job.jd_url,
                    job.apply_url,
                    job.posted_on,
                    job.found_on,
                    app.notes,
                )
            )
        if cursor is None:
            return out.getvalue()
