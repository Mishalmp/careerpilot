import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from careerpilot.modules.tasks.enums import TaskKind, TaskStatus


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: TaskKind
    key: str
    status: TaskStatus
    attempts: int
    max_attempts: int
    run_after: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    created_at: datetime


class TaskCounts(BaseModel):
    queued: int
    running: int
    succeeded: int
    failed: int


class TaskList(BaseModel):
    items: list[TaskOut]
    counts: TaskCounts


class RetryAllOut(BaseModel):
    requeued: int
