import uuid

from fastapi import APIRouter, status

from careerpilot.core.clock import today_in
from careerpilot.core.deps import AppLlm, AppSettings, DbSession
from careerpilot.modules.auth.dependencies import Authenticated
from careerpilot.modules.knowledge.dependencies import AppEmbedder
from careerpilot.modules.mock import service
from careerpilot.modules.mock.schemas import (
    AnswerMockRequest,
    MockSessionItem,
    MockSessionOut,
    StartMockRequest,
)

router = APIRouter(prefix="/mock", tags=["mock"])


@router.get("/sessions", operation_id="list_mock_sessions")
async def list_sessions(session: Authenticated, db: DbSession) -> list[MockSessionItem]:
    return await service.list_sessions(db, session.user_id)


@router.post("/sessions", operation_id="start_mock", status_code=status.HTTP_201_CREATED)
async def start(
    body: StartMockRequest,
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
    llm: AppLlm,
) -> MockSessionOut:
    """Start a mock interview on a job or a topic. The model asks the first question."""
    return await service.start(
        db,
        session.user_id,
        body,
        llm=llm,
        settings=settings,
        today=today_in(settings.timezone),
    )


@router.get("/sessions/{session_id}", operation_id="get_mock")
async def get_session(
    session_id: uuid.UUID, session: Authenticated, db: DbSession
) -> MockSessionOut:
    return await service.get_session(db, session.user_id, session_id)


@router.post("/sessions/{session_id}/answer", operation_id="answer_mock")
async def answer(
    session_id: uuid.UUID,
    body: AnswerMockRequest,
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
    llm: AppLlm,
    embedder: AppEmbedder,
) -> MockSessionOut:
    """Answer the current question; you get a score, feedback and the next question."""
    return await service.answer(
        db, session.user_id, session_id, body, llm=llm, settings=settings, embedder=embedder
    )


@router.delete(
    "/sessions/{session_id}", operation_id="delete_mock", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_session(session_id: uuid.UUID, session: Authenticated, db: DbSession) -> None:
    await service.delete_session(db, session.user_id, session_id)
