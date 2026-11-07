"""SQL for the status page. Read-only."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.llm import LlmCall


async def current_revision(db: AsyncSession) -> str | None:
    """The schema version recorded by Alembic, or None if the table is missing."""
    try:
        return await db.scalar(text("select version_num from alembic_version limit 1"))
    except Exception:
        await db.rollback()
        return None


async def recent_ai_calls(
    db: AsyncSession, owner_id: uuid.UUID, *, only_problems: bool, limit: int
) -> Sequence[LlmCall]:
    """Newest first. A "problem" is any call that did not end ok (refused or errored)."""
    query = select(LlmCall).where(LlmCall.owner_id == owner_id)
    if only_problems:
        query = query.where(LlmCall.status != "ok")
    return (await db.scalars(query.order_by(LlmCall.created_at.desc()).limit(limit))).all()
