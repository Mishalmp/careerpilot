import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from careerpilot.core.db import Base


class UserProfile(Base):
    """What the CV says about you. One row per user. The CV text itself stays here and is never
    sent anywhere; only the skills and role titles derived from it are used (for example in the
    search queries of a research run)."""

    __tablename__ = "user_profiles"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    cv_text: Mapped[str | None] = mapped_column(Text)
    skills: Mapped[list[str]] = mapped_column(JSONB, default=list)
    role_titles: Mapped[list[str]] = mapped_column(JSONB, default=list)
    years_experience: Mapped[int | None] = mapped_column(SmallInteger)
    # Account setup answers (docs/phase-7/12): who you are and what you are looking for.
    full_name: Mapped[str | None] = mapped_column(Text)
    headline: Mapped[str | None] = mapped_column(Text)
    current_role: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    target_roles: Mapped[list[str]] = mapped_column(JSONB, default=list)
    target_levels: Mapped[list[str]] = mapped_column(JSONB, default=list)
    regions: Mapped[list[str]] = mapped_column(JSONB, default=list)
    work_modes: Mapped[list[str]] = mapped_column(JSONB, default=list)
    needs_visa: Mapped[bool] = mapped_column(Boolean, default=False)
    salary_floor_lpa: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    salary_target_lpa: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    links: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    # Where the CV text came from. The file itself is never stored.
    cv_source: Mapped[str | None] = mapped_column(Text)
    cv_filename: Mapped[str | None] = mapped_column(Text)
    cv_chars: Mapped[int | None] = mapped_column(Integer)
    setup_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
