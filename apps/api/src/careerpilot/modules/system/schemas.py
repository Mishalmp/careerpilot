import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DatabaseStatus(BaseModel):
    ok: bool
    revision: str | None  # the schema version the database is at


class TaskStatusCounts(BaseModel):
    queued: int
    running: int
    failed: int
    succeeded: int


class AiStatus(BaseModel):
    configured: bool  # an Anthropic API key is set
    tokens_today: int
    daily_cap: int


class SearchStatus(BaseModel):
    provider: str  # none, searxng or brave
    configured: bool


class BackupStatus(BaseModel):
    key_set: bool
    last_backup_at: datetime | None
    age_hours: float | None


class SystemStatus(BaseModel):
    """A snapshot of the parts of the system you can act on. No secrets are included."""

    checked_at: datetime
    database: DatabaseStatus
    tasks: TaskStatusCounts
    last_task_finished_at: datetime | None  # a rough sign that the worker is alive
    ai: AiStatus
    search: SearchStatus
    backups: BackupStatus


class AiCallOut(BaseModel):
    """One request to the model. The prompt and the answer are deliberately not kept."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    purpose: str  # which feature asked (for example the prompt name)
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    status: str  # ok | refused | error
    error: str | None


class AiCalls(BaseModel):
    items: list[AiCallOut]  # newest first
    tokens_today: int
    daily_cap: int
