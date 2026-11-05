"""Reliability and brief ranking for interview intel: pure rules."""

import uuid
from datetime import date

from careerpilot.modules.intel.enums import ItemKind
from careerpilot.modules.intel.rules import (
    ItemFacts,
    build_brief,
    matching_prep_topics,
    reliability,
)

TODAY = date(2026, 11, 5)
QUOTE = "x" * 100


def item(
    source: uuid.UUID, key: str, kind: ItemKind, published: date | None, inferred: bool = False
):
    return ItemFacts(uuid.uuid4(), source, kind, key, f"{key} text", QUOTE, published, inferred)


def test_reliability_rewards_recent_specific_corroborated_facts() -> None:
    best = reliability(
        published_on=date(2026, 6, 1), quote=QUOTE, other_sources=2, inferred=False, today=TODAY
    )
    assert best == 100
    worst = reliability(
        published_on=None, quote="short", other_sources=0, inferred=False, today=TODAY
    )
    assert worst == 5


def test_inferred_facts_rank_below_the_same_fact_about_the_company() -> None:
    own = reliability(
        published_on=date(2026, 6, 1), quote=QUOTE, other_sources=0, inferred=False, today=TODAY
    )
    peer = reliability(
        published_on=date(2026, 6, 1), quote=QUOTE, other_sources=0, inferred=True, today=TODAY
    )
    assert peer < own and peer == round(own * 0.6)


def test_brief_counts_distinct_sources_and_flags_thin_evidence() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    items = [
        item(a, "sql", ItemKind.TOPIC, date(2026, 5, 1)),
        item(b, "sql", ItemKind.QUESTION, date(2026, 1, 1)),
        item(a, "coding test", ItemKind.ROUND, date(2026, 5, 1)),
        item(a, "coding test", ItemKind.ROUND, date(2026, 5, 1)),
    ]
    brief = build_brief(items, [(a, date(2026, 5, 1))], TODAY)
    assert brief.topics[0].key == "sql" and brief.topics[0].sources == 2
    assert [r.facts.key for r in brief.rounds] == ["coding test"]  # listed once
    assert len(brief.likely_questions) == 1
    assert brief.own_recent_sources == 1 and brief.needs_more_sources


def test_two_recent_own_sources_are_enough() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    brief = build_brief([], [(a, date(2026, 1, 1)), (b, date(2025, 6, 1))], TODAY)
    assert not brief.needs_more_sources
    old = build_brief([], [(a, date(2020, 1, 1)), (b, None)], TODAY)
    assert old.needs_more_sources


def test_topics_link_to_prep_topics_by_whole_word() -> None:
    topics = [("SQL window functions", "Databases"), ("Postgres internals", "Databases")]
    assert matching_prep_topics("sql", topics) == ["SQL window functions"]
    assert matching_prep_topics("sq", topics) == []
