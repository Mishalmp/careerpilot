import uuid

from fastapi import APIRouter, status

from careerpilot.core.clock import today_in
from careerpilot.core.deps import AppFetcher, AppSearch, AppSettings, DbSession
from careerpilot.modules.apply import service
from careerpilot.modules.apply.schemas import ApplyItemOut, ApplyQueueOut, BuildOut, DecisionIn
from careerpilot.modules.auth.dependencies import Authenticated

router = APIRouter(prefix="/apply", tags=["apply"])


@router.get("/queue", operation_id="get_apply_queue")
async def get_queue(session: Authenticated, db: DbSession, settings: AppSettings) -> ApplyQueueOut:
    """Today's list and the last week's, with the policy that chose it."""
    return await service.get_queue(db, session.user_id, settings, today_in(settings.timezone))


@router.post("/build", operation_id="build_apply_queue", status_code=status.HTTP_202_ACCEPTED)
async def build(session: Authenticated, db: DbSession, settings: AppSettings) -> BuildOut:
    """Queues a build and returns at once; the worker does the looking-up."""
    return BuildOut(queued=await service.request_build(db, session.user_id, settings))


@router.post("/items/{item_id}/approve", operation_id="approve_apply_item")
async def approve(
    item_id: uuid.UUID,
    body: DecisionIn,
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
) -> ApplyItemOut:
    """You read it and want to apply. The job becomes Shortlisted; nothing is sent."""
    return await service.approve(
        db, session.user_id, item_id, body.note, today=today_in(settings.timezone)
    )


@router.post("/items/{item_id}/applied", operation_id="mark_apply_item_applied")
async def applied(
    item_id: uuid.UUID,
    body: DecisionIn,
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
) -> ApplyItemOut:
    """You applied yourself. The job becomes Applied - Pending with a follow-up date."""
    return await service.mark_applied(
        db, session.user_id, item_id, body.note, today=today_in(settings.timezone)
    )


@router.post("/items/{item_id}/skip", operation_id="skip_apply_item")
async def skip(
    item_id: uuid.UUID,
    body: DecisionIn,
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
) -> ApplyItemOut:
    return await service.skip(
        db, session.user_id, item_id, body.note, today=today_in(settings.timezone)
    )


@router.post("/items/{item_id}/research", operation_id="research_apply_item")
async def research(
    item_id: uuid.UUID,
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
    search: AppSearch,
    fetcher: AppFetcher,
) -> ApplyItemOut:
    """Look up pay, interview information and the company for one listed job, now."""
    return await service.deepen(
        db,
        session.user_id,
        item_id,
        today=today_in(settings.timezone),
        settings=settings,
        search=search,
        fetcher=fetcher,
    )
