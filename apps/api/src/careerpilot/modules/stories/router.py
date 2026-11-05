import uuid

from fastapi import APIRouter, Query, status

from careerpilot.core.deps import DbSession
from careerpilot.modules.auth.dependencies import Authenticated
from careerpilot.modules.stories import service
from careerpilot.modules.stories.schemas import StoryCreate, StoryOut, StoryUpdate

router = APIRouter(prefix="/stories", tags=["stories"])


@router.get("", operation_id="list_stories")
async def list_stories(
    session: Authenticated,
    db: DbSession,
    tag: str | None = Query(default=None, max_length=30),
    q: str | None = Query(default=None, max_length=100),
) -> list[StoryOut]:
    return await service.list_stories(db, session.user_id, tag=tag, query=q)


@router.post("", operation_id="create_story", status_code=status.HTTP_201_CREATED)
async def create_story(body: StoryCreate, session: Authenticated, db: DbSession) -> StoryOut:
    return await service.create(db, session.user_id, body)


@router.patch("/{story_id}", operation_id="update_story")
async def update_story(
    story_id: uuid.UUID, body: StoryUpdate, session: Authenticated, db: DbSession
) -> StoryOut:
    return await service.update(db, session.user_id, story_id, body)


@router.delete("/{story_id}", operation_id="delete_story", status_code=status.HTTP_204_NO_CONTENT)
async def delete_story(story_id: uuid.UUID, session: Authenticated, db: DbSession) -> None:
    await service.delete(db, session.user_id, story_id)
