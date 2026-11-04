from enum import StrEnum


class Priority(StrEnum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class TopicStatus(StrEnum):
    NOT_STARTED = "Not started"
    LEARNING = "Learning"
    REVISED = "Revised"
    MOCK_TESTED = "Mock-tested"


class DayStatus(StrEnum):
    PLANNED = "Planned"
    DONE = "Done"
    SKIPPED = "Skipped"
    MOVED = "Moved"


class StudyKind(StrEnum):
    LEARN = "learn"
    PRACTICE = "practice"
    REVIEW = "review"
    MOCK = "mock"


class PlanPhase(StrEnum):
    NOT_CONFIGURED = "not_configured"
    UPCOMING = "upcoming"
    ACTIVE = "active"
    FINISHED = "finished"
