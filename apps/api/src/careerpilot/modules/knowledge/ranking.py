"""Combine ranked lists into one."""

import re
import uuid
from collections.abc import Sequence

RRF_K = 60  # the usual constant; larger values flatten the difference between ranks


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[uuid.UUID]],
    k: int = RRF_K,
    weights: Sequence[float] | None = None,
) -> list[tuple[uuid.UUID, float]]:
    """Fuse several ranked lists of ids. An id scores weight/(k + rank) in every list it appears in.

    Only ranks matter, so a vector distance and a text-search score can be combined without
    pretending they are on the same scale.
    """
    scores: dict[uuid.UUID, float] = {}
    for index, ranking in enumerate(rankings):
        weight = weights[index] if weights else 1.0
        for position, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + weight / (k + position)
    return sorted(scores.items(), key=lambda pair: (-pair[1], str(pair[0])))


_WORD = re.compile(r"[A-Za-z0-9]{2,}")


def or_query(question: str) -> str:
    """A to_tsquery string that matches any word in the question (words only: nothing to inject)."""
    seen: list[str] = []
    for word in _WORD.findall(question.lower()):
        if word not in seen:
            seen.append(word)
    return " | ".join(seen[:30])
