import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.intel.models import IntelItem, IntelSource


async def list_sources(
    db: AsyncSession, owner_id: uuid.UUID, company_id: uuid.UUID
) -> Sequence[IntelSource]:
    rows = await db.scalars(
        select(IntelSource)
        .where(IntelSource.owner_id == owner_id, IntelSource.company_id == company_id)
        .order_by(IntelSource.created_at)
    )
    return rows.all()


async def get_source(
    db: AsyncSession, owner_id: uuid.UUID, company_id: uuid.UUID, source_id: uuid.UUID
) -> IntelSource | None:
    return await db.scalar(
        select(IntelSource).where(
            IntelSource.owner_id == owner_id,
            IntelSource.company_id == company_id,
            IntelSource.id == source_id,
        )
    )


def add_source(db: AsyncSession, owner_id: uuid.UUID, **fields: Any) -> IntelSource:
    source = IntelSource(owner_id=owner_id, **fields)
    db.add(source)
    return source


async def delete_source(
    db: AsyncSession, owner_id: uuid.UUID, company_id: uuid.UUID, source_id: uuid.UUID
) -> bool:
    result = await db.execute(
        delete(IntelSource)
        .where(
            IntelSource.owner_id == owner_id,
            IntelSource.company_id == company_id,
            IntelSource.id == source_id,
        )
        .returning(IntelSource.id)
    )
    return result.first() is not None


async def list_items(
    db: AsyncSession, owner_id: uuid.UUID, source_ids: Sequence[uuid.UUID]
) -> Sequence[IntelItem]:
    rows = await db.scalars(
        select(IntelItem)
        .where(IntelItem.owner_id == owner_id, IntelItem.source_id.in_(source_ids))
        .order_by(IntelItem.created_at, IntelItem.id)
    )
    return rows.all()


async def replace_items(
    db: AsyncSession, owner_id: uuid.UUID, source_id: uuid.UUID, items: list[dict[str, Any]]
) -> None:
    await db.execute(
        delete(IntelItem).where(IntelItem.owner_id == owner_id, IntelItem.source_id == source_id)
    )
    db.add_all(IntelItem(owner_id=owner_id, source_id=source_id, **item) for item in items)
