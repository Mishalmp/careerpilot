"""The profile: who you are, what you are looking for, and what your CV says.

Account setup fills it in (name, current role, the roles you want, where, pay, public links, a CV).
Nothing in the app is hard-coded to one person: scoring, research and the daily apply list all read
this. The CV file is read in memory and never stored; the CV text is stored but never returned.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.errors import ProblemError
from careerpilot.core.fetcher import Fetcher, FetchError
from careerpilot.modules.profile import cvfile, github, repository, rules
from careerpilot.modules.profile.models import UserProfile
from careerpilot.modules.profile.schemas import (
    CvIn,
    CvInfo,
    CvUploadOut,
    GithubLanguage,
    GithubReading,
    ProfileLink,
    ProfileOut,
    ProfileUpdate,
    SetupStatus,
)
from careerpilot.modules.scoring import service as scoring_service

MAX_SKILLS = 60
MAX_TITLES = 12
CV_READ_SECONDS = 30  # a damaged or hostile file must not tie the server up
TOP_LANGUAGES = 8


def missing_steps(profile: UserProfile | None) -> list[str]:
    """What account setup still needs, in the order a person does it."""
    if profile is None:
        return ["your name", "your current role", "the roles you want", "your CV or your skills"]
    need: list[str] = []
    if not (profile.full_name or "").strip():
        need.append("your name")
    if not (profile.current_role or "").strip():
        need.append("your current role")
    if not profile.target_roles:
        need.append("the roles you want")
    if not (profile.cv_text or profile.skills):
        need.append("your CV or your skills")
    return need


def _out(profile: UserProfile | None) -> ProfileOut:
    missing = missing_steps(profile)
    if profile is None:
        return ProfileOut(
            has_cv=False,
            skills=[],
            role_titles=[],
            years_experience=None,
            updated_at=None,
            full_name=None,
            headline=None,
            current_role=None,
            location=None,
            target_roles=[],
            target_levels=[],
            regions=[],
            work_modes=[],
            needs_visa=False,
            salary_floor_lpa=None,
            salary_target_lpa=None,
            links=[],
            cv=CvInfo(has_cv=False, source=None, filename=None, chars=None),
            setup=SetupStatus(complete=False, completed_at=None, missing=missing),
        )
    has_cv = bool(profile.cv_text)
    return ProfileOut(
        has_cv=has_cv,
        skills=list(profile.skills or []),
        role_titles=list(profile.role_titles or []),
        years_experience=profile.years_experience,
        updated_at=profile.updated_at,
        full_name=profile.full_name,
        headline=profile.headline,
        current_role=profile.current_role,
        location=profile.location,
        target_roles=list(profile.target_roles or []),
        target_levels=list(profile.target_levels or []),
        regions=list(profile.regions or []),
        work_modes=list(profile.work_modes or []),
        needs_visa=bool(profile.needs_visa),
        salary_floor_lpa=float(profile.salary_floor_lpa)
        if profile.salary_floor_lpa is not None
        else None,
        salary_target_lpa=float(profile.salary_target_lpa)
        if profile.salary_target_lpa is not None
        else None,
        links=[ProfileLink.model_validate(link) for link in profile.links or []],
        cv=CvInfo(
            has_cv=has_cv,
            source=profile.cv_source,
            filename=profile.cv_filename,
            chars=profile.cv_chars,
        ),
        setup=SetupStatus(
            complete=profile.setup_completed_at is not None and not missing,
            completed_at=profile.setup_completed_at,
            missing=missing,
        ),
    )


async def get_profile(db: AsyncSession, owner_id: uuid.UUID) -> ProfileOut:
    return _out(await repository.get(db, owner_id))


async def owners_with_profile(db: AsyncSession) -> list[uuid.UUID]:
    return await repository.owners_with_profile(db)


async def _read_cv_text(
    db: AsyncSession,
    owner_id: uuid.UUID,
    text: str,
    *,
    source: str,
    filename: str | None,
    content_dir: Path,
) -> tuple[UserProfile, list[str]]:
    """Read CV text with rules (no model, nothing leaves this computer) and replace the profile's
    skills, titles and years with what it finds. Earlier hand edits to those are overwritten:
    reading a CV again means "start from this CV". Your name and current role are only filled when
    they are empty."""
    profile = await repository.get(db, owner_id) or repository.add(db, owner_id)
    notes: list[str] = []
    profile.cv_text = text
    profile.cv_source, profile.cv_filename, profile.cv_chars = source, filename, len(text)
    profile.skills = scoring_service.detect_skills(content_dir, text)[:MAX_SKILLS]
    profile.role_titles = rules.role_titles(text, MAX_TITLES)
    profile.years_experience = rules.years_experience(text)
    if not (profile.full_name or "").strip() and (name := rules.guess_name(text)):
        profile.full_name = name
        notes.append(f"Took your name from the top of the CV ({name}). Fix it if it is wrong.")
    if not (profile.current_role or "").strip() and profile.role_titles:
        profile.current_role = profile.role_titles[0]
        notes.append(
            f"Guessed your current role from the CV ({profile.current_role}). Fix it if wrong."
        )
    if not profile.skills:
        notes.append("No known skills were found in the text. Add yours by hand below.")
    return profile, notes


async def analyse_cv(
    db: AsyncSession, owner_id: uuid.UUID, data: CvIn, content_dir: Path
) -> ProfileOut:
    profile, _ = await _read_cv_text(
        db, owner_id, data.text, source="paste", filename=None, content_dir=content_dir
    )
    await db.commit()
    await db.refresh(profile)
    return _out(profile)


async def upload_cv(
    db: AsyncSession,
    owner_id: uuid.UUID,
    filename: str | None,
    data: bytes,
    content_dir: Path,
    ocr: cvfile.OcrFactory,
) -> CvUploadOut:
    """Read an uploaded CV file (PDF, Word, text or a picture). The file itself is not kept."""
    try:
        read = await asyncio.wait_for(
            asyncio.to_thread(cvfile.read_cv, data, ocr), timeout=CV_READ_SECONDS
        )
    except cvfile.CvReadError as exc:
        raise ProblemError(422, "This CV could not be read", str(exc)) from exc
    except TimeoutError as exc:
        raise ProblemError(
            422, "This CV took too long to read", "Try a smaller file or paste the text."
        ) from exc
    profile, notes = await _read_cv_text(
        db,
        owner_id,
        read.text,
        source=read.source,
        filename=cvfile.safe_filename(filename),
        content_dir=content_dir,
    )
    await db.commit()
    await db.refresh(profile)
    return CvUploadOut(profile=_out(profile), notes=[*read.notes, *notes])


_PLAIN = ("full_name", "headline", "current_role", "location", "needs_visa")
_LISTS = ("target_roles", "target_levels", "regions", "work_modes")


async def update_profile(db: AsyncSession, owner_id: uuid.UUID, data: ProfileUpdate) -> ProfileOut:
    profile = await repository.get(db, owner_id) or repository.add(db, owner_id)
    sent = data.model_fields_set
    if "skills" in sent and data.skills is not None:
        profile.skills = rules.clean_list(data.skills, limit=MAX_SKILLS)
    if "role_titles" in sent and data.role_titles is not None:
        profile.role_titles = rules.clean_list(data.role_titles, limit=MAX_TITLES)
    if "years_experience" in sent:
        profile.years_experience = data.years_experience
    for name in _PLAIN:
        if name in sent:
            value: Any = getattr(data, name)
            if name == "needs_visa":
                value = bool(value)
            elif isinstance(value, str):
                value = value.strip() or None
            setattr(profile, name, value)
    for name in _LISTS:
        if name in sent and getattr(data, name) is not None:
            setattr(profile, name, rules.clean_list(getattr(data, name), limit=8))
    for name in ("salary_floor_lpa", "salary_target_lpa"):
        if name in sent:
            setattr(profile, name, getattr(data, name))
    if "links" in sent and data.links is not None:
        profile.links = [link.model_dump(mode="json") for link in data.links]
    await db.commit()
    await db.refresh(profile)
    return _out(profile)


async def complete_setup(
    db: AsyncSession, owner_id: uuid.UUID, now: datetime | None = None
) -> ProfileOut:
    """Mark account setup finished, once the required answers are there."""
    profile = await repository.get(db, owner_id)
    need = missing_steps(profile)
    if profile is None or need:
        raise ProblemError(422, "Setup is not finished", "Still needed: " + ", ".join(need) + ".")
    profile.setup_completed_at = now or datetime.now(UTC)
    await db.commit()
    await db.refresh(profile)
    return _out(profile)


async def read_github(
    db: AsyncSession, owner_id: uuid.UUID, fetcher: Fetcher, content_dir: Path
) -> GithubReading:
    """Suggest skills from the languages in your public GitHub repositories. Nothing is saved."""
    profile = await get_profile(db, owner_id)
    link = next((link for link in profile.links if link.kind == "github"), None)
    user = github.username(link.url) if link else None
    if user is None:
        raise ProblemError(
            409, "No GitHub link", "Add your GitHub profile link (github.com/your-name) first."
        )
    try:
        page = await fetcher.fetch(
            f"https://api.github.com/users/{user}/repos?per_page=100&sort=pushed&type=owner"
        )
    except FetchError as exc:
        raise ProblemError(
            502, "GitHub could not be read", f"{exc.message} GitHub allows 60 requests an hour."
        ) from exc
    try:
        repos = github.parse_repos(page.text)
    except github.GithubReadError as exc:
        raise ProblemError(502, "GitHub could not be read", str(exc)) from exc
    top = repos.languages.most_common(TOP_LANGUAGES)
    suggested = scoring_service.detect_skills(
        content_dir, " ".join(name for name, _ in top) + "\n" + repos.text
    )
    notes = [] if repos.read else ["No public repositories of your own were found."]
    if repos.read >= 100:
        notes.append("Only the 100 most recently pushed repositories were read.")
    return GithubReading(
        username=user,
        repos_read=repos.read,
        languages=[GithubLanguage(name=n, repos=c) for n, c in top],
        suggested_skills=[s for s in suggested if s not in profile.skills],
        notes=notes,
    )


async def clear_cv(db: AsyncSession, owner_id: uuid.UUID) -> None:
    """Forget the stored CV text (the derived skills and titles stay until edited)."""
    profile = await repository.get(db, owner_id)
    if profile is not None:
        profile.cv_text = None
        profile.cv_source = profile.cv_filename = profile.cv_chars = None
        await db.commit()
