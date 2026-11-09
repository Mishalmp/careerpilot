import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

from careerpilot.modules.discovery.adapters import TOKEN
from careerpilot.modules.discovery.enums import BoardKind, CandidateStatus
from careerpilot.modules.profile.schemas import RegionName, WorkModeName

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
    last_kept: int | None  # of the listed jobs, how many fit your searches
    left_out: dict[str, int]  # why the rest did not, with counts
    new_count: int  # listings waiting for your decision


class SuggestedBoardOut(BaseModel):
    key: str  # "greenhouse/okta"
    kind: BoardKind
    board: str
    company: str
    tags: list[str]
    roles: int
    india: int
    remote: int
    followed: bool


class FollowSuggested(BaseModel):
    keys: Annotated[list[str], Field(min_length=1, max_length=60)]


class FollowedOut(BaseModel):
    added: int
    already: int


class RunOut(BaseModel):
    listed: int  # jobs on the board
    kept: int  # after your keyword filters
    new: int  # not seen before
    outside_search: int = 0  # kept by your words, but not in the places or ways you search
    left_out: dict[str, int] = {}  # why, with counts
    source: str = ""  # whose board this was


class Listing(BaseModel):
    """What a caller may look at to decide whether a waiting listing is worth adding."""

    title: str
    company: str
    location: str | None
    published_on: date | None
    remote: bool


class CandidateOut(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    company_name: str
    via: str | None  # the feed that listed it, when the job came from one
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


City = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class SearchProfileIn(BaseModel):
    """One way of searching. Everything in it must hold; several profiles are alternatives."""

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    enabled: bool = True
    regions: Annotated[list[RegionName], Field(min_length=1, max_length=5)]
    cities: Annotated[
        list[City], Field(max_length=15)
    ] = []  # any spelling: Bangalore finds Bengaluru
    work_modes: Annotated[list[WorkModeName], Field(min_length=1, max_length=3)]
    keywords: Keywords = []  # the title must have one of these
    exclude: Keywords = []


class SearchProfileUpdate(BaseModel):
    """Only the fields you send change."""

    name: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)] | None
    ) = None
    enabled: bool | None = None
    regions: Annotated[list[RegionName], Field(min_length=1, max_length=5)] | None = None
    cities: Annotated[list[City], Field(max_length=15)] | None = None
    work_modes: Annotated[list[WorkModeName], Field(min_length=1, max_length=3)] | None = None
    keywords: Keywords | None = None
    exclude: Keywords | None = None


class SearchProfileOut(SearchProfileIn):
    id: uuid.UUID
