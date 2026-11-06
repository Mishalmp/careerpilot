"""Pure rules for questions: what a valid question looks like, how multiple choice is marked,
and how an answer becomes a review rating. No database and no model, so every rule is
table-testable.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from careerpilot.modules.learn.enums import QuestionType, Rating

MIN_OPTIONS = 3
MAX_OPTIONS = 5
MAX_STEM = 2000
MAX_OPTION = 500
# Giving up on options like these is a common way to make a question guessable.
_LAZY_OPTIONS = (
    "all of the above",
    "none of the above",
    "both a and b",
    "all of these",
    "none of these",
)


@dataclass(frozen=True)
class Option:
    text: str
    is_correct: bool


class QuestionInvalidError(ValueError):
    """The question breaks a rule. The message is written for the person editing it."""


def validate_options(question_type: QuestionType, options: Sequence[Option]) -> None:
    """Rules for multiple-choice options. Other question types must have none."""
    if question_type not in (QuestionType.MCQ_SINGLE, QuestionType.MCQ_MULTI):
        if options:
            raise QuestionInvalidError("Only multiple-choice questions have options.")
        return
    if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
        raise QuestionInvalidError(f"Give between {MIN_OPTIONS} and {MAX_OPTIONS} options.")
    seen: set[str] = set()
    for option in options:
        text = " ".join(option.text.split())
        if not text:
            raise QuestionInvalidError("Options cannot be empty.")
        if len(text) > MAX_OPTION:
            raise QuestionInvalidError(f"An option is longer than {MAX_OPTION} characters.")
        key = text.casefold().rstrip(".")
        if key in _LAZY_OPTIONS:
            raise QuestionInvalidError(f'"{text}" is not allowed: write a real option instead.')
        if key in seen:
            raise QuestionInvalidError("Two options say the same thing.")
        seen.add(key)
    correct = sum(option.is_correct for option in options)
    if question_type is QuestionType.MCQ_SINGLE and correct != 1:
        raise QuestionInvalidError("A single-answer question needs exactly one correct option.")
    if question_type is QuestionType.MCQ_MULTI and not 1 <= correct < len(options):
        raise QuestionInvalidError(
            "A multiple-answer question needs at least one correct option, and not all of them."
        )


def validate_stem(stem: str) -> str:
    text = stem.strip()
    if not text:
        raise QuestionInvalidError("The question cannot be empty.")
    if len(text) > MAX_STEM:
        raise QuestionInvalidError(f"The question is longer than {MAX_STEM} characters.")
    return text


@dataclass(frozen=True)
class McqResult:
    score: float  # 0.0 to 1.0
    correct: bool  # exactly right
    right_picked: int
    wrong_picked: int
    missed: int


def grade_mcq(correct_ids: frozenset[int], chosen_ids: frozenset[int]) -> McqResult:
    """Mark a multiple-choice answer by option index.

    Single answer: 1 or 0. Multiple answer: (right picks minus wrong picks) over the number of
    correct options, never below 0, so guessing every option cannot score. Exact only if all right
    and nothing wrong.
    """
    if not correct_ids:
        raise ValueError("a multiple-choice question has at least one correct option")
    right = len(chosen_ids & correct_ids)
    wrong = len(chosen_ids - correct_ids)
    missed = len(correct_ids - chosen_ids)
    exact = wrong == 0 and missed == 0
    score = 1.0 if exact else max(0.0, (right - wrong) / len(correct_ids))
    if len(correct_ids) == 1:
        score = 1.0 if exact else 0.0
    return McqResult(
        score=score, correct=exact, right_picked=right, wrong_picked=wrong, missed=missed
    )


# --- answer -> review rating ---------------------------------------------------------------------

PASS_SCORE = 0.8  # at or above this counts as remembered
SLOW_FACTOR = 2.0  # slower than this many times your usual time counts as "hard"
FAST_FACTOR = 0.5


def rating_from_answer(
    score: float,
    confidence: int,
    seconds: float | None = None,
    typical_seconds: float | None = None,
) -> Rating:
    """Turn how well you answered into the grade the scheduler needs.

    Wrong -> Again. Right but unsure (confidence 1) or very slow -> Hard. Right and confident and
    quick -> Easy. Otherwise Good. Confidence is 1 (guessing) to 3 (sure).
    """
    if not 1 <= confidence <= 3:
        raise ValueError("confidence is 1 to 3")
    if not 0.0 <= score <= 1.0:
        raise ValueError("score is 0 to 1")
    if score < PASS_SCORE:
        return Rating.AGAIN
    slow = seconds is not None and typical_seconds and seconds > SLOW_FACTOR * typical_seconds
    fast = seconds is not None and typical_seconds and seconds < FAST_FACTOR * typical_seconds
    if confidence == 1 or slow:
        return Rating.HARD
    if confidence == 3 and fast:
        return Rating.EASY
    return Rating.GOOD
