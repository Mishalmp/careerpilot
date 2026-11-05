import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.discovery.enums import CandidateStatus
from careerpilot.modules.discovery.models import DiscoveredJob, DiscoverySource

CANDIDATE_LIMIT = 200
CHUNK = 500


async def list_sources(db: AsyncSession, owner_id: uuid.UUID) -> Sequence[DiscoverySource]:
    rows = await db.scalars(
        select(DiscoverySource)
        .where(DiscoverySource.owner_id == owner_id)
        .order_by(DiscoverySource.company_name)
    )
    return rows.all()


async def get_source(
    db: AsyncSession, owner_id: uuid.UUID, source_id: uuid.UUID
) -> DiscoverySource | None:
    return await db.scalar(
        select(DiscoverySource).where(
            DiscoverySource.owner_id == owner_id, DiscoverySource.id == source_id
        )
    )


def add_source(db: AsyncSession, owner_id: uuid.UUID, **fields: Any) -> DiscoverySource:
    source = DiscoverySource(owner_id=owner_id, **fields)
    db.add(source)
    return source


async def delete_source(db: AsyncSession, owner_id: uuid.UUID, source_id: uuid.UUID) -> bool:
    result = await db.execute(
        delete(DiscoverySource)
        .where(DiscoverySource.owner_id == owner_id, DiscoverySource.id == source_id)
        .returning(DiscoverySource.id)
    )
    return result.first() is not None


async def known_ids(db: AsyncSession, source_id: uuid.UUID) -> set[str]:
    rows = await db.scalars(
        select(DiscoveredJob.external_id).where(DiscoveredJob.source_id == source_id)
    )
    return set(rows)


async def insert_new(
    db: AsyncSession, owner_id: uuid.UUID, source_id: uuid.UUID, rows: list[dict[str, Any]]
) -> int:
    """Insert listings not seen before. Existing ones are left alone, including their status."""
    inserted = 0
    for start in range(0, len(rows), CHUNK):
        chunk = [
            {**row, "owner_id": owner_id, "source_id": source_id}
            for row in rows[start : start + CHUNK]
        ]
        statement = (
            insert(DiscoveredJob)
            .values(chunk)
            .on_conflict_do_nothing(constraint="uq_discovered_jobs_source_external")
            .returning(DiscoveredJob.id)
        )
        inserted += len((await db.execute(statement)).all())
    return inserted


async def touch_seen(
    db: AsyncSession, source_id: uuid.UUID, external_ids: Sequence[str], now: datetime
) -> None:
    for start in range(0, len(external_ids), CHUNK):
        await db.execute(
            update(DiscoveredJob)
            .where(
                DiscoveredJob.source_id == source_id,
                DiscoveredJob.external_id.in_(external_ids[start : start + CHUNK]),
            )
            .values(last_seen_at=now)
        )


async def list_candidates(
    db: AsyncSession,
    owner_id: uuid.UUID,
    status: CandidateStatus,
    source_id: uuid.UUID | None,
) -> Sequence[tuple[DiscoveredJob, DiscoverySource]]:
    query = (
        select(DiscoveredJob, DiscoverySource)
        .join(DiscoverySource, DiscoverySource.id == DiscoveredJob.source_id)
        .where(DiscoveredJob.owner_id == owner_id, DiscoveredJob.status == status)
        .order_by(DiscoveredJob.first_seen_at.desc(), DiscoveredJob.title)
        .limit(CANDIDATE_LIMIT)
    )
    if source_id is not None:
        query = query.where(DiscoveredJob.source_id == source_id)
    return [(job, source) for job, source in (await db.execute(query)).all()]


async def count_candidates(
    db: AsyncSession, owner_id: uuid.UUID, status: CandidateStatus, source_id: uuid.UUID | None
) -> int:
    query = select(func.count()).where(
        DiscoveredJob.owner_id == owner_id, DiscoveredJob.status == status
    )
    if source_id is not None:
        query = query.where(DiscoveredJob.source_id == source_id)
    return int(await db.scalar(query) or 0)


async def get_candidate(
    db: AsyncSession, owner_id: uuid.UUID, candidate_id: uuid.UUID, *, lock: bool = False
) -> DiscoveredJob | None:
    query = select(DiscoveredJob).where(
        DiscoveredJob.owner_id == owner_id, DiscoveredJob.id == candidate_id
    )
    return await db.scalar(query.with_for_update() if lock else query)


async def new_counts(db: AsyncSession, owner_id: uuid.UUID) -> dict[uuid.UUID, int]:
    rows = await db.execute(
        select(DiscoveredJob.source_id, func.count())
        .where(DiscoveredJob.owner_id == owner_id, DiscoveredJob.status == CandidateStatus.NEW)
        .group_by(DiscoveredJob.source_id)
    )
    return {source_id: count for source_id, count in rows}


async def count_new_since(db: AsyncSession, owner_id: uuid.UUID, since: datetime) -> int:
    return int(
        await db.scalar(
            select(func.count()).where(
                DiscoveredJob.owner_id == owner_id,
                DiscoveredJob.status == CandidateStatus.NEW,
                DiscoveredJob.first_seen_at >= since,
            )
        )
        or 0
    )


async def enabled_sources(db: AsyncSession) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """(owner, source) of every enabled source. For the scheduler, which works for all owners."""
    rows = await db.execute(
        select(DiscoverySource.owner_id, DiscoverySource.id).where(DiscoverySource.enabled)
    )
    return [(owner, source) for owner, source in rows]
