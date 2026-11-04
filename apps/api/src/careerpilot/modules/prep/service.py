import uuid
from collections.abc import Sequence
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.errors import ProblemError
from careerpilot.modules.prep import repository
from careerpilot.modules.prep.curriculum import Curriculum
from careerpilot.modules.prep.enums import PlanPhase, TopicStatus
from careerpilot.modules.prep.models import PrepDay, PrepTopic, StudySession
from careerpilot.modules.prep.schemas import (
    DayOut,
    DayUpdate,
    SeedResult,
    SessionCreate,
    TodayPrep,
    TopicOut,
    TopicUpdate,
)
from careerpilot.modules.prep.spaced import next_review

DUE_LIMIT = 10


def _not_found(what: str) -> ProblemError:
    return ProblemError(404, "Not found", f"{what} not found.")


async def seed(db: AsyncSession, owner_id: uuid.UUID, curriculum: Curriculum) -> SeedResult:
    """Make the database match the curriculum file. Never touches your progress."""
    topics = await repository.topics_by_key(db, owner_id)
    days = await repository.days_by_number(db, owner_id)
    result = {"topics_added": 0, "topics_updated": 0, "days_added": 0, "days_updated": 0}

    order = 0
    for area in curriculum.areas:
        for definition in area.topics:
            fields = {
                "area": area.name,
                "title": definition.title,
                "priority": definition.priority,
                "sort_order": order,
            }
            order += 1
            existing = topics.get(definition.key)
            if existing is None:
                repository.add_topic(
                    db, owner_id, key=definition.key, status=TopicStatus.NOT_STARTED, **fields
                )
                result["topics_added"] += 1
            elif any(getattr(existing, name) != value for name, value in fields.items()):
                for name, value in fields.items():
                    setattr(existing, name, value)
                result["topics_updated"] += 1

    for definition in curriculum.days:
        fields = definition.model_dump(exclude={"day"})
        existing_day = days.get(definition.day)
        if existing_day is None:
            repository.add_day(db, owner_id, day=definition.day, **fields)
            result["days_added"] += 1
        elif any(getattr(existing_day, name) != value for name, value in fields.items()):
            for name, value in fields.items():
                setattr(existing_day, name, value)
            result["days_updated"] += 1

    await db.commit()
    return SeedResult(**result)


async def list_topics(
    db: AsyncSession,
    owner_id: uuid.UUID,
    *,
    area: str | None,
    status: TopicStatus | None,
    due_on: date | None,
) -> Sequence[PrepTopic]:
    return await repository.list_topics(db, owner_id, area=area, status=status, due_on=due_on)


async def update_topic(
    db: AsyncSession, owner_id: uuid.UUID, topic_id: uuid.UUID, data: TopicUpdate, *, today: date
) -> PrepTopic:
    topic = await repository.get_topic(db, owner_id, topic_id)
    if topic is None:
        raise _not_found("Topic")
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(topic, field, value)
    if "confidence" in changes:
        # Rating a topic is a review: it schedules the next one (or clears it if unrated).
        topic.last_reviewed_on = today if topic.confidence is not None else topic.last_reviewed_on
        topic.next_review_on = (
            next_review(topic.confidence, today) if topic.confidence is not None else None
        )
    await db.commit()
    return topic


async def log_session(
    db: AsyncSession,
    owner_id: uuid.UUID,
    topic_id: uuid.UUID,
    data: SessionCreate,
    *,
    today: date,
) -> StudySession:
    topic = await repository.get_topic(db, owner_id, topic_id)
    if topic is None:
        raise _not_found("Topic")
    studied_on = data.studied_on or today
    if studied_on > today:
        raise ProblemError(422, "Invalid date", "A study session cannot be in the future.")
    session = repository.add_session(
        db,
        owner_id,
        topic_id=topic_id,
        minutes=data.minutes,
        kind=data.kind,
        notes=data.notes,
        studied_on=studied_on,
    )
    if topic.last_reviewed_on is None or studied_on > topic.last_reviewed_on:
        topic.last_reviewed_on = studied_on
    if topic.confidence is not None:
        topic.next_review_on = next_review(topic.confidence, topic.last_reviewed_on)
    if topic.status == TopicStatus.NOT_STARTED:
        topic.status = TopicStatus.LEARNING
    await db.commit()
    await db.refresh(session)
    return session


def _day_out(day: PrepDay, start: date | None) -> DayOut:
    out = DayOut.model_validate(day)
    out.scheduled_on = start + timedelta(days=day.day - 1) if start else None
    return out


async def get_start_date(db: AsyncSession, owner_id: uuid.UUID) -> date | None:
    return await repository.get_plan_start(db, owner_id)


async def set_start_date(db: AsyncSession, owner_id: uuid.UUID, start: date) -> None:
    await repository.set_plan_start(db, owner_id, start)
    await db.commit()


async def list_days(db: AsyncSession, owner_id: uuid.UUID) -> list[DayOut]:
    start = await repository.get_plan_start(db, owner_id)
    return [_day_out(day, start) for day in await repository.list_days(db, owner_id)]


async def update_day(db: AsyncSession, owner_id: uuid.UUID, number: int, data: DayUpdate) -> DayOut:
    day = await repository.get_day(db, owner_id, number)
    if day is None:
        raise _not_found("Day")
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "status" and value is None:
            continue
        setattr(day, field, value)
    await db.commit()
    return _day_out(day, await repository.get_plan_start(db, owner_id))


async def today_view(db: AsyncSession, owner_id: uuid.UUID, today: date) -> TodayPrep:
    start = await repository.get_plan_start(db, owner_id)
    days = await repository.list_days(db, owner_id)
    total = len(days)
    due = [
        TopicOut.model_validate(t)
        for t in await repository.due_topics(db, owner_id, today, DUE_LIMIT)
    ]
    minutes = await repository.minutes_studied_on(db, owner_id, today)

    phase, number, day = PlanPhase.NOT_CONFIGURED, None, None
    if start is not None:
        number = (today - start).days + 1
        if number < 1:
            phase, number = PlanPhase.UPCOMING, None
        elif number > total:
            phase, number = PlanPhase.FINISHED, None
        else:
            phase = PlanPhase.ACTIVE
            day = _day_out(days[number - 1], start)
    return TodayPrep(
        phase=phase,
        start_date=start,
        day_number=number,
        total_days=total,
        day=day,
        due_reviews=due,
        minutes_today=minutes,
    )
