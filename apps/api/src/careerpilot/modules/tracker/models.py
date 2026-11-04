import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from careerpilot.core.db import Base, str_enum
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


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def _owner() -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "normalized_name", name="uq_companies_owner_id_normalized_name"
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    owner_id: Mapped[uuid.UUID] = _owner()
    name: Mapped[str] = mapped_column(Text)
    normalized_name: Mapped[str] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contacts: Mapped[list["Contact"]] = relationship(
        lazy="raise", order_by="Contact.created_at", cascade="all, delete-orphan"
    )


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("owner_id", "fingerprint", name="uq_jobs_owner_id_fingerprint"),
        Index("ix_jobs_owner_id_updated_at_id", "owner_id", "updated_at", "id"),
    )

    id: Mapped[uuid.UUID] = _pk()
    owner_id: Mapped[uuid.UUID] = _owner()
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    fingerprint: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    source: Mapped[Portal | None] = mapped_column(str_enum(Portal, "portal"))
    region: Mapped[Region | None] = mapped_column(str_enum(Region, "region"))
    location_text: Mapped[str | None] = mapped_column(Text)
    work_mode: Mapped[WorkMode | None] = mapped_column(str_enum(WorkMode, "work_mode"))
    job_type: Mapped[JobType | None] = mapped_column(str_enum(JobType, "job_type"))
    hiring_from_india: Mapped[HiringFromIndia | None] = mapped_column(
        str_enum(HiringFromIndia, "hiring_from_india")
    )
    currency: Mapped[Currency | None] = mapped_column(str_enum(Currency, "currency"))
    salary_text: Mapped[str | None] = mapped_column(Text)
    est_ctc_lpa: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    visa: Mapped[Visa | None] = mapped_column(str_enum(Visa, "visa"))
    found_on: Mapped[date | None] = mapped_column(Date)
    posted_on: Mapped[date | None] = mapped_column(Date)
    jd_url: Mapped[str | None] = mapped_column(Text)
    apply_url: Mapped[str | None] = mapped_column(Text)
    careers_url: Mapped[str | None] = mapped_column(Text)
    jd_text: Mapped[str | None] = mapped_column(Text)
    jd_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    company: Mapped[Company] = relationship(lazy="joined")
    application: Mapped["Application"] = relationship(
        back_populates="job", lazy="joined", uselist=False, cascade="all, delete-orphan"
    )


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        Index("ix_applications_owner_id_status", "owner_id", "status"),
        Index("ix_applications_owner_id_next_followup_on", "owner_id", "next_followup_on"),
    )

    id: Mapped[uuid.UUID] = _pk()
    owner_id: Mapped[uuid.UUID] = _owner()
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[Status] = mapped_column(str_enum(Status, "application_status"))
    # Optimistic concurrency: bumped on every status change.
    version: Mapped[int] = mapped_column(Integer, default=1)
    applied_on: Mapped[date | None] = mapped_column(Date)
    next_followup_on: Mapped[date | None] = mapped_column(Date)
    portal_mode: Mapped[PortalMode] = mapped_column(
        str_enum(PortalMode, "portal_mode"), default=PortalMode.NOT_YET
    )
    site_mode: Mapped[PortalMode] = mapped_column(
        str_enum(PortalMode, "site_mode"), default=PortalMode.NOT_YET
    )
    email_mode: Mapped[EmailMode] = mapped_column(
        str_enum(EmailMode, "email_mode"), default=EmailMode.NOT_YET
    )
    resume_version: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    job: Mapped[Job] = relationship(back_populates="application", lazy="raise")
    events: Mapped[list["ApplicationEvent"]] = relationship(
        lazy="raise", order_by="ApplicationEvent.at", cascade="all, delete-orphan"
    )


class ApplicationEvent(Base):
    """Append-only history of an application."""

    __tablename__ = "application_events"
    __table_args__ = (Index("ix_application_events_application_id_at", "application_id", "at"),)

    id: Mapped[uuid.UUID] = _pk()
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE")
    )
    type: Mapped[EventType] = mapped_column(str_enum(EventType, "event_type"))
    from_status: Mapped[Status | None] = mapped_column(str_enum(Status, "event_from_status"))
    to_status: Mapped[Status] = mapped_column(str_enum(Status, "event_to_status"))
    note: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (
        CheckConstraint(
            "kind <> 'published_business' OR source_url IS NOT NULL",
            name="published_business_needs_source",
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    owner_id: Mapped[uuid.UUID] = _owner()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[ContactKind] = mapped_column(str_enum(ContactKind, "contact_kind"))
    source_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
