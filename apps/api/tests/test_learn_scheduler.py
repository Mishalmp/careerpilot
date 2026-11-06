"""The FSRS wrapper. We test behaviour we can state without knowing the algorithm's constants:
intervals grow with success, a lapse is counted, retrievability falls with time.
# covers: REQ-11
"""

from datetime import UTC, datetime, timedelta

import pytest

from careerpilot.modules.learn.enums import Rating
from careerpilot.modules.learn.scheduler import new_card, retrievability, review

T0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


def test_new_card_is_due_now_and_never_reviewed() -> None:
    card = new_card(T0)
    assert card.due == T0
    assert card.last_review is None
    assert card.stability is None
    assert (card.reps, card.lapses) == (0, 0)
    assert retrievability(card, T0) == 0.0


def test_successful_reviews_push_the_due_date_further_each_time() -> None:
    card = new_card(T0)
    now = T0
    gaps: list[timedelta] = []
    for _ in range(6):
        card = review(card, Rating.GOOD, now)
        gaps.append(card.due - now)
        now = card.due  # review exactly when it is due
    assert card.reps == 6
    assert card.lapses == 0
    assert gaps[-1] > gaps[2] > gaps[0]
    assert gaps[-1] >= timedelta(days=5)  # after six good reviews it is no longer minutes away


def test_again_on_a_remembered_card_is_a_lapse_and_brings_it_back_soon() -> None:
    card = new_card(T0)
    now = T0
    for _ in range(5):
        card = review(card, Rating.GOOD, now)
        now = card.due
    long_gap = card.due - card.last_review  # type: ignore[operator]
    card = review(card, Rating.AGAIN, now)
    assert card.lapses == 1
    assert card.due - now < long_gap
    assert card.due - now <= timedelta(days=1)


def test_again_on_a_brand_new_card_is_not_a_lapse() -> None:
    card = review(new_card(T0), Rating.AGAIN, T0)
    assert card.lapses == 0
    assert card.reps == 1


def test_easy_schedules_further_out_than_hard() -> None:
    now = T0
    hard = easy = new_card(T0)
    for _ in range(3):
        hard = review(hard, Rating.HARD, now)
        easy = review(easy, Rating.EASY, now)
        now = max(hard.due, easy.due)
    assert (easy.due - easy.last_review) > (hard.due - hard.last_review)  # type: ignore[operator]


def test_same_history_gives_the_same_schedule() -> None:
    def run() -> object:
        card = new_card(T0)
        now = T0
        for rating in (Rating.GOOD, Rating.GOOD, Rating.HARD, Rating.EASY):
            card = review(card, rating, now)
            now = card.due
        return card

    assert run() == run()


def test_retrievability_is_high_after_review_and_falls_with_time() -> None:
    card = review(new_card(T0), Rating.GOOD, T0)
    soon = retrievability(card, T0 + timedelta(minutes=1))
    later = retrievability(card, T0 + timedelta(days=30))
    assert soon > 0.99
    assert 0.0 <= later < soon


def test_a_higher_retention_target_means_shorter_intervals() -> None:
    now = T0
    relaxed = strict = new_card(T0)
    for _ in range(4):
        relaxed = review(relaxed, Rating.GOOD, now, retention=0.8)
        strict = review(strict, Rating.GOOD, now, retention=0.95)
        now = max(relaxed.due, strict.due)
    assert (strict.due - strict.last_review) <= (relaxed.due - relaxed.last_review)  # type: ignore[operator]


def test_times_must_have_a_time_zone() -> None:
    with pytest.raises(ValueError, match="timezone"):
        review(new_card(T0), Rating.GOOD, datetime(2026, 1, 1, 9, 0))
