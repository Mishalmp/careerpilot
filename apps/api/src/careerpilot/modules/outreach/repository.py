import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.outreach.enums import Channel, OutreachStatus
from careerpilot.modules.outreach.models import OutreachDraft

OTHER_DRAFTS_FOR_SIMILARITY = 50


async def list_for_job(
    db: AsyncSession, owner_id: uuid.UUID, job_id: uuid.UUID
) -> list[OutreachDraft]:
    rows = await db.scalars(
        select(OutreachDraft)
        .where(OutreachDraft.owner_id == owner_id, OutreachDraft.job_id == job_id)
        .order_by(OutreachDraft.created_at, OutreachDraft.variant)
    )
    return list(rows)


async def get(
    db: AsyncSession, owner_id: uuid.UUID, draft_id: uuid.UUID, *, lock: bool = False
) -> OutreachDraft | None:
    query = select(OutreachDraft).where(
        OutreachDraft.owner_id == owner_id, OutreachDraft.id == draft_id
    )
    return await db.scalar(query.with_for_update() if lock else query)


def add(db: AsyncSession, owner_id: uuid.UUID, **fields: Any) -> OutreachDraft:
    draft = OutreachDraft(owner_id=owner_id, **fields)
    db.add(draft)
    return draft


async def other_bodies(
    db: AsyncSession, owner_id: uuid.UUID, job_id: uuid.UUID
) -> list[tuple[str, str]]:
    """Your recent drafts for other jobs, to spot a message copied from one to the next."""
    rows = await db.execute(
        select(OutreachDraft.id, OutreachDraft.body)
        .where(OutreachDraft.owner_id == owner_id, OutreachDraft.job_id != job_id)
        .order_by(OutreachDraft.created_at.desc())
        .limit(OTHER_DRAFTS_FOR_SIMILARITY)
    )
    return [(f"another draft ({str(draft_id)[:8]})", body) for draft_id, body in rows]


async def active_for_job(
    db: AsyncSession, owner_id: uuid.UUID, job_id: uuid.UUID, channel: Channel
) -> OutreachDraft | None:
    return await db.scalar(
        select(OutreachDraft).where(
            OutreachDraft.owner_id == owner_id,
            OutreachDraft.job_id == job_id,
            OutreachDraft.channel == channel,
            OutreachDraft.status.in_([OutreachStatus.APPROVED, OutreachStatus.SENT]),
        )
    )


async def approved_since(db: AsyncSession, owner_id: uuid.UUID, since: datetime) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(OutreachDraft)
            .where(OutreachDraft.owner_id == owner_id, OutreachDraft.approved_at >= since)
        )
        or 0
    )


async def reject_sibling_drafts(db: AsyncSession, owner_id: uuid.UUID, keep: OutreachDraft) -> None:
    await db.execute(
        update(OutreachDraft)
        .where(
            OutreachDraft.owner_id == owner_id,
            OutreachDraft.job_id == keep.job_id,
            OutreachDraft.channel == keep.channel,
            OutreachDraft.id != keep.id,
            OutreachDraft.status == OutreachStatus.DRAFT,
        )
        .values(status=OutreachStatus.REJECTED)
    )


async def delete_draft(db: AsyncSession, owner_id: uuid.UUID, draft_id: uuid.UUID) -> None:
    await db.execute(
        delete(OutreachDraft).where(
            OutreachDraft.owner_id == owner_id, OutreachDraft.id == draft_id
        )
    )
