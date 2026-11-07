from typing import Annotated

from fastapi import APIRouter, Query

from careerpilot.core.deps import AppSearch, AppSettings, DbSession
from careerpilot.modules.auth.dependencies import Authenticated
from careerpilot.modules.system import service
from careerpilot.modules.system.schemas import AiCalls, SystemStatus

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status", operation_id="get_system_status")
async def status(
    session: Authenticated, db: DbSession, settings: AppSettings, search: AppSearch
) -> SystemStatus:
    return await service.build(db, session.user_id, settings, search_configured=search is not None)


@router.get("/ai-calls", operation_id="list_ai_calls")
async def ai_calls(
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
    problems_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AiCalls:
    """Recent model calls with tokens, time and errors (no prompts or answers are stored)."""
    return await service.ai_calls(
        db, session.user_id, settings, only_problems=problems_only, limit=limit
    )
