"""All SQL for research runs and findings. Every query is scoped by owner_id."""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.research.enums import FindingStatus, RunStatus
from careerpilot.modules.research.models import ResearchFinding, ResearchRun

MAX_LIMIT = 100


def add_run(db: AsyncSession, owner_id: uuid.UUID, **fields: Any) -> ResearchRun:
    run = ResearchRun(owner_id=owner_id, **fields)
    db.add(run)
    return run


async def get_run(db: AsyncSession, owner_id: uuid.UUID, run_id: uuid.UUID) -> ResearchRun | None:
    return await db.scalar(
        select(ResearchRun).where(ResearchRun.owner_id == owner_id, ResearchRun.id == run_id)
    )


async def active_run_for_job(
    db: AsyncSession, owner_id: uuid.UUID, job_id: uuid.UUID, since: datetime
) -> ResearchRun | None:
    """A run for this job that is still waiting or working (and not stuck from long ago)."""
    return await db.scalar(
        select(ResearchRun)
        .where(
            ResearchRun.owner_id == owner_id,
            ResearchRun.job_id == job_id,
            ResearchRun.status.in_([RunStatus.QUEUED, RunStatus.RUNNING]),
            ResearchRun.created_at >= since,
        )
        .order_by(ResearchRun.created_at.desc())
    )


async def list_runs(
    db: AsyncSession, owner_id: uuid.UUID, job_id: uuid.UUID | None, limit: int
) -> Sequence[ResearchRun]:
    statement = select(ResearchRun).where(ResearchRun.owner_id == owner_id)
    if job_id:
        statement = statement.where(ResearchRun.job_id == job_id)
    rows = await db.scalars(
        statement.order_by(ResearchRun.created_at.desc()).limit(min(limit, MAX_LIMIT))
    )
    return rows.all()


async def pending_counts(db: AsyncSession, owner_id: uuid.UUID) -> dict[uuid.UUID, int]:
    rows = await db.execute(
        select(ResearchFinding.run_id, func.count())
        .where(
            ResearchFinding.owner_id == owner_id, ResearchFinding.status == FindingStatus.PENDING
        )
        .group_by(ResearchFinding.run_id)
    )
    return {run_id: count for run_id, count in rows.all()}


def add_finding(db: AsyncSession, owner_id: uuid.UUID, **fields: Any) -> ResearchFinding:
    finding = ResearchFinding(owner_id=owner_id, **fields)
    db.add(finding)
    return finding


async def existing_keys(db: AsyncSession, owner_id: uuid.UUID) -> set[str]:
    """Dedupe keys of everything ever found for this owner (approved, rejected or waiting)."""
    rows = await db.scalars(
        select(ResearchFinding.dedupe_key).where(ResearchFinding.owner_id == owner_id)
    )
    return set(rows.all())


async def get_finding(
    db: AsyncSession, owner_id: uuid.UUID, finding_id: uuid.UUID
) -> ResearchFinding | None:
    return await db.scalar(
        select(ResearchFinding).where(
            ResearchFinding.owner_id == owner_id, ResearchFinding.id == finding_id
        )
    )


async def list_findings(
    db: AsyncSession,
    owner_id: uuid.UUID,
    *,
    status: FindingStatus,
    run_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[Sequence[ResearchFinding], int]:
    base = select(ResearchFinding).where(
        ResearchFinding.owner_id == owner_id, ResearchFinding.status == status
    )
    if run_id:
        base = base.where(ResearchFinding.run_id == run_id)
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = await db.scalars(
        base.order_by(  # asked on more pages first, then closer to the role
            ResearchFinding.mentions.desc(),
            ResearchFinding.relevance.desc(),
            ResearchFinding.created_at,
            ResearchFinding.id,
        )
        .limit(min(limit, MAX_LIMIT))
        .offset(offset)
    )
    return rows.all(), total or 0


async def add_mention(
    db: AsyncSession,
    owner_id: uuid.UUID,
    dedupe_key: str,
    *,
    url: str,
    title: str | None,
) -> bool:
    """The same question or topic was found on another page: count it, and keep that page as a
    source. A page that is already a source of it is not counted twice. True when it counted."""
    finding = await db.scalar(
        select(ResearchFinding)
        .where(ResearchFinding.owner_id == owner_id, ResearchFinding.dedupe_key == dedupe_key)
        .order_by(ResearchFinding.created_at)
        .limit(1)
    )
    if finding is None or finding.source_url == url:
        return False
    if any(source.get("url") == url for source in finding.more_sources):
        return False
    finding.mentions += 1
    finding.more_sources = [*finding.more_sources, {"url": url, "title": title}]
    return True
