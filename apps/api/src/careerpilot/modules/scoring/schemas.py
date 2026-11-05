import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CHANCE_NOTE = (
    "A rule of thumb from how well the job fits you, not a probability. It is not calibrated "
    "against real outcomes."
)


class ComponentOut(BaseModel):
    key: Literal["skills", "pay", "seniority", "company", "location", "growth"]
    weight: int
    score: int | None  # None: not enough information, left out of the total
    detail: str


class RedFlagOut(BaseModel):
    text: str
    quote: str  # copied from the job description and checked against it


class ReadingOut(BaseModel):
    summary: str
    growth: int
    growth_reason: str
    red_flags: list[RedFlagOut]
    dropped_flags: int  # warning signs the model named whose quote was not in the description


class ScoreOut(BaseModel):
    job_id: uuid.UUID
    score: int | None
    chance: Literal["good", "possible", "unlikely", "unknown"]
    chance_note: str
    priority: Literal["high", "medium", "low"] | None
    coverage: int  # percent of the weight that could be measured
    version: int
    stale: bool  # the rules or your profile changed since this was computed
    components: list[ComponentOut]
    blockers: list[str]
    reading: ReadingOut | None
    computed_at: datetime


class RawFlag(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str = ""
    quote: str = ""


class RawReading(BaseModel):
    """What the model is asked to return; validated before anything is stored."""

    model_config = ConfigDict(extra="ignore")

    summary: str = Field(max_length=1000)
    growth: int = Field(ge=0, le=100)
    growth_reason: str = Field(default="", max_length=500)
    red_flags: list[RawFlag] = []
