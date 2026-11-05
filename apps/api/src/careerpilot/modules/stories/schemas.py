import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Part = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=3000)]
Evidence = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]


def _clean_tags(tags: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for tag in tags:
        seen.setdefault(" ".join(tag.lower().split()), None)
    return list(seen)


class StoryFields(BaseModel):
    title: Title
    situation: Part
    task: Part
    action: Part
    result: Part
    tags: Annotated[list[Tag], Field(max_length=8)] = []
    evidence: Evidence | None = None

    @field_validator("tags")
    @classmethod
    def _tidy(cls, value: list[str]) -> list[str]:
        return _clean_tags(value)


class StoryCreate(StoryFields):
    pass


class StoryUpdate(BaseModel):
    """Only the fields you send change."""

    title: Title | None = None
    situation: Part | None = None
    task: Part | None = None
    action: Part | None = None
    result: Part | None = None
    tags: Annotated[list[Tag], Field(max_length=8)] | None = None
    evidence: Evidence | None = None

    @field_validator("tags")
    @classmethod
    def _tidy(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _clean_tags(value)


class StoryOut(StoryFields):
    id: uuid.UUID
    hints: list[str]  # weak spots an interviewer would probe; not a judgement of truth
    updated_at: datetime
