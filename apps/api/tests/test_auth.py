from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from careerpilot.core.config import Settings
from careerpilot.main import create_app
from tests.conftest import EMAIL, PASSWORD

LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"
LOGOUT = "/api/v1/auth/logout"


async def login(client: AsyncClient) -> tuple[dict[str, str], str]:
    """Return (cookie header, csrf token). Cookies are passed explicitly, not via the jar."""
    response = await client.post(LOGIN, json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Cookie": f"cp_session={response.cookies['cp_session']}"}, response.json()["csrf_token"]


@pytest.mark.usefixtures("user")
async def test_login_sets_hardened_cookie_and_returns_csrf(client: AsyncClient) -> None:
    response = await client.post(LOGIN, json={"email": EMAIL.upper(), "password": PASSWORD})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/" in cookie
    body = response.json()
    assert body["user"]["email"] == EMAIL
    assert len(body["csrf_token"]) >= 32
    assert PASSWORD not in response.text


@pytest.mark.usefixtures("user")
async def test_wrong_password_and_unknown_email_look_identical(client: AsyncClient) -> None:
    wrong = await client.post(LOGIN, json={"email": EMAIL, "password": "nope"})
    unknown = await client.post(LOGIN, json={"email": "who@example.com", "password": "nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


async def test_me_requires_a_valid_session(client: AsyncClient) -> None:
    assert (await client.get(ME)).status_code == 401
    forged = await client.get(ME, headers={"Cookie": "cp_session=forged-token"})
    assert forged.status_code == 401


@pytest.mark.usefixtures("user")
async def test_me_returns_the_session_user_and_csrf(client: AsyncClient) -> None:
    cookie, csrf = await login(client)
    response = await client.get(ME, headers=cookie)
    assert response.status_code == 200
    assert response.json()["user"]["email"] == EMAIL
    assert response.json()["csrf_token"] == csrf


@pytest.mark.usefixtures("user")
async def test_logout_needs_csrf_header_then_revokes_the_session(client: AsyncClient) -> None:
    cookie, csrf = await login(client)
    assert (await client.post(LOGOUT, headers=cookie)).status_code == 403
    wrong = await client.post(LOGOUT, headers={**cookie, "X-CSRF-Token": "wrong"})
    assert wrong.status_code == 403
    assert (await client.get(ME, headers=cookie)).status_code == 200

    done = await client.post(LOGOUT, headers={**cookie, "X-CSRF-Token": csrf})
    assert done.status_code == 204
    assert (await client.get(ME, headers=cookie)).status_code == 401


@pytest.mark.usefixtures("user")
async def test_validation_errors_do_not_echo_the_password(client: AsyncClient) -> None:
    response = await client.post(LOGIN, json={"email": "not-an-email", "password": PASSWORD})
    assert response.status_code == 422
    assert PASSWORD not in response.text


@pytest.mark.usefixtures("user")
async def test_state_changing_request_from_foreign_origin_is_rejected(client: AsyncClient) -> None:
    body = {"email": EMAIL, "password": PASSWORD}
    foreign = await client.post(LOGIN, json=body, headers={"Origin": "https://evil.example"})
    assert foreign.status_code == 403
    own = await client.post(LOGIN, json=body, headers={"Origin": "http://localhost:3100"})
    assert own.status_code == 200


@pytest.mark.usefixtures("user")
async def test_login_is_throttled_after_repeated_failures(settings: Settings) -> None:
    app = create_app(settings.model_copy(update={"login_max_failures": 3}))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
        for _ in range(3):
            bad = await c.post(LOGIN, json={"email": EMAIL, "password": "bad"})
            assert bad.status_code == 401
        blocked = await c.post(LOGIN, json={"email": EMAIL, "password": PASSWORD})
        assert blocked.status_code == 429
        assert int(blocked.headers["retry-after"]) > 0
    await app.state.engine.dispose()


@pytest.mark.usefixtures("user")
async def test_successful_login_resets_the_failure_count(settings: Settings) -> None:
    app = create_app(settings.model_copy(update={"login_max_failures": 2}))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
        assert (await c.post(LOGIN, json={"email": EMAIL, "password": "bad"})).status_code == 401
        assert (await c.post(LOGIN, json={"email": EMAIL, "password": PASSWORD})).status_code == 200
        assert (await c.post(LOGIN, json={"email": EMAIL, "password": "bad"})).status_code == 401
    await app.state.engine.dispose()


@pytest.mark.usefixtures("user")
async def test_expired_session_is_rejected(app: FastAPI, client: AsyncClient) -> None:
    cookie, _ = await login(client)
    async with app.state.engine.begin() as conn:
        await conn.execute(
            text("update sessions set expires_at = :t"),
            {"t": datetime.now(UTC) - timedelta(minutes=1)},
        )
    assert (await client.get(ME, headers=cookie)).status_code == 401


async def test_resetting_a_password_changes_it_and_signs_every_session_out(
    app: FastAPI, user: None, client: AsyncClient
) -> None:
    from careerpilot.modules.auth import service

    login = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert login.status_code == 200
    async with app.state.sessionmaker() as db:
        await service.reset_password(db, EMAIL.upper(), "a brand new password 2026")
    assert (await client.get("/api/v1/auth/me")).status_code == 401  # the old session is gone
    old = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert old.status_code == 401
    new = await client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": "a brand new password 2026"}
    )
    assert new.status_code == 200


async def test_resetting_refuses_a_short_password_and_an_unknown_user(
    app: FastAPI, user: None
) -> None:
    from careerpilot.modules.auth import service

    async with app.state.sessionmaker() as db:
        with pytest.raises(ValueError, match="at least"):
            await service.reset_password(db, EMAIL, "short")
        with pytest.raises(service.UserNotFoundError):
            await service.reset_password(db, "nobody@example.com", "a long enough password 1")
