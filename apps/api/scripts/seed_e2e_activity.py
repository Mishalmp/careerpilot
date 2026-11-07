"""Put background tasks (with history) and AI calls into the E2E database, for browser tests.

Usage (from apps/api):
  python -m uv run python scripts/seed_e2e_activity.py seed    # four tasks and three AI calls
  python -m uv run python scripts/seed_e2e_activity.py reset   # delete them all
Only ever touches the `careerpilot_e2e` database (same guard as prepare_e2e.py).
"""

import asyncio
import sys
from datetime import UTC, datetime, timedelta

from prepare_e2e import E2E_DB, E2E_EMAIL, e2e_url
from sqlalchemy import delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import careerpilot.models  # noqa: F401  (registers every table, so the foreign keys resolve)
from careerpilot.core.llm import LlmCall
from careerpilot.modules.auth.models import User
from careerpilot.modules.tasks.enums import TaskKind, TaskStatus
from careerpilot.modules.tasks.models import Task, TaskEvent


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
            await db.execute(delete(Task).where(Task.owner_id == owner))  # events cascade
            await db.execute(delete(LlmCall).where(LlmCall.owner_id == owner))
            if mode == "seed":
                now = datetime.now(UTC)
                specs = [
                    (
                        TaskKind.RESEARCH,
                        TaskStatus.FAILED,
                        "Unexpected error; see the server log.",
                        {"step": "Reading page 2 of 3", "done": 1, "total": 3},
                        [
                            ("info", "Attempt 1 of 1 started."),
                            ("info", "Searching 1 of 4"),
                            ("info", "Reading page 1 of 3"),
                            ("info", "Reading page 2 of 3"),
                            (
                                "error",
                                "Unexpected error; see the server log. Gave up after 1 attempt(s).",
                            ),
                        ],
                    ),
                    (
                        TaskKind.APPLY_QUEUE,
                        TaskStatus.RUNNING,
                        None,
                        {"step": "Researching Acme: Python Developer", "done": 1, "total": 3},
                        [
                            ("info", "Attempt 1 of 1 started."),
                            ("info", "Researching Acme: Python Developer"),
                        ],
                    ),
                    (TaskKind.DAILY_DIGEST, TaskStatus.QUEUED, None, None, []),
                    (
                        TaskKind.BACKUP,
                        TaskStatus.SUCCEEDED,
                        None,
                        {
                            "step": "Dumping, encrypting and pruning the backup",
                            "done": None,
                            "total": None,
                        },
                        [("info", "Attempt 1 of 3 started."), ("info", "Finished.")],
                    ),
                ]
                for index, (kind, status, error, progress, events) in enumerate(specs):
                    task = Task(
                        owner_id=owner,
                        kind=kind,
                        key=f"e2e:{kind.value}:{index}",
                        payload={},
                        status=status,
                        attempts=1 if status is not TaskStatus.QUEUED else 0,
                        max_attempts=1 if kind is TaskKind.RESEARCH else 3,
                        error=error,
                        progress=progress,
                        run_after=now,
                        started_at=now if status is not TaskStatus.QUEUED else None,
                        finished_at=now
                        if status in (TaskStatus.FAILED, TaskStatus.SUCCEEDED)
                        else None,
                        created_at=now - timedelta(minutes=index),
                    )
                    db.add(task)
                    await db.flush()
                    for offset, (level, message) in enumerate(events):
                        db.add(
                            TaskEvent(
                                task_id=task.id,
                                owner_id=owner,
                                at=now - timedelta(seconds=60 - offset),
                                attempt=1,
                                level=level,
                                step=None,
                                message=message,
                            )
                        )
                for purpose, status, error in (
                    ("research-extract", "ok", None),
                    ("jd-reading", "error", "The model service is busy."),
                    ("research-extract", "ok", None),
                ):
                    db.add(
                        LlmCall(
                            owner_id=owner,
                            purpose=purpose,
                            model="claude-haiku-5-5",
                            input_tokens=1200,
                            output_tokens=300,
                            latency_ms=900,
                            status=status,
                            error=error,
                        )
                    )
            await db.commit()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("seed", "reset"):
        raise SystemExit(__doc__)
    asyncio.run(seed(sys.argv[1]))
    print("activity " + ("seeded" if sys.argv[1] == "seed" else "reset"))
