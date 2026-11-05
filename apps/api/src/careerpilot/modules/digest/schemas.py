import uuid
from datetime import date, datetime

from pydantic import BaseModel


class FollowUp(BaseModel):
    job_id: uuid.UUID
    company: str
    title: str
    due_on: date | None


class DigestPayload(BaseModel):
    new_listings_24h: int  # found on followed job boards in the last day
    waiting_listings: int  # all listings waiting for your decision
    due_followups: list[FollowUp]
    applications: dict[str, int]  # applications per status
    failed_tasks_24h: int


class DigestOut(BaseModel):
    day: date
    created_at: datetime
    payload: DigestPayload
