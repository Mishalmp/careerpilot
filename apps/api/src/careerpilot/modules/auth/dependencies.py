import secrets
from typing import Annotated

from fastapi import Cookie, Depends, Request

from careerpilot.core.deps import DbSession
from careerpilot.core.errors import ProblemError
from careerpilot.core.middleware import SAFE_METHODS
from careerpilot.modules.auth import service
from careerpilot.modules.auth.models import AuthSession

COOKIE_NAME = "cp_session"


async def current_session(
    request: Request, db: DbSession, cp_session: Annotated[str | None, Cookie()] = None
) -> AuthSession:
    """Authenticate, and enforce the CSRF header on every state-changing method.

    Every protected route depends on this, so CSRF protection cannot be forgotten per route.
    """
    if cp_session is None:
        raise ProblemError(401, "Not authenticated")
    session = await service.get_live_session(db, cp_session)
    if session is None:
        raise ProblemError(401, "Not authenticated")
    if request.method not in SAFE_METHODS:
        sent = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(sent.encode(), session.csrf_token.encode()):
            raise ProblemError(403, "CSRF token missing or invalid")
    return session


Authenticated = Annotated[AuthSession, Depends(current_session)]
