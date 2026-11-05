import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.scoring.models import JobScore


async def get_score(db: AsyncSession, owner_id: uuid.UUID, job_id: uuid.UUID) -> JobScore | None:
    return await db.scalar(
        select(JobScore).where(JobScore.owner_id == owner_id, JobScore.job_id == job_id)
    )


async def upsert_score(
    db: AsyncSession, *, owner_id: uuid.UUID, job_id: uuid.UUID, **values: Any
) -> JobScore:
    statement = insert(JobScore).values(owner_id=owner_id, job_id=job_id, **values)
    statement = statement.on_conflict_do_update(
        index_elements=[JobScore.job_id], set_={**values, "computed_at": func.now()}
    ).returning(JobScore)
    row = (await db.execute(statement, execution_options={"populate_existing": True})).scalar_one()
    return row
