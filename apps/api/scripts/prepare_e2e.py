"""Create a fresh, separate database for browser end-to-end tests and put one test user in it.

Run from apps/api:  python -m uv run python scripts/prepare_e2e.py [--serve]
With --serve it then starts the API on 127.0.0.1:8011 against that database (worker off, hash
embedder, no AI key, origin http://localhost:3101 allowed), which is what Playwright uses.
The database is always `careerpilot_e2e` (never the development or unit-test database) and is
dropped and recreated each run, so every E2E run starts from the same empty state.
The test user is created only in that database. Its values live in apps/web/e2e/fixtures.ts.
"""

import asyncio
import os
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from careerpilot.core.config import REPO_ROOT, Settings
from careerpilot.modules.auth import service as auth_service

E2E_DB = "careerpilot_e2e"
E2E_EMAIL = "e2e@example.com"
E2E_PASSWORD = (
    "e2e test password 2026"  # test-only value; same constants in apps/web/e2e/fixtures.ts
)
API_DIR = REPO_ROOT / "apps" / "api"


def e2e_url() -> str:
    dev = make_url(Settings().database_url)  # pyright: ignore[reportCallIssue]
    return dev.set(database=E2E_DB).render_as_string(hide_password=False)


async def recreate_database(url: str) -> None:
    admin_url = make_url(url).set(database="postgres").render_as_string(hide_password=False)
    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    try:
        async with admin.connect() as conn:
            await conn.execute(text(f'drop database if exists "{E2E_DB}" with (force)'))
            await conn.execute(text(f'create database "{E2E_DB}"'))
    finally:
        await admin.dispose()


async def create_user(url: str) -> None:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, class_=AsyncSession)() as db:
            await auth_service.create_user(db, E2E_EMAIL, E2E_PASSWORD)  # pyright: ignore[reportArgumentType]
    finally:
        await engine.dispose()


def migrate(url: str) -> None:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "alembic"))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")


def main() -> int:
    os.environ.setdefault("ANTHROPIC_API_KEY", "")
    url = e2e_url()
    if make_url(url).database != E2E_DB:  # belt and braces: never operate on another database
        print("Refusing to run: not the E2E database.", file=sys.stderr)
        return 2
    asyncio.run(recreate_database(url))
    migrate(url)  # runs its own event loop, so it must not be inside asyncio.run
    asyncio.run(create_user(url))
    print(
        f"E2E database ready: {E2E_DB} (user {E2E_EMAIL}). Url host: {make_url(url).host}",
        flush=True,
    )
    if "--serve" in sys.argv:
        import uvicorn

        os.environ["CAREERPILOT_DATABASE_URL"] = url
        os.environ["CAREERPILOT_WORKER_ENABLED"] = "false"
        os.environ["CAREERPILOT_EMBEDDER"] = "hash"
        os.environ["CAREERPILOT_ALLOWED_ORIGINS"] = (
            '["http://localhost:3101","http://127.0.0.1:3101"]'
        )
        uvicorn.run("careerpilot.main:app_factory", factory=True, host="127.0.0.1", port=8011)
    return 0


if __name__ == "__main__":
    sys.exit(main())
