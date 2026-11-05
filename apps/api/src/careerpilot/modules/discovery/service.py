import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.errors import ProblemError
from careerpilot.core.fetcher import Fetcher
from careerpilot.modules.discovery import repository
from careerpilot.modules.discovery.adapters import (
    AdapterError,
    RawJob,
    fetch_board,
    fetch_greenhouse_description,
)
from careerpilot.modules.discovery.enums import BoardKind, CandidateStatus
from careerpilot.modules.discovery.models import DiscoveredJob, DiscoverySource
from careerpilot.modules.discovery.schemas import (
    AcceptOut,
    CandidateList,
    CandidateOut,
    DiscoverySourceCreate,
    DiscoverySourceOut,
    DiscoverySourceUpdate,
    RunOut,
)
from careerpilot.modules.tracker import service as tracker_service
from careerpilot.modules.tracker.enums import Portal, WorkMode
from careerpilot.modules.tracker.schemas import JobCreate

MAX_TITLE = 200


def _not_found(what: str) -> ProblemError:
    return ProblemError(404, "Not found", f"{what} not found.")


def matches(title: str, include: list[str], exclude: list[str]) -> bool:
    """Your keyword filters on a job title. Empty `include` keeps everything not excluded."""
    lowered = title.casefold()
    if any(word.casefold() in lowered for word in exclude):
        return False
    return not include or any(word.casefold() in lowered for word in include)


# --- sources -------------------------------------------------------------------------------


def _source_out(source: DiscoverySource, new_count: int) -> DiscoverySourceOut:
    return DiscoverySourceOut(
        id=source.id,
        kind=source.kind,
        board=source.board,
        company_name=source.company_name,
        include=source.include,
        exclude=source.exclude,
        enabled=source.enabled,
        last_run_at=source.last_run_at,
        last_error=source.last_error,
        last_listed=source.last_listed,
        new_count=new_count,
    )


async def list_sources(db: AsyncSession, owner_id: uuid.UUID) -> list[DiscoverySourceOut]:
    counts = await repository.new_counts(db, owner_id)
    return [
        _source_out(s, counts.get(s.id, 0)) for s in await repository.list_sources(db, owner_id)
    ]


async def add_source(
    db: AsyncSession, owner_id: uuid.UUID, data: DiscoverySourceCreate
) -> DiscoverySourceOut:
    source = repository.add_source(
        db,
        owner_id,
        kind=data.kind,
        board=data.board,
        company_name=data.company_name,
        include=data.include,
        exclude=data.exclude,
        enabled=True,
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ProblemError(409, "Already added", "That board is already in your list.") from exc
    return _source_out(source, 0)


async def update_source(
    db: AsyncSession, owner_id: uuid.UUID, source_id: uuid.UUID, data: DiscoverySourceUpdate
) -> DiscoverySourceOut:
    source = await repository.get_source(db, owner_id, source_id)
    if source is None:
        raise _not_found("Source")
    for field in data.model_fields_set:
        value = getattr(data, field)
        if value is not None:
            setattr(source, field, value)
    await db.commit()
    return _source_out(source, (await repository.new_counts(db, owner_id)).get(source.id, 0))


async def delete_source(db: AsyncSession, owner_id: uuid.UUID, source_id: uuid.UUID) -> None:
    if not await repository.delete_source(db, owner_id, source_id):
        raise _not_found("Source")
    await db.commit()


# --- running a board -----------------------------------------------------------------------


def _row(job: RawJob) -> dict[str, Any]:
    return {
        "external_id": job.external_id,
        "title": job.title[:MAX_TITLE],
        "location": job.location,
        "url": job.url,
        "apply_url": job.apply_url,
        "description": job.description,
        "published_on": job.published_on,
        "remote": job.remote,
    }


async def run_source(
    db: AsyncSession,
    owner_id: uuid.UUID,
    source_id: uuid.UUID,
    fetcher: Fetcher,
    *,
    now: datetime | None = None,
) -> RunOut:
    """Read a board and store new listings. Safe to repeat: nothing is duplicated, and listings
    you already accepted or dismissed keep their status. Raises AdapterError if the board cannot
    be read (the failure is also recorded on the source)."""
    now = now or datetime.now(UTC)
    source = await repository.get_source(db, owner_id, source_id)
    if source is None:
        raise _not_found("Source")
    try:
        jobs = await fetch_board(fetcher, source.kind, source.board)
    except AdapterError as exc:
        source.last_run_at, source.last_error = now, str(exc)
        await db.commit()
        raise

    kept = [j for j in jobs if matches(j.title, source.include, source.exclude)]
    known = await repository.known_ids(db, source.id)
    fresh = [j for j in kept if j.external_id not in known]
    inserted = await repository.insert_new(db, owner_id, source.id, [_row(j) for j in fresh])
    await repository.touch_seen(
        db, source.id, [j.external_id for j in kept if j.external_id in known], now
    )
    source.last_run_at, source.last_error, source.last_listed = now, None, len(jobs)
    await db.commit()
    return RunOut(listed=len(jobs), kept=len(kept), new=inserted)


# --- the inbox -----------------------------------------------------------------------------


def _candidate_out(job: DiscoveredJob, source: DiscoverySource) -> CandidateOut:
    return CandidateOut(
        id=job.id,
        source_id=job.source_id,
        company_name=source.company_name,
        title=job.title,
        location=job.location,
        url=job.url,
        published_on=job.published_on,
        remote=job.remote,
        status=job.status,
        job_id=job.job_id,
        first_seen_at=job.first_seen_at,
        listed=source.last_run_at is None or job.last_seen_at >= source.last_run_at,
    )


async def list_candidates(
    db: AsyncSession,
    owner_id: uuid.UUID,
    status: CandidateStatus,
    source_id: uuid.UUID | None,
) -> CandidateList:
    rows = await repository.list_candidates(db, owner_id, status, source_id)
    return CandidateList(
        items=[_candidate_out(job, source) for job, source in rows],
        total=await repository.count_candidates(db, owner_id, status, source_id),
    )


async def accept(
    db: AsyncSession,
    owner_id: uuid.UUID,
    candidate_id: uuid.UUID,
    fetcher: Fetcher,
    *,
    today: date,
) -> AcceptOut:
    """Copy a listing into the tracker. The tracker recognises a job it already has."""
    candidate = await repository.get_candidate(db, owner_id, candidate_id)
    if candidate is None:
        raise _not_found("Listing")
    if candidate.status is CandidateStatus.ACCEPTED and candidate.job_id is not None:
        return AcceptOut(job_id=candidate.job_id, already_tracked=True)
    source = await repository.get_source(db, owner_id, candidate.source_id)
    if source is None:
        raise _not_found("Source")

    description = candidate.description
    if description is None and source.kind is BoardKind.GREENHOUSE:
        description = await fetch_greenhouse_description(
            fetcher, source.board, candidate.external_id
        )

    created = await tracker_service.create_job(
        db,
        owner_id,
        JobCreate(
            company_name=source.company_name,
            title=candidate.title,
            location_text=(candidate.location or "")[:200] or None,
            jd_url=candidate.url,
            apply_url=candidate.apply_url or candidate.url,
            jd_text=description,
            source=Portal.OTHER,
            work_mode=WorkMode.REMOTE if candidate.remote else None,
            posted_on=candidate.published_on,
        ),
        today=today,
    )
    candidate = await repository.get_candidate(db, owner_id, candidate_id, lock=True)
    if candidate is None:
        raise _not_found("Listing")
    candidate.status, candidate.job_id = CandidateStatus.ACCEPTED, created.job.id
    await db.commit()
    return AcceptOut(job_id=created.job.id, already_tracked=not created.created)


async def set_status(
    db: AsyncSession, owner_id: uuid.UUID, candidate_id: uuid.UUID, status: CandidateStatus
) -> None:
    """Dismiss a listing, or bring a dismissed one back."""
    candidate = await repository.get_candidate(db, owner_id, candidate_id, lock=True)
    if candidate is None:
        raise _not_found("Listing")
    if candidate.status is CandidateStatus.ACCEPTED:
        raise ProblemError(409, "Already in your tracker", "Manage it from the Jobs page.")
    candidate.status = status
    await db.commit()


async def count_new_since(db: AsyncSession, owner_id: uuid.UUID, since: datetime) -> int:
    return await repository.count_new_since(db, owner_id, since)


async def total_new(db: AsyncSession, owner_id: uuid.UUID) -> int:
    return sum((await repository.new_counts(db, owner_id)).values())


async def enabled_sources(db: AsyncSession) -> list[tuple[uuid.UUID, uuid.UUID]]:
    return await repository.enabled_sources(db)
