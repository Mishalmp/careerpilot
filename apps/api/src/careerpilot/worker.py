"""The background worker: schedules the daily jobs and runs queued tasks.

It runs inside the API process while the API is up, or on its own with
`python -m careerpilot.cli worker`. Both can run at once: tasks are claimed with SKIP LOCKED and
scheduling is idempotent (a task key is unique per day).
"""

import asyncio
import contextlib
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from careerpilot.core.backup import BackupError, backup_tools, create_backup, prune
from careerpilot.core.clock import today_in
from careerpilot.core.config import Settings
from careerpilot.core.fetcher import Fetcher
from careerpilot.core.llm import LlmClient
from careerpilot.core.search import SearchProvider
from careerpilot.modules.apply import service as apply_service
from careerpilot.modules.auth import service as auth_service
from careerpilot.modules.digest import service as digest_service
from careerpilot.modules.discovery import service as discovery_service
from careerpilot.modules.discovery.adapters import AdapterError
from careerpilot.modules.profile import service as profile_service
from careerpilot.modules.research import service as research_service
from careerpilot.modules.tasks import service as tasks_service
from careerpilot.modules.tasks.enums import TaskKind
from careerpilot.modules.tasks.models import Task
from careerpilot.modules.tasks.service import Handler, TaskFailure

log = structlog.get_logger()


def make_handlers(
    fetcher: Fetcher,
    settings: Settings,
    *,
    llm: LlmClient | None = None,
    search: SearchProvider | None = None,
) -> Mapping[TaskKind, Handler]:
    async def discover(db: AsyncSession, task: Task) -> None:
        try:
            await discovery_service.run_source(
                db, task.owner_id, uuid.UUID(task.payload["source_id"]), fetcher
            )
        except AdapterError as exc:
            raise TaskFailure(str(exc)) from exc

    async def daily_digest(db: AsyncSession, task: Task) -> None:
        await digest_service.build(db, task.owner_id, today_in(settings.timezone))

    async def backup(db: AsyncSession, task: Task) -> None:
        if settings.backup_key is None:
            raise TaskFailure("No backup key is set. Run `careerpilot backup-key` and set it.")
        try:
            await asyncio.to_thread(_backup_now, settings)
        except BackupError as exc:
            raise TaskFailure(str(exc)) from exc

    async def research(db: AsyncSession, task: Task) -> None:
        await research_service.execute(
            db,
            task.owner_id,
            uuid.UUID(task.payload["run_id"]),
            provider=search,
            fetcher=fetcher,
            llm=llm,
            settings=settings,
        )

    async def apply_queue(db: AsyncSession, task: Task) -> None:
        await apply_service.build_queue(
            db,
            task.owner_id,
            today=today_in(settings.timezone),
            settings=settings,
            search=search,
            fetcher=fetcher,
        )

    return {
        TaskKind.APPLY_QUEUE: apply_queue,
        TaskKind.RESEARCH: research,
        TaskKind.DISCOVER: discover,
        TaskKind.DAILY_DIGEST: daily_digest,
        TaskKind.BACKUP: backup,
    }


def _backup_now(settings: Settings) -> None:
    assert settings.backup_key is not None  # noqa: S101 - checked by the caller
    create_backup(
        settings.database_url,
        settings.backup_dir,
        settings.backup_key.get_secret_value(),
        tools=backup_tools(settings),
    )
    prune(settings.backup_dir, settings.backup_keep)


async def schedule_due(
    sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, now: datetime
) -> int:
    """Queue today's runs once the local hour has come. Returns how many tasks were queued."""
    local = now.astimezone(ZoneInfo(settings.timezone))
    day = local.date().isoformat()
    queued = 0
    async with sessionmaker() as db:
        if local.hour >= settings.discovery_hour:
            for owner_id, source_id in await discovery_service.enabled_sources(db):
                queued += await tasks_service.enqueue(
                    db,
                    owner_id,
                    TaskKind.DISCOVER,
                    f"discover:{source_id}:{day}",
                    {"source_id": str(source_id)},
                    max_attempts=settings.task_max_attempts,
                )
        if local.hour >= settings.digest_hour:
            for owner_id in await auth_service.user_ids(db):
                queued += await tasks_service.enqueue(
                    db,
                    owner_id,
                    TaskKind.DAILY_DIGEST,
                    f"daily_digest:{day}",
                    {},
                    max_attempts=settings.task_max_attempts,
                )
        if settings.apply_enabled and local.hour >= settings.apply_hour:
            for owner_id in await profile_service.owners_with_profile(db):
                queued += await tasks_service.enqueue(
                    db,
                    owner_id,
                    TaskKind.APPLY_QUEUE,
                    f"apply_queue:{day}",
                    {},
                    max_attempts=1,  # a profile or policy problem will not fix itself
                )
        if local.hour >= settings.backup_hour and settings.backup_key is not None:
            # One dump covers every user, so it is queued once, under the first user.
            owners = await auth_service.user_ids(db)
            if owners:
                queued += await tasks_service.enqueue(
                    db,
                    owners[0],
                    TaskKind.BACKUP,
                    f"backup:{day}",
                    {},
                    max_attempts=settings.task_max_attempts,
                )
        await db.commit()
    return queued


async def tick(
    sessionmaker: async_sessionmaker[AsyncSession],
    handlers: Mapping[TaskKind, Handler],
    settings: Settings,
    now: datetime | None = None,
) -> None:
    """One pass: schedule what is due, then run every due task."""
    now = now or datetime.now(UTC)
    await schedule_due(sessionmaker, settings, now)
    stuck_after = timedelta(minutes=settings.task_stuck_minutes)
    while await tasks_service.run_next(sessionmaker, handlers, now=now, stuck_after=stuck_after):
        pass


async def worker_loop(
    sessionmaker: async_sessionmaker[AsyncSession],
    fetcher: Fetcher,
    settings: Settings,
    stop: asyncio.Event,
    *,
    llm: LlmClient | None = None,
    search: SearchProvider | None = None,
) -> None:
    handlers = make_handlers(fetcher, settings, llm=llm, search=search)
    log.info("worker_started", poll_seconds=settings.worker_poll_seconds)
    while not stop.is_set():
        try:
            await tick(sessionmaker, handlers, settings)
        except Exception:
            log.exception("worker_tick_failed")  # never let one bad pass end the loop
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_seconds)
    log.info("worker_stopped")
