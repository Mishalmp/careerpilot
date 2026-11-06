"""The daily apply list: choose a few jobs, find out what you would want to know about each, and
wait for you.

What happens, in order, when the list is built:
  1. read your apply policy (a file you edit) and your CV profile
  2. take jobs in your tracker that are still New or Shortlisted and not listed before
  3. drop those the policy excludes, score the rest against your profile, keep the best
  4. for each: check the company, look for the pay and interview information step by step (see
     `chain.py`), and look for the same job on other sites
  5. save it all, each part labelled with where it came from

Nothing is sent anywhere and nothing is applied for. You read an item, press Approve (the job
becomes Shortlisted) and open the apply page yourself; afterwards you press "I applied" (the job
becomes Applied - Pending, with a follow-up date). CareerPilot has no way to submit an application.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.config import Settings
from careerpilot.core.errors import ProblemError
from careerpilot.core.fetcher import Fetcher
from careerpilot.core.search import SearchProvider
from careerpilot.modules.apply import company, matching, repository
from careerpilot.modules.apply.enrich import JobFacts, PoolEntry, enrich
from careerpilot.modules.apply.enums import ApplyStatus
from careerpilot.modules.apply.models import ApplyItem
from careerpilot.modules.apply.policy import Policy, PolicyProblem, load_policy
from careerpilot.modules.apply.schemas import (
    AlsoListed,
    ApplyItemOut,
    ApplyQueueOut,
    CompanyCheckSummary,
    InterviewNotes,
    PayEstimate,
)
from careerpilot.modules.apply.web import JobWeb
from careerpilot.modules.profile import service as profile_service
from careerpilot.modules.profile.schemas import ProfileOut
from careerpilot.modules.scoring import service as scoring_service
from careerpilot.modules.tasks import service as tasks_service
from careerpilot.modules.tasks.enums import TaskKind
from careerpilot.modules.tracker import service as tracker_service
from careerpilot.modules.tracker.enums import Status
from careerpilot.modules.tracker.filters import JobFilters
from careerpilot.modules.tracker.schemas import StatusChange
from careerpilot.modules.tracker.service import JobRecord
from careerpilot.modules.verification import service as verification_service

log = structlog.get_logger()

RECENT_DAYS = 7
FOLLOWUP_DAYS = 7  # "I applied" sets a follow-up this many days ahead
MAX_PAGES = 5  # of 200 jobs each, when reading your tracker
EXAMINE_FACTOR = 2  # look at up to twice the daily limit, so held-back jobs do not empty the list
OPEN = (Status.NEW, Status.SHORTLISTED)


@dataclass(frozen=True)
class BuildResult:
    listed: int
    held_back: int
    examined: int


def policy_for(content_dir: Path) -> tuple[Policy, str]:
    try:
        return load_policy(content_dir)
    except PolicyProblem as exc:
        raise ProblemError(
            422, "The apply policy file has a problem", " ".join(exc.problems)
        ) from exc


def _need_profile(profile: ProfileOut) -> None:
    if not profile.skills and not profile.role_titles:
        raise ProblemError(
            409,
            "Add your CV first",
            "The daily list needs your skills and role titles. Paste your CV on the Profile page.",
        )


async def check_ready(db: AsyncSession, owner_id: uuid.UUID, settings: Settings) -> None:
    """Fail early, with a plain message, when a build cannot work (used before queueing one)."""
    policy_for(settings.content_dir)
    _need_profile(await profile_service.get_profile(db, owner_id))


async def request_build(
    db: AsyncSession, owner_id: uuid.UUID, settings: Settings, *, now: datetime | None = None
) -> bool:
    """Queue a build now (the worker does the work). False when this minute's is already queued."""
    await check_ready(db, owner_id, settings)
    local = (now or datetime.now(UTC)).astimezone(ZoneInfo(settings.timezone))
    queued = await tasks_service.enqueue(
        db,
        owner_id,
        TaskKind.APPLY_QUEUE,
        f"apply_queue:{local:%Y-%m-%d}:manual:{local:%H%M}",
        {},
        max_attempts=1,  # a profile or policy problem will not fix itself by retrying
    )
    await db.commit()
    return queued


# --- choosing -------------------------------------------------------------------------------


def _allowed(job: JobRecord, policy: Policy) -> bool:
    """The policy's hard rules. A field the post does not state never excludes a job."""
    if policy.regions and job.region is not None and job.region.value not in policy.regions:
        return False
    if (
        policy.work_modes
        and job.work_mode is not None
        and job.work_mode.value not in policy.work_modes
    ):
        return False
    skipped = {name.casefold() for name in policy.skip_companies}
    if job.company.name.casefold() in skipped:
        return False
    return not (policy.require_apply_link and not (job.apply_url or job.jd_url))


async def _open_jobs(db: AsyncSession, owner_id: uuid.UUID, filters: JobFilters) -> list[JobRecord]:
    jobs: list[JobRecord] = []
    cursor: str | None = None
    for _ in range(MAX_PAGES):
        page, cursor = await tracker_service.list_jobs(
            db, owner_id, filters, cursor=cursor, limit=tracker_service.MAX_PAGE
        )
        jobs.extend(page)
        if cursor is None:
            break
    return jobs


def _job_text(job: JobRecord) -> str:
    return f"{job.title}\n{job.jd_text or ''}"


def _rank(
    jobs: list[JobRecord],
    policy: Policy,
    profile: ProfileOut,
    content_dir: Path,
    today: date,
) -> list[tuple[JobRecord, matching.Match]]:
    ranked: list[tuple[JobRecord, matching.Match]] = []
    for job in jobs:
        if not _allowed(job, policy):
            continue
        found = matching.match(
            job_title=job.title,
            job_skills=scoring_service.detect_skills(content_dir, _job_text(job)),
            profile_skills=profile.skills,
            profile_titles=profile.role_titles,
            posted_on=job.posted_on or job.found_on,
            today=today,
        )
        if found.score >= policy.min_match_score:
            ranked.append((job, found))
    ranked.sort(key=lambda pair: (-pair[1].score, pair[0].title.casefold()))
    return ranked


def _facts(job: JobRecord, skills: list[str]) -> JobFacts:
    own = frozenset(u for u in (job.jd_url, job.apply_url) if u)
    return JobFacts(
        title=job.title,
        company=job.company.name,
        region=job.region.value if job.region else None,
        salary_text=job.salary_text,
        est_ctc_lpa=float(job.est_ctc_lpa) if job.est_ctc_lpa is not None else None,
        jd_text=job.jd_text,
        jd_url=job.jd_url,
        own_urls=own,
        skills=skills,
    )


# --- building -------------------------------------------------------------------------------


async def build_queue(
    db: AsyncSession,
    owner_id: uuid.UUID,
    *,
    today: date,
    settings: Settings,
    search: SearchProvider | None,
    fetcher: Fetcher | None,
    now: datetime | None = None,
) -> BuildResult:
    """Add today's items. Safe to run again: it only tops the day up to the daily limit, and a job
    is never listed twice."""
    now = now or datetime.now(UTC)
    policy, _ = policy_for(settings.content_dir)
    profile = await profile_service.get_profile(db, owner_id)
    _need_profile(profile)

    remaining = policy.daily_limit - await repository.count_counted_on(db, owner_id, today)
    if remaining <= 0:
        return BuildResult(0, 0, 0)

    already = await repository.listed_job_ids(db, owner_id)
    candidates = [
        pair
        for pair in _rank(
            await _open_jobs(db, owner_id, JobFilters(statuses=OPEN)),
            policy,
            profile,
            settings.content_dir,
            today,
        )
        if pair[0].id not in already
    ]
    pool = [
        PoolEntry(
            company=job.company.name,
            title=job.title,
            lpa=float(job.est_ctc_lpa),
            url=job.jd_url,
            job_id=job.id,
        )
        for job in await _open_jobs(db, owner_id, JobFilters(min_ctc=1.0))
        if job.est_ctc_lpa is not None
    ]

    listed = held = examined = 0
    for job, found in candidates[: remaining * EXAMINE_FACTOR + 2]:
        if listed >= remaining:
            break
        examined += 1
        item = await repository.add_if_new(
            db,
            owner_id,
            job.id,
            queued_on=today,
            status=ApplyStatus.READY,
            match_score=found.score,
            reasons=found.reasons,
            also_listed=[],
            notes=[],
        )
        if item is None:  # another build listed it first
            continue
        if await _fill(
            db, owner_id, item, job, found, pool, policy, settings, search, fetcher, today, now
        ):
            held += 1
        else:
            listed += 1
        await db.commit()
    return BuildResult(listed, held, examined)


async def _fill(
    db: AsyncSession,
    owner_id: uuid.UUID,
    item: ApplyItem,
    job: JobRecord,
    found: matching.Match,
    pool: list[PoolEntry],
    policy: Policy,
    settings: Settings,
    search: SearchProvider | None,
    fetcher: Fetcher | None,
    today: date,
    now: datetime,
) -> bool:
    """Look everything up for one item. Returns True when the item was held back."""
    notes: list[str] = []
    held_reason: str | None = None

    # The company check first: a company that fails it should not take up web searches.
    try:
        verification = (
            await verification_service.run(
                db,
                owner_id,
                job.id,
                fetcher=fetcher,
                llm=None,
                settings=settings,
                today=today,
                use_ai=False,
            )
            if policy.enrich_with_web and fetcher is not None
            else await verification_service.get_verification(
                db, owner_id, job.id, ai_available=False
            )
        )
        summary, held_reason = company.summarise(verification)
        item.company_check = summary.model_dump(mode="json")
    except Exception:  # one company's lookup must not stop the list
        log.exception("apply_company_check_failed", job_id=str(job.id))
        notes.append("The company check could not be completed.")

    if held_reason is not None and policy.block_if_company_suspicious:
        item.status = ApplyStatus.BLOCKED
        item.decision_note = held_reason
        item.notes = notes
        return True

    if policy.enrich_with_web:
        web = JobWeb(search, fetcher, max_pages=policy.max_web_pages_per_job)
    else:
        web = JobWeb(None, None, max_pages=0)
    skills = found.job_skills
    try:
        result = await enrich(
            _facts(job, skills),
            [e for e in pool if e.job_id != job.id],
            web,
            lambda text: set(scoring_service.detect_skills(settings.content_dir, text)),
        )
        item.pay = result.pay.model_dump(mode="json")
        item.interview = result.interview.model_dump(mode="json")
        item.also_listed = [x.model_dump(mode="json") for x in result.also_listed]
    except Exception:
        log.exception("apply_enrich_failed", job_id=str(job.id))
        notes.append("Looking up pay and interview information failed; check them yourself.")
    if search is None and policy.enrich_with_web:
        notes.append("No search service is set up, so the web was not searched.")
    item.notes = [*notes, *web.notes]
    item.enriched_at = now
    return False


# --- reading --------------------------------------------------------------------------------


def _out(item: ApplyItem, job: JobRecord) -> ApplyItemOut:
    return ApplyItemOut(
        id=item.id,
        job_id=item.job_id,
        title=job.title,
        company=job.company.name,
        location=job.location_text,
        work_mode=job.work_mode.value if job.work_mode else None,
        region=job.region.value if job.region else None,
        apply_url=job.apply_url,
        jd_url=job.jd_url,
        queued_on=item.queued_on,
        status=item.status,
        tracker_status=job.application.status.value,
        match_score=item.match_score,
        reasons=list(item.reasons),
        pay=PayEstimate.model_validate(item.pay) if item.pay else None,
        interview=InterviewNotes.model_validate(item.interview) if item.interview else None,
        also_listed=[AlsoListed.model_validate(x) for x in item.also_listed],
        company_check=CompanyCheckSummary.model_validate(item.company_check)
        if item.company_check
        else None,
        notes=list(item.notes),
        enriched_at=item.enriched_at,
        decided_at=item.decided_at,
        decision_note=item.decision_note,
    )


async def get_queue(
    db: AsyncSession, owner_id: uuid.UUID, settings: Settings, today: date
) -> ApplyQueueOut:
    problems: list[str] = []
    try:
        policy, source = load_policy(settings.content_dir)
    except PolicyProblem as exc:
        policy, source, problems = Policy(), "built-in defaults", exc.problems
    items = await repository.list_since(db, owner_id, today - timedelta(days=RECENT_DAYS))
    out = [_out(item, await tracker_service.get_job(db, owner_id, item.job_id)) for item in items]
    return ApplyQueueOut(
        items=out,
        ready_count=sum(1 for o in out if o.status is ApplyStatus.READY),
        policy=policy,
        policy_source=source,
        policy_problems=problems,
    )


async def ready_count(db: AsyncSession, owner_id: uuid.UUID) -> int:
    return await repository.count_ready(db, owner_id)


# --- deciding -------------------------------------------------------------------------------


async def _item(db: AsyncSession, owner_id: uuid.UUID, item_id: uuid.UUID) -> ApplyItem:
    item = await repository.get(db, owner_id, item_id, lock=True)
    if item is None:
        raise ProblemError(404, "Not found", "That item is not on your list.")
    return item


def _wrong_state(item: ApplyItem, action: str) -> ProblemError:
    return ProblemError(
        409, "Already decided", f"This item is {item.status.value}, so it cannot be {action}."
    )


async def _finish(
    db: AsyncSession,
    owner_id: uuid.UUID,
    item: ApplyItem,
    change: StatusChange | None,
    today: date,
) -> ApplyItemOut:
    """Save the item's new state together with the tracker change (one commit), then re-read."""
    job_id = item.job_id
    if change is None:
        await db.commit()
    else:
        job = await tracker_service.get_job(db, owner_id, job_id)
        application = job.application
        await tracker_service.change_status(
            db,
            owner_id,
            application.id,
            change.model_copy(update={"expected_version": application.version}),
            today=today,
        )
    item = await _item(db, owner_id, item.id)
    return _out(item, await tracker_service.get_job(db, owner_id, job_id))


async def approve(
    db: AsyncSession,
    owner_id: uuid.UUID,
    item_id: uuid.UUID,
    note: str | None,
    *,
    today: date,
    now: datetime | None = None,
) -> ApplyItemOut:
    """You read it and want to apply: the job becomes Shortlisted. Nothing is sent."""
    item = await _item(db, owner_id, item_id)
    if item.status not in (ApplyStatus.READY, ApplyStatus.BLOCKED):
        raise _wrong_state(item, "approved")
    item.status, item.decided_at = ApplyStatus.APPROVED, now or datetime.now(UTC)
    if note:
        item.decision_note = note
    job = await tracker_service.get_job(db, owner_id, item.job_id)
    change = (
        StatusChange(
            status=Status.SHORTLISTED,
            expected_version=1,
            note="Approved from the daily apply list." + (f" {note}" if note else ""),
        )
        if job.application.status is Status.NEW
        else None
    )
    return await _finish(db, owner_id, item, change, today)


async def mark_applied(
    db: AsyncSession,
    owner_id: uuid.UUID,
    item_id: uuid.UUID,
    note: str | None,
    *,
    today: date,
    now: datetime | None = None,
) -> ApplyItemOut:
    """You applied yourself: the job becomes Applied - Pending, with a follow-up date."""
    item = await _item(db, owner_id, item_id)
    if item.status is not ApplyStatus.APPROVED:
        raise ProblemError(
            409, "Approve it first", "Approve the item after reading it, then say you applied."
        )
    item.status, item.decided_at = ApplyStatus.APPLIED, now or datetime.now(UTC)
    if note:
        item.decision_note = note
    job = await tracker_service.get_job(db, owner_id, item.job_id)
    change = (
        StatusChange(
            status=Status.APPLIED_PENDING,
            expected_version=1,
            note="Applied (marked from the daily apply list)." + (f" {note}" if note else ""),
            next_followup_on=today + timedelta(days=FOLLOWUP_DAYS),
        )
        if job.application.status in (Status.NEW, Status.SHORTLISTED)
        else None
    )
    return await _finish(db, owner_id, item, change, today)


async def skip(
    db: AsyncSession,
    owner_id: uuid.UUID,
    item_id: uuid.UUID,
    note: str | None,
    *,
    today: date,
    now: datetime | None = None,
) -> ApplyItemOut:
    """Not for you. The job stays in the tracker as it was and is not listed again."""
    item = await _item(db, owner_id, item_id)
    if item.status not in (ApplyStatus.READY, ApplyStatus.APPROVED, ApplyStatus.BLOCKED):
        raise _wrong_state(item, "skipped")
    item.status, item.decided_at = ApplyStatus.SKIPPED, now or datetime.now(UTC)
    if note:
        item.decision_note = note
    return await _finish(db, owner_id, item, None, today)
