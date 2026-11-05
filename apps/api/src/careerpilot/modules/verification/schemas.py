import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from careerpilot.modules.tracker.schemas import Url
from careerpilot.modules.verification.enums import (
    CheckKey,
    CheckSource,
    CheckStatus,
    VerdictLabel,
)

NOTICE = (
    "No check proves a company is genuine. Look at the evidence yourself before you share "
    "personal documents or pay anything."
)

Quote = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class CheckUpdate(BaseModel):
    """Your own finding about a check or flag. Automatic runs never overwrite it."""

    status: CheckStatus
    evidence_url: Url | None = None
    # With a URL, the page is fetched and the quote must appear in it before this is saved.
    evidence_quote: Quote | None = None
    note: Note | None = None


class CheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: CheckKey
    kind: Literal["check", "flag"]
    status: CheckStatus
    source: CheckSource | None  # None: never checked
    evidence_url: str | None
    evidence_quote: str | None
    note: str | None
    checked_at: datetime | None


class VerificationOut(BaseModel):
    job_id: uuid.UUID
    company_name: str
    website: str | None
    verdict: VerdictLabel
    passed: int
    total: int
    raised_flags: list[CheckKey]
    needs_review: bool  # anything below "verified" asks for your attention
    notice: str
    ai_available: bool
    checks: list[CheckOut]
