import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from careerpilot.modules.learn.enums import (
    GradedBy,
    LearnTopicStatus,
    QuestionOrigin,
    QuestionStatus,
    QuestionType,
    Rating,
    TopicOrigin,
)
from careerpilot.modules.tracker.schemas import Url

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- topics ---


class LearnTopicCreate(BaseModel):
    title: Title
    summary: Text | None = None
    area: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None
    priority: Annotated[int, Field(ge=1, le=3)] = 2
    notes: Text | None = None


class LearnTopicUpdate(BaseModel):
    """Only the fields you send change."""

    title: Title | None = None
    summary: Text | None = None
    area: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None
    priority: Annotated[int, Field(ge=1, le=3)] | None = None
    status: LearnTopicStatus | None = None
    notes: Text | None = None
    archived: bool | None = None


class LearnTopicOut(_Out):
    id: uuid.UUID
    title: str
    summary: str | None
    area: str | None
    priority: int
    status: LearnTopicStatus
    origin: TopicOrigin
    notes: str | None
    archived: bool
    question_count: int = 0
    mastery: float | None = None  # 0 to 100, None until something was reviewed
    updated_at: datetime


# --- questions ---


class LearnOptionIn(BaseModel):
    text: Annotated[str, StringConstraints(max_length=500)]
    is_correct: bool
    rationale: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = (
        None
    )


class LearnSourceIn(BaseModel):
    url: Url
    title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    quote: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    fetched_on: date | None = None


class LearnQuestionCreate(BaseModel):
    topic_id: uuid.UUID
    type: QuestionType
    stem: Annotated[str, StringConstraints(max_length=2000)]
    explanation: Text | None = None
    difficulty: Annotated[int, Field(ge=1, le=5)] = 3
    options: Annotated[list[LearnOptionIn], Field(max_length=5)] = []
    sources: Annotated[list[LearnSourceIn], Field(max_length=5)] = []
    rubric: (
        Annotated[list[Annotated[str, StringConstraints(max_length=300)]], Field(max_length=6)]
        | None
    ) = None
    practice_slug: Annotated[str, StringConstraints(pattern=r"^[a-z0-9-]{1,80}$")] | None = None
    tags: Annotated[list[Tag], Field(max_length=8)] = []

    @field_validator("tags")
    @classmethod
    def _tidy(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(" ".join(t.lower().split()) for t in value))


class LearnQuestionUpdate(BaseModel):
    """Only the fields you send change. Changing options or type is a re-create, not an edit."""

    topic_id: uuid.UUID | None = None
    stem: Annotated[str, StringConstraints(max_length=2000)] | None = None
    explanation: Text | None = None
    difficulty: Annotated[int, Field(ge=1, le=5)] | None = None
    status: QuestionStatus | None = None
    tags: Annotated[list[Tag], Field(max_length=8)] | None = None


class LearnOptionOut(_Out):
    position: int
    text: str
    is_correct: bool
    rationale: str | None


class LearnSourceOut(_Out):
    url: str
    title: str | None
    quote: str
    fetched_on: date | None
    reliability: int | None


class LearnQuestionOut(_Out):
    """The full question, including the answers. For editing and review, never for answering."""

    id: uuid.UUID
    topic_id: uuid.UUID
    type: QuestionType
    stem: str
    explanation: str | None
    difficulty: int
    status: QuestionStatus
    origin: QuestionOrigin
    rubric: list[str] | None
    practice_slug: str | None
    tags: list[str]
    options: list[LearnOptionOut]
    sources: list[LearnSourceOut]
    updated_at: datetime


class LearnPublicOption(BaseModel):
    position: int
    text: str


class LearnQuestionToAnswer(BaseModel):
    """What the learner sees while answering: no correct flags, rationales or explanation."""

    id: uuid.UUID
    topic_id: uuid.UUID
    topic_title: str
    type: QuestionType
    stem: str
    difficulty: int
    status: QuestionStatus
    options: list[LearnPublicOption]
    rubric: list[str] | None = None
    practice_slug: str | None = None
    is_new: bool


# --- answering and review ---


class LearnAnswerIn(BaseModel):
    """`token` is made by the client for each answer; sending the same one again is harmless."""

    token: uuid.UUID
    selected: Annotated[list[int], Field(max_length=5)] | None = None  # option positions
    text: Annotated[str, StringConstraints(max_length=4000)] | None = None
    # For written/explain/scenario questions the learner rates themselves, 0 to 1.
    self_score: Annotated[float, Field(ge=0, le=1)] | None = None
    confidence: Annotated[int, Field(ge=1, le=3)] = 2
    seconds: Annotated[float, Field(ge=0, le=3600)] | None = None


class LearnAnswerOut(BaseModel):
    already_answered: bool = False
    correct: bool
    score: float
    rating: Rating
    graded_by: GradedBy
    correct_positions: list[int]
    explanation: str | None
    options: list[LearnOptionOut]
    sources: list[LearnSourceOut]
    next_due: datetime


class LearnReviewQueue(BaseModel):
    due: int  # cards due now
    new_available: int  # new questions you may still start today
    items: list[LearnQuestionToAnswer]


class LearnStats(BaseModel):
    topics: int
    questions: int
    due_now: int
    new_today_left: int
    answered_today: int
    streak_days: int
