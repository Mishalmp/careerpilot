import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.practice.enums import Language, ProgressStatus
from careerpilot.modules.practice.models import Submission

KEEP_PER_PROBLEM = 30


def add_submission(db: AsyncSession, owner_id: uuid.UUID, **fields: Any) -> Submission:
    submission = Submission(owner_id=owner_id, **fields)
    db.add(submission)
    return submission


async def prune(db: AsyncSession, owner_id: uuid.UUID, slug: str) -> None:
    """Keep the newest few submissions per problem so history cannot grow without bound."""
    newest = (
        select(Submission.id)
        .where(Submission.owner_id == owner_id, Submission.problem_slug == slug)
        .order_by(Submission.created_at.desc(), Submission.id.desc())
        .limit(KEEP_PER_PROBLEM)
    )
    await db.execute(
        delete(Submission).where(
            Submission.owner_id == owner_id,
            Submission.problem_slug == slug,
            Submission.id.not_in(newest),
        )
    )


async def list_submissions(
    db: AsyncSession, owner_id: uuid.UUID, slug: str, language: Language | None, limit: int
) -> Sequence[Submission]:
    stmt = select(Submission).where(
        Submission.owner_id == owner_id, Submission.problem_slug == slug
    )
    if language:
        stmt = stmt.where(Submission.language == language)
    return (
        await db.scalars(
            stmt.order_by(Submission.created_at.desc(), Submission.id.desc()).limit(limit)
        )
    ).all()


async def progress_by_slug(db: AsyncSession, owner_id: uuid.UUID) -> dict[str, ProgressStatus]:
    solved = func.bool_or(and_(Submission.passed == Submission.total, Submission.total > 0))
    rows = await db.execute(
        select(Submission.problem_slug, solved)
        .where(Submission.owner_id == owner_id)
        .group_by(Submission.problem_slug)
    )
    return {
        slug: ProgressStatus.SOLVED if is_solved else ProgressStatus.ATTEMPTED
        for slug, is_solved in rows.all()
    }
