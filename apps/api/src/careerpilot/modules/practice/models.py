import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from careerpilot.core.db import Base, str_enum
from careerpilot.modules.practice.enums import Language


class Submission(Base):
    """One run of a solution. The tests run in the browser, so the counts are self-reported."""

    __tablename__ = "submissions"
    __table_args__ = (
        CheckConstraint("passed >= 0 AND passed <= total", name="passed_within_total"),
        Index(
            "ix_submissions_owner_id_problem_slug_created_at",
            "owner_id",
            "problem_slug",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    problem_slug: Mapped[str] = mapped_column(Text)
    language: Mapped[Language] = mapped_column(str_enum(Language, "submission_language"))
    code: Mapped[str] = mapped_column(Text)
    passed: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)
    runtime_ms: Mapped[int] = mapped_column(Integer)
    # Per-test status only ([{"name": ..., "status": ...}]), never test inputs or expected values.
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
