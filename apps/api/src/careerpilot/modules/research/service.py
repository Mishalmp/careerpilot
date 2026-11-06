"""Research runs: find interview topics and questions for a job, then let the owner decide.

The run is a fixed pipeline with limits, not a free-roaming agent:
  plan searches (templates) -> search -> choose pages -> fetch (safe fetcher) -> extract with a
  model -> keep only items whose quote is really on the page -> store in the inbox.
Nothing reaches the learning area until the owner approves it.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.config import Settings
from careerpilot.core.errors import ProblemError
from careerpilot.core.evidence import quote_appears
from careerpilot.core.fetcher import Fetcher, FetchError
from careerpilot.core.llm import LlmClient, call_llm_json, tokens_used_today
from careerpilot.core.prompts import data_block, load_prompt
from careerpilot.core.search import SearchError, SearchHit, SearchProvider
from careerpilot.modules.learn import service as learn_service
from careerpilot.modules.learn.enums import (
    QuestionOrigin,
    QuestionStatus,
    QuestionType,
    TopicOrigin,
)
from careerpilot.modules.learn.schemas import LearnQuestionCreate, LearnSourceIn
from careerpilot.modules.research import repository, rules
from careerpilot.modules.research.enums import FindingKind, FindingStatus, RunStatus
from careerpilot.modules.research.models import ResearchFinding, ResearchRun
from careerpilot.modules.research.schemas import (
    Approved,
    ExtractReply,
    FindingOut,
    FindingPage,
    RunOut,
)
from careerpilot.modules.tasks import service as tasks_service
from careerpilot.modules.tasks.enums import TaskKind
from careerpilot.modules.tasks.service import TaskFailure
from careerpilot.modules.tracker import service as tracker_service

STALE_RUN = timedelta(hours=1)  # a run still "running" after this is considered dead


def _run_out(run: ResearchRun, pending: int = 0) -> RunOut:
    out = RunOut.model_validate(run)
    out.pending_findings = pending
    return out


# --- starting and reading ----------------------------------------------------------------------


async def start_run(
    db: AsyncSession,
    owner_id: uuid.UUID,
    job_id: uuid.UUID,
    settings: Settings,
    *,
    search_configured: bool,
    now: datetime | None = None,
) -> RunOut:
    """Queue a research run for a job. Asking again while one is active returns that run."""
    now = now or datetime.now(UTC)
    await tracker_service.get_job(db, owner_id, job_id)  # 404 when it is not yours
    if not search_configured:
        raise ProblemError(
            409,
            "No search service is set up",
            "Set CAREERPILOT_SEARCH_PROVIDER to searxng (with CAREERPILOT_SEARXNG_URL) or brave "
            "(with CAREERPILOT_BRAVE_API_KEY). You can also add topics by hand.",
        )
    active = await repository.active_run_for_job(db, owner_id, job_id, now - STALE_RUN)
    if active is not None:
        return _run_out(active)
    budgets = rules.Budgets(
        searches=settings.research_max_searches,
        pages=settings.research_max_pages,
        tokens=settings.research_max_tokens,
    )
    run = repository.add_run(
        db, owner_id, job_id=job_id, budgets=budgets.as_dict(), queries=[], usage={}
    )
    await db.flush()
    await tasks_service.enqueue(
        db,
        owner_id,
        TaskKind.RESEARCH,
        f"research:{run.id}",
        {"run_id": str(run.id)},
        max_attempts=1,  # a run handles its own problems; ask again to retry
    )
    await db.commit()
    await db.refresh(run)
    return _run_out(run)


async def list_runs(
    db: AsyncSession, owner_id: uuid.UUID, job_id: uuid.UUID | None, limit: int
) -> list[RunOut]:
    runs = await repository.list_runs(db, owner_id, job_id, limit)
    pending = await repository.pending_counts(db, owner_id)
    return [_run_out(r, pending.get(r.id, 0)) for r in runs]


async def get_run(db: AsyncSession, owner_id: uuid.UUID, run_id: uuid.UUID) -> RunOut:
    run = await repository.get_run(db, owner_id, run_id)
    if run is None:
        raise ProblemError(404, "Not found", "Research run not found.")
    pending = await repository.pending_counts(db, owner_id)
    return _run_out(run, pending.get(run.id, 0))


async def list_findings(
    db: AsyncSession,
    owner_id: uuid.UUID,
    *,
    status: FindingStatus,
    run_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> FindingPage:
    rows, total = await repository.list_findings(
        db, owner_id, status=status, run_id=run_id, limit=limit, offset=offset
    )
    return FindingPage(items=[FindingOut.model_validate(r) for r in rows], total=total)


# --- the run itself ----------------------------------------------------------------------------


async def execute(
    db: AsyncSession,
    owner_id: uuid.UUID,
    run_id: uuid.UUID,
    *,
    provider: SearchProvider | None,
    fetcher: Fetcher,
    llm: LlmClient | None,
    settings: Settings,
    now: datetime | None = None,
) -> RunOut:
    """Do the work. Raises TaskFailure (message for the owner) only if nothing could be done."""
    run = await repository.get_run(db, owner_id, run_id)
    if run is None:
        raise TaskFailure("The research run no longer exists.")
    if provider is None:
        raise TaskFailure("No search service is configured.")
    if llm is None:
        raise TaskFailure("Research needs an Anthropic API key to read the pages it finds.")
    job = await tracker_service.get_job(db, owner_id, run.job_id)
    role, company = job.title, job.company.name
    budgets = run.budgets
    prompt = load_prompt(settings.prompts_dir, "research-extract")

    run.status = RunStatus.RUNNING
    run.queries = rules.plan_queries(role, company, limit=int(budgets["searches"]))
    await db.commit()

    notes: list[str] = []
    usage = {
        "searches": 0,
        "pages_read": 0,
        "pages_failed": 0,
        "items_found": 0,
        "items_dropped": 0,
        "tokens": 0,
    }
    start_tokens = await tokens_used_today(db, owner_id)

    # 1. search
    hits: list[SearchHit] = []
    for query in run.queries:
        try:
            hits.extend(await provider.search(query, 5))
            usage["searches"] += 1
        except SearchError as error:
            if not hits:
                run.status = RunStatus.FAILED
                run.message = str(error)
                run.usage = usage
                run.finished_at = now or datetime.now(UTC)
                await db.commit()
                raise TaskFailure(str(error)) from error
            notes.append(f"Search stopped early: {error}")
            break
    pages = rules.select_pages(hits, int(budgets["pages"]))
    if not pages:
        notes.append("The searches found no pages worth reading.")

    # 2. read pages one at a time (one database session cannot be shared between parallel tasks)
    known = await repository.existing_keys(db, owner_id)
    stopped_by_budget = False
    for page in pages:
        used = await tokens_used_today(db, owner_id) - start_tokens
        if used >= int(budgets["tokens"]):
            notes.append("Stopped: the token budget for this run was used.")
            stopped_by_budget = True
            break
        try:
            fetched = await fetcher.fetch(page.url)
        except FetchError as error:
            usage["pages_failed"] += 1
            notes.append(f"Could not read {page.url}: {error.message}")
            continue
        text = fetched.text[: rules.PAGE_TEXT_CHARS]
        if not text.strip():
            usage["pages_failed"] += 1
            continue
        user = f"Role: {role}\nCompany: {company}\n\n" + data_block("source", text, url=page.url)
        try:
            reply = await call_llm_json(
                db, owner_id, llm, settings, prompt=prompt, user=user, schema=ExtractReply
            )
        except ProblemError as error:
            if error.status == 429:  # the daily cap
                notes.append(f"Stopped: {error.detail or error.title}")
                stopped_by_budget = True
                break
            usage["pages_failed"] += 1
            notes.append(f"The model could not use {page.url}: {error.title}")
            continue
        usage["pages_read"] += 1
        for item in reply.items:
            kind = {"topic": FindingKind.TOPIC, "question": FindingKind.QUESTION}.get(
                item.kind.strip().lower()
            )
            topic = " ".join(item.topic.split())[:60]
            body = " ".join(item.text.split())
            quote = " ".join(item.quote.split())
            if (
                kind is None
                or not topic
                or not body
                or len(body) > 300
                or not quote_appears(quote, text)
            ):
                usage["items_dropped"] += 1  # a quote that is not on the page is never kept
                continue
            key = rules.dedupe_key(kind.value, body)
            if key in known:
                continue  # already found before, in this run or an earlier one
            known.add(key)
            repository.add_finding(
                db,
                owner_id,
                run_id=run.id,
                kind=kind,
                topic=topic,
                text=body,
                quote=quote[:300],
                source_url=page.url,
                source_title=page.title or None,
                relevance=rules.relevance(body, topic, role, company),
                dedupe_key=key,
            )
            usage["items_found"] += 1

    usage["tokens"] = await tokens_used_today(db, owner_id) - start_tokens
    run.usage = usage
    run.finished_at = now or datetime.now(UTC)
    if usage["items_found"] == 0 and usage["pages_read"] == 0:
        run.status = RunStatus.FAILED
        run.message = " ".join(notes) or "Nothing could be read."
        await db.commit()
        raise TaskFailure(run.message)
    run.status = (
        RunStatus.PARTIAL
        if (stopped_by_budget or usage["pages_failed"] or notes)
        else RunStatus.SUCCEEDED
    )
    run.message = " ".join(notes)[:1000] or None
    await db.commit()
    await db.refresh(run)
    return _run_out(run)


# --- deciding ----------------------------------------------------------------------------------


async def _pending(db: AsyncSession, owner_id: uuid.UUID, finding_id: uuid.UUID) -> ResearchFinding:
    finding = await repository.get_finding(db, owner_id, finding_id)
    if finding is None:
        raise ProblemError(404, "Not found", "Finding not found.")
    if finding.status is not FindingStatus.PENDING:
        raise ProblemError(
            409, "Already decided", f"This finding was already {finding.status.value}."
        )
    return finding


async def approve(
    db: AsyncSession, owner_id: uuid.UUID, finding_id: uuid.UUID, now: datetime | None = None
) -> Approved:
    """Move a finding into the learning area: its topic, and for a question the question too."""
    now = now or datetime.now(UTC)
    finding = await _pending(db, owner_id, finding_id)
    topic = await learn_service.ensure_topic(
        db,
        owner_id,
        finding.topic,
        TopicOrigin.RESEARCH,
        summary=finding.text if finding.kind is FindingKind.TOPIC else None,
    )
    finding.status = FindingStatus.APPROVED
    finding.decided_at = now
    if finding.kind is FindingKind.TOPIC:
        await db.commit()
        return Approved(topic_id=topic.id, question_id=None)
    # The question, its source and the finding's new status are saved together by create_question.
    created = await learn_service.create_question(
        db,
        owner_id,
        LearnQuestionCreate(
            topic_id=topic.id,
            type=QuestionType.EXPLAIN,
            stem=finding.text,
            difficulty=3,
            options=[],
            sources=[
                LearnSourceIn(
                    url=finding.source_url,
                    title=finding.source_title,
                    quote=finding.quote,
                    fetched_on=now.date(),
                )
            ],
            tags=[],
        ),
        now,
        origin=QuestionOrigin.RESEARCH,
        status=QuestionStatus.VERIFIED,
    )
    return Approved(topic_id=topic.id, question_id=created.id)


async def reject(
    db: AsyncSession, owner_id: uuid.UUID, finding_id: uuid.UUID, now: datetime | None = None
) -> None:
    finding = await _pending(db, owner_id, finding_id)
    finding.status = FindingStatus.REJECTED
    finding.decided_at = now or datetime.now(UTC)
    await db.commit()
