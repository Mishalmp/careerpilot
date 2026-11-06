import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from careerpilot.core.db import Base, str_enum
from careerpilot.modules.learn.enums import (
    GradedBy,
    LearnTopicStatus,
    QuestionOrigin,
    QuestionStatus,
    QuestionType,
    Rating,
    TopicOrigin,
)


class LearnTopic(Base):
    """Something to learn, such as "database transactions". Nothing is predefined: the owner adds
    them, approves research results, or imports the old curriculum once."""

    __tablename__ = "learn_topics"
    __table_args__ = (
        UniqueConstraint("owner_id", "title", name="uq_learn_topics_owner_title"),
        CheckConstraint("priority BETWEEN 1 AND 3", name="priority_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    area: Mapped[str | None] = mapped_column(Text)  # loose grouping such as "Databases"
    priority: Mapped[int] = mapped_column(SmallInteger, default=2)  # 1 high, 2 medium, 3 low
    status: Mapped[LearnTopicStatus] = mapped_column(
        str_enum(LearnTopicStatus, "learn_topic_status"), default=LearnTopicStatus.NOT_STARTED
    )
    origin: Mapped[TopicOrigin] = mapped_column(
        str_enum(TopicOrigin, "learn_topic_origin"), default=TopicOrigin.MANUAL
    )
    notes: Mapped[str | None] = mapped_column(Text)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LearnQuestion(Base):
    __tablename__ = "learn_questions"
    __table_args__ = (
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="difficulty_range"),
        # Only practical questions point at a practice problem, and they must.
        CheckConstraint(
            "(type = 'practical') = (practice_slug IS NOT NULL)", name="practical_has_slug"
        ),
        Index("ix_learn_questions_owner_topic", "owner_id", "topic_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learn_topics.id", ondelete="CASCADE"))
    type: Mapped[QuestionType] = mapped_column(str_enum(QuestionType, "learn_question_type"))
    stem: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)  # shown after answering
    difficulty: Mapped[int] = mapped_column(SmallInteger, default=3)
    status: Mapped[QuestionStatus] = mapped_column(
        str_enum(QuestionStatus, "learn_question_status"), default=QuestionStatus.VERIFIED
    )
    origin: Mapped[QuestionOrigin] = mapped_column(
        str_enum(QuestionOrigin, "learn_question_origin"), default=QuestionOrigin.MANUAL
    )
    rubric: Mapped[list[str] | None] = mapped_column(JSONB)  # criteria for written answers
    practice_slug: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    prompt_version: Mapped[str | None] = mapped_column(Text)  # which prompt made it, if a model did
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    options: Mapped[list["LearnOption"]] = relationship(
        order_by="LearnOption.position", lazy="selectin", cascade="all, delete-orphan"
    )
    sources: Mapped[list["LearnSource"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan"
    )


class LearnOption(Base):
    __tablename__ = "learn_options"
    __table_args__ = (
        UniqueConstraint("question_id", "position", name="uq_learn_options_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learn_questions.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(SmallInteger)
    text: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    rationale: Mapped[str | None] = mapped_column(Text)


class LearnSource(Base):
    """Where a question came from: a link, the date it was read, and a short quote we checked."""

    __tablename__ = "learn_sources"
    __table_args__ = (CheckConstraint("char_length(quote) <= 300", name="quote_short"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learn_questions.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    quote: Mapped[str] = mapped_column(Text)
    fetched_on: Mapped[date | None] = mapped_column(Date)
    reliability: Mapped[int | None] = mapped_column(SmallInteger)  # 0 to 100, from rules


class LearnAttempt(Base):
    """One answer to one question. The token makes a repeated submit harmless."""

    __tablename__ = "learn_attempts"
    __table_args__ = (
        UniqueConstraint("owner_id", "token", name="uq_learn_attempts_owner_token"),
        CheckConstraint("score BETWEEN 0 AND 1", name="score_range"),
        CheckConstraint("confidence BETWEEN 1 AND 3", name="confidence_range"),
        Index("ix_learn_attempts_owner_question", "owner_id", "question_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learn_questions.id", ondelete="CASCADE")
    )
    token: Mapped[uuid.UUID] = mapped_column(Uuid)
    answer: Mapped[dict[str, object]] = mapped_column(JSONB)
    score: Mapped[float] = mapped_column(Float)
    correct: Mapped[bool] = mapped_column(Boolean)
    confidence: Mapped[int] = mapped_column(SmallInteger)
    seconds: Mapped[float | None] = mapped_column(Float)
    graded_by: Mapped[GradedBy] = mapped_column(str_enum(GradedBy, "learn_graded_by"))
    rating: Mapped[Rating] = mapped_column(str_enum(Rating, "learn_rating"))
    feedback: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LearnReviewCard(Base):
    """The spaced-repetition schedule of one question (FSRS state)."""

    __tablename__ = "learn_review_cards"
    __table_args__ = (
        UniqueConstraint("owner_id", "question_id", name="uq_learn_cards_owner_question"),
        Index("ix_learn_cards_owner_due", "owner_id", "due_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learn_questions.id", ondelete="CASCADE")
    )
    state: Mapped[int] = mapped_column(SmallInteger)
    step: Mapped[int | None] = mapped_column(Integer)
    stability: Mapped[float | None] = mapped_column(Float)
    difficulty: Mapped[float | None] = mapped_column(Float)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)


class LearnCheckpoint(Base):
    """A timed exam built from questions you have already studied. Items are snapshots, so editing
    a question later cannot change an exam that is running or finished."""

    __tablename__ = "learn_checkpoints"
    __table_args__ = (
        CheckConstraint("pass_mark BETWEEN 0.5 AND 1", name="pass_mark_range"),
        CheckConstraint("status IN ('in_progress', 'submitted')", name="status_values"),
        Index("ix_learn_checkpoints_owner_started", "owner_id", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(Text, default="in_progress")
    size: Mapped[int] = mapped_column(Integer)
    minutes: Mapped[int] = mapped_column(Integer)
    pass_mark: Mapped[float] = mapped_column(Float)
    seed: Mapped[int] = mapped_column(Integer)
    topic_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)  # empty = all topics
    notes: Mapped[list[str]] = mapped_column(
        JSONB, default=list
    )  # e.g. "fewer questions than asked"
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    score: Mapped[float | None] = mapped_column(Float)
    passed: Mapped[bool | None] = mapped_column(Boolean)
    per_topic: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    items: Mapped[list["LearnCheckpointItem"]] = relationship(
        order_by="LearnCheckpointItem.position", lazy="selectin", cascade="all, delete-orphan"
    )


class LearnCheckpointItem(Base):
    __tablename__ = "learn_checkpoint_items"
    __table_args__ = (
        UniqueConstraint("checkpoint_id", "position", name="uq_learn_checkpoint_items_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    checkpoint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learn_checkpoints.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(SmallInteger)
    # Not a foreign key on purpose: the exam must survive the question being deleted.
    question_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    topic_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)  # question text, options with answers
    selected: Mapped[list[int] | None] = mapped_column(JSONB)
    flagged: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    score: Mapped[float | None] = mapped_column(Float)
    correct: Mapped[bool | None] = mapped_column(Boolean)
