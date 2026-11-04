import uuid
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.errors import ProblemError
from careerpilot.modules.practice import problems, repository
from careerpilot.modules.practice.enums import Difficulty, Kind, Language, ProgressStatus
from careerpilot.modules.practice.models import Submission
from careerpilot.modules.practice.problems import Problem
from careerpilot.modules.practice.schemas import (
    FunctionTestOut,
    LanguageSpec,
    ProblemDetail,
    ProblemSummary,
    SqlExpectedOut,
    SqlTestOut,
    SubmissionCreate,
)

HISTORY_LIMIT = 20


def _summary(problem: Problem, status: ProgressStatus) -> ProblemSummary:
    return ProblemSummary(
        slug=problem.slug,
        title=problem.title,
        kind=problem.kind,
        difficulty=problem.difficulty,
        tags=problem.tags,
        topic_keys=problem.topic_keys,
        languages=problem.languages,
        status=status,
    )


async def list_problems(
    db: AsyncSession,
    owner_id: uuid.UUID,
    content_dir: Path,
    *,
    difficulty: Difficulty | None,
    kind: Kind | None,
    tag: str | None,
    topic_key: str | None,
    status: ProgressStatus | None,
    query: str | None,
) -> list[ProblemSummary]:
    progress = await repository.progress_by_slug(db, owner_id)
    needle = query.casefold() if query else None
    found: list[ProblemSummary] = []
    for problem in problems.load_problems(content_dir).problems.values():
        current = progress.get(problem.slug, ProgressStatus.UNSOLVED)
        if (
            (difficulty and problem.difficulty != difficulty)
            or (kind and problem.kind != kind)
            or (tag and tag not in problem.tags)
            or (topic_key and topic_key not in problem.topic_keys)
            or (status and current != status)
            or (needle and needle not in problem.title.casefold())
        ):
            continue
        found.append(_summary(problem, current))
    order = {Difficulty.EASY: 0, Difficulty.MEDIUM: 1, Difficulty.HARD: 2}
    return sorted(found, key=lambda p: (order[p.difficulty], p.title))


def _require(content_dir: Path, slug: str) -> Problem:
    problem = problems.load_problems(content_dir).problems.get(slug)
    if problem is None:
        raise ProblemError(404, "Not found", "Problem not found.")
    return problem


async def get_problem(
    db: AsyncSession, owner_id: uuid.UUID, content_dir: Path, slug: str
) -> ProblemDetail:
    problem = _require(content_dir, slug)
    progress = await repository.progress_by_slug(db, owner_id)
    summary = _summary(problem, progress.get(slug, ProgressStatus.UNSOLVED))
    sql = problem.sql
    return ProblemDetail(
        **summary.model_dump(),
        statement=problem.statement,
        specs=[
            LanguageSpec(language=s.language, starter=s.code, entry=s.entry)
            for s in problems.starters(problem)
        ],
        function_tests=[
            FunctionTestOut(
                name=t.name, hidden=t.hidden, args=t.args, expected=t.expected, compare=t.compare
            )
            for t in problem.tests
        ],
        sql_ddl=sql.ddl if sql else None,
        sql_tests=[
            SqlTestOut(
                name=t.name,
                hidden=t.hidden,
                data=t.data,
                expected=SqlExpectedOut(**t.expected.model_dump()),
            )
            for t in (sql.tests if sql else [])
        ],
    )


async def submit(
    db: AsyncSession,
    owner_id: uuid.UUID,
    content_dir: Path,
    slug: str,
    data: SubmissionCreate,
) -> Submission:
    problem = _require(content_dir, slug)
    if data.language not in problem.languages:
        raise ProblemError(422, "Wrong language", f"{data.language.value} is not available here.")
    if data.total != problem.test_count or len(data.results) != data.total:
        raise ProblemError(422, "Wrong test count", f"This problem has {problem.test_count} tests.")
    if data.passed != sum(r.status == "pass" for r in data.results):
        raise ProblemError(422, "Inconsistent result", "`passed` must match the per-test results.")

    submission = repository.add_submission(
        db,
        owner_id,
        problem_slug=slug,
        language=data.language,
        code=data.code,
        passed=data.passed,
        total=data.total,
        runtime_ms=data.runtime_ms,
        results=[r.model_dump() for r in data.results],
    )
    await db.flush()
    await repository.prune(db, owner_id, slug)
    await db.commit()
    await db.refresh(submission)
    return submission


async def list_submissions(
    db: AsyncSession,
    owner_id: uuid.UUID,
    content_dir: Path,
    slug: str,
    language: Language | None,
) -> Sequence[Submission]:
    _require(content_dir, slug)
    return await repository.list_submissions(db, owner_id, slug, language, HISTORY_LIMIT)
