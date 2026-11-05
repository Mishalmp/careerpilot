import uuid

from fastapi import APIRouter

from careerpilot.core.deps import DbSession
from careerpilot.modules.auth.dependencies import Authenticated
from careerpilot.modules.tasks import service
from careerpilot.modules.tasks.enums import TaskStatus
from careerpilot.modules.tasks.schemas import RetryAllOut, TaskList, TaskOut

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", operation_id="list_tasks")
async def list_tasks(
    session: Authenticated, db: DbSession, status: TaskStatus | None = None
) -> TaskList:
    """Recent background work, newest first, with a count per status."""
    return await service.list_tasks(db, session.user_id, status)


@router.post("/retry-failed", operation_id="retry_failed_tasks")
async def retry_failed(session: Authenticated, db: DbSession) -> RetryAllOut:
    return RetryAllOut(requeued=await service.retry_all(db, session.user_id))


@router.post("/{task_id}/retry", operation_id="retry_task")
async def retry_task(task_id: uuid.UUID, session: Authenticated, db: DbSession) -> TaskOut:
    """Queue a failed task again."""
    return await service.retry(db, session.user_id, task_id)
