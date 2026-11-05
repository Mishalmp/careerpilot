import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.mock.models import MockSession

LIST_LIMIT = 30


async def get(
    db: AsyncSession, owner_id: uuid.UUID, session_id: uuid.UUID, *, lock: bool = False
) -> MockSession | None:
    query = select(MockSession).where(
        MockSession.owner_id == owner_id, MockSession.id == session_id
    )
    return await db.scalar(query.with_for_update() if lock else query)


async def list_recent(db: AsyncSession, owner_id: uuid.UUID) -> Sequence[MockSession]:
    rows = await db.scalars(
        select(MockSession)
        .where(MockSession.owner_id == owner_id)
        .order_by(MockSession.created_at.desc())
        .limit(LIST_LIMIT)
    )
    return rows.all()


def add(db: AsyncSession, owner_id: uuid.UUID, **fields: Any) -> MockSession:
    session = MockSession(owner_id=owner_id, **fields)
    db.add(session)
    return session


async def delete_session(db: AsyncSession, owner_id: uuid.UUID, session_id: uuid.UUID) -> bool:
    result = await db.execute(
        delete(MockSession)
        .where(MockSession.owner_id == owner_id, MockSession.id == session_id)
        .returning(MockSession.id)
    )
    return result.first() is not None
