import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from careerpilot.core.db import Base, str_enum
from careerpilot.modules.discovery.enums import BoardKind, CandidateStatus


class DiscoverySource(Base):
    """A company job board that is read once a day."""

    __tablename__ = "discovery_sources"
    __table_args__ = (
        UniqueConstraint("owner_id", "kind", "board", name="uq_discovery_sources_owner_kind_board"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[BoardKind] = mapped_column(str_enum(BoardKind, "discovery_source_kind"))
    board: Mapped[str] = mapped_column(Text)  # the board name in the provider's address
    company_name: Mapped[str] = mapped_column(Text)
    # A job is kept when its title has one of `include` (if any) and none of `exclude`.
    include: Mapped[list[str]] = mapped_column(JSONB)
    exclude: Mapped[list[str]] = mapped_column(JSONB)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    last_listed: Mapped[int | None] = mapped_column(Integer)  # jobs on the board at the last run
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DiscoveredJob(Base):
    """A listing found on a board. It reaches the tracker only when you accept it."""

    __tablename__ = "discovered_jobs"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_discovered_jobs_source_external"),
        Index("ix_discovered_jobs_owner_status_seen", "owner_id", "status", "first_seen_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discovery_sources.id", ondelete="CASCADE")
    )
    external_id: Mapped[str] = mapped_column(Text)
    # Set by feeds that list many companies; a company's own board uses the source's name.
    company_name: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    apply_url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    published_on: Mapped[date | None] = mapped_column(Date)
    remote: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[CandidateStatus] = mapped_column(
        str_enum(CandidateStatus, "candidate_status"), default=CandidateStatus.NEW
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SearchProfile(Base):
    """One way of searching, for example "India, Bengaluru or Hyderabad, hybrid or onsite". All of
    it must hold for a listing to fit; several profiles are alternatives."""

    __tablename__ = "search_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    regions: Mapped[list[str]] = mapped_column(JSONB, default=list)
    cities: Mapped[list[str]] = mapped_column(JSONB, default=list)
    work_modes: Mapped[list[str]] = mapped_column(JSONB, default=list)
    keywords: Mapped[list[str]] = mapped_column(JSONB, default=list)
    exclude: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
