import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from careerpilot.core.clock import today_in
from careerpilot.core.deps import AppFetcher, AppLlm, AppSettings, DbSession
from careerpilot.modules.auth.dependencies import Authenticated
from careerpilot.modules.verification import service
from careerpilot.modules.verification.enums import CheckKey
from careerpilot.modules.verification.schemas import CheckUpdate, VerificationOut

router = APIRouter(prefix="/jobs/{job_id}/verification", tags=["verification"])


@router.get("", operation_id="get_verification")
async def get_verification(
    job_id: uuid.UUID, session: Authenticated, db: DbSession, llm: AppLlm
) -> VerificationOut:
    return await service.get_verification(db, session.user_id, job_id, ai_available=llm is not None)


@router.post("/run", operation_id="run_verification")
async def run_verification(
    job_id: uuid.UUID,
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
    fetcher: AppFetcher,
    llm: AppLlm,
    ai: Annotated[bool, Query(description="Let the model read the company's own pages")] = True,
) -> VerificationOut:
    """Run the lookups. Takes several seconds; safe to repeat. Your own findings are kept."""
    return await service.run(
        db,
        session.user_id,
        job_id,
        fetcher=fetcher,
        llm=llm,
        settings=settings,
        today=today_in(settings.timezone),
        use_ai=ai,
    )


@router.put("/checks/{key}", operation_id="set_verification_check")
async def set_check(
    job_id: uuid.UUID,
    key: CheckKey,
    body: CheckUpdate,
    session: Authenticated,
    db: DbSession,
    fetcher: AppFetcher,
    llm: AppLlm,
) -> VerificationOut:
    return await service.set_check(
        db, session.user_id, job_id, key, body, fetcher=fetcher, ai_available=llm is not None
    )


@router.delete("/checks/{key}", operation_id="clear_verification_check")
async def clear_check(
    job_id: uuid.UUID, key: CheckKey, session: Authenticated, db: DbSession, llm: AppLlm
) -> VerificationOut:
    """Forget a result (yours or automatic) so the next run can fill it in."""
    return await service.clear_check(db, session.user_id, job_id, key, ai_available=llm is not None)
