import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.stories.models import StarStory

LIMIT = 200


def _like(text: str) -> str:
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


async def list_stories(
    db: AsyncSession, owner_id: uuid.UUID, *, tag: str | None, query: str | None
) -> Sequence[StarStory]:
    statement = select(StarStory).where(StarStory.owner_id == owner_id)
    if tag:
        statement = statement.where(StarStory.tags.contains([tag]))
    if query:
        pattern = _like(query)
        statement = statement.where(
            or_(
                StarStory.title.ilike(pattern, escape="\\"),
                StarStory.action.ilike(pattern, escape="\\"),
                StarStory.result.ilike(pattern, escape="\\"),
            )
        )
    rows = await db.scalars(statement.order_by(StarStory.updated_at.desc()).limit(LIMIT))
    return rows.all()


async def get(db: AsyncSession, owner_id: uuid.UUID, story_id: uuid.UUID) -> StarStory | None:
    return await db.scalar(
        select(StarStory).where(StarStory.owner_id == owner_id, StarStory.id == story_id)
    )


def add(db: AsyncSession, owner_id: uuid.UUID, **fields: Any) -> StarStory:
    story = StarStory(owner_id=owner_id, **fields)
    db.add(story)
    return story


async def delete_story(db: AsyncSession, owner_id: uuid.UUID, story_id: uuid.UUID) -> bool:
    result = await db.execute(
        delete(StarStory)
        .where(StarStory.owner_id == owner_id, StarStory.id == story_id)
        .returning(StarStory.id)
    )
    return result.first() is not None
