import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from careerpilot.core.db import Base, str_enum
from careerpilot.modules.research.enums import FindingKind, FindingStatus, RunStatus


class ResearchRun(Base):
    """One attempt to find interview topics and questions for a job."""

    __tablename__ = "research_runs"
    __table_args__ = (Index("ix_research_runs_owner_job", "owner_id", "job_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    status: Mapped[RunStatus] = mapped_column(
        str_enum(RunStatus, "research_run_status"), default=RunStatus.QUEUED
    )
    queries: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # What the run was allowed to spend, and what it did spend (searches, pages, tokens).
    budgets: Mapped[dict[str, Any]] = mapped_column(JSONB)
    usage: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    message: Mapped[str | None] = mapped_column(Text)  # why it ended early, in plain words
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ResearchFinding(Base):
    """One thing a run found. It waits in the inbox until the owner approves or rejects it."""

    __tablename__ = "research_findings"
    __table_args__ = (
        UniqueConstraint("run_id", "dedupe_key", name="uq_research_findings_run_dedupe"),
        CheckConstraint("relevance BETWEEN 0 AND 100", name="relevance_range"),
        CheckConstraint("char_length(quote) <= 300", name="quote_short"),
        Index("ix_research_findings_owner_status", "owner_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[FindingKind] = mapped_column(str_enum(FindingKind, "research_finding_kind"))
    topic: Mapped[str] = mapped_column(Text)  # the subject label it belongs to
    text: Mapped[str] = mapped_column(Text)  # the question, or why the topic matters
    quote: Mapped[str] = mapped_column(Text)  # copied from the page and checked against it
    source_url: Mapped[str] = mapped_column(Text)
    source_title: Mapped[str | None] = mapped_column(Text)
    relevance: Mapped[int] = mapped_column(
        SmallInteger
    )  # rough 0-100 from word overlap, not a model
    dedupe_key: Mapped[str] = mapped_column(Text)
    # How many separate pages asked this (or covered this topic). Found again elsewhere, a finding
    # is not duplicated: it gains a mention and the extra source. More mentions rank it higher.
    mentions: Mapped[int] = mapped_column(Integer, default=1)
    more_sources: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    status: Mapped[FindingStatus] = mapped_column(
        str_enum(FindingStatus, "research_finding_status"), default=FindingStatus.PENDING
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
