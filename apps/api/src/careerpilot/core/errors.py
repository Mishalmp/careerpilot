from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_JSON = "application/problem+json"


class ProblemError(Exception):
    """Raise anywhere to return an RFC 9457 problem response."""

    def __init__(
        self,
        status: int,
        title: str,
        detail: str | None = None,
        headers: dict[str, str] | None = None,
        **extra: Any,
    ) -> None:
        super().__init__(title)
        self.status = status
        self.title = title
        self.detail = detail
        self.headers = headers
        self.extra = extra


def problem_response(
    status: int,
    title: str,
    detail: str | None = None,
    headers: Mapping[str, str] | None = None,
    **extra: Any,
) -> JSONResponse:
    body: dict[str, Any] = {"type": "about:blank", "title": title, "status": status}
    if detail:
        body["detail"] = detail
    body.update(extra)
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemError)
    async def _problem(_: Request, exc: ProblemError) -> JSONResponse:
        return problem_response(exc.status, exc.title, exc.detail, exc.headers, **exc.extra)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem_response(
            exc.status_code, HTTPStatus(exc.status_code).phrase, str(exc.detail), exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic errors echo the submitted value ("input"), which can be a password. Drop it.
        errors = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return problem_response(422, "Validation failed", errors=errors)
