"""A record of changes made by something other than the web app (the MCP server, for now)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from careerpilot.core.db import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    actor: Mapped[str] = mapped_column(Text)  # "mcp"
    action: Mapped[str] = mapped_column(Text)  # "add_job", "update_application_status", ...
    entity_type: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


async def record(
    db: AsyncSession,
    owner_id: uuid.UUID,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: object | None,
    details: dict[str, Any],
) -> None:
    """Add an audit row. Services commit their own changes; the caller commits this after."""
    db.add(
        AuditEvent(
            owner_id=owner_id,
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=details,
        )
    )
