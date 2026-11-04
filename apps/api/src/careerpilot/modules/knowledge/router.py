from typing import Annotated

from fastapi import APIRouter, Query

from careerpilot.core.deps import AppSettings, DbSession
from careerpilot.modules.auth.dependencies import Authenticated
from careerpilot.modules.knowledge import service
from careerpilot.modules.knowledge.dependencies import AppEmbedder, AppLlm
from careerpilot.modules.knowledge.schemas import (
    AskOut,
    AskRequest,
    IngestOut,
    Question,
    SearchOut,
    StatusOut,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/status", operation_id="knowledge_status")
async def knowledge_status(
    session: Authenticated, db: DbSession, settings: AppSettings, llm: AppLlm
) -> StatusOut:
    return await service.status(db, session.user_id, settings, ai_enabled=llm is not None)


@router.post("/ingest", operation_id="knowledge_ingest")
async def knowledge_ingest(
    session: Authenticated, db: DbSession, settings: AppSettings, embedder: AppEmbedder
) -> IngestOut:
    """Re-index changed notes. Safe to repeat; the first run downloads the embedding model."""
    return await service.ingest(db, session.user_id, settings.content_dir, embedder)


@router.get("/search", operation_id="knowledge_search")
async def knowledge_search(
    q: Annotated[Question, Query()],
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
    embedder: AppEmbedder,
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
) -> SearchOut:
    return await service.search(db, session.user_id, embedder, settings, q, limit)


@router.post("/ask", operation_id="knowledge_ask")
async def knowledge_ask(
    body: AskRequest,
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
    embedder: AppEmbedder,
    llm: AppLlm,
) -> AskOut:
    return await service.ask(db, session.user_id, embedder, llm, settings, body.question)
