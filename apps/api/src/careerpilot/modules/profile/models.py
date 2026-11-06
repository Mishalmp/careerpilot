import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, SmallInteger, Text, func
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
