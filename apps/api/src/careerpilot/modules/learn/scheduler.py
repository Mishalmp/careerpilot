"""Spaced-repetition scheduling. The only place that imports the `fsrs` package, so swapping the
algorithm (or its version) touches one file. FSRS (Free Spaced Repetition Scheduler) models each
card by *stability* (days until recall falls to the target), *difficulty*, and *retrievability*
(the chance you remember it right now), and picks the next review so recall is about the target.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from fsrs import Card, Scheduler, State
from fsrs import Rating as FsrsRating

from careerpilot.modules.learn.enums import Rating

DEFAULT_RETENTION = 0.9
_RATING = {
    Rating.AGAIN: FsrsRating.Again,
    Rating.HARD: FsrsRating.Hard,
    Rating.GOOD: FsrsRating.Good,
    Rating.EASY: FsrsRating.Easy,
}


@dataclass(frozen=True)
class CardState:
    """What we store for one question's schedule."""

    state: int  # 1 learning, 2 review, 3 relearning (fsrs.State)
    step: int | None
    stability: float | None
    difficulty: float | None
    due: datetime
    last_review: datetime | None
    reps: int = 0
    lapses: int = 0


def _scheduler(retention: float) -> Scheduler:
    # Fuzzing spreads due dates randomly; off so the same history always gives the same schedule.
    return Scheduler(desired_retention=retention, enable_fuzzing=False)


def _utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        raise ValueError("times must be timezone-aware")
    return moment.astimezone(UTC)


def new_card(now: datetime) -> CardState:
    now = _utc(now)
    card = Card(due=now)
    return CardState(
        state=int(card.state),
        step=card.step,
        stability=None,
        difficulty=None,
        due=now,
        last_review=None,
    )


def _to_fsrs(card: CardState) -> Card:
    return Card(
        state=State(card.state),
        step=card.step,
        stability=card.stability,
        difficulty=card.difficulty,
        due=_utc(card.due),
        last_review=_utc(card.last_review) if card.last_review else None,
    )


def review(
    card: CardState, rating: Rating, now: datetime, retention: float = DEFAULT_RETENTION
) -> CardState:
    """The card after one review. Counts a lapse when a remembered card is forgotten."""
    now = _utc(now)
    updated, _ = _scheduler(retention).review_card(_to_fsrs(card), _RATING[rating], now)
    lapsed = rating is Rating.AGAIN and card.state == int(State.Review)
    return CardState(
        state=int(updated.state),
        step=updated.step,
        stability=updated.stability,
        difficulty=updated.difficulty,
        due=_utc(updated.due),
        last_review=now,
        reps=card.reps + 1,
        lapses=card.lapses + (1 if lapsed else 0),
    )


def retrievability(card: CardState, now: datetime, retention: float = DEFAULT_RETENTION) -> float:
    """Chance (0 to 1) the card is remembered at `now`. 0 for a card never reviewed."""
    if card.last_review is None or card.stability is None:
        return 0.0
    return float(_scheduler(retention).get_card_retrievability(_to_fsrs(card), _utc(now)))
