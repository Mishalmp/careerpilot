import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.errors import ProblemError
from careerpilot.modules.stories import repository, rules
from careerpilot.modules.stories.models import StarStory
from careerpilot.modules.stories.schemas import StoryCreate, StoryOut, StoryUpdate


def _out(story: StarStory) -> StoryOut:
    return StoryOut(
        id=story.id,
        title=story.title,
        situation=story.situation,
        task=story.task,
        action=story.action,
        result=story.result,
        tags=story.tags,
        evidence=story.evidence,
        hints=rules.hints(story.situation, story.task, story.action, story.result, story.evidence),
        updated_at=story.updated_at,
    )


async def list_stories(
    db: AsyncSession, owner_id: uuid.UUID, *, tag: str | None, query: str | None
) -> list[StoryOut]:
    wanted = " ".join(tag.lower().split()) if tag else None
    rows = await repository.list_stories(db, owner_id, tag=wanted, query=query)
    return [_out(s) for s in rows]


async def create(db: AsyncSession, owner_id: uuid.UUID, data: StoryCreate) -> StoryOut:
    story = repository.add(db, owner_id, **data.model_dump())
    await db.commit()
    await db.refresh(story)
    return _out(story)


async def update(
    db: AsyncSession, owner_id: uuid.UUID, story_id: uuid.UUID, data: StoryUpdate
) -> StoryOut:
    story = await repository.get(db, owner_id, story_id)
    if story is None:
        raise ProblemError(404, "Not found", "Story not found.")
    for field in data.model_fields_set:
        value = getattr(data, field)
        if value is None and field != "evidence":
            continue  # only evidence may be cleared
        setattr(story, field, value)
    await db.commit()
    await db.refresh(story)
    return _out(story)


async def delete(db: AsyncSession, owner_id: uuid.UUID, story_id: uuid.UUID) -> None:
    if not await repository.delete_story(db, owner_id, story_id):
        raise ProblemError(404, "Not found", "Story not found.")
    await db.commit()
