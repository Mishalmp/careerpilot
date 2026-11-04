from fastapi import APIRouter

from careerpilot.core.clock import today_in
from careerpilot.core.deps import AppSettings, DbSession
from careerpilot.modules.auth.dependencies import Authenticated
from careerpilot.modules.today import service
from careerpilot.modules.today.schemas import TodayOut

router = APIRouter(tags=["today"])


@router.get("/today", operation_id="get_today")
async def get_today(session: Authenticated, db: DbSession, settings: AppSettings) -> TodayOut:
    return await service.build(db, session.user_id, today_in(settings.timezone))
