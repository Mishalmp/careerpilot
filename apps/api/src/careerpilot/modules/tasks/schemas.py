import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from careerpilot.modules.tasks.enums import TaskKind, TaskStatus


class TaskProgress(BaseModel):
    step: str
    done: int | None = None
    total: int | None = None


class TaskEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    at: datetime
    attempt: int
    level: str  # info | warning | error
    step: str | None
    message: str


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
    progress: TaskProgress | None
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


class TaskDetail(BaseModel):
    task: TaskOut
    events: list[TaskEventOut]  # oldest first
