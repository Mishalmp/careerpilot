import hashlib
import uuid
from pathlib import Path
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.config import Settings
from careerpilot.core.errors import ProblemError
from careerpilot.core.evidence import quote_appears
from careerpilot.core.llm import LlmClient, call_llm_json
from careerpilot.core.prompts import data_block, load_prompt
from careerpilot.modules.profile.schemas import ProfileOut
from careerpilot.modules.scoring import repository
from careerpilot.modules.scoring.models import JobScore
from careerpilot.modules.scoring.profile import Profile, load_profile
from careerpilot.modules.scoring.rules import (
    SCORING_VERSION,
    Chance,
    Component,
    Priority,
    combine,
    company_component,
    growth_component,
    location_component,
    pay_component,
    seniority_component,
    skills_component,
)
from careerpilot.modules.scoring.schemas import (
    CHANCE_NOTE,
    ComponentOut,
    RawReading,
    ReadingOut,
    RedFlagOut,
    ScoreOut,
)
from careerpilot.modules.scoring.skills import (
    level_of_title,
    load_vocabulary,
    skills_in,
    years_required,
)
from careerpilot.modules.tracker import service as tracker_service
from careerpilot.modules.tracker.enums import Region
from careerpilot.modules.verification import service as verification_service

MAX_JD_CHARS = 12_000


def profile_for_scoring(mine: ProfileOut, content_dir: Path) -> Profile:
    """What a job is compared against: your account setup when it has skills, regions and years,
    otherwise `content/private/profile.yaml`, otherwise a 409 that says what to fill in."""
    regions = [Region(r) for r in mine.regions if r in {x.value for x in Region}]
    if mine.skills and regions and mine.years_experience is not None:
        levels = [lv for lv in mine.target_levels if lv in ("junior", "mid", "senior", "lead")]
        return Profile(
            years_experience=mine.years_experience,
            target_levels=levels or ["junior", "mid"],
            skills=mine.skills,
            regions=regions,
            needs_visa_sponsorship=mine.needs_visa,
            salary_floor_lpa=mine.salary_floor_lpa or None,
            salary_target_lpa=mine.salary_target_lpa or None,
        )
    try:
        return load_profile(content_dir)
    except ProblemError as exc:
        if exc.status != 409:
            raise
        need = [
            name
            for name, present in (
                ("skills", bool(mine.skills)),
                ("regions", bool(regions)),
                ("years of experience", mine.years_experience is not None),
            )
            if not present
        ]
        raise ProblemError(
            409, "Finish account setup first", "Your profile still needs: " + ", ".join(need) + "."
        ) from exc


def _profile_hash(profile: Profile) -> str:
    return hashlib.sha256(profile.model_dump_json().encode()).hexdigest()[:16]


def _out(row: JobScore, current_hash: str | None) -> ScoreOut:
    return ScoreOut(
        job_id=row.job_id,
        score=row.score,
        chance=cast(Chance, row.chance),
        chance_note=CHANCE_NOTE,
        priority=cast(Priority | None, row.priority),
        coverage=row.coverage,
        version=row.version,
        stale=row.version != SCORING_VERSION
        or (current_hash is not None and row.profile_hash != current_hash),
        components=[ComponentOut.model_validate(c) for c in row.components],
        blockers=row.blockers,
        reading=ReadingOut.model_validate(row.reading) if row.reading else None,
        computed_at=row.computed_at,
    )


async def get_score(
    db: AsyncSession,
    owner_id: uuid.UUID,
    job_id: uuid.UUID,
    settings: Settings,
    mine: ProfileOut,
) -> ScoreOut | None:
    await tracker_service.get_job(db, owner_id, job_id)  # 404 for jobs that are not yours
    row = await repository.get_score(db, owner_id, job_id)
    if row is None:
        return None
    try:
        current = _profile_hash(profile_for_scoring(mine, settings.content_dir))
    except ProblemError:
        current = None
    return _out(row, current)


async def read_description(
    db: AsyncSession,
    owner_id: uuid.UUID,
    llm: LlmClient,
    settings: Settings,
    jd_text: str,
) -> ReadingOut:
    """The model's reading of a description; its quoted warning signs are checked against it."""
    prompt = load_prompt(settings.prompts_dir, "jd-reading", 1)
    visible = jd_text[:MAX_JD_CHARS]
    raw = await call_llm_json(
        db,
        owner_id,
        llm,
        settings,
        prompt=prompt,
        user=data_block("job_description", visible),
        schema=RawReading,
    )
    kept = [
        RedFlagOut(text=f.text.strip(), quote=f.quote.strip())
        for f in raw.red_flags[:4]
        if f.text.strip() and quote_appears(f.quote, visible)
    ]
    return ReadingOut(
        summary=raw.summary.strip(),
        growth=raw.growth,
        growth_reason=raw.growth_reason.strip(),
        red_flags=kept,
        dropped_flags=len(raw.red_flags[:4]) - len(kept),
    )


async def score_job(
    db: AsyncSession,
    owner_id: uuid.UUID,
    job_id: uuid.UUID,
    *,
    settings: Settings,
    mine: ProfileOut,
    llm: LlmClient | None,
    use_ai: bool,
) -> ScoreOut:
    """Score one job against your profile and store the result. Safe to repeat."""
    job = await tracker_service.get_job(db, owner_id, job_id)
    profile = profile_for_scoring(mine, settings.content_dir)
    vocabulary = load_vocabulary(settings.content_dir)

    verification = await verification_service.get_verification(
        db, owner_id, job_id, ai_available=False
    )
    checked = any(check.source is not None for check in verification.checks)

    # The model's reading depends only on the description, so scoring again (a changed profile, a
    # new verification) reuses it. The description's hash is kept inside the stored reading.
    reading: ReadingOut | None = None
    jd_hash = hashlib.sha256((job.jd_text or "")[:MAX_JD_CHARS].encode()).hexdigest()[:16]
    if use_ai and llm is not None and job.jd_text:
        earlier = await repository.get_score(db, owner_id, job_id)
        if earlier is not None and earlier.reading and earlier.reading.get("jd_hash") == jd_hash:
            reading = ReadingOut.model_validate(earlier.reading)
        else:
            reading = await read_description(db, owner_id, llm, settings, job.jd_text)

    my_skills = {vocabulary.canonical(skill) for skill in profile.skills}
    jd_skills = skills_in(f"{job.title}\n{job.jd_text or ''}", vocabulary)
    components: list[Component] = [
        skills_component(jd_skills, my_skills),
        pay_component(float(job.est_ctc_lpa) if job.est_ctc_lpa is not None else None, profile),
        seniority_component(level_of_title(job.title), years_required(job.jd_text or ""), profile),
        company_component(verification.verdict if checked else None),
        location_component(job.region, job.work_mode, job.hiring_from_india, job.visa, profile),
        growth_component(
            reading.growth if reading else None, reading.growth_reason if reading else None
        ),
    ]
    total = combine(components)

    values: dict[str, Any] = {
        "version": SCORING_VERSION,
        "profile_hash": _profile_hash(profile),
        "score": total.score,
        "coverage": total.coverage,
        "chance": total.chance,
        "priority": total.priority,
        "components": [
            {"key": c.key, "weight": c.weight, "score": c.score, "detail": c.detail}
            for c in components
        ],
        "blockers": list(total.blockers),
        "reading": {**reading.model_dump(), "jd_hash": jd_hash} if reading else None,
    }
    stored = await repository.upsert_score(db, owner_id=owner_id, job_id=job_id, **values)
    await db.commit()
    return _out(stored, _profile_hash(profile))


async def scored_jobs(
    db: AsyncSession, owner_id: uuid.UUID
) -> list[tuple[uuid.UUID, str, int | None]]:
    """(job, chance label, score) for every scored job, for the calibration view."""
    return await repository.scored(db, owner_id)


def detect_skills(content_dir: Path, text: str) -> list[str]:
    """Skills from the shared vocabulary (content/skills.yaml) found in any text, sorted."""
    return sorted(skills_in(text, load_vocabulary(content_dir)))
