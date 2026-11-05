import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

from careerpilot.modules.discovery.adapters import TOKEN
from careerpilot.modules.discovery.enums import BoardKind, CandidateStatus

Keyword = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Keywords = Annotated[list[Keyword], Field(max_length=10)]
Company = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class DiscoverySourceCreate(BaseModel):
    kind: BoardKind
    # The board name in the company's job-board address, for example "acme" in
    # boards.greenhouse.io/acme.
    board: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)]
    company_name: Company
    include: Keywords = []
    exclude: Keywords = []

    @field_validator("board")
    @classmethod
    def _valid_board(cls, value: str) -> str:
        if not TOKEN.match(value):
            raise ValueError("letters, digits, dots, dashes and underscores only")
        return value


class DiscoverySourceUpdate(BaseModel):
    """Only the fields you send change."""

    enabled: bool | None = None
    include: Keywords | None = None
    exclude: Keywords | None = None


class DiscoverySourceOut(BaseModel):
    id: uuid.UUID
    kind: BoardKind
    board: str
    company_name: str
    include: list[str]
    exclude: list[str]
    enabled: bool
    last_run_at: datetime | None
    last_error: str | None
    last_listed: int | None
    new_count: int  # listings waiting for your decision


class RunOut(BaseModel):
    listed: int  # jobs on the board
    kept: int  # after your keyword filters
    new: int  # not seen before


class CandidateOut(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    company_name: str
    title: str
    location: str | None
    url: str
    published_on: date | None
    remote: bool
    status: CandidateStatus
    job_id: uuid.UUID | None
    first_seen_at: datetime
    listed: bool  # still on the board at the last run


class CandidateList(BaseModel):
    items: list[CandidateOut]  # the newest 200
    total: int  # all listings with this status, so a cut-off list is never mistaken for everything


class AcceptOut(BaseModel):
    job_id: uuid.UUID
    already_tracked: bool  # the tracker already had this job, so nothing was duplicated
