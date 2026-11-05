"""Security properties that must hold for every route, now and for any route added later."""

import re
import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# Routes a visitor who is not signed in may call. Everything else must answer 401.
PUBLIC = {
    ("GET", "/healthz"),
    ("GET", "/readyz"),
    ("POST", "/api/v1/auth/login"),
}
PARAM = re.compile(r"\{[^}]+\}")


def operations(app: FastAPI) -> list[tuple[str, str]]:
    schema = app.openapi()
    found: list[tuple[str, str]] = []
    for path, item in schema["paths"].items():
        for method in item:
            if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                found.append((method.upper(), path))
    return sorted(found)


def concrete(path: str) -> str:
    return PARAM.sub(str(uuid.uuid4()), path)


async def test_the_api_has_the_routes_this_test_expects(app: FastAPI) -> None:
    found = operations(app)
    assert len(found) > 60  # a guard against the walk silently finding nothing
    assert {op for op in PUBLIC} <= set(found) | {("GET", "/healthz"), ("GET", "/readyz")}


async def test_every_route_refuses_a_visitor_who_is_not_signed_in(
    app: FastAPI, client: AsyncClient
) -> None:
    open_routes: list[str] = []
    for method, path in operations(app):
        if (method, path) in PUBLIC:
            continue
        response = await client.request(
            method, concrete(path), json={} if method != "GET" else None
        )
        if response.status_code != 401:
            open_routes.append(f"{method} {path} -> {response.status_code}")
    assert open_routes == [], "routes that answered an anonymous caller:\n" + "\n".join(open_routes)


async def test_every_state_changing_route_also_demands_the_csrf_token(
    app: FastAPI, api: AsyncClient
) -> None:
    """A signed-in cookie alone, as a hostile web page would have, must not be enough."""
    cookie = {"Cookie": api.headers["Cookie"]}
    unprotected: list[str] = []
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as bare:
        for method, path in operations(app):
            if method == "GET" or (method, path) in PUBLIC:
                continue
            body: dict[str, Any] = {}
            response = await bare.request(method, concrete(path), json=body, headers=cookie)
            if response.status_code != 403:  # signed in, but no token: exactly 403, not 401
                unprotected.append(f"{method} {path} -> {response.status_code}")
    assert unprotected == [], (
        "state-changing routes that worked without a CSRF token:\n" + "\n".join(unprotected)
    )


@pytest.mark.parametrize(
    ("origin", "expected"),
    [("http://localhost:3100", False), ("https://evil.example", True), ("null", True)],
)
async def test_a_cross_site_request_with_a_session_is_rejected(
    api: AsyncClient, origin: str, expected: bool
) -> None:
    response = await api.post("/api/v1/stories", json={}, headers={"Origin": origin})
    assert (response.status_code == 403) is expected
