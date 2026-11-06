"""The CV-derived profile: skills and role titles come from the CV text and can be edited."""

import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.profile import repository, rules
from careerpilot.modules.profile.models import UserProfile
from careerpilot.modules.profile.schemas import CvIn, ProfileOut, ProfileUpdate
from careerpilot.modules.scoring import service as scoring_service

MAX_SKILLS = 60
MAX_TITLES = 12


def _out(profile: UserProfile | None) -> ProfileOut:
    if profile is None:
        return ProfileOut(
            has_cv=False, skills=[], role_titles=[], years_experience=None, updated_at=None
        )
    return ProfileOut(
        has_cv=bool(profile.cv_text),
        skills=list(profile.skills or []),
        role_titles=list(profile.role_titles or []),
        years_experience=profile.years_experience,
        updated_at=profile.updated_at,
    )


async def get_profile(db: AsyncSession, owner_id: uuid.UUID) -> ProfileOut:
    return _out(await repository.get(db, owner_id))


async def owners_with_profile(db: AsyncSession) -> list[uuid.UUID]:
    return await repository.owners_with_profile(db)


async def analyse_cv(
    db: AsyncSession, owner_id: uuid.UUID, data: CvIn, content_dir: Path
) -> ProfileOut:
    """Read the CV with rules (no model, nothing leaves this computer) and replace the profile's
    skills, titles and years with what it finds. Earlier hand edits are overwritten: analysing again
    means "start from this CV"."""
    profile = await repository.get(db, owner_id) or repository.add(db, owner_id)
    profile.cv_text = data.text
    profile.skills = scoring_service.detect_skills(content_dir, data.text)[:MAX_SKILLS]
    profile.role_titles = rules.role_titles(data.text, MAX_TITLES)
    profile.years_experience = rules.years_experience(data.text)
    await db.commit()
    await db.refresh(profile)
    return _out(profile)


async def update_profile(db: AsyncSession, owner_id: uuid.UUID, data: ProfileUpdate) -> ProfileOut:
    profile = await repository.get(db, owner_id) or repository.add(db, owner_id)
    if "skills" in data.model_fields_set and data.skills is not None:
        profile.skills = rules.clean_list(data.skills, limit=MAX_SKILLS)
    if "role_titles" in data.model_fields_set and data.role_titles is not None:
        profile.role_titles = rules.clean_list(data.role_titles, limit=MAX_TITLES)
    if "years_experience" in data.model_fields_set:
        profile.years_experience = data.years_experience
    await db.commit()
    await db.refresh(profile)
    return _out(profile)


async def clear_cv(db: AsyncSession, owner_id: uuid.UUID) -> None:
    """Forget the stored CV text (the derived skills and titles stay until edited)."""
    profile = await repository.get(db, owner_id)
    if profile is not None:
        profile.cv_text = None
        await db.commit()
