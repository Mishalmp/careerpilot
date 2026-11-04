import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from careerpilot.core.clock import today_in
from careerpilot.core.deps import AppSettings, DbSession
from careerpilot.core.errors import ProblemError
from careerpilot.modules.auth.dependencies import Authenticated
from careerpilot.modules.prep import guides, service
from careerpilot.modules.prep.curriculum import load_curriculum
from careerpilot.modules.prep.enums import TopicStatus
from careerpilot.modules.prep.schemas import (
    DayOut,
    DayUpdate,
    GuideInfoOut,
    GuideOut,
    PlanOut,
    PlanUpdate,
    SeedResult,
    SessionCreate,
    SessionOut,
    TodayPrep,
    TopicOut,
    TopicUpdate,
)

router = APIRouter(prefix="/prep", tags=["prep"])


@router.post("/seed", operation_id="seed_prep")
async def seed_prep(session: Authenticated, db: DbSession, settings: AppSettings) -> SeedResult:
    """Load or refresh the curriculum from content/curriculum.yaml. Safe to repeat."""
    return await service.seed(db, session.user_id, load_curriculum(settings.content_dir))


@router.get("/plan", operation_id="get_plan")
async def get_plan(session: Authenticated, db: DbSession) -> PlanOut:
    return PlanOut(start_date=await service.get_start_date(db, session.user_id))


@router.put("/plan", operation_id="set_plan")
async def set_plan(body: PlanUpdate, session: Authenticated, db: DbSession) -> PlanOut:
    await service.set_start_date(db, session.user_id, body.start_date)
    return PlanOut(start_date=body.start_date)


@router.get("/today", operation_id="get_prep_today")
async def get_prep_today(session: Authenticated, db: DbSession, settings: AppSettings) -> TodayPrep:
    return await service.today_view(db, session.user_id, today_in(settings.timezone))


@router.get("/days", operation_id="list_days")
async def list_days(session: Authenticated, db: DbSession) -> list[DayOut]:
    return await service.list_days(db, session.user_id)


@router.patch("/days/{number}", operation_id="update_day")
async def update_day(number: int, body: DayUpdate, session: Authenticated, db: DbSession) -> DayOut:
    return await service.update_day(db, session.user_id, number, body)


@router.get("/topics", operation_id="list_topics")
async def list_topics(
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
    area: Annotated[str | None, Query(max_length=100)] = None,
    topic_status: Annotated[TopicStatus | None, Query(alias="status")] = None,
    due: bool = False,
) -> list[TopicOut]:
    topics = await service.list_topics(
        db,
        session.user_id,
        area=area,
        status=topic_status,
        due_on=today_in(settings.timezone) if due else None,
    )
    return [TopicOut.model_validate(topic) for topic in topics]


@router.patch("/topics/{topic_id}", operation_id="update_topic")
async def update_topic(
    topic_id: uuid.UUID,
    body: TopicUpdate,
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
) -> TopicOut:
    topic = await service.update_topic(
        db, session.user_id, topic_id, body, today=today_in(settings.timezone)
    )
    return TopicOut.model_validate(topic)


@router.post(
    "/topics/{topic_id}/sessions",
    operation_id="log_session",
    status_code=status.HTTP_201_CREATED,
)
async def log_session(
    topic_id: uuid.UUID,
    body: SessionCreate,
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
) -> SessionOut:
    study = await service.log_session(
        db, session.user_id, topic_id, body, today=today_in(settings.timezone)
    )
    return SessionOut.model_validate(study)


@router.get("/guides", operation_id="list_guides")
async def list_guides(_: Authenticated, settings: AppSettings) -> list[GuideInfoOut]:
    return [
        GuideInfoOut(name=g.name, title=g.title, private=g.private)
        for g in guides.list_guides(settings.content_dir)
    ]


@router.get("/guides/{name}", operation_id="get_guide")
async def get_guide(name: str, _: Authenticated, settings: AppSettings) -> GuideOut:
    guide = guides.read_guide(settings.content_dir, name)
    if guide is None:
        raise ProblemError(404, "Not found", "Guide not found.")
    return GuideOut(
        name=guide.info.name,
        title=guide.info.title,
        private=guide.info.private,
        markdown=guide.markdown,
    )
