"""Finding pay figures in text, and summarising several figures into a range. Pure functions.

A figure is only reported with the exact words it came from (`quote`), so the owner can read the
source sentence instead of trusting a number. Hourly and monthly figures are converted only when
the text says so; anything ambiguous is dropped rather than guessed.
"""

import re
import statistics
from dataclasses import dataclass

MIN_INR_LPA = 1.0
MAX_INR_LPA = 500.0
MIN_FOREIGN_YEARLY = 10_000
MAX_FOREIGN_YEARLY = 1_000_000
QUOTE_CONTEXT = 70  # characters of surrounding text kept as the quote

_NUM = r"\d{1,3}(?:\.\d+)?"
_SEP = r"\s*(?:-|–|—|to)\s*"
# "12-18 LPA", "Rs. 15 lakhs", "INR 12 to 18 LPA", "12 LPA"
_CUR = r"(?:\u20b9|rs\.?|inr)"
_LPA = re.compile(
    rf"(?:{_CUR}\s*)?({_NUM})(?:{_SEP}(?:{_CUR}\s*)?({_NUM}))?\s*"
    r"(?:lpa|l\.p\.a\.?|(?:lakhs?|lacs?)\s+per\s+annum)\b",
    re.IGNORECASE,
)
# "Rs. 15 lakhs", "INR 12-18 lakh". A rupee marker is required: "5 lakh lines" is not pay.
_LAKH = re.compile(
    rf"{_CUR}\s*({_NUM})(?:{_SEP}(?:{_CUR}\s*)?({_NUM}))?\s*(?:lakhs?|lacs?)\b",
    re.IGNORECASE,
)
# "INR 1,200,000 - 1,800,000", "Rs 15,00,000"
_INR_ABS = re.compile(
    r"(?:₹|rs\.?|inr)\s*(\d[\d,]{5,})(?:\s*(?:-|–|to)\s*(?:(?:₹|rs\.?|inr)\s*)?(\d[\d,]{5,}))?",
    re.IGNORECASE,
)
_AMOUNT = r"(?:\d{1,3}(?:,\d{3})+|\d{2,3}(?:\.\d)?\s?k)"
# "$90,000 - $120,000", "USD 90k-120k", "EUR 70,000", "GBP 60k"
_FOREIGN = re.compile(
    rf"(\$|usd|€|eur|£|gbp|aed|cad|aud|sgd)\s?({_AMOUNT})(?:{_SEP}(?:\$|usd|€|eur|£|gbp|aed|cad|aud|sgd)?\s?({_AMOUNT}))?",
    re.IGNORECASE,
)
_MONTHLY = re.compile(r"per\s+month|/\s*month|a\s+month|monthly|\bpm\b|/\s*mo\b", re.IGNORECASE)
_HOURLY = re.compile(r"per\s+hour|/\s*h(?:ou)?r|hourly|an\s+hour", re.IGNORECASE)
_CURRENCY = {
    "$": "USD", "usd": "USD", "€": "EUR", "eur": "EUR", "£": "GBP", "gbp": "GBP",
    "aed": "AED", "cad": "CAD", "aud": "AUD", "sgd": "SGD",
}  # fmt: skip


@dataclass(frozen=True)
class PayFigure:
    currency: str  # INR, USD, ...
    low: float  # per year; for INR also expressed in lakhs per annum
    high: float | None
    quote: str  # the words it came from

    @property
    def lpa(self) -> tuple[float, float | None] | None:
        """Lakhs per annum, for rupee figures only."""
        if self.currency != "INR":
            return None
        return (self.low / 100_000, None if self.high is None else self.high / 100_000)


def _amount(raw: str) -> float:
    text = raw.replace(",", "").replace(" ", "").lower()
    return float(text[:-1]) * 1000 if text.endswith("k") else float(text)


def _context(text: str, start: int, end: int) -> str:
    left = max(0, start - QUOTE_CONTEXT)
    right = min(len(text), end + QUOTE_CONTEXT)
    return " ".join(text[left:right].split())


def _period_after(text: str, end: int) -> str:
    return text[end : end + 24]


def find_pay(text: str) -> list[PayFigure]:
    """Every plausible yearly pay figure in `text`, in the order they appear."""
    found: list[tuple[int, PayFigure]] = []
    taken: list[tuple[int, int]] = []

    def free(start: int, end: int) -> bool:
        return all(end <= a or start >= b for a, b in taken)

    for m in sorted([*_LPA.finditer(text), *_LAKH.finditer(text)], key=lambda x: x.start()):
        if not free(m.start(), m.end()):
            continue
        low = float(m.group(1))
        high = float(m.group(2)) if m.group(2) else None
        if not MIN_INR_LPA <= low <= MAX_INR_LPA or (
            high is not None and not low <= high <= MAX_INR_LPA
        ):
            continue
        taken.append((m.start(), m.end()))
        found.append(
            (
                m.start(),
                PayFigure(
                    "INR",
                    low * 100_000,
                    None if high is None else high * 100_000,
                    _context(text, m.start(), m.end()),
                ),
            )
        )
    for m in _INR_ABS.finditer(text):
        if not free(m.start(), m.end()):
            continue
        low, high = _amount(m.group(1)), _amount(m.group(2)) if m.group(2) else None
        after = _period_after(text, m.end())
        if _MONTHLY.search(after):
            low, high = low * 12, None if high is None else high * 12
        if not MIN_INR_LPA * 100_000 <= low <= MAX_INR_LPA * 100_000 or (
            high is not None and high < low
        ):
            continue
        taken.append((m.start(), m.end()))
        found.append((m.start(), PayFigure("INR", low, high, _context(text, m.start(), m.end()))))
    for m in _FOREIGN.finditer(text):
        if not free(m.start(), m.end()):
            continue
        low = _amount(m.group(2))
        high = _amount(m.group(3)) if m.group(3) else None
        after = _period_after(text, m.end())
        if _HOURLY.search(after):
            continue  # hourly rates are not annual pay
        if _MONTHLY.search(after):
            low, high = low * 12, None if high is None else high * 12
        if not MIN_FOREIGN_YEARLY <= low <= MAX_FOREIGN_YEARLY or (
            high is not None and not low <= high <= MAX_FOREIGN_YEARLY
        ):
            continue
        taken.append((m.start(), m.end()))
        found.append(
            (
                m.start(),
                PayFigure(
                    _CURRENCY[m.group(1).lower()], low, high, _context(text, m.start(), m.end())
                ),
            )
        )
    return [figure for _, figure in sorted(found, key=lambda item: item[0])]


@dataclass(frozen=True)
class Range:
    low: float
    mid: float
    high: float
    n: int  # how many figures it is based on


def summarise(values: list[float]) -> Range | None:
    """The range a set of figures suggests: the middle half (25th to 75th percentile) when there
    are at least four, otherwise min to max. `mid` is the median. None for no figures."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) >= 4:
        q = statistics.quantiles(ordered, n=4, method="inclusive")
        low, high = q[0], q[2]
    else:
        low, high = ordered[0], ordered[-1]
    return Range(low=low, mid=statistics.median(ordered), high=high, n=len(ordered))
