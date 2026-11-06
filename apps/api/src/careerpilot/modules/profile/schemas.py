from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

Item = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class ProfileOut(BaseModel):
    has_cv: bool
    skills: list[str]
    role_titles: list[str]
    years_experience: int | None
    updated_at: datetime | None


class CvIn(BaseModel):
    text: Annotated[str, StringConstraints(min_length=20, max_length=60_000)]


class ProfileUpdate(BaseModel):
    """Only the fields you send change. Use this to fix what the CV reading got wrong."""

    skills: Annotated[list[Item], Field(max_length=60)] | None = None
    role_titles: Annotated[list[Item], Field(max_length=12)] | None = None
    years_experience: Annotated[int, Field(ge=0, le=60)] | None = None
