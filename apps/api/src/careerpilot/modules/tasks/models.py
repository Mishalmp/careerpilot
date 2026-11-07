import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from careerpilot.core.db import Base, str_enum
from careerpilot.modules.tasks.enums import TaskKind, TaskStatus


class Task(Base):
    """Background work. `key` makes enqueueing idempotent: the same key is never queued twice."""

    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("owner_id", "key", name="uq_tasks_owner_key"),
        Index("ix_tasks_status_run_after", "status", "run_after"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[TaskKind] = mapped_column(str_enum(TaskKind, "task_kind"))
    key: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[TaskStatus] = mapped_column(
        str_enum(TaskStatus, "task_status"), default=TaskStatus.QUEUED
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    # What the running attempt is doing now: {"step": ..., "done": n, "total": n or null}.
    progress: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class TaskEvent(Base):
    """One line of a task's history: an attempt starting, a step, a warning, a failure, the end.

    Written in their own short transactions, so a failed attempt still keeps its history.
    """

    __tablename__ = "task_events"
    __table_args__ = (Index("ix_task_events_task_at", "task_id", "at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    attempt: Mapped[int] = mapped_column(Integer)
    level: Mapped[str] = mapped_column(Text)  # info | warning | error
    step: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
