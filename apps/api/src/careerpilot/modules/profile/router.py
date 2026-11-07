from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status

from careerpilot.core.deps import AppFetcher, AppSettings, DbSession
from careerpilot.core.errors import ProblemError
from careerpilot.modules.auth.dependencies import Authenticated
from careerpilot.modules.profile import service
from careerpilot.modules.profile.cvfile import MAX_BYTES
from careerpilot.modules.profile.dependencies import AppOcr
from careerpilot.modules.profile.schemas import (
    CvIn,
    CvUploadOut,
    GithubReading,
    ProfileOut,
    ProfileUpdate,
)

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


@router.post("/cv/file", operation_id="upload_cv")
async def upload_cv(
    file: Annotated[UploadFile, File(description="PDF, Word (.docx), text or a picture of a CV")],
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
    ocr: AppOcr,
) -> CvUploadOut:
    """Reads an uploaded CV in memory (the file is not kept) and fills in the profile from it."""
    data = await file.read(MAX_BYTES + 1)  # one byte over the limit is enough to refuse it
    if len(data) > MAX_BYTES:
        raise ProblemError(
            413, "File too large", f"CV files can be up to {MAX_BYTES // 1_000_000} MB."
        )
    return await service.upload_cv(
        db, session.user_id, file.filename, data, settings.content_dir, ocr
    )


@router.patch("", operation_id="update_profile")
async def update_profile(body: ProfileUpdate, session: Authenticated, db: DbSession) -> ProfileOut:
    return await service.update_profile(db, session.user_id, body)


@router.post("/setup/complete", operation_id="complete_setup")
async def complete_setup(session: Authenticated, db: DbSession) -> ProfileOut:
    """Marks account setup finished. Refused, with what is missing, until the answers are there."""
    return await service.complete_setup(db, session.user_id)


@router.post("/github/read", operation_id="read_github")
async def read_github(
    session: Authenticated, db: DbSession, fetcher: AppFetcher, settings: AppSettings
) -> GithubReading:
    """Suggests skills from the public repositories of the GitHub link in your profile."""
    return await service.read_github(db, session.user_id, fetcher, settings.content_dir)


@router.delete("/cv", operation_id="forget_cv", status_code=status.HTTP_204_NO_CONTENT)
async def forget_cv(session: Authenticated, db: DbSession) -> None:
    await service.clear_cv(db, session.user_id)
