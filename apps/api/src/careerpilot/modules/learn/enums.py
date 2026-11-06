from enum import StrEnum


class QuestionType(StrEnum):
    MCQ_SINGLE = "mcq_single"
    MCQ_MULTI = "mcq_multi"
    SHORT = "short"
    PRACTICAL = "practical"
    EXPLAIN = "explain"
    SCENARIO = "scenario"


# Types a computer can mark exactly. The others need a rubric (model or the learner) to grade.
AUTO_GRADED = frozenset({QuestionType.MCQ_SINGLE, QuestionType.MCQ_MULTI})


class QuestionStatus(StrEnum):
    DRAFT = "draft"  # written but not checked
    VERIFIED = "verified"  # has a source whose quote was found, or the owner wrote it
    UNVERIFIED = "unverified"  # model-made, could not be grounded: shown with a warning
    ARCHIVED = "archived"


class QuestionOrigin(StrEnum):
    MANUAL = "manual"
    GUIDE = "guide"
    RESEARCH = "research"
    GENERATED = "generated"


class LearnTopicStatus(StrEnum):
    NOT_STARTED = "not_started"
    LEARNING = "learning"
    PRACTISING = "practising"
    MASTERED = "mastered"


class TopicOrigin(StrEnum):
    MANUAL = "manual"
    SEED = "seed"
    RESEARCH = "research"
    GUIDE = "guide"


class Rating(StrEnum):
    """How well a card was remembered. Same four grades as FSRS."""

    AGAIN = "again"
    HARD = "hard"
    GOOD = "good"
    EASY = "easy"


class GradedBy(StrEnum):
    CODE = "code"
    MODEL = "model"
    SELF = "self"
