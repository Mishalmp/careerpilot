"""All SQL for the profile. Scoped by owner_id."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.profile.models import UserProfile


async def get(db: AsyncSession, owner_id: uuid.UUID) -> UserProfile | None:
    return await db.scalar(select(UserProfile).where(UserProfile.owner_id == owner_id))


def add(db: AsyncSession, owner_id: uuid.UUID) -> UserProfile:
    profile = UserProfile(owner_id=owner_id, skills=[], role_titles=[])
    db.add(profile)
    return profile
