import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from careerpilot.core.db import Base


class JobScore(Base):
    """The latest score of a job. A snapshot: recomputing replaces it."""

    __tablename__ = "job_scores"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), unique=True
    )
    version: Mapped[int] = mapped_column(Integer)
    profile_hash: Mapped[str] = mapped_column(Text)
    score: Mapped[int | None] = mapped_column(Integer)
    coverage: Mapped[int] = mapped_column(Integer)
    chance: Mapped[str] = mapped_column(Text)
    priority: Mapped[str | None] = mapped_column(Text)
    components: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    blockers: Mapped[list[str]] = mapped_column(JSONB)
    reading: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
