import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, status
from pydantic import BaseModel

from careerpilot.core.deps import AppSettings, DbSession
from careerpilot.modules.auth.dependencies import Authenticated
from careerpilot.modules.learn import service
from careerpilot.modules.learn.enums import QuestionStatus, QuestionType
from careerpilot.modules.learn.schemas import (
    LearnAnswerIn,
    LearnAnswerOut,
    LearnCheckpointCreate,
    LearnCheckpointOut,
    LearnCheckpointSave,
    LearnCheckpointSummary,
    LearnQuestionCreate,
    LearnQuestionOut,
    LearnQuestionUpdate,
    LearnReviewQueue,
    LearnStats,
    LearnTopicCreate,
    LearnTopicOut,
    LearnTopicUpdate,
)

router = APIRouter(prefix="/learn", tags=["learn"])


class LearnQuestionPage(BaseModel):
    items: list[LearnQuestionOut]
    total: int


def _now() -> datetime:
    return datetime.now(UTC)


@router.get("/topics", operation_id="list_learn_topics")
async def list_topics(
    session: Authenticated, db: DbSession, archived: bool = False
) -> list[LearnTopicOut]:
    return await service.list_topics(db, session.user_id, _now(), include_archived=archived)


@router.post("/topics", operation_id="create_learn_topic", status_code=status.HTTP_201_CREATED)
async def create_topic(
    body: LearnTopicCreate, session: Authenticated, db: DbSession
) -> LearnTopicOut:
    return await service.create_topic(db, session.user_id, body)


@router.patch("/topics/{topic_id}", operation_id="update_learn_topic")
async def update_topic(
    topic_id: uuid.UUID, body: LearnTopicUpdate, session: Authenticated, db: DbSession
) -> LearnTopicOut:
    return await service.update_topic(db, session.user_id, topic_id, body, _now())


@router.delete(
    "/topics/{topic_id}", operation_id="delete_learn_topic", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_topic(topic_id: uuid.UUID, session: Authenticated, db: DbSession) -> None:
    await service.delete_topic(db, session.user_id, topic_id)


@router.get("/questions", operation_id="list_learn_questions")
async def list_questions(
    session: Authenticated,
    db: DbSession,
    topic_id: uuid.UUID | None = None,
    status_filter: Annotated[QuestionStatus | None, Query(alias="status")] = None,
    type_filter: Annotated[QuestionType | None, Query(alias="type")] = None,
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> LearnQuestionPage:
    items, total = await service.list_questions(
        db,
        session.user_id,
        topic_id=topic_id,
        status=status_filter,
        kind=type_filter,
        query=q,
        limit=limit,
        offset=offset,
    )
    return LearnQuestionPage(items=items, total=total)


@router.post(
    "/questions", operation_id="create_learn_question", status_code=status.HTTP_201_CREATED
)
async def create_question(
    body: LearnQuestionCreate, session: Authenticated, db: DbSession
) -> LearnQuestionOut:
    return await service.create_question(db, session.user_id, body, _now())


@router.get("/questions/{question_id}", operation_id="get_learn_question")
async def get_question(
    question_id: uuid.UUID, session: Authenticated, db: DbSession
) -> LearnQuestionOut:
    return await service.get_question(db, session.user_id, question_id)


@router.patch("/questions/{question_id}", operation_id="update_learn_question")
async def update_question(
    question_id: uuid.UUID, body: LearnQuestionUpdate, session: Authenticated, db: DbSession
) -> LearnQuestionOut:
    return await service.update_question(db, session.user_id, question_id, body)


@router.delete(
    "/questions/{question_id}",
    operation_id="delete_learn_question",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_question(question_id: uuid.UUID, session: Authenticated, db: DbSession) -> None:
    await service.delete_question(db, session.user_id, question_id)


@router.post("/questions/{question_id}/answer", operation_id="answer_learn_question")
async def answer_question(
    question_id: uuid.UUID, body: LearnAnswerIn, session: Authenticated, db: DbSession
) -> LearnAnswerOut:
    return await service.answer(db, session.user_id, question_id, body, _now())


@router.get("/review", operation_id="get_learn_review_queue")
async def review_queue(
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
    limit: int = Query(default=20, ge=1, le=50),
) -> LearnReviewQueue:
    return await service.review_queue(db, session.user_id, _now(), settings.timezone, limit=limit)


@router.get("/stats", operation_id="get_learn_stats")
async def learn_stats(session: Authenticated, db: DbSession, settings: AppSettings) -> LearnStats:
    return await service.stats(db, session.user_id, _now(), settings.timezone)


@router.post(
    "/checkpoints", operation_id="create_learn_checkpoint", status_code=status.HTTP_201_CREATED
)
async def create_checkpoint(
    body: LearnCheckpointCreate, session: Authenticated, db: DbSession
) -> LearnCheckpointOut:
    return await service.create_checkpoint(db, session.user_id, body, _now())


@router.get("/checkpoints", operation_id="list_learn_checkpoints")
async def list_checkpoints(
    session: Authenticated, db: DbSession, limit: Annotated[int, Query(ge=1, le=100)] = 20
) -> list[LearnCheckpointSummary]:
    return await service.list_checkpoints(db, session.user_id, limit)


@router.get("/checkpoints/{checkpoint_id}", operation_id="get_learn_checkpoint")
async def get_checkpoint(
    checkpoint_id: uuid.UUID, session: Authenticated, db: DbSession
) -> LearnCheckpointOut:
    return await service.get_checkpoint(db, session.user_id, checkpoint_id, _now())


@router.put(
    "/checkpoints/{checkpoint_id}/items/{position}", operation_id="save_learn_checkpoint_item"
)
async def save_checkpoint_item(
    checkpoint_id: uuid.UUID,
    position: int,
    body: LearnCheckpointSave,
    session: Authenticated,
    db: DbSession,
) -> LearnCheckpointOut:
    return await service.save_checkpoint_item(
        db, session.user_id, checkpoint_id, position, body, _now()
    )


@router.post("/checkpoints/{checkpoint_id}/submit", operation_id="submit_learn_checkpoint")
async def submit_checkpoint(
    checkpoint_id: uuid.UUID, session: Authenticated, db: DbSession
) -> LearnCheckpointOut:
    return await service.submit_checkpoint(db, session.user_id, checkpoint_id, _now())
