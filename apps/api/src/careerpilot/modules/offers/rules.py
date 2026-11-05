"""Comparing job offers in one currency. Pure functions: no database, no network.

Everything is gross (before tax): taxes differ by country and are not modelled. Variable pay is
counted at the share you expect to receive, and equity is kept apart from cash, because neither
is guaranteed. An exchange rate you stored is used with its date; a missing rate leaves the
converted numbers empty instead of guessing, and an old one is flagged.
"""

from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal

STALE_RATE_DAYS = 90
HOME_CURRENCY = "INR"


@dataclass(frozen=True)
class Rate:
    to_inr: Decimal
    as_of: date


@dataclass(frozen=True)
class OfferInput:
    name: str
    currency: str
    fixed_annual: Decimal  # guaranteed pay per year
    variable_target_annual: Decimal = Decimal(0)
    variable_payout_pct: Decimal = Decimal(100)  # the share of the target you expect to get
    joining_bonus: Decimal = Decimal(0)  # one time, in the first year
    equity_annual_value: Decimal = Decimal(0)  # your own estimate of the value that vests per year
    notice_days: int = 0  # notice you must serve at your current employer
    joining_date: date | None = None  # the date the new employer asks for


@dataclass(frozen=True)
class OfferResult:
    name: str
    currency: str
    steady_cash: Decimal  # per year, once settled: fixed plus expected variable
    first_year_cash: Decimal  # the same plus the joining bonus
    guaranteed_cash: Decimal  # fixed pay only
    equity_annual: Decimal
    # The same four figures in rupees, or None when no usable rate is stored.
    steady_cash_inr: Decimal | None
    first_year_cash_inr: Decimal | None
    guaranteed_cash_inr: Decimal | None
    equity_annual_inr: Decimal | None
    variable_share_pct: Decimal | None  # how much of steady cash is not guaranteed
    earliest_start: date
    rank: int | None  # by steady cash in rupees; None when it could not be converted
    behind_best_pct: Decimal | None
    notes: list[str]


def _convert(amount: Decimal, rate: Decimal | None) -> Decimal | None:
    return None if rate is None else (amount * rate).quantize(Decimal(1))


def compare(offers: list[OfferInput], rates: dict[str, Rate], today: date) -> list[OfferResult]:
    """One result per offer, in the order given, with ranks by steady cash in rupees."""
    results: list[OfferResult] = []
    for offer in offers:
        notes: list[str] = []
        expected_variable = offer.variable_target_annual * offer.variable_payout_pct / 100
        steady = offer.fixed_annual + expected_variable
        first_year = steady + offer.joining_bonus

        rate: Decimal | None
        if offer.currency == HOME_CURRENCY:
            rate = Decimal(1)
        elif offer.currency in rates:
            stored = rates[offer.currency]
            rate = stored.to_inr
            age = (today - stored.as_of).days
            if age > STALE_RATE_DAYS:
                notes.append(
                    f"The {offer.currency} rate is from {stored.as_of} ({age} days ago). "
                    "Update it before you rely on this."
                )
        else:
            rate = None
            notes.append(f"No {offer.currency} rate is stored, so rupee figures are left out.")

        if offer.variable_target_annual > 0 and offer.variable_payout_pct < 100:
            notes.append(
                f"Variable pay is counted at {offer.variable_payout_pct:g}% of its target."
            )
        if offer.equity_annual_value > 0:
            notes.append("Equity is your own estimate and is not in the cash totals.")
        if offer.joining_bonus > 0:
            notes.append("The joining bonus is in the first year only; check the clawback terms.")

        earliest = today + timedelta(days=offer.notice_days)
        if offer.joining_date is not None and offer.joining_date < earliest:
            late = (earliest - offer.joining_date).days
            notes.append(
                f"Your notice period ends {late} day(s) after the joining date they asked for."
            )

        results.append(
            OfferResult(
                name=offer.name,
                currency=offer.currency,
                steady_cash=steady,
                first_year_cash=first_year,
                guaranteed_cash=offer.fixed_annual,
                equity_annual=offer.equity_annual_value,
                steady_cash_inr=_convert(steady, rate),
                first_year_cash_inr=_convert(first_year, rate),
                guaranteed_cash_inr=_convert(offer.fixed_annual, rate),
                equity_annual_inr=_convert(offer.equity_annual_value, rate),
                variable_share_pct=(
                    (expected_variable / steady * 100).quantize(Decimal("0.1")) if steady else None
                ),
                earliest_start=earliest,
                rank=None,
                behind_best_pct=None,
                notes=notes,
            )
        )
    return _ranked(results)


def _ranked(results: list[OfferResult]) -> list[OfferResult]:
    order = sorted(
        (i for i, r in enumerate(results) if r.steady_cash_inr is not None),
        key=lambda i: results[i].steady_cash_inr or Decimal(0),
        reverse=True,
    )
    best = results[order[0]].steady_cash_inr if order else None
    ranked = list(results)
    for rank, i in enumerate(order, start=1):
        value = results[i].steady_cash_inr or Decimal(0)
        behind = ((best - value) / best * 100).quantize(Decimal("0.1")) if best else Decimal(0)
        ranked[i] = replace(results[i], rank=rank, behind_best_pct=behind)
    return ranked
