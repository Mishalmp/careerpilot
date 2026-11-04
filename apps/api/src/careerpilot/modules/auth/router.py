from fastapi import APIRouter, Request, Response, status

from careerpilot.core.deps import AppSettings, DbSession
from careerpilot.modules.auth import service
from careerpilot.modules.auth.dependencies import COOKIE_NAME, Authenticated
from careerpilot.modules.auth.models import AuthSession
from careerpilot.modules.auth.schemas import LoginRequest, SessionOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _session_out(session: AuthSession) -> SessionOut:
    return SessionOut(user=UserOut.model_validate(session.user), csrf_token=session.csrf_token)


@router.post("/login", operation_id="login")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
) -> SessionOut:
    result = await service.authenticate(
        db,
        request.app.state.login_throttle,
        settings,
        body.email,
        body.password.get_secret_value(),
    )
    response.set_cookie(
        COOKIE_NAME,
        result.token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    return _session_out(result.session)


@router.get("/me", operation_id="me")
async def me(session: Authenticated) -> SessionOut:
    return _session_out(session)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, operation_id="logout")
async def logout(session: Authenticated, db: DbSession, response: Response) -> None:
    await service.logout(db, session)
    response.delete_cookie(COOKIE_NAME, path="/")
