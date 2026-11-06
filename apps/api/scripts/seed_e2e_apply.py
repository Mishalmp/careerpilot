"""Put daily-apply-list items into the E2E database, for browser tests.

Usage (from apps/api):
  python -m uv run python scripts/seed_e2e_apply.py seed    # a ready item and a held-back item
  python -m uv run python scripts/seed_e2e_apply.py reset   # delete all apply items
Only ever touches the `careerpilot_e2e` database (same guard as prepare_e2e.py).
"""

import asyncio
import sys
from datetime import UTC, date, datetime

from prepare_e2e import E2E_DB, E2E_EMAIL, e2e_url
from sqlalchemy import delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import careerpilot.models  # noqa: F401  (registers every table, so the foreign keys resolve)
from careerpilot.modules.apply.enums import ApplyStatus
from careerpilot.modules.apply.models import ApplyItem
from careerpilot.modules.auth.models import User
from careerpilot.modules.tracker.models import Company, Job

PAY = {
    "level": "same_job_elsewhere",
    "label": "The same job, listed on another site",
    "currency": "INR",
    "low": 1_400_000,
    "mid": 1_700_000,
    "high": 2_000_000,
    "n": 1,
    "evidence": [
        {
            "url": "https://jobs.example.net/acme-python",
            "title": "Python Developer - Acme | Example Jobs",
            "quote": "Acme is hiring a Python Developer. Salary 14 - 20 LPA.",
        }
    ],
    "tried": [
        {"label": "This post", "found": False, "note": "The post does not state the pay."},
        {
            "label": "The same job on other sites",
            "found": True,
            "note": "1 listing(s) found; a figure is on them.",
        },
    ],
}
INTERVIEW = {
    "level": "similar_roles",
    "label": "Typical for this kind of role (not this company)",
    "points": [
        {
            "url": "https://guide.example.org/python",
            "title": "Python developer interview guide",
            "quote": "A Python interview has a screening call, a coding round and a design round.",
        }
    ],
    "tried": [
        {"label": "This post", "found": False, "note": "The post says nothing about it."},
        {"label": "This company's interview process", "found": False, "note": "Nothing found."},
        {
            "label": "Similar roles elsewhere",
            "found": True,
            "note": "A typical process is described on a page.",
        },
    ],
}


async def seed(mode: str) -> None:
    url = e2e_url()
    if make_url(url).database != E2E_DB:
        raise SystemExit("Refusing to run: not the E2E database.")
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, class_=AsyncSession)() as db:
            owner = await db.scalar(select(User.id).where(User.email == E2E_EMAIL))
            if owner is None:
                raise SystemExit("The E2E user does not exist.")
            await db.execute(delete(ApplyItem).where(ApplyItem.owner_id == owner))
            if mode == "seed":
                for company, status, score in (
                    ("Applyco", ApplyStatus.READY, 90),
                    ("Heldco", ApplyStatus.BLOCKED, 60),
                ):
                    job = await db.scalar(
                        select(Job)
                        .join(Company)
                        .where(Job.owner_id == owner, Company.name == company)
                    )
                    if job is None:
                        raise SystemExit(f"Seed the jobs first: no job for {company}.")
                    blocked = status is ApplyStatus.BLOCKED
                    db.add(
                        ApplyItem(
                            owner_id=owner,
                            job_id=job.id,
                            queued_on=date.today(),
                            status=status,
                            match_score=score,
                            reasons=[
                                "You have 3 of the 4 skills it names (fastapi, python, sql).",
                                "The title is like one on your CV (Python Full Stack Developer).",
                            ],
                            pay=None if blocked else PAY,
                            interview=None if blocked else INTERVIEW,
                            also_listed=[]
                            if blocked
                            else [
                                {
                                    "url": "https://jobs.example.net/acme-python",
                                    "title": "Python Developer - Acme",
                                    "host": "jobs.example.net",
                                    "kind": "same_job",
                                    "overlap": 0.75,
                                    "opened": True,
                                }
                            ],
                            company_check={
                                "verdict": "suspicious" if blocked else "likely_genuine",
                                "passed": 1 if blocked else 5,
                                "total": 8,
                                "flags": ["asks_for_money"] if blocked else [],
                                "note": "Red flag raised: asks for money."
                                if blocked
                                else "5 of 8 checks passed; no red flags.",
                            },
                            notes=[],
                            enriched_at=datetime.now(UTC),
                            decision_note="Red flag raised: asks for money." if blocked else None,
                        )
                    )
            await db.commit()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("seed", "reset"):
        raise SystemExit(__doc__)
    asyncio.run(seed(sys.argv[1]))
    print("apply items " + ("seeded" if sys.argv[1] == "seed" else "reset"))
