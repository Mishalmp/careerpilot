import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.tasks.enums import TaskKind, TaskStatus
from careerpilot.modules.tasks.models import Task, TaskEvent

LIST_LIMIT = 100


async def enqueue(
    db: AsyncSession,
    *,
    owner_id: uuid.UUID,
    kind: TaskKind,
    key: str,
    payload: dict[str, str],
    max_attempts: int,
) -> bool:
    """Queue a task unless one with this key already exists. True when it was queued."""
    statement = (
        insert(Task)
        .values(owner_id=owner_id, kind=kind, key=key, payload=payload, max_attempts=max_attempts)
        .on_conflict_do_nothing(constraint="uq_tasks_owner_key")
        .returning(Task.id)
    )
    return (await db.execute(statement)).first() is not None


async def claim_next(db: AsyncSession, now: datetime) -> Task | None:
    """Take the oldest due task. SKIP LOCKED keeps several workers off the same one."""
    task = await db.scalar(
        select(Task)
        .where(Task.status == TaskStatus.QUEUED, Task.run_after <= now)
        .order_by(Task.run_after, Task.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if task is not None:
        task.status = TaskStatus.RUNNING
        task.started_at = now
        task.attempts += 1
    return task


async def stuck(db: AsyncSession, now: datetime, after: timedelta) -> Sequence[Task]:
    """Tasks marked running for too long: their worker died."""
    rows = await db.scalars(
        select(Task)
        .where(Task.status == TaskStatus.RUNNING, Task.started_at < now - after)
        .with_for_update(skip_locked=True)
    )
    return rows.all()


async def get(db: AsyncSession, task_id: uuid.UUID, *, lock: bool = False) -> Task | None:
    query = select(Task).where(Task.id == task_id)
    return await db.scalar(query.with_for_update() if lock else query)


async def get_owned(db: AsyncSession, owner_id: uuid.UUID, task_id: uuid.UUID) -> Task | None:
    return await db.scalar(select(Task).where(Task.owner_id == owner_id, Task.id == task_id))


async def list_recent(
    db: AsyncSession, owner_id: uuid.UUID, status: TaskStatus | None
) -> Sequence[Task]:
    query = select(Task).where(Task.owner_id == owner_id)
    if status is not None:
        query = query.where(Task.status == status)
    rows = await db.scalars(query.order_by(Task.created_at.desc()).limit(LIST_LIMIT))
    return rows.all()


async def counts(db: AsyncSession, owner_id: uuid.UUID) -> dict[TaskStatus, int]:
    rows = await db.execute(
        select(Task.status, func.count()).where(Task.owner_id == owner_id).group_by(Task.status)
    )
    return {status: count for status, count in rows}


async def failed_since(db: AsyncSession, owner_id: uuid.UUID, since: datetime) -> int:
    return int(
        await db.scalar(
            select(func.count()).where(
                Task.owner_id == owner_id,
                Task.status == TaskStatus.FAILED,
                Task.finished_at >= since,
            )
        )
        or 0
    )


async def requeue_all_failed(db: AsyncSession, owner_id: uuid.UUID, now: datetime) -> int:
    result = await db.execute(
        update(Task)
        .where(Task.owner_id == owner_id, Task.status == TaskStatus.FAILED)
        .values(status=TaskStatus.QUEUED, attempts=0, run_after=now, error=None, finished_at=None)
        .returning(Task.id)
    )
    return len(result.all())


async def latest_event_messages(
    db: AsyncSession, owner_id: uuid.UUID, kind: TaskKind, level: str
) -> list[str]:
    task_id = await db.scalar(
        select(Task.id)
        .where(Task.owner_id == owner_id, Task.kind == kind)
        .order_by(Task.created_at.desc())
        .limit(1)
    )
    if task_id is None:
        return []
    rows = await db.scalars(
        select(TaskEvent.message)
        .where(TaskEvent.task_id == task_id, TaskEvent.level == level)
        .order_by(TaskEvent.at)
    )
    return list(rows)


def add_event(
    db: AsyncSession,
    *,
    task_id: uuid.UUID,
    owner_id: uuid.UUID,
    attempt: int,
    level: str,
    step: str | None,
    message: str,
) -> None:
    db.add(
        TaskEvent(
            task_id=task_id,
            owner_id=owner_id,
            attempt=attempt,
            level=level,
            step=step,
            message=message[:1000],
        )
    )


async def list_events(
    db: AsyncSession, owner_id: uuid.UUID, task_id: uuid.UUID, limit: int
) -> Sequence[TaskEvent]:
    rows = await db.scalars(
        select(TaskEvent)
        .where(TaskEvent.owner_id == owner_id, TaskEvent.task_id == task_id)
        .order_by(TaskEvent.at.desc())
        .limit(limit)
    )
    return list(reversed(rows.all()))  # oldest first, the last `limit` of them
