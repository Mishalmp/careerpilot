import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Text, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from careerpilot.core.db import Base, str_enum
from careerpilot.modules.outreach.enums import Channel, OutreachStatus


class OutreachDraft(Base):
    """A message you may send. Nothing here sends anything; see workflow.py."""

    __tablename__ = "outreach_drafts"
    __table_args__ = (
        # One message per role and channel: only a single draft may be approved or sent.
        Index(
            "uq_outreach_drafts_one_per_job_channel",
            "owner_id",
            "job_id",
            "channel",
            unique=True,
            postgresql_where=text("status IN ('approved', 'sent')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL")
    )
    channel: Mapped[Channel] = mapped_column(str_enum(Channel, "outreach_channel"))
    status: Mapped[OutreachStatus] = mapped_column(
        str_enum(OutreachStatus, "outreach_status"), default=OutreachStatus.DRAFT
    )
    variant: Mapped[str] = mapped_column(Text)  # "A", "B" or "manual"
    subject: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    # Copied from the contact when the draft is made, so the record stays true if it is edited.
    recipient_email: Mapped[str | None] = mapped_column(Text)
    recipient_source_url: Mapped[str | None] = mapped_column(Text)
    facts: Mapped[list[str]] = mapped_column(JSONB)
    lint: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
