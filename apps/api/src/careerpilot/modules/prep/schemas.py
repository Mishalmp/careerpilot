import uuid
from datetime import date
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from careerpilot.modules.prep.enums import DayStatus, PlanPhase, Priority, StudyKind, TopicStatus

Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TopicOut(_Out):
    id: uuid.UUID
    key: str
    area: str
    title: str
    priority: Priority
    sort_order: int
    confidence: int | None
    status: TopicStatus
    last_reviewed_on: date | None
    next_review_on: date | None
    notes: str | None


class TopicUpdate(BaseModel):
    confidence: Annotated[int, Field(ge=1, le=5)] | None = None
    status: TopicStatus | None = None
    notes: Note | None = None

    @model_validator(mode="after")
    def _status_not_cleared(self) -> Self:
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be cleared")
        return self


class SessionCreate(BaseModel):
    minutes: Annotated[int, Field(ge=1, le=720)]
    kind: StudyKind
    notes: Note | None = None
    studied_on: date | None = None


class SessionOut(_Out):
    id: uuid.UUID
    topic_id: uuid.UUID
    minutes: int
    kind: StudyKind
    studied_on: date
    notes: str | None


class DayOut(_Out):
    day: int
    phase: str
    focus: str
    core_topics: str
    practice: str
    speaking: str
    hours: int
    deliverable: str
    status: DayStatus
    notes: str | None
    scheduled_on: date | None = None


class DayUpdate(BaseModel):
    status: DayStatus | None = None
    notes: Note | None = None


class PlanOut(BaseModel):
    start_date: date | None


class PlanUpdate(BaseModel):
    start_date: date


class TodayPrep(BaseModel):
    phase: PlanPhase
    start_date: date | None
    day_number: int | None
    total_days: int
    day: DayOut | None
    due_reviews: list[TopicOut]
    minutes_today: int


class SeedResult(BaseModel):
    topics_added: int
    topics_updated: int
    days_added: int
    days_updated: int


class GuideInfoOut(BaseModel):
    name: str
    title: str
    private: bool


class GuideOut(GuideInfoOut):
    markdown: str
