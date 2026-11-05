import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from careerpilot.core.db import Base


class MockSession(Base):
    """A mock interview: the questions asked, your answers, and how each was scored."""

    __tablename__ = "mock_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(Text)
    focus: Mapped[str] = mapped_column(Text)
    total_questions: Mapped[int] = mapped_column(Integer)
    # One entry per question: {question, topic, answer, score, feedback}. The last entry has no
    # answer until you give one. Stored as a transcript; nothing else reads it.
    turns: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
