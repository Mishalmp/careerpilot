import uuid

from fastapi import APIRouter, status

from careerpilot.core.clock import today_in
from careerpilot.core.deps import AppFetcher, AppLlm, AppSettings, DbSession
from careerpilot.modules.auth.dependencies import Authenticated
from careerpilot.modules.knowledge.dependencies import AppEmbedder
from careerpilot.modules.outreach import service
from careerpilot.modules.outreach.schemas import (
    DraftCreate,
    DraftEdit,
    DraftOut,
    GenerateRequest,
    Move,
    OutreachList,
)

router = APIRouter(tags=["outreach"])


@router.get("/jobs/{job_id}/outreach", operation_id="list_outreach")
async def list_outreach(
    job_id: uuid.UUID, session: Authenticated, db: DbSession, settings: AppSettings
) -> OutreachList:
    return await service.list_drafts(
        db, session.user_id, job_id, settings, today_in(settings.timezone)
    )


@router.post(
    "/jobs/{job_id}/outreach",
    operation_id="create_outreach",
    status_code=status.HTTP_201_CREATED,
)
async def create_outreach(
    job_id: uuid.UUID, body: DraftCreate, session: Authenticated, db: DbSession
) -> DraftOut:
    """Save a draft you wrote yourself. It gets the same checks as a generated one."""
    return await service.create_manual(db, session.user_id, job_id, body)


@router.post(
    "/jobs/{job_id}/outreach/generate",
    operation_id="generate_outreach",
    status_code=status.HTTP_201_CREATED,
)
async def generate_outreach(
    job_id: uuid.UUID,
    body: GenerateRequest,
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
    llm: AppLlm,
    fetcher: AppFetcher,
    embedder: AppEmbedder,
) -> list[DraftOut]:
    """Two variants, from facts you give (checked against the job text or your source page)."""
    return await service.generate(
        db,
        session.user_id,
        job_id,
        body,
        settings=settings,
        llm=llm,
        fetcher=fetcher,
        embedder=embedder,
    )


@router.patch("/outreach/{draft_id}", operation_id="edit_outreach")
async def edit_outreach(
    draft_id: uuid.UUID, body: DraftEdit, session: Authenticated, db: DbSession
) -> DraftOut:
    return await service.edit(db, session.user_id, draft_id, body)


@router.post("/outreach/{draft_id}/status", operation_id="move_outreach")
async def move_outreach(
    draft_id: uuid.UUID, body: Move, session: Authenticated, db: DbSession, settings: AppSettings
) -> DraftOut:
    """Approve, reject, reopen, or record that you sent it yourself. Nothing is ever sent."""
    return await service.move(
        db,
        session.user_id,
        draft_id,
        body,
        settings=settings,
        today=today_in(settings.timezone),
    )


@router.delete(
    "/outreach/{draft_id}", operation_id="delete_outreach", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_outreach(draft_id: uuid.UUID, session: Authenticated, db: DbSession) -> None:
    await service.delete(db, session.user_id, draft_id)
