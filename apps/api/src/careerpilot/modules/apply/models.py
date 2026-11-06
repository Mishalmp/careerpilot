import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from careerpilot.core.db import Base, str_enum
from careerpilot.modules.apply.enums import ApplyStatus


class ApplyItem(Base):
    """One job put on the daily list, with what was found about it. A job is listed once ever."""

    __tablename__ = "apply_items"
    __table_args__ = (
        UniqueConstraint("owner_id", "job_id", name="uq_apply_items_owner_job"),
        CheckConstraint("match_score BETWEEN 0 AND 100", name="match_score_range"),
        Index("ix_apply_items_owner_status_queued", "owner_id", "status", "queued_on"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    queued_on: Mapped[date] = mapped_column(Date)
    status: Mapped[ApplyStatus] = mapped_column(
        str_enum(ApplyStatus, "apply_status"), default=ApplyStatus.READY
    )
    match_score: Mapped[int] = mapped_column(SmallInteger)
    reasons: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # What was found, each part with the level it came from and the words it was read from.
    pay: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    interview: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    also_listed: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    company_check: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    notes: Mapped[list[str]] = mapped_column(JSONB, default=list)  # what could not be looked up
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
