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

    def __init__(self, app: ASGIApp, *, hsts: bool = False) -> None:
        super().__init__(app)
        self._hsts = hsts

    async def dispatch(self, request: Request, call_next: Next) -> Response:
        request_id = uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        # The API only ever returns data: nothing it sends may be framed, scripted or embedded.
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if self._hsts:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
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


class LimitsMiddleware(BaseHTTPMiddleware):
    """Two blunt safety nets: a request-size cap and a per-address requests-per-minute cap.

    The size check trusts Content-Length (a client that lies is cut off by the server's own body
    limits); the rate limit is a fixed one-minute window held in this process. Both answer with a
    plain problem response, so the web app can show the reason.
    """

    def __init__(self, app: ASGIApp, *, per_minute: int, max_body_bytes: int) -> None:
        super().__init__(app)
        self._per_minute = per_minute
        self._max_body = max_body_bytes
        self._window = 0
        self._counts: dict[str, int] = {}

    def _allow(self, client: str) -> bool:
        if self._per_minute <= 0:
            return True
        window = int(time.monotonic() // 60)
        if window != self._window:
            self._window, self._counts = window, {}
        self._counts[client] = self._counts.get(client, 0) + 1
        return self._counts[client] <= self._per_minute

    async def dispatch(self, request: Request, call_next: Next) -> Response:
        length = request.headers.get("content-length", "")
        if length.isdigit() and int(length) > self._max_body:
            return problem_response(413, "Request too large", "That upload is bigger than allowed.")
        client = request.client.host if request.client else "unknown"
        if not self._allow(client):
            return problem_response(
                429, "Too many requests", "Slow down: too many requests in one minute."
            )
        return await call_next(request)
