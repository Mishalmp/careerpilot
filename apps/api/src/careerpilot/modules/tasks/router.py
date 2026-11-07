import uuid

from fastapi import APIRouter

from careerpilot.core.deps import DbSession
from careerpilot.modules.auth.dependencies import Authenticated
from careerpilot.modules.tasks import service
from careerpilot.modules.tasks.enums import TaskStatus
from careerpilot.modules.tasks.schemas import RetryAllOut, TaskDetail, TaskList, TaskOut

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


@router.get("/{task_id}", operation_id="get_task")
async def get_task(task_id: uuid.UUID, session: Authenticated, db: DbSession) -> TaskDetail:
    """One task with its step-by-step history (what each attempt did and where it stopped)."""
    return await service.get_detail(db, session.user_id, task_id)


@router.post("/{task_id}/retry", operation_id="retry_task")
async def retry_task(task_id: uuid.UUID, session: Authenticated, db: DbSession) -> TaskOut:
    """Queue a failed task again; it continues from where it stopped."""
    return await service.retry(db, session.user_id, task_id)


@router.post("/{task_id}/cancel", operation_id="cancel_task")
async def cancel_task(task_id: uuid.UUID, session: Authenticated, db: DbSession) -> TaskOut:
    """Stop a task that is still waiting."""
    return await service.cancel(db, session.user_id, task_id)
