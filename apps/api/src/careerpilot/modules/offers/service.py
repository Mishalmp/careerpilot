import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.errors import ProblemError
from careerpilot.modules.offers import repository, rules
from careerpilot.modules.offers.models import FxRate
from careerpilot.modules.offers.schemas import (
    CompareOut,
    CompareRequest,
    OfferOut,
    RateIn,
    RateOut,
)


def _rate_out(rate: FxRate, today: date) -> RateOut:
    age = (today - rate.as_of).days
    return RateOut(
        currency=rate.currency,
        to_inr=rate.to_inr,
        as_of=rate.as_of,
        age_days=age,
        stale=age > rules.STALE_RATE_DAYS,
    )


async def list_rates(db: AsyncSession, owner_id: uuid.UUID, today: date) -> list[RateOut]:
    return [_rate_out(r, today) for r in await repository.list_rates(db, owner_id)]


async def set_rate(db: AsyncSession, owner_id: uuid.UUID, data: RateIn, today: date) -> RateOut:
    """Store or replace the rate for a currency. One rate per currency, with its date."""
    if data.as_of > today:
        raise ProblemError(422, "Rate dated in the future", "Use the date the rate was valid on.")
    rate = await repository.upsert_rate(db, owner_id, data.currency.value, data.to_inr, data.as_of)
    await db.commit()
    return _rate_out(rate, today)


async def delete_rate(db: AsyncSession, owner_id: uuid.UUID, currency: str) -> None:
    if not await repository.delete_rate(db, owner_id, currency):
        raise ProblemError(404, "Not found", f"No stored rate for {currency}.")
    await db.commit()


async def compare(
    db: AsyncSession, owner_id: uuid.UUID, data: CompareRequest, today: date
) -> CompareOut:
    stored = await repository.list_rates(db, owner_id)
    rates = {r.currency: rules.Rate(r.to_inr, r.as_of) for r in stored}
    results = rules.compare(
        [
            rules.OfferInput(
                name=o.name,
                currency=o.currency.value,
                fixed_annual=o.fixed_annual,
                variable_target_annual=o.variable_target_annual,
                variable_payout_pct=o.variable_payout_pct,
                joining_bonus=o.joining_bonus,
                equity_annual_value=o.equity_annual_value,
                notice_days=o.notice_days,
                joining_date=o.joining_date,
            )
            for o in data.offers
        ],
        rates,
        today,
    )
    return CompareOut(offers=[OfferOut(**vars(r)) for r in results])
