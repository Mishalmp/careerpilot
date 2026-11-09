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
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
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
from careerpilot.modules.discovery import service as discovery_service
from careerpilot.modules.discovery.locations import SearchSpec
from careerpilot.modules.discovery.schemas import Listing
from careerpilot.modules.profile import service as profile_service
from careerpilot.modules.profile.schemas import ProfileOut
from careerpilot.modules.scoring import service as scoring_service
from careerpilot.modules.tasks import service as tasks_service
from careerpilot.modules.tasks.enums import TaskKind
from careerpilot.modules.tracker import service as tracker_service
from careerpilot.modules.tracker.enums import Status, WorkMode
from careerpilot.modules.tracker.filters import JobFilters
from careerpilot.modules.tracker.schemas import CompanyUpdate, StatusChange
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


def _refusal(job: JobRecord, policy: Policy, today: date, specs: list[SearchSpec]) -> str | None:
    """Why the policy's hard rules refuse a job, in words (None when they allow it).

    A field the post does not state never excludes a job.
    """
    if policy.regions and job.region is not None and job.region.value not in policy.regions:
        return "outside the regions in your policy"
    if (
        policy.work_modes
        and job.work_mode is not None
        and job.work_mode.value not in policy.work_modes
    ):
        return "not a way of working in your policy"
    if policy.max_age_days and job.posted_on and (today - job.posted_on).days > policy.max_age_days:
        return f"posted more than {policy.max_age_days} days ago"
    judged = bool(
        specs and (job.location_text or job.work_mode)
    )  # nothing stated: nothing to judge
    if judged and not discovery_service.fits_searches(
        specs,
        title=job.title,
        location=job.location_text,
        remote=job.work_mode is WorkMode.REMOTE,
    ):
        return "outside the places and ways you search"
    skipped = {name.casefold() for name in policy.skip_companies}
    if job.company.name.casefold() in skipped:
        return "the company is on your skip list"
    if policy.require_apply_link and not (job.apply_url or job.jd_url):
        return "no link to apply"
    return None


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
    specs: list[SearchSpec],
    tally: Counter[str] | None = None,
) -> list[tuple[JobRecord, matching.Match]]:
    """Jobs the policy allows with a match at or above the minimum, best first.

    `tally` (if given) is filled with how many jobs were left out and why.
    """
    ranked: list[tuple[JobRecord, matching.Match]] = []
    for job in jobs:
        reason = _refusal(job, policy, today, specs)
        if reason is not None:
            if tally is not None:
                tally[reason] += 1
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
        elif tally is not None:
            tally[f"match below {policy.min_match_score} (the minimum in your policy)"] += 1
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


async def _pool(db: AsyncSession, owner_id: uuid.UUID) -> list[PoolEntry]:
    """Jobs in your tracker with an estimated pay: the source of earlier-post and market ranges."""
    return [
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


# --- building -------------------------------------------------------------------------------


async def _explain_choice(
    open_count: int, tally: Counter[str], listed_before: int, available: int
) -> None:
    """Write, in plain words, what the build had to choose from and why jobs were left out."""
    await tasks_service.note(f"Your tracker has {open_count} open job(s) (New or Shortlisted).")
    if open_count == 0:
        await tasks_service.note(
            "Nothing to choose from. Follow job boards on the Discover page, paste job links on "
            "the Jobs page, or add jobs by hand; boards only add jobs that fit your searches."
        )
        return
    if tally:
        parts = [f"{n} {why}" for why, n in tally.most_common(5)]
        await tasks_service.note("Left out: " + "; ".join(parts) + ".")
    if listed_before:
        await tasks_service.note(f"{listed_before} good match(es) were already on an earlier list.")
    await tasks_service.note(f"{available} job(s) are available to put on today's list.")


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

    if policy.auto_add_limit:
        await tasks_service.step("Adding new listings from your boards to the tracker")

        def score(listing: Listing) -> int:
            # A listing from a board has only a title to judge by. Skills named in a long
            # description can make a product manager look like a fit, so the title must also be
            # like a role on your CV before it is copied into your tracker.
            if not matching.is_development_title(listing.title) or not any(
                matching.similar_titles(listing.title, t) for t in profile.role_titles
            ):
                return 0
            return matching.match(
                job_title=listing.title,
                job_skills=scoring_service.detect_skills(settings.content_dir, listing.title),
                profile_skills=profile.skills,
                profile_titles=profile.role_titles,
                posted_on=listing.published_on,
                today=today,
            ).score

        auto = await discovery_service.auto_accept(
            db,
            owner_id,
            fetcher,
            limit=policy.auto_add_limit,
            today=today,
            score=score,
            minimum=policy.min_match_score,
        )
        said = f"Copied {auto.added} new listing{'s' if auto.added != 1 else ''} from the boards "
        said += "you follow into your tracker."
        if auto.unwanted:
            said += f" {auto.unwanted} stayed waiting because their title does not match your CV."
        if auto.failed:
            said += f" {auto.failed} could not be added."
        await tasks_service.note(said)

    specs = await discovery_service.search_specs(db, owner_id) if policy.use_search_profiles else []
    already = await repository.listed_job_ids(db, owner_id)
    open_jobs = await _open_jobs(db, owner_id, JobFilters(statuses=OPEN))
    tally: Counter[str] = Counter()
    ranked = _rank(open_jobs, policy, profile, settings.content_dir, today, specs, tally)
    candidates = [pair for pair in ranked if pair[0].id not in already]
    await _explain_choice(len(open_jobs), tally, len(ranked) - len(candidates), len(candidates))
    pool = await _pool(db, owner_id)

    # An earlier build that stopped part-way (a crash, a restart) leaves items that were listed but
    # never looked up. Finish those first: this is what "retry continues from where it stopped"
    # means for this task.
    held = 0
    for stale in await repository.unfinished(db, owner_id):
        job = await tracker_service.get_job(db, owner_id, stale.job_id)
        await tasks_service.step(f"Finishing {job.company.name}: {job.title}")
        found = matching.match(
            job_title=job.title,
            job_skills=scoring_service.detect_skills(settings.content_dir, _job_text(job)),
            profile_skills=profile.skills,
            profile_titles=profile.role_titles,
            posted_on=job.posted_on or job.found_on,
            today=today,
        )
        if await _fill(
            db,
            owner_id,
            stale,
            job,
            found,
            pool,
            policy,
            settings,
            search,
            fetcher,
            today,
            now,
            deep=stale.deep,
        ):
            held += 1
        await db.commit()

    counted = await repository.count_counted_on(db, owner_id, today)
    remaining = policy.daily_limit - counted
    if remaining <= 0:
        await tasks_service.note(
            f"Today's limit of {policy.daily_limit} is already reached ({counted} listed)."
        )
        return BuildResult(0, held, 0)

    listed = examined = 0
    for job, found in candidates[: remaining * EXAMINE_FACTOR + 2]:
        if listed >= remaining:
            break
        examined += 1
        await tasks_service.step(
            f"Researching {job.company.name}: {job.title}", done=listed, total=remaining
        )
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
        deep = counted + listed < policy.deep_limit
        item.deep = deep
        if await _fill(
            db,
            owner_id,
            item,
            job,
            found,
            pool,
            policy,
            settings,
            search,
            fetcher,
            today,
            now,
            deep=deep,
        ):
            held += 1
        else:
            listed += 1
        await db.commit()
    await tasks_service.note(
        f"Listed {listed} job(s) for today; {held} more were held back for a reason shown on them."
    )
    return BuildResult(listed, held, examined)


# Pages where a job is hosted for many companies: their address says nothing about the employer.
_JOB_BOARD_HOSTS = (
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "workable.com",
    "smartrecruiters.com",
    "myworkdayjobs.com",
    "linkedin.com",
    "indeed.com",
    "naukri.com",
    "glassdoor.com",
    "wellfound.com",
    "instahyre.com",
    "bamboohr.com",
    "jobvite.com",
    "icims.com",
    "recruitee.com",
    "breezy.hr",
)


async def _remember_website(
    db: AsyncSession, owner_id: uuid.UUID, job: JobRecord, policy: Policy
) -> None:
    """A company found through a job board has no website on file, so its checks could never run.
    When the post itself sits on the employer's own site, use that address (only if none is set)."""
    if not policy.enrich_with_web or job.company.website:
        return
    link = job.apply_url or job.jd_url
    parts = urlsplit(link) if link else None
    host = (parts.hostname or "").lower() if parts else ""
    if not host or any(host == h or host.endswith("." + h) for h in _JOB_BOARD_HOSTS):
        return
    await tracker_service.update_company(
        db,
        owner_id,
        job.id,
        CompanyUpdate(website=f"{parts.scheme}://{host}"),  # pyright: ignore[reportOptionalMemberAccess]
    )
    await db.refresh(job.company)


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
    *,
    deep: bool = True,
) -> bool:
    """Look everything up for one item. Returns True when the item was held back."""
    notes: list[str] = []
    held_reason: str | None = None

    if deep:
        await _remember_website(db, owner_id, job, policy)
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
            if deep and policy.enrich_with_web and fetcher is not None
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

    if deep and policy.enrich_with_web:
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
    if not deep:
        notes.append(
            "Not researched on the web yet: the day's deep-research limit was reached. "
            "Press Research this job to do it now."
        )
    elif search is None and policy.enrich_with_web:
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
        deep=item.deep,
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
        last_build=await tasks_service.latest_results(db, owner_id, TaskKind.APPLY_QUEUE),
        policy=policy,
        policy_source=source,
        policy_problems=problems,
    )


async def deepen(
    db: AsyncSession,
    owner_id: uuid.UUID,
    item_id: uuid.UUID,
    *,
    today: date,
    settings: Settings,
    search: SearchProvider | None,
    fetcher: Fetcher | None,
    now: datetime | None = None,
) -> ApplyItemOut:
    """Research one listed job on the web now (pay, interview, same job elsewhere, company check),
    for an item that was listed without it because the day's deep-research limit was reached."""
    now = now or datetime.now(UTC)
    item = await _item(db, owner_id, item_id)
    if item.status not in (ApplyStatus.READY, ApplyStatus.APPROVED, ApplyStatus.BLOCKED):
        raise _wrong_state(item, "researched")
    policy, _ = policy_for(settings.content_dir)
    profile = await profile_service.get_profile(db, owner_id)
    job = await tracker_service.get_job(db, owner_id, item.job_id)
    found = matching.match(
        job_title=job.title,
        job_skills=scoring_service.detect_skills(settings.content_dir, _job_text(job)),
        profile_skills=profile.skills,
        profile_titles=profile.role_titles,
        posted_on=job.posted_on or job.found_on,
        today=today,
    )
    pool = await _pool(db, owner_id)
    item.deep = True
    await _fill(
        db,
        owner_id,
        item,
        job,
        found,
        pool,
        policy,
        settings,
        search,
        fetcher,
        today,
        now,
        deep=True,
    )
    await db.commit()
    return _out(item, await tracker_service.get_job(db, owner_id, item.job_id))


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
