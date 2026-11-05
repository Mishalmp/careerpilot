import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.digest.models import Digest


async def upsert(db: AsyncSession, owner_id: uuid.UUID, day: date, payload: dict[str, Any]) -> None:
    statement = insert(Digest).values(owner_id=owner_id, day=day, payload=payload)
    await db.execute(
        statement.on_conflict_do_update(
            constraint="uq_digests_owner_day", set_={"payload": payload, "created_at": func.now()}
        )
    )


async def latest(db: AsyncSession, owner_id: uuid.UUID) -> Digest | None:
    return await db.scalar(
        select(Digest).where(Digest.owner_id == owner_id).order_by(Digest.day.desc()).limit(1)
    )
