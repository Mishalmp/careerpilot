from enum import StrEnum


class TaskKind(StrEnum):
    DISCOVER = "discover"
    DAILY_DIGEST = "daily_digest"
    BACKUP = "backup"
    RESEARCH = "research"
    APPLY_QUEUE = "apply_queue"


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
