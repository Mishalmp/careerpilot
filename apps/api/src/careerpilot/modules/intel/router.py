import uuid

from fastapi import APIRouter, status

from careerpilot.core.clock import today_in
from careerpilot.core.deps import AppFetcher, AppLlm, AppSettings, DbSession
from careerpilot.modules.auth.dependencies import Authenticated
from careerpilot.modules.intel import service
from careerpilot.modules.intel.schemas import (
    ExtractOut,
    IntelOut,
    PeersOut,
    QuestionsOut,
    SourceCreate,
)

router = APIRouter(prefix="/jobs/{job_id}/intel", tags=["intel"])


@router.get("", operation_id="get_intel")
async def get_intel(
    job_id: uuid.UUID, session: Authenticated, db: DbSession, settings: AppSettings, llm: AppLlm
) -> IntelOut:
    """Sources about how this company interviews, and the brief built from them."""
    return await service.get_intel(
        db, session.user_id, job_id, today=today_in(settings.timezone), ai_available=llm is not None
    )


@router.post("/sources", operation_id="add_intel_source", status_code=status.HTTP_201_CREATED)
async def add_source(
    job_id: uuid.UUID,
    body: SourceCreate,
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
    fetcher: AppFetcher,
    llm: AppLlm,
) -> ExtractOut:
    """Add a text you pasted, or a page to fetch. With a key, the model extracts facts from it
    and code keeps only those whose quote is really in the text."""
    return await service.add_source(
        db, session.user_id, job_id, body, fetcher=fetcher, llm=llm, settings=settings
    )


@router.post("/sources/{source_id}/extract", operation_id="extract_intel_source")
async def extract_source(
    job_id: uuid.UUID,
    source_id: uuid.UUID,
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
    llm: AppLlm,
) -> ExtractOut:
    return await service.extract_source(
        db, session.user_id, job_id, source_id, llm=llm, settings=settings
    )


@router.delete(
    "/sources/{source_id}",
    operation_id="delete_intel_source",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_source(
    job_id: uuid.UUID, source_id: uuid.UUID, session: Authenticated, db: DbSession
) -> None:
    await service.delete_source(db, session.user_id, job_id, source_id)


@router.post("/peers", operation_id="suggest_intel_peers")
async def suggest_peers(
    job_id: uuid.UUID, session: Authenticated, db: DbSession, settings: AppSettings, llm: AppLlm
) -> PeersOut:
    """Companies worth reading about when this one has little public information."""
    return await service.suggest_peers(db, session.user_id, job_id, llm=llm, settings=settings)


@router.post("/questions-to-ask", operation_id="suggest_questions_to_ask")
async def suggest_questions(
    job_id: uuid.UUID, session: Authenticated, db: DbSession, settings: AppSettings, llm: AppLlm
) -> QuestionsOut:
    return await service.suggest_questions(db, session.user_id, job_id, llm=llm, settings=settings)
