import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from careerpilot.modules.research.enums import FindingKind, FindingStatus, RunStatus


class ResearchRunStart(BaseModel):
    job_id: uuid.UUID


class ResearchRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    status: RunStatus
    queries: list[str]
    budgets: dict[str, Any]
    usage: dict[str, Any]
    message: str | None
    created_at: datetime
    finished_at: datetime | None
    pending_findings: int = 0


class ResearchFindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    kind: FindingKind
    topic: str
    text: str
    quote: str
    source_url: str
    source_title: str | None
    relevance: int
    status: FindingStatus
    created_at: datetime


class ResearchFindingPage(BaseModel):
    items: list[ResearchFindingOut]
    total: int


class ResearchApproved(BaseModel):
    """What an approval created in the learning area."""

    topic_id: uuid.UUID
    question_id: uuid.UUID | None


# --- what the model must return for one page (validated leniently; items are filtered by code) ---


class RawItem(BaseModel):
    kind: str = ""
    topic: str = ""
    text: str = ""
    quote: str = ""


class ExtractReply(BaseModel):
    items: list[RawItem] = []
