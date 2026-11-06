"""SQL for the status page. Read-only."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def current_revision(db: AsyncSession) -> str | None:
    """The schema version recorded by Alembic, or None if the table is missing."""
    try:
        return await db.scalar(text("select version_num from alembic_version limit 1"))
    except Exception:
        await db.rollback()
        return None
