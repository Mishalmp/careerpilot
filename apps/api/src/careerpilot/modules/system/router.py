from fastapi import APIRouter

from careerpilot.core.deps import AppSearch, AppSettings, DbSession
from careerpilot.modules.auth.dependencies import Authenticated
from careerpilot.modules.system import service
from careerpilot.modules.system.schemas import SystemStatus

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status", operation_id="get_system_status")
async def status(
    session: Authenticated, db: DbSession, settings: AppSettings, search: AppSearch
) -> SystemStatus:
    return await service.build(db, session.user_id, settings, search_configured=search is not None)
