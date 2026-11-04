import uuid
from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.prep.enums import TopicStatus
from careerpilot.modules.prep.models import PrepDay, PrepPlan, PrepTopic, StudySession


async def topics_by_key(db: AsyncSession, owner_id: uuid.UUID) -> dict[str, PrepTopic]:
    rows = await db.scalars(select(PrepTopic).where(PrepTopic.owner_id == owner_id))
    return {topic.key: topic for topic in rows}


async def days_by_number(db: AsyncSession, owner_id: uuid.UUID) -> dict[int, PrepDay]:
    rows = await db.scalars(select(PrepDay).where(PrepDay.owner_id == owner_id))
    return {day.day: day for day in rows}


def add_topic(db: AsyncSession, owner_id: uuid.UUID, **fields: Any) -> PrepTopic:
    topic = PrepTopic(owner_id=owner_id, **fields)
    db.add(topic)
    return topic


def add_day(db: AsyncSession, owner_id: uuid.UUID, **fields: Any) -> PrepDay:
    day = PrepDay(owner_id=owner_id, **fields)
    db.add(day)
    return day


async def list_topics(
    db: AsyncSession,
    owner_id: uuid.UUID,
    *,
    area: str | None,
    status: TopicStatus | None,
    due_on: date | None,
) -> Sequence[PrepTopic]:
    stmt = select(PrepTopic).where(PrepTopic.owner_id == owner_id)
    if area:
        stmt = stmt.where(PrepTopic.area == area)
    if status:
        stmt = stmt.where(PrepTopic.status == status)
    if due_on:
        stmt = stmt.where(PrepTopic.next_review_on <= due_on)
    return (await db.scalars(stmt.order_by(PrepTopic.sort_order))).all()


async def get_topic(db: AsyncSession, owner_id: uuid.UUID, topic_id: uuid.UUID) -> PrepTopic | None:
    return await db.scalar(
        select(PrepTopic).where(PrepTopic.id == topic_id, PrepTopic.owner_id == owner_id)
    )


async def list_days(db: AsyncSession, owner_id: uuid.UUID) -> Sequence[PrepDay]:
    return (
        await db.scalars(select(PrepDay).where(PrepDay.owner_id == owner_id).order_by(PrepDay.day))
    ).all()


async def get_day(db: AsyncSession, owner_id: uuid.UUID, number: int) -> PrepDay | None:
    return await db.scalar(
        select(PrepDay).where(PrepDay.owner_id == owner_id, PrepDay.day == number)
    )


async def get_plan_start(db: AsyncSession, owner_id: uuid.UUID) -> date | None:
    return await db.scalar(select(PrepPlan.start_date).where(PrepPlan.owner_id == owner_id))


async def set_plan_start(db: AsyncSession, owner_id: uuid.UUID, start: date) -> None:
    await db.execute(
        insert(PrepPlan)
        .values(owner_id=owner_id, start_date=start)
        .on_conflict_do_update(index_elements=["owner_id"], set_={"start_date": start})
    )


def add_session(db: AsyncSession, owner_id: uuid.UUID, **fields: Any) -> StudySession:
    session = StudySession(owner_id=owner_id, **fields)
    db.add(session)
    return session


async def minutes_studied_on(db: AsyncSession, owner_id: uuid.UUID, on: date) -> int:
    total = await db.scalar(
        select(func.coalesce(func.sum(StudySession.minutes), 0)).where(
            StudySession.owner_id == owner_id, StudySession.studied_on == on
        )
    )
    return int(total or 0)


async def due_topics(
    db: AsyncSession, owner_id: uuid.UUID, on_or_before: date, limit: int
) -> Sequence[PrepTopic]:
    return (
        await db.scalars(
            select(PrepTopic)
            .where(PrepTopic.owner_id == owner_id, PrepTopic.next_review_on <= on_or_before)
            .order_by(PrepTopic.next_review_on, PrepTopic.sort_order)
            .limit(limit)
        )
    ).all()
