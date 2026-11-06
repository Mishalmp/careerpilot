"""Put a finished research run with three findings into the E2E database, for browser tests.

Usage (from apps/api):
  python -m uv run python scripts/seed_e2e_findings.py <job_id>   # one seeded run, replaces others
  python -m uv run python scripts/seed_e2e_findings.py reset      # delete all research runs
Only ever touches the `careerpilot_e2e` database (same guard as prepare_e2e.py).
"""

import asyncio
import sys
import uuid
from datetime import UTC, datetime

from prepare_e2e import E2E_DB, E2E_EMAIL, e2e_url
from sqlalchemy import delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import careerpilot.models  # noqa: F401  (registers every table, so the foreign keys resolve)
from careerpilot.modules.auth.models import User
from careerpilot.modules.research.enums import FindingKind, RunStatus
from careerpilot.modules.research.models import ResearchFinding, ResearchRun

FINDINGS = [
    (FindingKind.QUESTION, "database transactions", "What is a database transaction?", 90),
    (FindingKind.QUESTION, "REST API design", "How do you version a REST API?", 80),
    (FindingKind.TOPIC, "caching", "Caching comes up in most backend interviews.", 70),
]


async def seed(job_id: uuid.UUID | None) -> None:
    url = e2e_url()
    if make_url(url).database != E2E_DB:
        raise SystemExit("Refusing to run: not the E2E database.")
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, class_=AsyncSession)() as db:
            owner = await db.scalar(select(User.id).where(User.email == E2E_EMAIL))
            if owner is None:
                raise SystemExit("The E2E user does not exist.")
            await db.execute(
                delete(ResearchRun).where(ResearchRun.owner_id == owner)
            )  # findings cascade
            if job_id is None:
                await db.commit()
                return
            run = ResearchRun(
                owner_id=owner,
                job_id=job_id,
                status=RunStatus.SUCCEEDED,
                queries=["seeded"],
                budgets={"searches": 10, "pages": 12, "tokens": 80000},
                usage={"pages_read": 2, "items_found": 3, "items_dropped": 1},
                finished_at=datetime.now(UTC),
            )
            db.add(run)
            await db.flush()
            for kind, topic, text, relevance in FINDINGS:
                db.add(
                    ResearchFinding(
                        owner_id=owner,
                        run_id=run.id,
                        kind=kind,
                        topic=topic,
                        text=text,
                        quote=text,
                        source_url="https://blog.example.com/interviews",
                        source_title="Backend interview guide",
                        relevance=relevance,
                        dedupe_key=uuid.uuid4().hex[:32],
                    )
                )
            await db.commit()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    target = None if sys.argv[1] == "reset" else uuid.UUID(sys.argv[1])
    asyncio.run(seed(target))
    print("research data reset" if target is None else "seeded 3 findings")
