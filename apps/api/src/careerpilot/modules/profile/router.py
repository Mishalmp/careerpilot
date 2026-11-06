from fastapi import APIRouter, status

from careerpilot.core.deps import AppSettings, DbSession
from careerpilot.modules.auth.dependencies import Authenticated
from careerpilot.modules.profile import service
from careerpilot.modules.profile.schemas import CvIn, ProfileOut, ProfileUpdate

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", operation_id="get_profile")
async def get_profile(session: Authenticated, db: DbSession) -> ProfileOut:
    return await service.get_profile(db, session.user_id)


@router.put("/cv", operation_id="analyse_cv")
async def analyse_cv(
    body: CvIn, session: Authenticated, db: DbSession, settings: AppSettings
) -> ProfileOut:
    """Reads the CV text with rules and fills in skills, role titles and years."""
    return await service.analyse_cv(db, session.user_id, body, settings.content_dir)


@router.patch("", operation_id="update_profile")
async def update_profile(body: ProfileUpdate, session: Authenticated, db: DbSession) -> ProfileOut:
    return await service.update_profile(db, session.user_id, body)


@router.delete("/cv", operation_id="forget_cv", status_code=status.HTTP_204_NO_CONTENT)
async def forget_cv(session: Authenticated, db: DbSession) -> None:
    await service.clear_cv(db, session.user_id)
