"""Load and validate content/curriculum.yaml, the single source of the prep plan."""

from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, model_validator

from careerpilot.modules.prep.enums import Priority


class TopicDef(BaseModel):
    key: str
    title: str
    priority: Priority


class AreaDef(BaseModel):
    name: str
    topics: list[TopicDef]


class DayDef(BaseModel):
    day: int
    phase: str
    focus: str
    core_topics: str
    practice: str
    speaking: str
    hours: int
    deliverable: str


class Curriculum(BaseModel):
    areas: list[AreaDef]
    days: list[DayDef]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        keys = [topic.key for area in self.areas for topic in area.topics]
        if len(keys) != len(set(keys)):
            raise ValueError("topic keys must be unique")
        if [day.day for day in self.days] != list(range(1, len(self.days) + 1)):
            raise ValueError("days must be numbered 1..N in order")
        return self


def load_curriculum(content_dir: Path) -> Curriculum:
    raw = yaml.safe_load((content_dir / "curriculum.yaml").read_text(encoding="utf-8"))
    return Curriculum.model_validate(raw)
