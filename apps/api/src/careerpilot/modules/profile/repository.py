"""All SQL for the profile. Scoped by owner_id."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.profile.models import UserProfile


async def get(db: AsyncSession, owner_id: uuid.UUID) -> UserProfile | None:
    return await db.scalar(select(UserProfile).where(UserProfile.owner_id == owner_id))


def add(db: AsyncSession, owner_id: uuid.UUID) -> UserProfile:
    profile = UserProfile(owner_id=owner_id, skills=[], role_titles=[])
    db.add(profile)
    return profile


async def owners_with_profile(db: AsyncSession) -> list[uuid.UUID]:
    """Users whose profile has any skill or role title (the daily jobs that need a CV)."""
    rows = await db.scalars(
        select(UserProfile.owner_id).where(
            (func.jsonb_array_length(UserProfile.skills) > 0)
            | (func.jsonb_array_length(UserProfile.role_titles) > 0)
        )
    )
    return list(rows)
