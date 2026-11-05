import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from fastapi.responses import PlainTextResponse

from careerpilot.core.clock import today_in
from careerpilot.core.deps import AppSettings, DbSession
from careerpilot.modules.auth.dependencies import Authenticated
from careerpilot.modules.tracker import service
from careerpilot.modules.tracker.enums import Region, Status, WorkMode
from careerpilot.modules.tracker.filters import JobFilters
from careerpilot.modules.tracker.models import Job
from careerpilot.modules.tracker.schemas import (
    ApplicationUpdate,
    CompanyUpdate,
    ContactCreate,
    ContactOut,
    EventOut,
    JobCreate,
    JobDetail,
    JobPage,
    JobSummary,
    JobUpdate,
    StatusChange,
)

router = APIRouter(tags=["tracker"])


def _detail(job: Job) -> JobDetail:
    return JobDetail(
        **JobSummary.model_validate(job).model_dump(),
        jd_text=job.jd_text,
        jd_summary=job.jd_summary,
        events=[EventOut.model_validate(event) for event in job.application.events],
        contacts=[ContactOut.model_validate(contact) for contact in job.company.contacts],
    )


@router.post(
    "/jobs",
    operation_id="create_job",
    response_model=JobSummary,
    responses={200: {"model": JobSummary, "description": "The job already existed"}},
    status_code=status.HTTP_201_CREATED,
)
async def create_job(
    body: JobCreate,
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
    response: Response,
) -> JobSummary:
    result = await service.create_job(db, session.user_id, body, today=today_in(settings.timezone))
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return JobSummary.model_validate(result.job)


@router.get("/jobs", operation_id="list_jobs")
async def list_jobs(
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
    status_in: Annotated[list[Status] | None, Query(alias="status")] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    region: Region | None = None,
    work_mode: WorkMode | None = None,
    min_ctc: Annotated[float | None, Query(ge=0)] = None,
    followup_due: bool = False,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=service.MAX_PAGE)] = 50,
) -> JobPage:
    filters = JobFilters(
        statuses=status_in,
        query=q,
        region=region,
        work_mode=work_mode,
        min_ctc=min_ctc,
        followup_due_on=today_in(settings.timezone) if followup_due else None,
    )
    jobs, next_cursor = await service.list_jobs(
        db, session.user_id, filters, cursor=cursor, limit=limit
    )
    return JobPage(items=[JobSummary.model_validate(job) for job in jobs], next_cursor=next_cursor)


@router.get("/jobs/export.csv", operation_id="export_jobs_csv", response_class=PlainTextResponse)
async def export_jobs(session: Authenticated, db: DbSession) -> PlainTextResponse:
    body = await service.export_csv(db, session.user_id)
    return PlainTextResponse(
        body,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="careerpilot-jobs.csv"'},
    )


@router.get("/jobs/{job_id}", operation_id="get_job")
async def get_job(job_id: uuid.UUID, session: Authenticated, db: DbSession) -> JobDetail:
    return _detail(await service.get_job(db, session.user_id, job_id))


@router.patch("/jobs/{job_id}", operation_id="update_job")
async def update_job(
    job_id: uuid.UUID, body: JobUpdate, session: Authenticated, db: DbSession
) -> JobDetail:
    return _detail(await service.update_job(db, session.user_id, job_id, body))


@router.delete("/jobs/{job_id}", operation_id="delete_job", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: uuid.UUID, session: Authenticated, db: DbSession) -> None:
    await service.delete_job(db, session.user_id, job_id)


@router.post("/applications/{application_id}/status", operation_id="change_status")
async def change_status(
    application_id: uuid.UUID,
    body: StatusChange,
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
) -> JobDetail:
    job = await service.change_status(
        db, session.user_id, application_id, body, today=today_in(settings.timezone)
    )
    return _detail(job)


@router.patch("/applications/{application_id}", operation_id="update_application")
async def update_application(
    application_id: uuid.UUID, body: ApplicationUpdate, session: Authenticated, db: DbSession
) -> JobDetail:
    return _detail(await service.update_application(db, session.user_id, application_id, body))


@router.patch("/jobs/{job_id}/company", operation_id="update_company")
async def update_company(
    job_id: uuid.UUID, body: CompanyUpdate, session: Authenticated, db: DbSession
) -> JobDetail:
    return _detail(await service.update_company(db, session.user_id, job_id, body))


@router.post(
    "/jobs/{job_id}/contacts",
    operation_id="add_contact",
    status_code=status.HTTP_201_CREATED,
)
async def add_contact(
    job_id: uuid.UUID, body: ContactCreate, session: Authenticated, db: DbSession
) -> ContactOut:
    return ContactOut.model_validate(await service.add_contact(db, session.user_id, job_id, body))


@router.delete(
    "/contacts/{contact_id}", operation_id="delete_contact", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_contact(contact_id: uuid.UUID, session: Authenticated, db: DbSession) -> None:
    await service.delete_contact(db, session.user_id, contact_id)
