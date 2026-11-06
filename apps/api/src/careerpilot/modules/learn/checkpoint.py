"""Builds a checkpoint exam from the questions you have studied. Pure and seedable: the same
candidates, spec and seed always give the same exam, and no database or model is involved.

Rules, in order:
  1. Prefer questions you have not seen in the last `avoid_days`; use recent ones only if there are
     not enough fresh ones.
  2. Share the questions across topics in proportion to the topic weights (usually priority), at
     least one per topic when there is room, never more than a topic has to offer.
  3. Within that, follow the wanted mix of question kinds as closely as the supply allows.
  4. Shuffle with the seed so topics are interleaved.
"""

import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from careerpilot.modules.learn.enums import QuestionType

KIND_OF = {
    QuestionType.MCQ_SINGLE: "choice",
    QuestionType.MCQ_MULTI: "choice",
    QuestionType.SHORT: "written",
    QuestionType.EXPLAIN: "written",
    QuestionType.SCENARIO: "written",
    QuestionType.PRACTICAL: "practical",
}
DEFAULT_MIX: Mapping[str, float] = {"choice": 0.6, "written": 0.25, "practical": 0.15}


@dataclass(frozen=True)
class Candidate:
    id: str
    topic_id: str
    type: QuestionType
    difficulty: int = 3
    seen_days_ago: int | None = None  # None: never seen


@dataclass(frozen=True)
class Spec:
    size: int = 20
    seed: int = 0
    avoid_days: int = 7
    mix: Mapping[str, float] = field(default_factory=lambda: dict(DEFAULT_MIX))
    # A topic missing from here has weight 1.
    topic_weights: Mapping[str, float] = field(default_factory=lambda: dict[str, float]())


@dataclass(frozen=True)
class Built:
    question_ids: list[str]
    per_topic: dict[str, int]
    shortfall: int  # how many fewer than `size` could be built
    notes: list[str]


def _allocate(size: int, supply: Mapping[str, int], weights: Mapping[str, float]) -> dict[str, int]:
    """How many questions each topic gets: one each if there is room, then by weight (D'Hondt:
    each extra slot goes to the open topic with the highest weight / (already given + 1)), never
    more than the topic has."""
    topics = sorted(t for t, n in supply.items() if n > 0)
    target = min(size, sum(supply[t] for t in topics))
    out = dict.fromkeys(topics, 0)

    def weight(t: str) -> float:
        return max(weights.get(t, 1.0), 0.0)

    if target < len(topics):  # not enough room for every topic: the heaviest ones
        for t in sorted(topics, key=lambda t: (-weight(t), t))[:target]:
            out[t] = 1
        return out
    for t in topics:
        out[t] = 1
    while sum(out.values()) < target:
        open_topics = [t for t in topics if out[t] < supply[t]]
        best = min(open_topics, key=lambda t: (-weight(t) / (out[t] + 1), t))
        out[best] += 1
    return out


def build(candidates: Sequence[Candidate], spec: Spec) -> Built:
    if spec.size < 1:
        raise ValueError("size must be at least 1")
    notes: list[str] = []
    ordered = sorted(candidates, key=lambda c: c.id)  # input order must not matter
    seen_ids: set[str] = set()
    unique: list[Candidate] = []
    for c in ordered:
        if c.id not in seen_ids:
            seen_ids.add(c.id)
            unique.append(c)

    fresh = [c for c in unique if c.seen_days_ago is None or c.seen_days_ago >= spec.avoid_days]
    pool = fresh
    if len(fresh) < spec.size:
        pool = unique  # not enough fresh questions: fall back to everything, fresh ones first below
        if len(unique) > len(fresh):
            notes.append("Not enough new questions, so some you saw recently are included.")

    by_topic: dict[str, list[Candidate]] = defaultdict(list)
    for c in pool:
        by_topic[c.topic_id].append(c)
    supply = {t: len(items) for t, items in by_topic.items()}
    allocation = _allocate(spec.size, supply, spec.topic_weights)

    total_mix = sum(spec.mix.values()) or 1.0
    wanted = {kind: round(spec.size * share / total_mix) for kind, share in spec.mix.items()}
    picked_per_kind: dict[str, int] = defaultdict(int)
    rng = random.Random(spec.seed)  # noqa: S311  (shuffling an exam, not security)
    chosen: list[Candidate] = []

    for topic in sorted(allocation):
        remaining = list(by_topic[topic])
        rng.shuffle(remaining)
        # Fresh questions before recently seen ones, then keep the shuffle's order.
        remaining.sort(key=lambda c: 0 if c in fresh else 1)
        for _ in range(allocation[topic]):

            def need(c: Candidate) -> float:
                kind = KIND_OF[c.type]
                return wanted.get(kind, 0) - picked_per_kind[kind]

            best = max(remaining, key=need)  # first best wins ties, so the shuffle breaks them
            remaining.remove(best)
            picked_per_kind[KIND_OF[best.type]] += 1
            chosen.append(best)

    rng.shuffle(chosen)
    per_topic: dict[str, int] = defaultdict(int)
    for c in chosen:
        per_topic[c.topic_id] += 1
    shortfall = spec.size - len(chosen)
    if shortfall > 0:
        notes.append(
            f"Only {len(chosen)} questions are available; "
            f"{shortfall} short of the {spec.size} asked for."
        )
    for kind, number in wanted.items():
        if picked_per_kind[kind] < number and shortfall == 0:
            notes.append(
                f"Fewer {kind} questions than wanted ({picked_per_kind[kind]} of {number})."
            )
    return Built(
        question_ids=[c.id for c in chosen],
        per_topic=dict(per_topic),
        shortfall=max(0, shortfall),
        notes=notes,
    )
