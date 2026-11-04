import asyncio

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from careerpilot.models import metadata
from tests.conftest import TEST_URL, alembic_config


async def _tables() -> set[str]:
    engine = create_async_engine(TEST_URL, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            return set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    finally:
        await engine.dispose()


async def test_migrations_apply_down_and_up_again() -> None:
    assert {"users", "sessions"} <= await _tables()
    await asyncio.to_thread(command.downgrade, alembic_config(), "base")
    assert not {"users", "sessions"} & await _tables()
    await asyncio.to_thread(command.upgrade, alembic_config(), "head")
    assert {"users", "sessions"} <= await _tables()


async def test_models_match_migrations() -> None:
    """Fails when a model changes without a migration (or the reverse)."""
    engine = create_async_engine(TEST_URL, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            diff = await conn.run_sync(
                lambda c: compare_metadata(MigrationContext.configure(c), metadata)
            )
    finally:
        await engine.dispose()
    assert diff == []
