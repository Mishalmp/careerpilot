"""What a task did, step by step, and continuing from where it stopped.
# covers: REQ-19 (long work shows progress; failures are visible and retryable from the screen)
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select

from careerpilot.modules.apply.enums import ApplyStatus
from careerpilot.modules.apply.models import ApplyItem
from careerpilot.modules.auth.models import User
from careerpilot.modules.tasks import service as tasks
from careerpilot.modules.tasks.enums import TaskKind, TaskStatus
from careerpilot.modules.tasks.service import TaskFailure
from tests.conftest import EMAIL
from tests.fakes import FakeLlm, FakeSearch, FakeWeb, run_worker
from tests.test_research_api import GOOD_A, GOOD_B, PAGES, hits, job, setup, start

TASKS = "/api/v1/tasks"


async def enqueue(app: FastAPI, owner: uuid.UUID, key: str = "k", attempts: int = 2) -> None:
    async with app.state.sessionmaker() as db:
        await tasks.enqueue(db, owner, TaskKind.BACKUP, key, {}, max_attempts=attempts)
        await db.commit()


async def run_with(app: FastAPI, handler: Any) -> bool:
    return await tasks.run_next(app.state.sessionmaker, {TaskKind.BACKUP: handler})


async def detail(api: AsyncClient, task_id: str) -> dict[str, Any]:
    response = await api.get(f"{TASKS}/{task_id}")
    assert response.status_code == 200, response.text
    return response.json()


async def only_task(api: AsyncClient) -> dict[str, Any]:
    (item,) = (await api.get(TASKS)).json()["items"]
    return item


# --- history --------------------------------------------------------------------------------


async def test_a_finished_task_keeps_its_steps_in_order(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID
) -> None:
    async def handler(db: Any, task: Any) -> None:
        await tasks.step("Reading page 1 of 2", done=0, total=2)
        await tasks.step("Reading page 2 of 2", done=1, total=2)

    await enqueue(app, owner_id)
    assert await run_with(app, handler)
    shown = await detail(api, (await only_task(api))["id"])
    assert [e["message"] for e in shown["events"]] == [
        "Attempt 1 of 2 started.",
        "Reading page 1 of 2",
        "Reading page 2 of 2",
        "Finished.",
    ]
    assert shown["task"]["status"] == "succeeded"
    assert shown["task"]["progress"] == {"step": "Reading page 2 of 2", "done": 1, "total": 2}


async def test_a_failed_attempt_still_has_its_history_and_the_reason(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID
) -> None:
    async def handler(db: Any, task: Any) -> None:
        await tasks.step("Dumping the database")
        await tasks.warn("The disk is nearly full.")
        raise TaskFailure("The backup folder is not writable.")

    await enqueue(app, owner_id, attempts=1)
    await run_with(app, handler)
    task = await only_task(api)
    assert task["status"] == "failed" and task["progress"]["step"] == "Dumping the database"
    events = (await detail(api, task["id"]))["events"]
    assert [(e["level"], e["message"]) for e in events][1:] == [
        ("info", "Dumping the database"),
        ("warning", "The disk is nearly full."),
        (
            "error",
            "The backup folder is not writable. Gave up after 1 attempt(s); you can retry it.",
        ),
    ]


async def test_a_retry_that_will_happen_says_when(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID
) -> None:
    async def handler(db: Any, task: Any) -> None:
        raise TaskFailure("The service is busy.")

    await enqueue(app, owner_id, attempts=3)
    await run_with(app, handler)
    events = (await detail(api, (await only_task(api))["id"]))["events"]
    assert "Will try again at" in events[-1]["message"] and events[-1]["level"] == "error"


async def test_a_crash_hides_the_exception_but_keeps_a_history_line(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID
) -> None:
    async def handler(db: Any, task: Any) -> None:
        raise RuntimeError("secret internal detail")

    await enqueue(app, owner_id, attempts=1)
    await run_with(app, handler)
    shown = await detail(api, (await only_task(api))["id"])
    assert "secret" not in str(shown)
    assert "Unexpected error" in shown["events"][-1]["message"]


async def test_steps_outside_a_task_do_nothing() -> None:
    await tasks.step("nobody is listening")  # no error, no database needed
    await tasks.warn("nobody is listening")


# --- retry and cancel from the screen ---------------------------------------------------------


async def test_retry_and_cancel_are_recorded_and_only_allowed_in_the_right_state(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID
) -> None:
    async def failing(db: Any, task: Any) -> None:
        raise TaskFailure("Nope.")

    await enqueue(app, owner_id, attempts=1)
    task_id = (await only_task(api))["id"]
    assert (await api.post(f"{TASKS}/{task_id}/retry")).status_code == 409  # not failed yet
    await run_with(app, failing)

    retried = await api.post(f"{TASKS}/{task_id}/retry")
    assert retried.json()["status"] == "queued" and retried.json()["progress"] is None
    assert (await api.post(f"{TASKS}/{task_id}/retry")).status_code == 409  # already queued
    cancelled = await api.post(f"{TASKS}/{task_id}/cancel")
    assert (
        cancelled.json()["status"] == "failed" and cancelled.json()["error"] == "Cancelled by you."
    )
    messages = [e["message"] for e in (await detail(api, task_id))["events"]]
    assert any("another try" in m for m in messages) and any("Cancelled" in m for m in messages)
    assert (await api.post(f"{TASKS}/{task_id}/cancel")).status_code == 409  # not waiting


async def test_another_user_cannot_read_retry_or_cancel_my_task(
    app: FastAPI, api: AsyncClient, other_api: AsyncClient
) -> None:
    async with app.state.sessionmaker() as db:
        mine = await db.scalar(select(User.id).where(User.email == EMAIL))
    assert mine is not None
    await enqueue(app, mine, attempts=1)
    task_id = (await only_task(api))["id"]
    for method, path in (("get", ""), ("post", "/retry"), ("post", "/cancel")):
        response = await getattr(other_api, method)(f"{TASKS}/{task_id}{path}")
        assert response.status_code == 404


# --- continuing from where a research run stopped ------------------------------------------------


class CrashingLlm(FakeLlm):
    """Raises an unexpected error (not a normal model failure) on its second call while `crash` is on."""

    crash = True

    async def complete(self, **kwargs: Any) -> Any:
        if self.crash and self.calls:
            raise RuntimeError("the model client exploded")
        return await super().complete(**kwargs)


async def test_a_research_run_that_crashed_continues_with_the_pages_it_had_not_read(
    app: FastAPI, api: AsyncClient
) -> None:
    search = FakeSearch(hits())
    llm = CrashingLlm(replies=[GOOD_A, GOOD_B])
    web = FakeWeb(PAGES)  # pyright: ignore[reportArgumentType]
    setup(app, search=search, llm=llm, pages=PAGES)
    app.state.fetcher = web.fetcher()
    started = await start(api, await job(api))
    await run_worker(app)

    failed = await only_task(api)
    assert failed["status"] == "failed" and "Unexpected error" in failed["error"]
    searches_before = len(search.queries)
    first_read = [r for r in web.requests if "blog.acme.dev" in r]
    assert len(first_read) == 1 and len(llm.calls) == 1  # the first page was read and paid for

    llm.crash = False  # the problem is fixed; press Retry
    assert (await api.post(f"{TASKS}/{failed['id']}/retry")).status_code == 200
    assert await run_worker(app)

    assert len(search.queries) == searches_before  # no new search
    assert len([r for r in web.requests if "blog.acme.dev" in r]) == 1  # page 1 not fetched again
    assert len(llm.calls) == 2  # only the missing page was sent to the model
    run = (await api.get(f"/api/v1/research/runs/{started['id']}")).json()
    assert run["status"] in ("succeeded", "partial")
    assert run["usage"]["pages_read"] == 2
    topics = {f["topic"] for f in (await api.get("/api/v1/research/findings")).json()["items"]}
    assert {"database transactions", "caching"} <= topics  # findings from both pages
    messages = [e["message"] for e in (await detail(api, failed["id"]))["events"]]
    assert any("1 of 2 pages were already read" in m for m in messages)
    assert (await only_task(api))["status"] == "succeeded"


# --- continuing from where the daily list stopped ---------------------------------------------


async def test_a_listed_but_unfinished_apply_item_is_finished_by_the_next_build(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID, content: Any
) -> None:
    from tests.test_apply_api import build, policy, profile, queue, wire
    from tests.test_apply_api import job as apply_job

    policy(content, "daily_limit: 1\nmin_match_score: 50\n")
    wire(app, FakeSearch([]))
    await profile(api)
    job_id = await apply_job(
        api, "Python Backend Developer", "Acme", jd_text="Python FastAPI PostgreSQL. 12-18 LPA."
    )
    # What an interrupted build leaves behind: the item exists but nothing was looked up.
    async with app.state.sessionmaker() as db:
        db.add(
            ApplyItem(
                owner_id=owner_id,
                job_id=uuid.UUID(job_id),
                queued_on=datetime.now(UTC).date(),
                status=ApplyStatus.READY,
                match_score=90,
                reasons=["x"],
                also_listed=[],
                notes=[],
            )
        )
        await db.commit()
    await build(app, api)
    (item,) = (await queue(api))["items"]
    assert item["pay"]["level"] == "posted" and item["enriched_at"] is not None
    async with app.state.sessionmaker() as db:
        rows = (await db.scalars(select(ApplyItem).where(ApplyItem.owner_id == owner_id))).all()
    assert len(rows) == 1  # finished, not duplicated
    status = (await api.get(TASKS)).json()["items"][0]["status"]
    assert status == TaskStatus.SUCCEEDED.value
