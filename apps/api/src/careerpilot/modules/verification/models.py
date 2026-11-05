import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from careerpilot.core.db import Base, str_enum
from careerpilot.modules.verification.enums import CheckKey, CheckSource, CheckStatus


class CompanyCheck(Base):
    """One check (or red flag) about a company. The verdict is computed from these rows."""

    __tablename__ = "company_checks"
    __table_args__ = (
        UniqueConstraint("company_id", "key", name="uq_company_checks_company_id_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    key: Mapped[CheckKey] = mapped_column(str_enum(CheckKey, "check_key"))
    status: Mapped[CheckStatus] = mapped_column(str_enum(CheckStatus, "check_status"))
    source: Mapped[CheckSource] = mapped_column(str_enum(CheckSource, "check_source"))
    evidence_url: Mapped[str | None] = mapped_column(Text)
    # Copied from the page and verified against its fetched text before it is stored.
    evidence_quote: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
