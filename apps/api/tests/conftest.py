import asyncio
import os
from collections.abc import AsyncIterator

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
