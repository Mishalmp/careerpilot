import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from careerpilot.modules.apply.enums import ApplyStatus, InterviewLevel, ListingKind, PayLevel
from careerpilot.modules.apply.policy import Policy
from careerpilot.modules.tracker.schemas import Url

NOTICE = (
    "This list is a starting point, not a decision. Everything below says where it came from; "
    "open the sources before you apply. CareerPilot never submits an application for you."
)
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class EvidenceLink(BaseModel):
    """One thing that was found, with the page it came from and the words it was read from."""

    url: Url | None  # None: it came from your own tracker
    title: str
    quote: str


class TriedStep(BaseModel):
    """A place that was looked at, whether or not it had an answer. Nothing is hidden."""

    label: str
    found: bool
    note: str


class PayEstimate(BaseModel):
    level: PayLevel | None  # None: nothing found at any level
    label: str  # the level in words, e.g. "Stated in this post"
    currency: str | None
    low: float | None  # per year, in `currency`; rupee figures are not converted to anything else
    mid: float | None
    high: float | None
    n: int  # how many figures it rests on
    evidence: list[EvidenceLink]
    tried: list[TriedStep]


class InterviewNotes(BaseModel):
    level: InterviewLevel | None
    label: str
    points: list[EvidenceLink]
    tried: list[TriedStep]


class AlsoListed(BaseModel):
    url: Url
    title: str
    host: str
    kind: ListingKind
    overlap: float | None  # share of skills in common with this post, when the page was read
    opened: bool  # False: only the search result was seen (the page was not opened)


class CompanyCheckSummary(BaseModel):
    verdict: str  # a verification label, or "not_checked"
    passed: int
    total: int
    flags: list[str]
    note: str


class ApplyItemOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    title: str
    company: str
    location: str | None
    work_mode: str | None
    region: str | None
    apply_url: Url | None
    jd_url: Url | None
    queued_on: date
    status: ApplyStatus
    tracker_status: str
    match_score: int
    reasons: list[str]
    pay: PayEstimate | None
    interview: InterviewNotes | None
    also_listed: list[AlsoListed]
    company_check: CompanyCheckSummary | None
    notes: list[str]
    enriched_at: datetime | None
    decided_at: datetime | None
    decision_note: str | None


class ApplyQueueOut(BaseModel):
    items: list[ApplyItemOut]
    ready_count: int
    policy: Policy
    policy_source: str
    policy_problems: list[str]  # non-empty: the policy file is wrong and nothing is built
    notice: str = NOTICE


class DecisionIn(BaseModel):
    note: Note | None = None


class BuildOut(BaseModel):
    queued: bool  # False: a build for this minute was already queued
