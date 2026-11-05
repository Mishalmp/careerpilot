import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.digest import repository
from careerpilot.modules.digest.schemas import DigestOut, DigestPayload, FollowUp
from careerpilot.modules.discovery import service as discovery_service
from careerpilot.modules.tasks import service as tasks_service
from careerpilot.modules.tracker import service as tracker_service


async def build(
    db: AsyncSession, owner_id: uuid.UUID, today: date, *, now: datetime | None = None
) -> DigestPayload:
    """Summarise the day and store it. Safe to repeat: the same day is replaced, not duplicated."""
    now = now or datetime.now(UTC)
    day_ago = now - timedelta(days=1)
    snapshot = await tracker_service.snapshot(db, owner_id, today)
    payload = DigestPayload(
        new_listings_24h=await discovery_service.count_new_since(db, owner_id, day_ago),
        waiting_listings=await discovery_service.total_new(db, owner_id),
        due_followups=[
            FollowUp(
                job_id=job.id,
                company=job.company.name,
                title=job.title,
                due_on=job.application.next_followup_on,
            )
            for job in snapshot.due_followups
        ],
        applications={status.value: count for status, count in snapshot.counts.items()},
        failed_tasks_24h=await tasks_service.failed_since(db, owner_id, day_ago),
    )
    await repository.upsert(db, owner_id, today, payload.model_dump(mode="json"))
    await db.commit()
    return payload


async def latest(db: AsyncSession, owner_id: uuid.UUID) -> DigestOut | None:
    row = await repository.latest(db, owner_id)
    if row is None:
        return None
    return DigestOut(
        day=row.day, created_at=row.created_at, payload=DigestPayload.model_validate(row.payload)
    )
