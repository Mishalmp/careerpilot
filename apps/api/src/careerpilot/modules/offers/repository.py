import uuid
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.offers.models import FxRate


async def list_rates(db: AsyncSession, owner_id: uuid.UUID) -> Sequence[FxRate]:
    rows = await db.scalars(
        select(FxRate).where(FxRate.owner_id == owner_id).order_by(FxRate.currency)
    )
    return rows.all()


async def upsert_rate(
    db: AsyncSession, owner_id: uuid.UUID, currency: str, to_inr: Decimal, as_of: date
) -> FxRate:
    statement = (
        insert(FxRate)
        .values(owner_id=owner_id, currency=currency, to_inr=to_inr, as_of=as_of)
        .on_conflict_do_update(
            constraint="uq_fx_rates_owner_currency", set_={"to_inr": to_inr, "as_of": as_of}
        )
        .returning(FxRate)
    )
    return (await db.execute(statement, execution_options={"populate_existing": True})).scalar_one()


async def delete_rate(db: AsyncSession, owner_id: uuid.UUID, currency: str) -> bool:
    result = await db.execute(
        delete(FxRate)
        .where(FxRate.owner_id == owner_id, FxRate.currency == currency)
        .returning(FxRate.id)
    )
    return result.first() is not None
