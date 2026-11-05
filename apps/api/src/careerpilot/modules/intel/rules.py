"""Turning extracted interview facts into a ranked brief. Pure functions: no database, no model.

Every number here comes from rules you can read: how recent a source is, how specific its quote
is, and whether other sources say the same thing. Facts that come from a text about a different
company are "inferred" and always rank below the company's own.
"""

import re
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from careerpilot.modules.intel.enums import ItemKind

RECENT_YEARS = 3
MIN_RECENT_SOURCES = 2  # fewer than this and the brief says so, and peers are worth looking up
INFERRED_FACTOR = 0.6
LIKELY_QUESTIONS = 3
TIPS = 3


@dataclass(frozen=True)
class ItemFacts:
    id: uuid.UUID
    source_id: uuid.UUID
    kind: ItemKind
    key: str
    text: str
    quote: str
    published_on: date | None
    inferred: bool


def normalize_key(key: str) -> str:
    return " ".join(key.lower().split())[:40]


def reliability(
    *, published_on: date | None, quote: str, other_sources: int, inferred: bool, today: date
) -> int:
    """0 to 100: recency (40) + a specific quote (20) + other sources saying the same (40)."""
    if published_on is None:
        age = 5
    else:
        years = (today - published_on).days / 365
        age = 40 if years <= 1 else 30 if years <= 2 else 15 if years <= 4 else 5
    length = len(quote)
    specific = 20 if length >= 100 else 12 if length >= 50 else 6 if length >= 25 else 0
    agree = 0 if other_sources == 0 else 25 if other_sources == 1 else 40
    total = age + specific + agree
    return round(total * INFERRED_FACTOR) if inferred else total


@dataclass(frozen=True)
class RankedItem:
    facts: ItemFacts
    reliability: int


@dataclass(frozen=True)
class RankedTopic:
    key: str
    sources: int  # distinct sources that mention it
    reliability: int  # the best of its items
    inferred_only: bool


@dataclass(frozen=True)
class Brief:
    rounds: list[RankedItem]
    topics: list[RankedTopic]
    likely_questions: list[RankedItem]
    tips: list[RankedItem]
    own_recent_sources: int
    needs_more_sources: bool


def rank_items(items: list[ItemFacts], today: date) -> list[RankedItem]:
    """Score every item; the other-sources count looks at the same kind and key elsewhere."""
    sources_for: dict[tuple[ItemKind, str], set[uuid.UUID]] = defaultdict(set)
    for item in items:
        sources_for[(item.kind, item.key)].add(item.source_id)
    ranked = [
        RankedItem(
            item,
            reliability(
                published_on=item.published_on,
                quote=item.quote,
                other_sources=len(sources_for[(item.kind, item.key)]) - 1,
                inferred=item.inferred,
                today=today,
            ),
        )
        for item in items
    ]
    return sorted(ranked, key=lambda r: (-r.reliability, r.facts.key, str(r.facts.id)))


def build_brief(
    items: list[ItemFacts], own_sources: list[tuple[uuid.UUID, date | None]], today: date
) -> Brief:
    """`own_sources` are (id, published_on) of the sources about the company itself."""
    ranked = rank_items(items, today)

    def of(*kinds: ItemKind) -> list[RankedItem]:
        return [r for r in ranked if r.facts.kind in kinds]

    # One round per key (the best-supported wording), so the same stage is not listed twice.
    rounds: dict[str, RankedItem] = {}
    for r in of(ItemKind.ROUND):
        rounds.setdefault(r.facts.key, r)

    grouped: dict[str, list[RankedItem]] = defaultdict(list)
    for r in of(ItemKind.TOPIC, ItemKind.QUESTION):
        grouped[r.facts.key].append(r)
    topics = sorted(
        (
            RankedTopic(
                key=key,
                sources=len({r.facts.source_id for r in group}),
                reliability=max(r.reliability for r in group),
                inferred_only=all(r.facts.inferred for r in group),
            )
            for key, group in grouped.items()
        ),
        key=lambda t: (-t.sources, -t.reliability, t.key),
    )

    recent = sum(
        1
        for _, published in own_sources
        if published is not None and (today - published).days <= RECENT_YEARS * 365
    )
    return Brief(
        rounds=list(rounds.values()),
        topics=topics,
        likely_questions=of(ItemKind.QUESTION)[:LIKELY_QUESTIONS],
        tips=of(ItemKind.TIP)[:TIPS],
        own_recent_sources=recent,
        needs_more_sources=recent < MIN_RECENT_SOURCES,
    )


def matching_prep_topics(key: str, topics: list[tuple[str, str]]) -> list[str]:
    """Titles of your prep topics that mention `key` as a whole word. `topics` are (title, area)."""
    pattern = re.compile(rf"(?<!\w){re.escape(key)}(?!\w)", re.IGNORECASE)
    return [title for title, area in topics if pattern.search(f"{title} {area}")][:3]
