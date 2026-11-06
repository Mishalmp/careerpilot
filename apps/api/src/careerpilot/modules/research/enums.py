from enum import StrEnum


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"  # ended early (a budget, a search or page problem) but found something
    FAILED = "failed"


class FindingKind(StrEnum):
    TOPIC = "topic"
    QUESTION = "question"


class FindingStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
