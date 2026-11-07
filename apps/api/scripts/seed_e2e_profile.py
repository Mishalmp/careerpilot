"""Reset the E2E user's profile, so a browser test can start account setup from nothing.

Usage (from apps/api):
  python -m uv run python scripts/seed_e2e_profile.py reset
Only ever touches the `careerpilot_e2e` database (same guard as prepare_e2e.py).
"""

import asyncio
import sys

from prepare_e2e import E2E_DB, E2E_EMAIL, e2e_url
from sqlalchemy import delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import careerpilot.models  # noqa: F401  (registers every table, so the foreign keys resolve)
from careerpilot.modules.auth.models import User
from careerpilot.modules.profile.models import UserProfile


async def reset() -> None:
    url = e2e_url()
    if make_url(url).database != E2E_DB:
        raise SystemExit("Refusing to run: not the E2E database.")
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, class_=AsyncSession)() as db:
            owner = await db.scalar(select(User.id).where(User.email == E2E_EMAIL))
            if owner is None:
                raise SystemExit("The E2E user does not exist.")
            await db.execute(delete(UserProfile).where(UserProfile.owner_id == owner))
            await db.commit()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    if sys.argv[1:] != ["reset"]:
        raise SystemExit(__doc__)
    asyncio.run(reset())
    print("profile reset")
