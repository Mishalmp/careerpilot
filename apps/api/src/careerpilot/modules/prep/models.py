import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
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
from sqlalchemy.orm import Mapped, mapped_column

from careerpilot.core.db import Base, str_enum
from careerpilot.modules.prep.enums import DayStatus, Priority, StudyKind, TopicStatus


class PrepTopic(Base):
    __tablename__ = "prep_topics"
    __table_args__ = (
        UniqueConstraint("owner_id", "key", name="uq_prep_topics_owner_id_key"),
        CheckConstraint("confidence BETWEEN 1 AND 5", name="confidence_range"),
        Index("ix_prep_topics_owner_id_area", "owner_id", "area"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # Static fields come from content/curriculum.yaml; the rest is your progress.
    key: Mapped[str] = mapped_column(Text)
    area: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    priority: Mapped[Priority] = mapped_column(str_enum(Priority, "topic_priority"))
    sort_order: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[int | None] = mapped_column(SmallInteger)
    status: Mapped[TopicStatus] = mapped_column(
        str_enum(TopicStatus, "topic_status"), default=TopicStatus.NOT_STARTED
    )
    last_reviewed_on: Mapped[date | None] = mapped_column(Date)
    next_review_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)


class PrepDay(Base):
    __tablename__ = "prep_days"
    __table_args__ = (UniqueConstraint("owner_id", "day", name="uq_prep_days_owner_id_day"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    day: Mapped[int] = mapped_column(Integer)
    phase: Mapped[str] = mapped_column(Text)
    focus: Mapped[str] = mapped_column(Text)
    core_topics: Mapped[str] = mapped_column(Text)
    practice: Mapped[str] = mapped_column(Text)
    speaking: Mapped[str] = mapped_column(Text)
    hours: Mapped[int] = mapped_column(Integer)
    deliverable: Mapped[str] = mapped_column(Text)
    status: Mapped[DayStatus] = mapped_column(
        str_enum(DayStatus, "day_status"), default=DayStatus.PLANNED
    )
    notes: Mapped[str | None] = mapped_column(Text)


class PrepPlan(Base):
    """One row per owner: when day 1 of the roadmap is."""

    __tablename__ = "prep_plans"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    start_date: Mapped[date] = mapped_column(Date)


class StudySession(Base):
    __tablename__ = "study_sessions"
    __table_args__ = (
        CheckConstraint("minutes BETWEEN 1 AND 720", name="minutes_range"),
        Index("ix_study_sessions_owner_id_studied_on", "owner_id", "studied_on"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("prep_topics.id", ondelete="CASCADE"), index=True
    )
    minutes: Mapped[int] = mapped_column(Integer)
    kind: Mapped[StudyKind] = mapped_column(str_enum(StudyKind, "study_kind"))
    studied_on: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
