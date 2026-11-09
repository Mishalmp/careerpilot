"""Safety nets: response headers, size and rate limits, hidden docs, and no secrets in the repo.
# covers: security hardening (docs/phase-7/16): headers on every response, a request-size cap, a
# per-minute request cap, no public API docs by default, and a guard against committed secrets
"""

import re
import subprocess
from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from careerpilot.core.config import REPO_ROOT, Settings
from careerpilot.main import create_app


def app_with(base: Settings, **changes: object) -> FastAPI:
    return create_app(base.model_copy(update={"worker_enabled": False, **changes}))


async def get(app: FastAPI, path: str = "/healthz", **kw: object) -> tuple[int, dict[str, str]]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
        response = await c.get(path, **kw)  # type: ignore[arg-type]
        return response.status_code, dict(response.headers)


async def test_every_response_carries_the_safety_headers(settings: Settings) -> None:
    status, headers = await get(app_with(settings))
    assert status == 200
    assert headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["cache-control"] == "no-store"
    assert "strict-transport-security" not in headers  # only when the cookie is Secure (HTTPS)

    _, secure = await get(app_with(settings, cookie_secure=True))
    assert secure["strict-transport-security"].startswith("max-age=")


async def test_the_api_docs_are_not_public_unless_asked_for(settings: Settings) -> None:
    for path in ("/docs", "/openapi.json", "/redoc"):
        assert (await get(app_with(settings), path))[0] == 404
    assert (await get(app_with(settings, expose_api_docs=True), "/openapi.json"))[0] == 200


async def test_too_many_requests_in_a_minute_get_a_plain_429(settings: Settings) -> None:
    app = app_with(settings, rate_limit_per_minute=3)
    codes = [(await get(app))[0] for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    off = app_with(settings, rate_limit_per_minute=0)
    assert [(await get(off))[0] for _ in range(5)] == [200] * 5


async def test_a_huge_body_is_refused_before_it_is_read(settings: Settings) -> None:
    app = app_with(settings, max_body_bytes=2000)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
        big = await c.post("/api/v1/auth/login", content=b"x" * 5000)
        assert big.status_code == 413 and big.json()["title"] == "Request too large"
        small = await c.post("/api/v1/auth/login", json={"email": "a@b.example", "password": "x"})
        assert small.status_code != 413


# --- secrets ---------------------------------------------------------------------------------

_PATTERNS = {
    "Anthropic key": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    "Telegram bot token": re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}


def test_no_secret_is_committed_anywhere_in_the_repository() -> None:
    files = subprocess.run(
        ["git", "ls-files"],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    found: list[str] = []
    for name in files:
        path = Path(REPO_ROOT, name)
        if path.suffix in {".png", ".jpg", ".ico", ".woff", ".woff2", ".wasm", ".zip", ".gz"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        found += [f"{name}: {label}" for label, rx in _PATTERNS.items() if rx.search(text)]
    assert found == []
