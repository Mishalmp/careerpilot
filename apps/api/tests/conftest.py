import asyncio
import os
import shutil
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from careerpilot.core.config import REPO_ROOT, Settings
from careerpilot.main import create_app
from careerpilot.modules.auth import service

TEST_DB = "careerpilot_test"
API_DIR = REPO_ROOT / "apps" / "api"
PASSWORD = "correct horse battery"
EMAIL = "owner@example.com"

# Point every code path at a separate database so tests can never touch development data.
_dev_url = make_url(Settings().database_url)  # pyright: ignore[reportCallIssue]
TEST_URL = _dev_url.set(database=TEST_DB).render_as_string(hide_password=False)
os.environ["CAREERPILOT_DATABASE_URL"] = TEST_URL
# Tests never download the embedding model or call the AI provider.
os.environ["CAREERPILOT_EMBEDDER"] = "hash"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["CAREERPILOT_WORKER_ENABLED"] = "false"  # tests run tasks by hand


def alembic_config() -> Config:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "alembic"))
    config.attributes["database_url"] = TEST_URL
    return config


async def _ensure_database() -> None:
    admin_url = _dev_url.set(database="postgres").render_as_string(hide_password=False)
    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    try:
        async with admin.connect() as conn:
            found = await conn.scalar(
                text("select 1 from pg_database where datname = :name"), {"name": TEST_DB}
            )
            if not found:
                await conn.execute(text(f'create database "{TEST_DB}"'))
    finally:
        await admin.dispose()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def database() -> None:
    await _ensure_database()
    # Alembic's env.py runs its own event loop, so it must run off this one.
    await asyncio.to_thread(command.upgrade, alembic_config(), "head")


@pytest.fixture
def settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]


@pytest_asyncio.fixture
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    app = create_app(settings)
    async with app.state.engine.begin() as conn:
        await conn.execute(text("truncate users, sessions cascade"))
    yield app
    await app.state.engine.dispose()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost"
    ) as http_client:
        yield http_client


@pytest_asyncio.fixture
async def user(app: FastAPI) -> None:
    async with app.state.sessionmaker() as db:
        await service.create_user(db, EMAIL, PASSWORD)


async def sign_in(app: FastAPI, email: str, password: str) -> AsyncClient:
    """A client already signed in: cookie and CSRF header are sent on every request."""
    http = AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost")
    response = await http.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    http.headers["Cookie"] = f"cp_session={response.cookies['cp_session']}"
    http.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return http


@pytest_asyncio.fixture
async def api(app: FastAPI, user: None) -> AsyncIterator[AsyncClient]:
    http = await sign_in(app, EMAIL, PASSWORD)
    yield http
    await http.aclose()


@pytest_asyncio.fixture
async def other_api(app: FastAPI, user: None) -> AsyncIterator[AsyncClient]:
    """A second, separate user, for tests that prove one owner cannot see another's data."""
    async with app.state.sessionmaker() as db:
        await service.create_user(db, "other@example.com", PASSWORD)
    http = await sign_in(app, "other@example.com", PASSWORD)
    yield http
    await http.aclose()


@pytest_asyncio.fixture
async def owner_id(app: FastAPI, user: None) -> uuid.UUID:
    async with app.state.sessionmaker() as db:
        return (await service.sole_user(db)).id


PROFILE = """\
years_experience: 2
target_levels: [junior, mid]
skills: [Python, SQL, Postgres, Docker, FastAPI, React]
regions: [India, Remote (Global)]
needs_visa_sponsorship: false
salary_floor_lpa: 10
salary_target_lpa: 20
"""


@pytest.fixture
def content(app: FastAPI, tmp_path: Path) -> Path:
    """A content folder with the real vocabulary and a test profile (for scoring)."""
    shutil.copy(REPO_ROOT / "content" / "skills.yaml", tmp_path / "skills.yaml")
    (tmp_path / "private").mkdir()
    (tmp_path / "private" / "profile.yaml").write_text(PROFILE, encoding="utf-8")
    app.state.settings = app.state.settings.model_copy(update={"content_dir": tmp_path})
    return tmp_path
