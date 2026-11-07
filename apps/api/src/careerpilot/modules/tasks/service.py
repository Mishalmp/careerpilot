"""A small Postgres-backed queue: idempotent enqueue, retry with backoff, watchdog, manual retry,
and a step-by-step history of what each attempt did.

Why not a queue library: one user, a handful of task kinds, and the pieces needed (SKIP LOCKED
claiming, backoff, visible failures) are about a hundred lines on the database that is already
there. If this ever needs many workers or priorities, replace this file with procrastinate (plan
spike S3); the handlers do not change.

History: while a handler runs it reports steps with `step()`. Each step is saved at once in its own
short transaction, so a failed attempt still leaves its history, and the Tasks screen can show
where it stopped. A retry runs the same handler again; handlers are written so that finished work
is not repeated (a research run skips pages it already read, the apply list skips jobs it already
listed), which is what "continue from where it stopped" means here.
"""

import contextvars
import random
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from careerpilot.core.errors import ProblemError
from careerpilot.modules.tasks import repository
from careerpilot.modules.tasks.enums import TaskKind, TaskStatus
from careerpilot.modules.tasks.models import Task
from careerpilot.modules.tasks.schemas import (
    TaskCounts,
    TaskDetail,
    TaskEventOut,
    TaskList,
    TaskOut,
)

log = structlog.get_logger()

BACKOFF_BASE_SECONDS = 60
BACKOFF_CAP_SECONDS = 3600
MAX_ERROR_CHARS = 500
EVENT_LIMIT = 200

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


# --- the history a running attempt writes ------------------------------------------------------


@dataclass(frozen=True)
class _Run:
    sessionmaker: async_sessionmaker[AsyncSession]
    task_id: uuid.UUID
    owner_id: uuid.UUID
    attempt: int


_current: contextvars.ContextVar[_Run | None] = contextvars.ContextVar("task_run", default=None)


async def _write(
    run: _Run,
    level: str,
    message: str,
    step: str | None,
    *,
    done: int | None = None,
    total: int | None = None,
    progress: bool = False,
) -> None:
    """One event in its own transaction. Never raises: losing a log line must not fail the task."""
    try:
        async with run.sessionmaker() as db:
            repository.add_event(
                db,
                task_id=run.task_id,
                owner_id=run.owner_id,
                attempt=run.attempt,
                level=level,
                step=step,
                message=message,
            )
            if progress:
                task = await repository.get(db, run.task_id)
                if task is not None:
                    task.progress = {"step": message, "done": done, "total": total}
            await db.commit()
    except Exception:
        log.exception("task_event_not_saved", task_id=str(run.task_id))


async def step(message: str, *, done: int | None = None, total: int | None = None) -> None:
    """Say what the running task is doing now ("Reading page 3 of 12"). A no-op outside a task."""
    run = _current.get()
    if run is not None:
        await _write(run, "info", message, message, done=done, total=total, progress=True)


async def warn(message: str) -> None:
    """Record something that went wrong but did not stop the task."""
    run = _current.get()
    if run is not None:
        await _write(run, "warning", message, None)


def _record_failure(task: Task, message: str, now: datetime) -> str:
    """Set the task's state after a failed attempt; returns the sentence for its history."""
    task.error = message[:MAX_ERROR_CHARS]
    if task.attempts < task.max_attempts:
        task.status = TaskStatus.QUEUED
        task.run_after = now + backoff(task.attempts)
        return f"{message} Will try again at {task.run_after.strftime('%H:%M')} UTC."
    task.status = TaskStatus.FAILED
    task.finished_at = now
    return f"{message} Gave up after {task.attempts} attempt(s); you can retry it."


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
        for dead in await repository.stuck(db, now, stuck_after):
            sentence = _record_failure(dead, "The worker stopped before this task finished.", now)
            repository.add_event(
                db,
                task_id=dead.id,
                owner_id=dead.owner_id,
                attempt=dead.attempts,
                level="error",
                step=None,
                message=sentence,
            )
        task = await repository.claim_next(db, now)
        if task is None:
            await db.commit()
            return False
        task_id, owner_id, kind, attempt, limit = (
            task.id,
            task.owner_id,
            task.kind,
            task.attempts,
            task.max_attempts,
        )
        task.progress = None
        repository.add_event(
            db,
            task_id=task_id,
            owner_id=owner_id,
            attempt=attempt,
            level="info",
            step=None,
            message=f"Attempt {attempt} of {limit} started.",
        )
        await db.commit()

    run = _Run(sessionmaker, task_id, owner_id, attempt)
    token = _current.set(run)
    try:
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
                await _finish(sessionmaker, run, error=str(exc))
            except ProblemError as exc:
                await db.rollback()
                await _finish(sessionmaker, run, error=f"{exc.title}: {exc.detail or ''}".strip())
            except Exception:
                await db.rollback()
                log.exception("task_crashed", task_id=str(task_id), kind=kind.value)
                await _finish(sessionmaker, run, error="Unexpected error; see the server log.")
            else:
                await _finish(sessionmaker, run, error=None)
    finally:
        _current.reset(token)
    return True


async def _finish(
    sessionmaker: async_sessionmaker[AsyncSession], run: _Run, *, error: str | None
) -> None:
    async with sessionmaker() as db:
        task = await repository.get(db, run.task_id, lock=True)
        if task is None:
            return
        now = datetime.now(UTC)
        if error is None:
            task.status, task.error, task.finished_at = TaskStatus.SUCCEEDED, None, now
            level, message = "info", "Finished."
        else:
            level, message = "error", _record_failure(task, error, now)
        repository.add_event(
            db,
            task_id=run.task_id,
            owner_id=run.owner_id,
            attempt=run.attempt,
            level=level,
            step=None,
            message=message,
        )
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


async def _owned(db: AsyncSession, owner_id: uuid.UUID, task_id: uuid.UUID) -> Task:
    task = await repository.get_owned(db, owner_id, task_id)
    if task is None:
        raise ProblemError(404, "Not found", "Task not found.")
    return task


async def get_detail(db: AsyncSession, owner_id: uuid.UUID, task_id: uuid.UUID) -> TaskDetail:
    task = await _owned(db, owner_id, task_id)
    events = await repository.list_events(db, owner_id, task_id, EVENT_LIMIT)
    return TaskDetail(task=_out(task), events=[TaskEventOut.model_validate(e) for e in events])


async def retry(db: AsyncSession, owner_id: uuid.UUID, task_id: uuid.UUID) -> TaskOut:
    """Queue a failed task again. It continues from where it stopped: finished work is kept."""
    task = await _owned(db, owner_id, task_id)
    if task.status is not TaskStatus.FAILED:
        raise ProblemError(
            409, "Only failed tasks can be retried", f"This task is {task.status.value}."
        )
    task.status, task.attempts, task.error = TaskStatus.QUEUED, 0, None
    task.run_after, task.finished_at, task.progress = datetime.now(UTC), None, None
    repository.add_event(
        db,
        task_id=task.id,
        owner_id=owner_id,
        attempt=0,
        level="info",
        step=None,
        message="You asked for another try. Work that was already finished is not repeated.",
    )
    await db.commit()
    await db.refresh(task)
    return _out(task)


async def cancel(db: AsyncSession, owner_id: uuid.UUID, task_id: uuid.UUID) -> TaskOut:
    """Stop a task that has not started. A running task cannot be stopped from here."""
    task = await _owned(db, owner_id, task_id)
    if task.status is not TaskStatus.QUEUED:
        raise ProblemError(
            409, "Only waiting tasks can be cancelled", f"This task is {task.status.value}."
        )
    task.status, task.error = TaskStatus.FAILED, "Cancelled by you."
    task.finished_at = datetime.now(UTC)
    repository.add_event(
        db,
        task_id=task.id,
        owner_id=owner_id,
        attempt=task.attempts,
        level="warning",
        step=None,
        message="Cancelled by you before it ran.",
    )
    await db.commit()
    await db.refresh(task)
    return _out(task)


async def retry_all(db: AsyncSession, owner_id: uuid.UUID) -> int:
    count = await repository.requeue_all_failed(db, owner_id, datetime.now(UTC))
    await db.commit()
    return count


async def failed_since(db: AsyncSession, owner_id: uuid.UUID, since: datetime) -> int:
    return await repository.failed_since(db, owner_id, since)
