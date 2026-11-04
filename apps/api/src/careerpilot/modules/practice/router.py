from typing import Annotated

from fastapi import APIRouter, Query, status

from careerpilot.core.deps import AppSettings, DbSession
from careerpilot.modules.auth.dependencies import Authenticated
from careerpilot.modules.practice import service
from careerpilot.modules.practice.enums import Difficulty, Kind, Language, ProgressStatus
from careerpilot.modules.practice.schemas import (
    ProblemDetail,
    ProblemSummary,
    SubmissionCreate,
    SubmissionOut,
)

router = APIRouter(prefix="/practice", tags=["practice"])


@router.get("/problems", operation_id="list_problems")
async def list_problems(
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
    difficulty: Difficulty | None = None,
    kind: Kind | None = None,
    tag: Annotated[str | None, Query(max_length=50)] = None,
    topic: Annotated[str | None, Query(max_length=120)] = None,
    progress: ProgressStatus | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> list[ProblemSummary]:
    return await service.list_problems(
        db,
        session.user_id,
        settings.content_dir,
        difficulty=difficulty,
        kind=kind,
        tag=tag,
        topic_key=topic,
        status=progress,
        query=q,
    )


@router.get("/problems/{slug}", operation_id="get_problem")
async def get_problem(
    slug: str, session: Authenticated, db: DbSession, settings: AppSettings
) -> ProblemDetail:
    return await service.get_problem(db, session.user_id, settings.content_dir, slug)


@router.post(
    "/problems/{slug}/submissions",
    operation_id="submit_solution",
    status_code=status.HTTP_201_CREATED,
)
async def submit_solution(
    slug: str,
    body: SubmissionCreate,
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
) -> SubmissionOut:
    submission = await service.submit(db, session.user_id, settings.content_dir, slug, body)
    return SubmissionOut.model_validate(submission)


@router.get("/problems/{slug}/submissions", operation_id="list_submissions")
async def list_submissions(
    slug: str,
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
    language: Language | None = None,
) -> list[SubmissionOut]:
    rows = await service.list_submissions(db, session.user_id, settings.content_dir, slug, language)
    return [SubmissionOut.model_validate(row) for row in rows]
