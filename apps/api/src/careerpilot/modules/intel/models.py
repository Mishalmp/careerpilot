import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from careerpilot.core.db import Base, str_enum
from careerpilot.modules.intel.enums import ItemKind, SourceKind


class IntelSource(Base):
    """A text about how a company interviews, with where it came from."""

    __tablename__ = "intel_sources"
    __table_args__ = (Index("ix_intel_sources_owner_id_company_id", "owner_id", "company_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    kind: Mapped[SourceKind] = mapped_column(str_enum(SourceKind, "intel_source_kind"))
    label: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    # The company the text is about. When it is not the job's company, items are "inferred".
    about_company: Mapped[str] = mapped_column(Text)
    published_on: Mapped[date | None] = mapped_column(Date)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IntelItem(Base):
    __tablename__ = "intel_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("intel_sources.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[ItemKind] = mapped_column(str_enum(ItemKind, "intel_item_kind"))
    key: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    # Copied from the source and verified against its text before it was stored.
    quote: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
