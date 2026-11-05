"""How a finished mock interview is summarised. Pure: no model decides the totals."""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

WEAK_BELOW = 3.0  # an average under this on a topic counts as weak
STRONG_FROM = 4.0


@dataclass(frozen=True)
class TopicResult:
    topic: str
    average: float
    questions: int


@dataclass(frozen=True)
class Summary:
    average: float | None
    answered: int
    weak: list[TopicResult]
    strong: list[TopicResult]


def summarise(turns: list[dict[str, Any]]) -> Summary:
    scored = [t for t in turns if t.get("score") is not None]
    if not scored:
        return Summary(None, 0, [], [])
    by_topic: dict[str, list[int]] = defaultdict(list)
    for turn in scored:
        by_topic[turn["topic"]].append(turn["score"])
    results = [
        TopicResult(topic, round(sum(scores) / len(scores), 1), len(scores))
        for topic, scores in by_topic.items()
    ]
    results.sort(key=lambda r: (r.average, r.topic))
    return Summary(
        average=round(sum(t["score"] for t in scored) / len(scored), 1),
        answered=len(scored),
        weak=[r for r in results if r.average < WEAK_BELOW],
        strong=[r for r in reversed(results) if r.average >= STRONG_FROM],
    )
