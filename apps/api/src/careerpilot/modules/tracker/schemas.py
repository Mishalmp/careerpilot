import uuid
from datetime import date, datetime
from typing import Annotated, Self
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

from careerpilot.modules.tracker.enums import (
    ContactKind,
    Currency,
    EmailMode,
    EventType,
    HiringFromIndia,
    JobType,
    Portal,
    PortalMode,
    Region,
    Status,
    Visa,
    WorkMode,
)


def _http_url(value: str) -> str:
    """Only http(s) links: a `javascript:` URL shown as a link would run code when clicked."""
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("must be an http or https URL")
    return value


Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
LongText = Annotated[str, StringConstraints(max_length=50_000)]
Url = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=2000), AfterValidator(_http_url)
]


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class JobFields(BaseModel):
    source: Portal | None = None
    region: Region | None = None
    location_text: Short | None = None
    work_mode: WorkMode | None = None
    job_type: JobType | None = None
    hiring_from_india: HiringFromIndia | None = None
    currency: Currency | None = None
    salary_text: Short | None = None
    est_ctc_lpa: Annotated[float, Field(ge=0, le=1000)] | None = None
    visa: Visa | None = None
    found_on: date | None = None
    posted_on: date | None = None
    jd_url: Url | None = None
    apply_url: Url | None = None
    careers_url: Url | None = None
    jd_text: LongText | None = None
    jd_summary: Annotated[str, StringConstraints(max_length=5000)] | None = None


class JobCreate(JobFields):
    company_name: Short
    title: Short


class JobUpdate(JobFields):
    title: Short | None = None

    @model_validator(mode="after")
    def _title_not_cleared(self) -> Self:
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("title cannot be cleared")
        return self


class ApplicationInit(BaseModel):
    """Starting state for an application, used by imports. The API creates jobs as 'New'."""

    status: Status = Status.NEW
    applied_on: date | None = None
    next_followup_on: date | None = None
    portal_mode: PortalMode = PortalMode.NOT_YET
    site_mode: PortalMode = PortalMode.NOT_YET
    email_mode: EmailMode = EmailMode.NOT_YET
    resume_version: Short | None = None
    notes: Note | None = None


class ApplicationUpdate(BaseModel):
    applied_on: date | None = None
    next_followup_on: date | None = None
    portal_mode: PortalMode | None = None
    site_mode: PortalMode | None = None
    email_mode: EmailMode | None = None
    resume_version: Short | None = None
    notes: Note | None = None


class StatusChange(BaseModel):
    status: Status
    expected_version: int = Field(ge=1)
    note: Note | None = None
    next_followup_on: date | None = None
    reopen: bool = False


class CompanyOut(_Out):
    id: uuid.UUID
    name: str
    website: str | None
    country: str | None


class ApplicationOut(_Out):
    id: uuid.UUID
    status: Status
    version: int
    applied_on: date | None
    next_followup_on: date | None
    portal_mode: PortalMode
    site_mode: PortalMode
    email_mode: EmailMode
    resume_version: str | None
    notes: str | None
    updated_at: datetime


class JobSummary(_Out):
    id: uuid.UUID
    title: str
    company: CompanyOut
    application: ApplicationOut
    source: Portal | None
    region: Region | None
    location_text: str | None
    work_mode: WorkMode | None
    job_type: JobType | None
    hiring_from_india: HiringFromIndia | None
    currency: Currency | None
    salary_text: str | None
    est_ctc_lpa: float | None
    visa: Visa | None
    found_on: date | None
    posted_on: date | None
    jd_url: str | None
    apply_url: str | None
    careers_url: str | None
    created_at: datetime
    updated_at: datetime


class EventOut(_Out):
    id: uuid.UUID
    type: EventType
    from_status: Status | None
    to_status: Status
    note: str | None
    at: datetime


class CompanyUpdate(BaseModel):
    """Only the fields you send change; send null to clear one."""

    website: Url | None = None
    country: Short | None = None


class ContactCreate(BaseModel):
    name: Short
    role: Short | None = None
    email: EmailStr | None = None
    phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    kind: ContactKind
    source_url: Url | None = None

    @model_validator(mode="after")
    def _published_needs_source(self) -> Self:
        if self.kind == ContactKind.PUBLISHED_BUSINESS and not self.source_url:
            raise ValueError("a published business contact needs the page where it is published")
        return self


class ContactOut(_Out):
    id: uuid.UUID
    name: str
    role: str | None
    email: str | None
    phone: str | None
    kind: ContactKind
    source_url: str | None


class JobDetail(JobSummary):
    jd_text: str | None
    jd_summary: str | None
    events: list[EventOut]
    contacts: list[ContactOut]


class JobPage(BaseModel):
    items: list[JobSummary]
    next_cursor: str | None
