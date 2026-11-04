import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from careerpilot.core.errors import problem_response

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

log = structlog.get_logger()

Next = Callable[[Request], Awaitable[Response]]


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Server-generated request id (never trusted from the client), one log line, safe headers."""

    async def dispatch(self, request: Request, call_next: Next) -> Response:
        request_id = uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        log.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return response


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """Reject state-changing requests whose Origin is not the web app.

    Browsers always send Origin on cross-site POST, so a hostile page cannot slip through.
    Requests without Origin (curl, tests) pass here but still need the CSRF header when
    they carry a session.
    """

    def __init__(self, app: ASGIApp, allowed_origins: list[str]) -> None:
        super().__init__(app)
        self._allowed = frozenset(allowed_origins)

    async def dispatch(self, request: Request, call_next: Next) -> Response:
        if request.method not in SAFE_METHODS:
            origin = request.headers.get("origin")
            if origin is not None and origin not in self._allowed:
                return problem_response(403, "Forbidden", "Origin not allowed")
        return await call_next(request)
