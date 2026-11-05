from fastapi import APIRouter

from careerpilot.core.clock import today_in
from careerpilot.core.deps import AppSettings, DbSession
from careerpilot.modules.analytics import service
from careerpilot.modules.analytics.schemas import AnalyticsOut
from careerpilot.modules.auth.dependencies import Authenticated

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("", operation_id="get_analytics")
async def get_analytics(
    session: Authenticated, db: DbSession, settings: AppSettings
) -> AnalyticsOut:
    """The application funnel, weekly pace, prep progress, mock scores and score calibration."""
    return await service.build(db, session.user_id, today_in(settings.timezone), settings.timezone)
