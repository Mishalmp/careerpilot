"""Collects the live status of the system for the explorer's status tab."""

import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.config import Settings
from careerpilot.core.llm import spend, tokens_used_today
from careerpilot.modules.system import repository
from careerpilot.modules.system.schemas import (
    AiCallOut,
    AiCalls,
    AiStatus,
    BackupStatus,
    DatabaseStatus,
    SearchStatus,
    SystemStatus,
    TaskStatusCounts,
)
from careerpilot.modules.tasks import service as tasks_service


def _last_backup(directory: Path) -> datetime | None:
    if not directory.is_dir():
        return None
    times = [p.stat().st_mtime for p in directory.glob("*.cpbk")]
    return datetime.fromtimestamp(max(times), UTC) if times else None


async def build(
    db: AsyncSession,
    owner_id: uuid.UUID,
    settings: Settings,
    *,
    search_configured: bool,
    now: datetime | None = None,
) -> SystemStatus:
    now = now or datetime.now(UTC)
    revision = await repository.current_revision(db)
    listing = await tasks_service.list_tasks(db, owner_id, None)
    finished = [t.finished_at for t in listing.items if t.finished_at is not None]
    last_backup = _last_backup(settings.backup_dir)
    money = await spend(db, owner_id, settings, now)
    return SystemStatus(
        checked_at=now,
        database=DatabaseStatus(ok=revision is not None, revision=revision),
        tasks=TaskStatusCounts(
            queued=listing.counts.queued,
            running=listing.counts.running,
            failed=listing.counts.failed,
            succeeded=listing.counts.succeeded,
        ),
        last_task_finished_at=max(finished) if finished else None,
        ai=AiStatus(
            configured=settings.anthropic_api_key is not None,
            tokens_today=await tokens_used_today(db, owner_id),
            daily_cap=settings.llm_daily_token_cap,
            spent_today_usd=money.today_usd,
            spent_month_usd=money.month_usd,
            daily_budget_usd=money.daily_budget_usd,
            monthly_budget_usd=money.monthly_budget_usd,
        ),
        search=SearchStatus(provider=settings.search_provider, configured=search_configured),
        backups=BackupStatus(
            key_set=settings.backup_key is not None,
            last_backup_at=last_backup,
            age_hours=round((now - last_backup).total_seconds() / 3600, 1) if last_backup else None,
        ),
    )


async def ai_calls(
    db: AsyncSession, owner_id: uuid.UUID, settings: Settings, *, only_problems: bool, limit: int
) -> AiCalls:
    rows = await repository.recent_ai_calls(db, owner_id, only_problems=only_problems, limit=limit)
    money = await spend(db, owner_id, settings)
    return AiCalls(
        items=[AiCallOut.model_validate(r) for r in rows],
        tokens_today=await tokens_used_today(db, owner_id),
        daily_cap=settings.llm_daily_token_cap,
        spent_today_usd=money.today_usd,
        spent_month_usd=money.month_usd,
        daily_budget_usd=money.daily_budget_usd,
        monthly_budget_usd=money.monthly_budget_usd,
    )
