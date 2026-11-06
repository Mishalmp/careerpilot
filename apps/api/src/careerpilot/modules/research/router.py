import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from careerpilot.core.deps import AppSearch, AppSettings, DbSession
from careerpilot.modules.auth.dependencies import Authenticated
from careerpilot.modules.research import service
from careerpilot.modules.research.enums import FindingStatus
from careerpilot.modules.research.schemas import (
    ResearchApproved,
    ResearchFindingPage,
    ResearchRunOut,
    ResearchRunStart,
)

router = APIRouter(prefix="/research", tags=["research"])


@router.post("/runs", operation_id="start_research_run", status_code=status.HTTP_202_ACCEPTED)
async def start_run(
    body: ResearchRunStart,
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
    search: AppSearch,
) -> ResearchRunOut:
    """Queues a run and returns at once; the work happens in the background."""
    return await service.start_run(
        db, session.user_id, body.job_id, settings, search_configured=search is not None
    )


@router.get("/runs", operation_id="list_research_runs")
async def list_runs(
    session: Authenticated,
    db: DbSession,
    job_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[ResearchRunOut]:
    return await service.list_runs(db, session.user_id, job_id, limit)


@router.get("/runs/{run_id}", operation_id="get_research_run")
async def get_run(run_id: uuid.UUID, session: Authenticated, db: DbSession) -> ResearchRunOut:
    return await service.get_run(db, session.user_id, run_id)


@router.get("/findings", operation_id="list_research_findings")
async def list_findings(
    session: Authenticated,
    db: DbSession,
    status_filter: Annotated[FindingStatus, Query(alias="status")] = FindingStatus.PENDING,
    run_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ResearchFindingPage:
    return await service.list_findings(
        db, session.user_id, status=status_filter, run_id=run_id, limit=limit, offset=offset
    )


@router.post("/findings/{finding_id}/approve", operation_id="approve_research_finding")
async def approve(finding_id: uuid.UUID, session: Authenticated, db: DbSession) -> ResearchApproved:
    return await service.approve(db, session.user_id, finding_id)


@router.post(
    "/findings/{finding_id}/reject",
    operation_id="reject_research_finding",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def reject(finding_id: uuid.UUID, session: Authenticated, db: DbSession) -> None:
    await service.reject(db, session.user_id, finding_id)
