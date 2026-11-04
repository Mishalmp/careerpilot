import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.prep import service as prep_service
from careerpilot.modules.today.schemas import StatusCount, TodayOut
from careerpilot.modules.tracker import service as tracker_service
from careerpilot.modules.tracker.enums import Status
from careerpilot.modules.tracker.schemas import JobSummary


async def build(db: AsyncSession, owner_id: uuid.UUID, today: date) -> TodayOut:
    """Everything the Today screen needs, from the modules' public services."""
    tracker = await tracker_service.snapshot(db, owner_id, today)
    return TodayOut(
        pipeline=[StatusCount(status=s, count=tracker.counts.get(s, 0)) for s in Status],
        due_followups=[JobSummary.model_validate(job) for job in tracker.due_followups],
        prep=await prep_service.today_view(db, owner_id, today),
    )
