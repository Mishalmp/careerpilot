"""Pure learning rules: option validation, multiple-choice marking, answer -> rating.
# covers: REQ-09 (question types), REQ-11 (rating for spaced repetition)
"""

import pytest

from careerpilot.modules.learn.enums import QuestionType, Rating
from careerpilot.modules.learn.rules import (
    Option,
    QuestionInvalidError,
    grade_mcq,
    rating_from_answer,
    validate_options,
    validate_stem,
)


def opts(*pairs: tuple[str, bool]) -> list[Option]:
    return [Option(text, ok) for text, ok in pairs]


GOOD_SINGLE = opts(("A", True), ("B", False), ("C", False))


def test_valid_single_and_multi_pass() -> None:
    validate_options(QuestionType.MCQ_SINGLE, GOOD_SINGLE)
    validate_options(
        QuestionType.MCQ_MULTI, opts(("A", True), ("B", True), ("C", False), ("D", False))
    )


@pytest.mark.parametrize(
    ("kind", "options", "message"),
    [
        (QuestionType.MCQ_SINGLE, opts(("A", True), ("B", False)), "between 3 and 5"),
        (QuestionType.MCQ_SINGLE, opts(*[(c, c == "A") for c in "ABCDEF"]), "between 3 and 5"),
        (QuestionType.MCQ_SINGLE, opts(("A", True), ("B", True), ("C", False)), "exactly one"),
        (QuestionType.MCQ_SINGLE, opts(("A", False), ("B", False), ("C", False)), "exactly one"),
        (QuestionType.MCQ_MULTI, opts(("A", False), ("B", False), ("C", False)), "at least one"),
        (QuestionType.MCQ_MULTI, opts(("A", True), ("B", True), ("C", True)), "not all"),
        (QuestionType.MCQ_SINGLE, opts(("A", True), ("A", False), ("C", False)), "same thing"),
        (QuestionType.MCQ_SINGLE, opts(("A", True), (" a. ", False), ("C", False)), "same thing"),
        (
            QuestionType.MCQ_SINGLE,
            opts(("A", True), ("All of the above", False), ("C", False)),
            "not allowed",
        ),
        (QuestionType.MCQ_SINGLE, opts(("A", True), ("   ", False), ("C", False)), "empty"),
        (
            QuestionType.MCQ_SINGLE,
            opts(("A", True), ("x" * 501, False), ("C", False)),
            "longer than",
        ),
        (QuestionType.SHORT, opts(("A", True)), "Only multiple-choice"),
    ],
)
def test_invalid_options_are_rejected_with_a_clear_message(
    kind: QuestionType, options: list[Option], message: str
) -> None:
    with pytest.raises(QuestionInvalidError, match=message):
        validate_options(kind, options)


def test_non_choice_questions_have_no_options() -> None:
    for kind in (
        QuestionType.SHORT,
        QuestionType.PRACTICAL,
        QuestionType.EXPLAIN,
        QuestionType.SCENARIO,
    ):
        validate_options(kind, [])


def test_stem_is_trimmed_and_bounded() -> None:
    assert validate_stem("  What is a lease?  ") == "What is a lease?"
    with pytest.raises(QuestionInvalidError):
        validate_stem("   ")
    with pytest.raises(QuestionInvalidError):
        validate_stem("x" * 2001)


@pytest.mark.parametrize(
    ("correct", "chosen", "score", "exact"),
    [  # pyright: ignore[reportUnknownArgumentType]
        ({0}, {0}, 1.0, True),
        ({0}, {1}, 0.0, False),
        ({0}, {0, 1}, 0.0, False),  # single answer: anything but the exact answer is wrong
        ({0}, set(), 0.0, False),
        ({0, 1}, {0, 1}, 1.0, True),
        ({0, 1}, {0}, 0.5, False),
        ({0, 1}, {0, 2}, 0.0, False),  # one right minus one wrong
        ({0, 1}, {0, 1, 2}, 0.5, False),  # all right but one wrong
        ({0, 1}, {2, 3}, 0.0, False),  # never negative
        ({0, 1, 2}, {0, 1, 2, 3, 4}, 1 / 3, False),  # picking everything cannot pass
    ],
)
def test_grade_mcq_table(correct: set[int], chosen: set[int], score: float, exact: bool) -> None:
    result = grade_mcq(frozenset(correct), frozenset(chosen))
    assert result.score == pytest.approx(score)
    assert result.correct is exact


def test_grade_mcq_counts() -> None:
    result = grade_mcq(frozenset({0, 1, 2}), frozenset({0, 3}))
    assert (result.right_picked, result.wrong_picked, result.missed) == (1, 1, 2)


def test_grade_mcq_needs_a_correct_option() -> None:
    with pytest.raises(ValueError, match="at least one correct"):
        grade_mcq(frozenset(), frozenset({0}))


@pytest.mark.parametrize(
    ("score", "confidence", "seconds", "typical", "expected"),
    [
        (0.0, 3, 5, 10, Rating.AGAIN),  # wrong is Again however sure you were
        (0.79, 3, 3, 10, Rating.AGAIN),  # just under the pass mark
        (0.8, 2, None, None, Rating.GOOD),
        (1.0, 1, 5, 10, Rating.HARD),  # right but guessing
        (1.0, 2, 30, 10, Rating.HARD),  # right but very slow (more than 2x)
        (1.0, 2, 20, 10, Rating.GOOD),  # exactly 2x is not "very slow"
        (1.0, 3, 4, 10, Rating.EASY),  # sure and quick
        (1.0, 3, 6, 10, Rating.GOOD),  # sure but not quick
        (1.0, 3, None, None, Rating.GOOD),  # no timing: cannot say Easy
        (1.0, 3, 4, None, Rating.GOOD),  # no typical time yet
    ],
)
def test_rating_table(
    score: float, confidence: int, seconds: float | None, typical: float | None, expected: Rating
) -> None:
    assert rating_from_answer(score, confidence, seconds, typical) is expected


def test_rating_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError):
        rating_from_answer(1.0, 0)
    with pytest.raises(ValueError):
        rating_from_answer(1.0, 4)
    with pytest.raises(ValueError):
        rating_from_answer(1.5, 2)
