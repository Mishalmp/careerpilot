"""All SQL for the daily apply list. Every query is scoped by owner_id."""

import uuid
from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.apply.enums import ApplyStatus
from careerpilot.modules.apply.models import ApplyItem

LIST_LIMIT = 100


async def add_if_new(
    db: AsyncSession, owner_id: uuid.UUID, job_id: uuid.UUID, **fields: Any
) -> ApplyItem | None:
    """List a job unless it was listed before (by any build, ever). None when it already was."""
    statement = (
        insert(ApplyItem)
        .values(owner_id=owner_id, job_id=job_id, **fields)
        .on_conflict_do_nothing(constraint="uq_apply_items_owner_job")
        .returning(ApplyItem.id)
    )
    new_id = (await db.execute(statement)).scalar_one_or_none()
    return None if new_id is None else await get(db, owner_id, new_id)


async def get(
    db: AsyncSession, owner_id: uuid.UUID, item_id: uuid.UUID, *, lock: bool = False
) -> ApplyItem | None:
    statement = select(ApplyItem).where(ApplyItem.owner_id == owner_id, ApplyItem.id == item_id)
    if lock:
        statement = statement.with_for_update()
    return await db.scalar(statement)


async def listed_job_ids(db: AsyncSession, owner_id: uuid.UUID) -> set[uuid.UUID]:
    rows = await db.scalars(select(ApplyItem.job_id).where(ApplyItem.owner_id == owner_id))
    return set(rows)


async def count_counted_on(db: AsyncSession, owner_id: uuid.UUID, day: date) -> int:
    """Items listed on `day` that count against the daily limit (held-back ones do not)."""
    return (
        await db.scalar(
            select(func.count())
            .select_from(ApplyItem)
            .where(
                ApplyItem.owner_id == owner_id,
                ApplyItem.queued_on == day,
                ApplyItem.status != ApplyStatus.BLOCKED,
            )
        )
    ) or 0


async def list_since(db: AsyncSession, owner_id: uuid.UUID, since: date) -> Sequence[ApplyItem]:
    """Everything still waiting, plus what was listed or decided since `since`."""
    return (
        await db.scalars(
            select(ApplyItem)
            .where(
                ApplyItem.owner_id == owner_id,
                (ApplyItem.queued_on >= since) | (ApplyItem.status == ApplyStatus.READY),
            )
            .order_by(
                ApplyItem.queued_on.desc(), ApplyItem.match_score.desc(), ApplyItem.created_at
            )
            .limit(LIST_LIMIT)
        )
    ).all()


async def count_ready(db: AsyncSession, owner_id: uuid.UUID) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(ApplyItem)
            .where(ApplyItem.owner_id == owner_id, ApplyItem.status == ApplyStatus.READY)
        )
    ) or 0


async def unfinished(db: AsyncSession, owner_id: uuid.UUID) -> Sequence[ApplyItem]:
    """Items that were listed but never looked up (a build stopped before it got to them)."""
    return (
        await db.scalars(
            select(ApplyItem)
            .where(
                ApplyItem.owner_id == owner_id,
                ApplyItem.status == ApplyStatus.READY,
                ApplyItem.enriched_at.is_(None),
            )
            .order_by(ApplyItem.created_at)
            .with_for_update(skip_locked=True)
        )
    ).all()
