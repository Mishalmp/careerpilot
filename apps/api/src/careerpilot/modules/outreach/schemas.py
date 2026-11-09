import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from careerpilot.modules.outreach.enums import Channel, OutreachStatus
from careerpilot.modules.tracker.schemas import ContactOut, Url

Subject = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=3000)]
FactText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]

NOTE = (
    "CareerPilot never sends anything. Approving a draft only marks it ready: you copy it into "
    "your own mail client, send it yourself, then record that it was sent."
)


class FactIn(BaseModel):
    """Something specific about the company or role that the message should mention."""

    text: FactText
    # Where you found it. Needed unless the text is in the job description itself.
    source_url: Url | None = None


class GenerateRequest(BaseModel):
    channel: Channel = Channel.EMAIL
    contact_id: uuid.UUID | None = None
    sender_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)
    ]
    facts: Annotated[list[FactIn], Field(min_length=1, max_length=3)]
    # A real constraint that makes it human, such as "my notice period ends on 31 December".
    constraint: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = (
        None
    )


class DraftCreate(BaseModel):
    """A draft you wrote yourself."""

    channel: Channel = Channel.EMAIL
    contact_id: uuid.UUID | None = None
    subject: Subject
    body: Body
    facts: Annotated[list[FactText], Field(max_length=3)] = []


class DraftEdit(BaseModel):
    subject: Subject | None = None
    body: Body | None = None
    facts: Annotated[list[FactText], Field(max_length=3)] | None = None


class Move(BaseModel):
    status: OutreachStatus
    # Required to approve a draft that still has lint flags: you have read them.
    acknowledge_flags: bool = False


class LintOut(BaseModel):
    words: int
    flags: list[str]


class DraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    contact_id: uuid.UUID | None
    channel: Channel
    status: OutreachStatus
    variant: str
    subject: str
    body: str
    recipient_email: str | None
    recipient_source_url: str | None
    facts: list[str]
    lint: LintOut
    created_at: datetime
    approved_at: datetime | None
    sent_at: datetime | None


class OutreachList(BaseModel):
    items: list[DraftOut]
    approved_today: int
    daily_cap: int
    note: str = NOTE


class RawVariant(BaseModel):
    model_config = ConfigDict(extra="ignore")

    subject: Subject
    body: Body


class RawVariants(BaseModel):
    """What the model is asked to return."""

    model_config = ConfigDict(extra="ignore")

    variants: Annotated[list[RawVariant], Field(min_length=1, max_length=2)]


class ContactsFound(BaseModel):
    added: list[ContactOut]  # new published hiring addresses, each with the page it was found on
    already_known: int  # addresses found that you already had
    pages_read: int
    notes: list[str]  # pages that could not be read, and why
