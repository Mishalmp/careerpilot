import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from careerpilot.core.deps import AppLlm, AppSettings, DbSession
from careerpilot.modules.auth.dependencies import Authenticated
from careerpilot.modules.profile import service as profile_service
from careerpilot.modules.scoring import service
from careerpilot.modules.scoring.schemas import ScoreOut

router = APIRouter(prefix="/jobs/{job_id}/score", tags=["scoring"])


@router.get("", operation_id="get_score")
async def get_score(
    job_id: uuid.UUID, session: Authenticated, db: DbSession, settings: AppSettings
) -> ScoreOut | None:
    """The stored score, or null when the job has not been scored."""
    mine = await profile_service.get_profile(db, session.user_id)
    return await service.get_score(db, session.user_id, job_id, settings, mine)


@router.post("", operation_id="score_job")
async def score_job(
    job_id: uuid.UUID,
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
    llm: AppLlm,
    ai: Annotated[bool, Query(description="Let the model read the description")] = True,
) -> ScoreOut:
    """Score the job against your profile (from account setup). Safe to repeat."""
    mine = await profile_service.get_profile(db, session.user_id)
    return await service.score_job(
        db, session.user_id, job_id, settings=settings, mine=mine, llm=llm, use_ai=ai
    )
