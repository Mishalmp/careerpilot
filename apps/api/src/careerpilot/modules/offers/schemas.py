from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

from careerpilot.modules.tracker.enums import Currency

Money = Annotated[Decimal, Field(ge=0, le=Decimal("1000000000"), max_digits=14, decimal_places=2)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]

NOTE = (
    "All figures are before tax; tax differs by country and is not modelled. Variable pay counts "
    "at the share you expect, and equity is your own estimate kept apart from cash."
)


class RateIn(BaseModel):
    currency: Currency
    # Rupees for one unit of the currency, for example 83.5 for USD.
    to_inr: Annotated[Decimal, Field(gt=0, le=Decimal("100000"), max_digits=14, decimal_places=6)]
    as_of: date

    @field_validator("currency")
    @classmethod
    def _not_rupees(cls, value: Currency) -> Currency:
        if value is Currency.INR:
            raise ValueError("rupees need no rate")
        return value


class RateOut(BaseModel):
    currency: str
    to_inr: Decimal
    as_of: date
    age_days: int
    stale: bool


class OfferIn(BaseModel):
    name: Name
    currency: Currency
    fixed_annual: Money
    variable_target_annual: Money = Decimal(0)
    variable_payout_pct: Annotated[Decimal, Field(ge=0, le=200)] = Decimal(100)
    joining_bonus: Money = Decimal(0)
    equity_annual_value: Money = Decimal(0)
    notice_days: Annotated[int, Field(ge=0, le=365)] = 0
    joining_date: date | None = None


class CompareRequest(BaseModel):
    offers: Annotated[list[OfferIn], Field(min_length=1, max_length=6)]


class OfferOut(BaseModel):
    name: str
    currency: str
    steady_cash: Decimal
    first_year_cash: Decimal
    guaranteed_cash: Decimal
    equity_annual: Decimal
    steady_cash_inr: Decimal | None
    first_year_cash_inr: Decimal | None
    guaranteed_cash_inr: Decimal | None
    equity_annual_inr: Decimal | None
    variable_share_pct: Decimal | None
    earliest_start: date
    rank: int | None
    behind_best_pct: Decimal | None
    notes: list[str]


class CompareOut(BaseModel):
    offers: list[OfferOut]
    note: str = NOTE
