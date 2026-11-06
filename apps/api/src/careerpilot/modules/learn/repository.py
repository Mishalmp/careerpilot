"""All SQL for the learning module. Every query is scoped by owner_id."""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.learn.enums import QuestionStatus, QuestionType
from careerpilot.modules.learn.models import (
    LearnAttempt,
    LearnCheckpoint,
    LearnCheckpointItem,
    LearnOption,
    LearnQuestion,
    LearnReviewCard,
    LearnSource,
    LearnTopic,
)

MAX_LIMIT = 100


def _like(text: str) -> str:
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


# --- topics ---


async def list_topics(
    db: AsyncSession, owner_id: uuid.UUID, *, include_archived: bool
) -> Sequence[LearnTopic]:
    statement = select(LearnTopic).where(LearnTopic.owner_id == owner_id)
    if not include_archived:
        statement = statement.where(LearnTopic.archived.is_(False))
    rows = await db.scalars(statement.order_by(LearnTopic.priority, LearnTopic.title))
    return rows.all()


async def get_topic(
    db: AsyncSession, owner_id: uuid.UUID, topic_id: uuid.UUID
) -> LearnTopic | None:
    return await db.scalar(
        select(LearnTopic).where(LearnTopic.owner_id == owner_id, LearnTopic.id == topic_id)
    )


async def find_topic_by_title(
    db: AsyncSession, owner_id: uuid.UUID, title: str
) -> LearnTopic | None:
    return await db.scalar(
        select(LearnTopic).where(
            LearnTopic.owner_id == owner_id, func.lower(LearnTopic.title) == title.lower()
        )
    )


def add_topic(db: AsyncSession, owner_id: uuid.UUID, **fields: Any) -> LearnTopic:
    topic = LearnTopic(owner_id=owner_id, **fields)
    db.add(topic)
    return topic


async def question_counts(db: AsyncSession, owner_id: uuid.UUID) -> dict[uuid.UUID, int]:
    rows = await db.execute(
        select(LearnQuestion.topic_id, func.count())
        .where(LearnQuestion.owner_id == owner_id, LearnQuestion.status != QuestionStatus.ARCHIVED)
        .group_by(LearnQuestion.topic_id)
    )
    return {topic_id: count for topic_id, count in rows.all()}


async def delete_topic(db: AsyncSession, owner_id: uuid.UUID, topic_id: uuid.UUID) -> bool:
    result = await db.execute(
        delete(LearnTopic)
        .where(LearnTopic.owner_id == owner_id, LearnTopic.id == topic_id)
        .returning(LearnTopic.id)
    )
    return result.first() is not None


# --- questions ---


async def get_question(
    db: AsyncSession, owner_id: uuid.UUID, question_id: uuid.UUID
) -> LearnQuestion | None:
    return await db.scalar(
        select(LearnQuestion).where(
            LearnQuestion.owner_id == owner_id, LearnQuestion.id == question_id
        )
    )


def _filtered(
    owner_id: uuid.UUID,
    *,
    topic_id: uuid.UUID | None,
    status: QuestionStatus | None,
    kind: QuestionType | None,
    query: str | None,
) -> Select[LearnQuestion]:
    statement = select(LearnQuestion).where(LearnQuestion.owner_id == owner_id)
    if topic_id:
        statement = statement.where(LearnQuestion.topic_id == topic_id)
    if status:
        statement = statement.where(LearnQuestion.status == status)
    else:
        statement = statement.where(LearnQuestion.status != QuestionStatus.ARCHIVED)
    if kind:
        statement = statement.where(LearnQuestion.type == kind)
    if query:
        statement = statement.where(or_(LearnQuestion.stem.ilike(_like(query), escape="\\")))
    return statement


async def list_questions(
    db: AsyncSession,
    owner_id: uuid.UUID,
    *,
    topic_id: uuid.UUID | None,
    status: QuestionStatus | None,
    kind: QuestionType | None,
    query: str | None,
    limit: int,
    offset: int,
) -> tuple[Sequence[LearnQuestion], int]:
    base = _filtered(owner_id, topic_id=topic_id, status=status, kind=kind, query=query)
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = await db.scalars(
        base.order_by(LearnQuestion.created_at.desc(), LearnQuestion.id)
        .limit(min(limit, MAX_LIMIT))
        .offset(offset)
    )
    return rows.all(), total or 0


def add_question(db: AsyncSession, owner_id: uuid.UUID, **fields: Any) -> LearnQuestion:
    question = LearnQuestion(owner_id=owner_id, **fields)
    db.add(question)
    return question


def option(owner_id: uuid.UUID, **fields: Any) -> LearnOption:
    return LearnOption(owner_id=owner_id, **fields)


def source(owner_id: uuid.UUID, **fields: Any) -> LearnSource:
    return LearnSource(owner_id=owner_id, **fields)


async def delete_question(db: AsyncSession, owner_id: uuid.UUID, question_id: uuid.UUID) -> bool:
    result = await db.execute(
        delete(LearnQuestion)
        .where(LearnQuestion.owner_id == owner_id, LearnQuestion.id == question_id)
        .returning(LearnQuestion.id)
    )
    return result.first() is not None


# --- cards and attempts ---


async def get_card(
    db: AsyncSession, owner_id: uuid.UUID, question_id: uuid.UUID
) -> LearnReviewCard | None:
    return await db.scalar(
        select(LearnReviewCard).where(
            LearnReviewCard.owner_id == owner_id, LearnReviewCard.question_id == question_id
        )
    )


def add_card(db: AsyncSession, owner_id: uuid.UUID, **fields: Any) -> LearnReviewCard:
    card = LearnReviewCard(owner_id=owner_id, **fields)
    db.add(card)
    return card


async def due_cards(
    db: AsyncSession, owner_id: uuid.UUID, now: datetime, limit: int
) -> Sequence[tuple[LearnReviewCard, LearnQuestion]]:
    """Cards that were reviewed before and are due now (new questions are listed separately)."""
    rows = await db.execute(
        select(LearnReviewCard, LearnQuestion)
        .join(LearnQuestion, LearnQuestion.id == LearnReviewCard.question_id)
        .where(
            LearnReviewCard.owner_id == owner_id,
            LearnReviewCard.reps > 0,
            LearnReviewCard.due_at <= now,
            LearnQuestion.status != QuestionStatus.ARCHIVED,
        )
        .order_by(LearnReviewCard.due_at)
        .limit(limit)
    )
    return [(card, question) for card, question in rows.all()]


async def count_due(db: AsyncSession, owner_id: uuid.UUID, now: datetime) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(LearnReviewCard)
            .join(LearnQuestion, LearnQuestion.id == LearnReviewCard.question_id)
            .where(
                LearnReviewCard.owner_id == owner_id,
                LearnReviewCard.reps > 0,
                LearnReviewCard.due_at <= now,
                LearnQuestion.status != QuestionStatus.ARCHIVED,
            )
        )
    ) or 0


async def new_cards(
    db: AsyncSession, owner_id: uuid.UUID, limit: int
) -> Sequence[tuple[LearnReviewCard, LearnQuestion]]:
    """Questions never answered, most important topics first."""
    rows = await db.execute(
        select(LearnReviewCard, LearnQuestion)
        .join(LearnQuestion, LearnQuestion.id == LearnReviewCard.question_id)
        .join(LearnTopic, LearnTopic.id == LearnQuestion.topic_id)
        .where(
            LearnReviewCard.owner_id == owner_id,
            LearnReviewCard.reps == 0,
            LearnQuestion.status != QuestionStatus.ARCHIVED,
            LearnTopic.archived.is_(False),
        )
        .order_by(LearnTopic.priority, LearnQuestion.created_at, LearnQuestion.id)
        .limit(limit)
    )
    return [(card, question) for card, question in rows.all()]


async def count_new(db: AsyncSession, owner_id: uuid.UUID) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(LearnReviewCard)
            .join(LearnQuestion, LearnQuestion.id == LearnReviewCard.question_id)
            .where(
                LearnReviewCard.owner_id == owner_id,
                LearnReviewCard.reps == 0,
                LearnQuestion.status != QuestionStatus.ARCHIVED,
            )
        )
    ) or 0


async def started_today(db: AsyncSession, owner_id: uuid.UUID, since: datetime) -> int:
    """Cards whose first review was today: counts against the daily new-card limit."""
    return (
        await db.scalar(
            select(func.count())
            .select_from(LearnReviewCard)
            .where(LearnReviewCard.owner_id == owner_id, LearnReviewCard.first_review_at >= since)
        )
    ) or 0


async def get_attempt_by_token(
    db: AsyncSession, owner_id: uuid.UUID, token: uuid.UUID
) -> LearnAttempt | None:
    return await db.scalar(
        select(LearnAttempt).where(LearnAttempt.owner_id == owner_id, LearnAttempt.token == token)
    )


def add_attempt(db: AsyncSession, owner_id: uuid.UUID, **fields: Any) -> LearnAttempt:
    attempt = LearnAttempt(owner_id=owner_id, **fields)
    db.add(attempt)
    return attempt


async def recent_seconds(
    db: AsyncSession, owner_id: uuid.UUID, kind: QuestionType, limit: int = 50
) -> list[float]:
    rows = await db.scalars(
        select(LearnAttempt.seconds)
        .join(LearnQuestion, LearnQuestion.id == LearnAttempt.question_id)
        .where(
            LearnAttempt.owner_id == owner_id,
            LearnQuestion.type == kind,
            LearnAttempt.seconds.is_not(None),
        )
        .order_by(LearnAttempt.created_at.desc())
        .limit(limit)
    )
    return [s for s in rows.all() if s is not None]


async def attempts_since(db: AsyncSession, owner_id: uuid.UUID, since: datetime) -> list[datetime]:
    rows = await db.scalars(
        select(LearnAttempt.created_at).where(
            LearnAttempt.owner_id == owner_id, LearnAttempt.created_at >= since
        )
    )
    return list(rows.all())


async def cards_for_mastery(
    db: AsyncSession, owner_id: uuid.UUID
) -> Sequence[tuple[uuid.UUID, LearnReviewCard]]:
    """(topic id, card) for every reviewed card of every live question."""
    rows = await db.execute(
        select(LearnQuestion.topic_id, LearnReviewCard)
        .join(LearnReviewCard, LearnReviewCard.question_id == LearnQuestion.id)
        .where(
            LearnReviewCard.owner_id == owner_id,
            LearnReviewCard.reps > 0,
            LearnQuestion.status != QuestionStatus.ARCHIVED,
        )
    )
    return [(topic_id, card) for topic_id, card in rows.all()]


# --- checkpoints ---


async def studied_questions(
    db: AsyncSession, owner_id: uuid.UUID, topic_ids: Sequence[uuid.UUID]
) -> Sequence[tuple[LearnQuestion, LearnTopic]]:
    """Verified multiple-choice questions you have answered at least once (so "studied")."""
    statement = (
        select(LearnQuestion, LearnTopic)
        .join(LearnTopic, LearnTopic.id == LearnQuestion.topic_id)
        .join(LearnReviewCard, LearnReviewCard.question_id == LearnQuestion.id)
        .where(
            LearnQuestion.owner_id == owner_id,
            LearnQuestion.status == QuestionStatus.VERIFIED,
            LearnQuestion.type.in_([QuestionType.MCQ_SINGLE, QuestionType.MCQ_MULTI]),
            LearnReviewCard.reps > 0,
            LearnTopic.archived.is_(False),
        )
    )
    if topic_ids:
        statement = statement.where(LearnQuestion.topic_id.in_(topic_ids))
    rows = await db.execute(statement)
    return [(question, topic) for question, topic in rows.all()]


async def last_in_checkpoint(db: AsyncSession, owner_id: uuid.UUID) -> dict[uuid.UUID, datetime]:
    """When each question last appeared in a checkpoint."""
    rows = await db.execute(
        select(LearnCheckpointItem.question_id, func.max(LearnCheckpoint.started_at))
        .join(LearnCheckpoint, LearnCheckpoint.id == LearnCheckpointItem.checkpoint_id)
        .where(LearnCheckpointItem.owner_id == owner_id)
        .group_by(LearnCheckpointItem.question_id)
    )
    return {question_id: when for question_id, when in rows.all()}


def add_checkpoint(db: AsyncSession, owner_id: uuid.UUID, **fields: Any) -> LearnCheckpoint:
    checkpoint = LearnCheckpoint(owner_id=owner_id, **fields)
    db.add(checkpoint)
    return checkpoint


async def get_checkpoint(
    db: AsyncSession, owner_id: uuid.UUID, checkpoint_id: uuid.UUID
) -> LearnCheckpoint | None:
    return await db.scalar(
        select(LearnCheckpoint).where(
            LearnCheckpoint.owner_id == owner_id, LearnCheckpoint.id == checkpoint_id
        )
    )


async def active_checkpoint(db: AsyncSession, owner_id: uuid.UUID) -> LearnCheckpoint | None:
    return await db.scalar(
        select(LearnCheckpoint)
        .where(LearnCheckpoint.owner_id == owner_id, LearnCheckpoint.status == "in_progress")
        .order_by(LearnCheckpoint.started_at.desc())
    )


async def list_checkpoints(
    db: AsyncSession, owner_id: uuid.UUID, limit: int
) -> Sequence[LearnCheckpoint]:
    rows = await db.scalars(
        select(LearnCheckpoint)
        .where(LearnCheckpoint.owner_id == owner_id)
        .order_by(LearnCheckpoint.started_at.desc())
        .limit(min(limit, MAX_LIMIT))
    )
    return rows.all()
