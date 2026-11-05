import uuid
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, delete, func, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, joinedload

from careerpilot.modules.tracker.enums import EventType, Status
from careerpilot.modules.tracker.filters import JobFilters
from careerpilot.modules.tracker.models import (
    Application,
    ApplicationEvent,
    Company,
    Contact,
    Job,
)
from careerpilot.modules.tracker.workflow import TERMINAL


async def get_or_create_company(
    db: AsyncSession, owner_id: uuid.UUID, name: str, normalized_name: str
) -> Company:
    await db.execute(
        insert(Company)
        .values(id=uuid.uuid4(), owner_id=owner_id, name=name, normalized_name=normalized_name)
        .on_conflict_do_nothing(index_elements=["owner_id", "normalized_name"])
    )
    company = await db.scalar(
        select(Company)
        .where(Company.owner_id == owner_id, Company.normalized_name == normalized_name)
        .execution_options(populate_existing=True)
    )
    if company is None:  # unreachable: the row was just inserted or already existed
        raise RuntimeError("company missing after upsert")
    return company


async def insert_job_if_new(
    db: AsyncSession, owner_id: uuid.UUID, company_id: uuid.UUID, fingerprint: str, **fields: Any
) -> uuid.UUID | None:
    """Insert, or return None when this owner already has a job with the same fingerprint."""
    return await db.scalar(
        insert(Job)
        .values(
            id=uuid.uuid4(),
            owner_id=owner_id,
            company_id=company_id,
            fingerprint=fingerprint,
            **fields,
        )
        .on_conflict_do_nothing(index_elements=["owner_id", "fingerprint"])
        .returning(Job.id)
    )


async def find_job_id_by_fingerprint(
    db: AsyncSession, owner_id: uuid.UUID, fingerprint: str
) -> uuid.UUID | None:
    return await db.scalar(
        select(Job.id).where(Job.owner_id == owner_id, Job.fingerprint == fingerprint)
    )


def add_application(
    db: AsyncSession, owner_id: uuid.UUID, job_id: uuid.UUID, **fields: Any
) -> Application:
    application = Application(owner_id=owner_id, job_id=job_id, version=1, **fields)
    db.add(application)
    return application


def add_event(
    db: AsyncSession,
    application_id: uuid.UUID,
    event_type: EventType,
    from_status: Status | None,
    to_status: Status,
    note: str | None,
) -> None:
    db.add(
        ApplicationEvent(
            application_id=application_id,
            type=event_type,
            from_status=from_status,
            to_status=to_status,
            note=note,
        )
    )


async def get_job(
    db: AsyncSession, owner_id: uuid.UUID, job_id: uuid.UUID, *, detail: bool = False
) -> Job | None:
    stmt = (
        select(Job)
        .where(Job.id == job_id, Job.owner_id == owner_id)
        .execution_options(populate_existing=True)
    )
    if detail:
        stmt = stmt.options(
            joinedload(Job.application).selectinload(Application.events),
            joinedload(Job.company).selectinload(Company.contacts),
        )
    return await db.scalar(stmt)


def _like(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


async def list_jobs(
    db: AsyncSession,
    owner_id: uuid.UUID,
    filters: JobFilters,
    *,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[Job]:
    """Newest activity first, keyset-paginated so deep pages stay cheap."""
    conditions: list[ColumnElement[bool]] = [Job.owner_id == owner_id]
    if filters.statuses:
        conditions.append(Application.status.in_(filters.statuses))
    if filters.query:
        pattern = _like(filters.query)
        conditions.append(
            Job.title.ilike(pattern, escape="\\") | Company.name.ilike(pattern, escape="\\")
        )
    if filters.region:
        conditions.append(Job.region == filters.region)
    if filters.work_mode:
        conditions.append(Job.work_mode == filters.work_mode)
    if filters.min_ctc is not None:
        conditions.append(Job.est_ctc_lpa >= filters.min_ctc)
    if filters.followup_due_on:
        conditions.append(Application.next_followup_on <= filters.followup_due_on)
        conditions.append(Application.status.not_in(list(TERMINAL)))
    if after:
        conditions.append(tuple_(Job.updated_at, Job.id) < tuple_(after[0], after[1]))

    stmt = (
        select(Job)
        .join(Job.application)
        .join(Job.company)
        .options(contains_eager(Job.application), contains_eager(Job.company))
        .where(*conditions)
        .order_by(Job.updated_at.desc(), Job.id.desc())
        .limit(limit)
        .execution_options(populate_existing=True)
    )
    return list((await db.scalars(stmt)).unique())


async def get_application_for_update(
    db: AsyncSession, owner_id: uuid.UUID, application_id: uuid.UUID
) -> Application | None:
    return await db.scalar(
        select(Application)
        .where(Application.id == application_id, Application.owner_id == owner_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def touch_job(db: AsyncSession, job_id: uuid.UUID) -> None:
    await db.execute(update(Job).where(Job.id == job_id).values(updated_at=func.now()))


async def delete_job(db: AsyncSession, owner_id: uuid.UUID, job_id: uuid.UUID) -> bool:
    result = await db.execute(
        delete(Job).where(Job.id == job_id, Job.owner_id == owner_id).returning(Job.id)
    )
    return result.first() is not None


def add_contact(
    db: AsyncSession, owner_id: uuid.UUID, company_id: uuid.UUID, **fields: Any
) -> Contact:
    contact = Contact(owner_id=owner_id, company_id=company_id, **fields)
    db.add(contact)
    return contact


async def delete_contact(db: AsyncSession, owner_id: uuid.UUID, contact_id: uuid.UUID) -> bool:
    result = await db.execute(
        delete(Contact)
        .where(Contact.id == contact_id, Contact.owner_id == owner_id)
        .returning(Contact.id)
    )
    return result.first() is not None


async def status_counts(db: AsyncSession, owner_id: uuid.UUID) -> dict[Status, int]:
    rows = await db.execute(
        select(Application.status, func.count())
        .where(Application.owner_id == owner_id)
        .group_by(Application.status)
    )
    return {status: count for status, count in rows.all()}


async def due_followups(
    db: AsyncSession, owner_id: uuid.UUID, on_or_before: date, limit: int
) -> list[Job]:
    stmt = (
        select(Job)
        .join(Job.application)
        .join(Job.company)
        .options(contains_eager(Job.application), contains_eager(Job.company))
        .where(
            Job.owner_id == owner_id,
            Application.next_followup_on <= on_or_before,
            Application.status.not_in(list(TERMINAL)),
        )
        .order_by(Application.next_followup_on, Job.id)
        .limit(limit)
        .execution_options(populate_existing=True)
    )
    return list((await db.scalars(stmt)).unique())


async def progress_inputs(
    db: AsyncSession, owner_id: uuid.UUID, zone: ZoneInfo
) -> list[tuple[uuid.UUID, Status, date | None, list[tuple[Status, date]]]]:
    """(job, current status, applied on, every status change with its local day) per application."""
    applications = (
        await db.execute(
            select(
                Application.id, Application.job_id, Application.status, Application.applied_on
            ).where(Application.owner_id == owner_id)
        )
    ).all()
    history: dict[uuid.UUID, list[tuple[Status, date]]] = {}
    events = await db.execute(
        select(ApplicationEvent.application_id, ApplicationEvent.to_status, ApplicationEvent.at)
        .join(Application, Application.id == ApplicationEvent.application_id)
        .where(Application.owner_id == owner_id)
    )
    for application_id, to_status, at in events:
        history.setdefault(application_id, []).append((to_status, at.astimezone(zone).date()))
    return [
        (job_id, status, applied_on, history.get(application_id, []))
        for application_id, job_id, status, applied_on in applications
    ]
