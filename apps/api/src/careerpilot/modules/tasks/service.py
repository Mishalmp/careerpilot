"""A small Postgres-backed queue: idempotent enqueue, retry with backoff, watchdog, manual retry.

Why not a queue library: one user, two task kinds, and the pieces needed (SKIP LOCKED claiming,
backoff, visible failures) are about a hundred lines on the database that is already there. If
this ever needs many workers or priorities, replace this file with procrastinate (plan spike S3);
the handlers do not change.
"""

import random
import uuid
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from careerpilot.core.errors import ProblemError
from careerpilot.modules.tasks import repository
from careerpilot.modules.tasks.enums import TaskKind, TaskStatus
from careerpilot.modules.tasks.models import Task
from careerpilot.modules.tasks.schemas import TaskCounts, TaskList, TaskOut

log = structlog.get_logger()

BACKOFF_BASE_SECONDS = 60
BACKOFF_CAP_SECONDS = 3600
MAX_ERROR_CHARS = 500

# A handler gets its own session and the task. It commits its own work and raises on failure.
Handler = Callable[[AsyncSession, Task], Awaitable[None]]


class TaskFailure(Exception):
    """A failure whose message is written for the user (shown on the Tasks screen)."""


def backoff(attempts: int) -> timedelta:
    """1 minute, 2, 4, ... up to an hour, plus up to 10 percent of jitter."""
    seconds = min(BACKOFF_BASE_SECONDS * 2 ** (attempts - 1), BACKOFF_CAP_SECONDS)
    return timedelta(seconds=seconds * (1 + random.random() * 0.1))  # noqa: S311


async def enqueue(
    db: AsyncSession,
    owner_id: uuid.UUID,
    kind: TaskKind,
    key: str,
    payload: dict[str, str],
    *,
    max_attempts: int,
) -> bool:
    """False when a task with this key already exists (so scheduling twice is harmless)."""
    return await repository.enqueue(
        db, owner_id=owner_id, kind=kind, key=key, payload=payload, max_attempts=max_attempts
    )


def _record_failure(task: Task, message: str, now: datetime) -> None:
    task.error = message[:MAX_ERROR_CHARS]
    if task.attempts < task.max_attempts:
        task.status = TaskStatus.QUEUED
        task.run_after = now + backoff(task.attempts)
    else:
        task.status = TaskStatus.FAILED
        task.finished_at = now


async def run_next(
    sessionmaker: async_sessionmaker[AsyncSession],
    handlers: Mapping[TaskKind, Handler],
    *,
    now: datetime | None = None,
    stuck_after: timedelta = timedelta(minutes=15),
) -> bool:
    """Run one due task. Returns False when nothing was due.

    The claim is committed before the handler runs, so a crash leaves the task `running` and the
    watchdog below returns it to the queue (or fails it once attempts are used up).
    """
    now = now or datetime.now(UTC)
    async with sessionmaker() as db:
        for task in await repository.stuck(db, now, stuck_after):
            _record_failure(task, "The worker stopped before this task finished.", now)
        task = await repository.claim_next(db, now)
        if task is None:
            await db.commit()
            return False
        task_id, kind = task.id, task.kind
        await db.commit()

    async with sessionmaker() as db:
        task = await repository.get(db, task_id)
        if task is None:  # deleted while queued
            return True
        try:
            handler = handlers.get(kind)
            if handler is None:
                raise TaskFailure(f"No handler for {kind.value} tasks.")
            await handler(db, task)
        except TaskFailure as exc:
            await db.rollback()
            await _finish(sessionmaker, task_id, error=str(exc))
        except ProblemError as exc:
            await db.rollback()
            await _finish(sessionmaker, task_id, error=f"{exc.title}: {exc.detail or ''}".strip())
        except Exception:
            await db.rollback()
            log.exception("task_crashed", task_id=str(task_id), kind=kind.value)
            await _finish(sessionmaker, task_id, error="Unexpected error; see the server log.")
        else:
            await _finish(sessionmaker, task_id, error=None)
    return True


async def _finish(
    sessionmaker: async_sessionmaker[AsyncSession], task_id: uuid.UUID, *, error: str | None
) -> None:
    async with sessionmaker() as db:
        task = await repository.get(db, task_id, lock=True)
        if task is None:
            return
        now = datetime.now(UTC)
        if error is None:
            task.status, task.error, task.finished_at = TaskStatus.SUCCEEDED, None, now
        else:
            _record_failure(task, error, now)
        await db.commit()


# --- reading and manual retry (the Tasks screen) ------------------------------------------


def _out(task: Task) -> TaskOut:
    return TaskOut.model_validate(task)


async def list_tasks(db: AsyncSession, owner_id: uuid.UUID, status: TaskStatus | None) -> TaskList:
    counts = await repository.counts(db, owner_id)
    return TaskList(
        items=[_out(t) for t in await repository.list_recent(db, owner_id, status)],
        counts=TaskCounts(**{s.value: counts.get(s, 0) for s in TaskStatus}),
    )


async def retry(db: AsyncSession, owner_id: uuid.UUID, task_id: uuid.UUID) -> TaskOut:
    task = await repository.get_owned(db, owner_id, task_id)
    if task is None:
        raise ProblemError(404, "Not found", "Task not found.")
    if task.status is not TaskStatus.FAILED:
        raise ProblemError(
            409, "Only failed tasks can be retried", f"This task is {task.status.value}."
        )
    task.status, task.attempts, task.error = TaskStatus.QUEUED, 0, None
    task.run_after, task.finished_at = datetime.now(UTC), None
    await db.commit()
    await db.refresh(task)
    return _out(task)


async def retry_all(db: AsyncSession, owner_id: uuid.UUID) -> int:
    count = await repository.requeue_all_failed(db, owner_id, datetime.now(UTC))
    await db.commit()
    return count


async def failed_since(db: AsyncSession, owner_id: uuid.UUID, since: datetime) -> int:
    return await repository.failed_since(db, owner_id, since)
