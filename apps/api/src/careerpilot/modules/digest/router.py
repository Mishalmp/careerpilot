from fastapi import APIRouter

from careerpilot.core.deps import DbSession
from careerpilot.modules.auth.dependencies import Authenticated
from careerpilot.modules.digest import service
from careerpilot.modules.digest.schemas import DigestOut

router = APIRouter(prefix="/digest", tags=["digest"])


@router.get("/latest", operation_id="latest_digest")
async def latest_digest(session: Authenticated, db: DbSession) -> DigestOut | None:
    """The most recent daily digest, or null before the first one has been built."""
    return await service.latest(db, session.user_id)
