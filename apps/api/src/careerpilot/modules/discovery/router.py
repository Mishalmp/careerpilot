import uuid

from fastapi import APIRouter, status

from careerpilot.core.clock import today_in
from careerpilot.core.deps import AppFetcher, AppSettings, DbSession
from careerpilot.core.errors import ProblemError
from careerpilot.modules.auth.dependencies import Authenticated
from careerpilot.modules.discovery import service
from careerpilot.modules.discovery.adapters import AdapterError
from careerpilot.modules.discovery.enums import CandidateStatus
from careerpilot.modules.discovery.schemas import (
    AcceptOut,
    CandidateList,
    DiscoverySourceCreate,
    DiscoverySourceOut,
    DiscoverySourceUpdate,
    FollowedOut,
    FollowSuggested,
    RunOut,
    SearchProfileIn,
    SearchProfileOut,
    SearchProfileUpdate,
    SuggestedBoardOut,
)

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.get("/sources", operation_id="list_discovery_sources")
async def list_sources(session: Authenticated, db: DbSession) -> list[DiscoverySourceOut]:
    return await service.list_sources(db, session.user_id)


@router.get("/suggestions", operation_id="list_suggested_boards")
async def list_suggested(
    session: Authenticated, db: DbSession, settings: AppSettings
) -> list[SuggestedBoardOut]:
    """Company boards that were checked and are worth following (content/job-boards.yaml)."""
    return await service.suggested(db, session.user_id, settings.content_dir)


@router.post("/suggestions/follow", operation_id="follow_suggested_boards")
async def follow_suggested(
    body: FollowSuggested, session: Authenticated, db: DbSession, settings: AppSettings
) -> FollowedOut:
    return await service.follow_suggested(db, session.user_id, settings.content_dir, body.keys)


@router.post("/sources", operation_id="add_discovery_source", status_code=status.HTTP_201_CREATED)
async def add_source(
    body: DiscoverySourceCreate, session: Authenticated, db: DbSession
) -> DiscoverySourceOut:
    """Follow a company's public job board (Greenhouse, Lever or Ashby)."""
    return await service.add_source(db, session.user_id, body)


@router.patch("/sources/{source_id}", operation_id="update_discovery_source")
async def update_source(
    source_id: uuid.UUID, body: DiscoverySourceUpdate, session: Authenticated, db: DbSession
) -> DiscoverySourceOut:
    return await service.update_source(db, session.user_id, source_id, body)


@router.delete(
    "/sources/{source_id}",
    operation_id="delete_discovery_source",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_source(source_id: uuid.UUID, session: Authenticated, db: DbSession) -> None:
    await service.delete_source(db, session.user_id, source_id)


@router.post("/sources/{source_id}/run", operation_id="run_discovery_source")
async def run_source(
    source_id: uuid.UUID, session: Authenticated, db: DbSession, fetcher: AppFetcher
) -> RunOut:
    """Read the board now. The daily run does the same through the task queue."""
    try:
        return await service.run_source(db, session.user_id, source_id, fetcher)
    except AdapterError as exc:
        raise ProblemError(502, "The board could not be read", str(exc)) from exc


@router.get("/candidates", operation_id="list_discovery_candidates")
async def list_candidates(
    session: Authenticated,
    db: DbSession,
    status: CandidateStatus = CandidateStatus.NEW,
    source_id: uuid.UUID | None = None,
) -> CandidateList:
    return await service.list_candidates(db, session.user_id, status, source_id)


@router.post("/candidates/{candidate_id}/accept", operation_id="accept_discovery_candidate")
async def accept(
    candidate_id: uuid.UUID,
    session: Authenticated,
    db: DbSession,
    settings: AppSettings,
    fetcher: AppFetcher,
) -> AcceptOut:
    """Add the listing to your tracker as a new job."""
    return await service.accept(
        db, session.user_id, candidate_id, fetcher, today=today_in(settings.timezone)
    )


@router.post(
    "/candidates/{candidate_id}/dismiss",
    operation_id="dismiss_discovery_candidate",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def dismiss(candidate_id: uuid.UUID, session: Authenticated, db: DbSession) -> None:
    await service.set_status(db, session.user_id, candidate_id, CandidateStatus.DISMISSED)


@router.post(
    "/candidates/{candidate_id}/restore",
    operation_id="restore_discovery_candidate",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def restore(candidate_id: uuid.UUID, session: Authenticated, db: DbSession) -> None:
    await service.set_status(db, session.user_id, candidate_id, CandidateStatus.NEW)


@router.get("/searches", operation_id="list_search_profiles")
async def list_searches(session: Authenticated, db: DbSession) -> list[SearchProfileOut]:
    """The ways you search: regions, cities and ways of working. Several are alternatives."""
    return await service.list_profiles(db, session.user_id)


@router.post("/searches", operation_id="create_search_profile", status_code=status.HTTP_201_CREATED)
async def create_search(
    body: SearchProfileIn, session: Authenticated, db: DbSession
) -> SearchProfileOut:
    return await service.create_profile(db, session.user_id, body)


@router.patch("/searches/{profile_id}", operation_id="update_search_profile")
async def update_search(
    profile_id: uuid.UUID, body: SearchProfileUpdate, session: Authenticated, db: DbSession
) -> SearchProfileOut:
    return await service.update_profile(db, session.user_id, profile_id, body)


@router.delete(
    "/searches/{profile_id}",
    operation_id="delete_search_profile",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_search(profile_id: uuid.UUID, session: Authenticated, db: DbSession) -> None:
    await service.delete_profile(db, session.user_id, profile_id)
