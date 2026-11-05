"""The task queue, the scheduler and the daily digest."""

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import text

from careerpilot.modules.tasks import service as tasks
from careerpilot.modules.tasks.enums import TaskKind, TaskStatus
from careerpilot.modules.tasks.models import Task
from careerpilot.modules.tasks.service import TaskFailure, backoff
from careerpilot.worker import make_handlers, schedule_due, tick
from tests.conftest import EMAIL
from tests.fakes import FakeWeb

TASKS = "/api/v1/tasks"
JSON = "application/json"
GH = "boards-api.greenhouse.io/v1/boards/acme/jobs"


def now() -> datetime:
    return datetime.now(UTC)


async def queue(app: FastAPI, owner: uuid.UUID, key: str = "k1", max_attempts: int = 3) -> bool:
    async with app.state.sessionmaker() as db:
        queued = await tasks.enqueue(
            db, owner, TaskKind.DISCOVER, key, {"source_id": "x"}, max_attempts=max_attempts
        )
        await db.commit()
        return queued


async def owner_of(app: FastAPI) -> uuid.UUID:
    """The first user's id (the `owner_id` fixture refuses to guess when there are two users)."""
    async with app.state.engine.begin() as conn:
        row = await conn.execute(text("select id from users where email = :e"), {"e": EMAIL})
        return row.scalar_one()


async def listing(api: AsyncClient) -> list[dict[str, Any]]:
    return (await api.get(TASKS)).json()["items"]


async def noop(db: Any, task: Task) -> None:
    return None


def handlers(handler: Any) -> dict[TaskKind, Any]:
    return {TaskKind.DISCOVER: handler, TaskKind.DAILY_DIGEST: handler}


async def run(app: FastAPI, handler: Any, at: datetime | None = None) -> bool:
    return await tasks.run_next(app.state.sessionmaker, handlers(handler), now=at)


# --- the queue -----------------------------------------------------------------------------


async def test_queueing_the_same_key_twice_queues_once(app: FastAPI, owner_id: uuid.UUID) -> None:
    assert await queue(app, owner_id, "discover:1:2026-11-06") is True
    assert await queue(app, owner_id, "discover:1:2026-11-06") is False
    assert await queue(app, owner_id, "discover:2:2026-11-06") is True


async def test_a_task_that_succeeds_is_marked_succeeded(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID
) -> None:
    await queue(app, owner_id)
    seen: list[Task] = []

    async def handler(db: Any, task: Task) -> None:
        seen.append(task)

    assert await run(app, handler) is True
    assert await run(app, handler) is False  # nothing left
    (item,) = await listing(api)
    assert item["status"] == "succeeded" and item["attempts"] == 1 and item["error"] is None
    assert seen[0].payload == {"source_id": "x"}


async def test_a_failure_is_retried_later_then_marked_failed_with_the_reason(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID
) -> None:
    await queue(app, owner_id, max_attempts=2)

    async def failing(db: Any, task: Task) -> None:
        raise TaskFailure("The board answered 404.")

    assert await run(app, failing) is True
    (item,) = await listing(api)
    assert (
        item["status"] == "queued"
        and item["attempts"] == 1
        and item["error"] == "The board answered 404."
    )
    assert datetime.fromisoformat(item["run_after"]) > now()  # backed off, not retried at once
    assert await run(app, failing) is False  # not due yet

    later = now() + timedelta(hours=2)
    assert await run(app, failing, later) is True
    (item,) = await listing(api)
    assert item["status"] == "failed" and item["attempts"] == 2 and item["finished_at"] is not None
    assert (await api.get(TASKS)).json()["counts"] == {
        "queued": 0,
        "running": 0,
        "succeeded": 0,
        "failed": 1,
    }


async def test_an_unexpected_error_is_recorded_without_leaking_its_text(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID
) -> None:
    await queue(app, owner_id, max_attempts=1)

    async def crashing(db: Any, task: Task) -> None:
        raise RuntimeError("password=hunter2 in a stack trace")

    await run(app, crashing)
    (item,) = await listing(api)
    assert (
        item["status"] == "failed"
        and "hunter2" not in item["error"]
        and "server log" in item["error"]
    )


async def test_a_task_with_no_handler_fails_clearly(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID
) -> None:
    await queue(app, owner_id, max_attempts=1)
    assert await tasks.run_next(app.state.sessionmaker, {}) is True
    assert (await listing(api))[0]["error"] == "No handler for discover tasks."


async def test_a_task_whose_worker_died_is_returned_to_the_queue_or_failed(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID
) -> None:
    await queue(app, owner_id, "a", max_attempts=3)
    await queue(app, owner_id, "b", max_attempts=1)
    async with app.state.engine.begin() as conn:
        await conn.execute(
            text(
                "update tasks set status = 'running', attempts = 1, started_at = now() - interval '1 hour'"
            )
        )
    await run(app, noop)  # the watchdog runs at the start of every pass
    by_key = {t["key"]: t for t in await listing(api)}
    assert by_key["a"]["status"] == "queued" and "worker stopped" in by_key["a"]["error"]
    assert by_key["b"]["status"] == "failed"


async def test_a_running_task_is_left_alone_until_it_is_overdue(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID
) -> None:
    await queue(app, owner_id)
    async with app.state.engine.begin() as conn:
        await conn.execute(text("update tasks set status = 'running', started_at = now()"))
    await run(app, noop)
    assert (await listing(api))[0]["status"] == "running"


def test_the_wait_grows_and_is_capped() -> None:
    waits = [backoff(n).total_seconds() for n in range(1, 10)]
    assert 60 <= waits[0] <= 66 and 120 <= waits[1] <= 132
    assert waits[:6] == sorted(waits[:6]) and max(waits) <= 3600 * 1.1


# --- the Tasks screen ----------------------------------------------------------------------


async def test_a_failed_task_can_be_retried_by_hand(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID
) -> None:
    await queue(app, owner_id, max_attempts=1)

    async def failing(db: Any, task: Task) -> None:
        raise TaskFailure("Boom.")

    await run(app, failing)
    task_id = (await listing(api))[0]["id"]
    retried = (await api.post(f"{TASKS}/{task_id}/retry")).json()
    assert retried["status"] == "queued" and retried["attempts"] == 0 and retried["error"] is None

    assert (await api.post(f"{TASKS}/{task_id}/retry")).status_code == 409  # not failed any more
    await run(app, failing)
    assert (await api.post(f"{TASKS}/retry-failed")).json() == {"requeued": 1}


async def test_tasks_belong_to_their_owner(
    app: FastAPI, api: AsyncClient, other_api: AsyncClient
) -> None:
    await queue(app, await owner_of(app), max_attempts=1)

    async def failing(db: Any, task: Task) -> None:
        raise TaskFailure("x")

    await run(app, failing)
    task_id = (await listing(api))[0]["id"]
    assert (await other_api.get(TASKS)).json()["items"] == []
    assert (await other_api.post(f"{TASKS}/{task_id}/retry")).status_code == 404
    assert (await other_api.post(f"{TASKS}/retry-failed")).json() == {"requeued": 0}
    assert (await listing(api))[0]["status"] == "failed"
    assert (await api.get(TASKS, params={"status": "failed"})).json()["items"][0]["id"] == task_id
    assert (await api.get(TASKS, params={"status": "queued"})).json()["items"] == []


# --- the scheduler -------------------------------------------------------------------------


def settings_at(app: FastAPI, **changes: Any) -> Any:
    app.state.settings = app.state.settings.model_copy(update=changes)
    return app.state.settings


async def add_source(api: AsyncClient, board: str = "acme") -> dict[str, Any]:
    response = await api.post(
        "/api/v1/discovery/sources",
        json={"kind": "greenhouse", "board": board, "company_name": f"{board} Inc"},
    )
    return response.json()


def board(*titles: str) -> tuple[str, str]:
    jobs = [
        {"id": n, "title": t, "absolute_url": f"https://job-boards.greenhouse.io/acme/jobs/{n}"}
        for n, t in enumerate(titles, 1)
    ]
    return json.dumps({"jobs": jobs}), JSON


async def test_the_daily_run_is_queued_once_per_day_and_only_for_enabled_sources(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID
) -> None:
    settings = settings_at(app, discovery_hour=0, digest_hour=23)
    first, second = await add_source(api, "acme"), await add_source(api, "globex")
    await api.patch(f"/api/v1/discovery/sources/{second['id']}", json={"enabled": False})
    sm = app.state.sessionmaker

    # 03:00 local on a day: discovery is due, the 23:00 digest is not.
    local = datetime(2026, 11, 6, 3, 0, tzinfo=UTC) + timedelta(hours=-5, minutes=-30)
    assert await schedule_due(sm, settings, local) == 1
    assert await schedule_due(sm, settings, local) == 0  # same day: nothing new
    keys = [t["key"] for t in await listing(api)]
    assert keys == [f"discover:{first['id']}:2026-11-06"]

    next_day = local + timedelta(days=1)
    assert await schedule_due(sm, settings, next_day) == 1


async def test_nothing_is_queued_before_the_hour_and_the_digest_is_queued_after_its_hour(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID
) -> None:
    settings = settings_at(app, discovery_hour=7, digest_hour=8)
    await add_source(api)
    sm = app.state.sessionmaker
    # 02:00 UTC is 07:30 in India: discovery is due, the 08:00 digest is not.
    early = datetime(2026, 11, 6, 2, 0, tzinfo=UTC)
    assert await schedule_due(sm, settings, early) == 1
    # 01:00 UTC is 06:30 in India: neither.
    assert await schedule_due(sm, settings, datetime(2026, 11, 7, 1, 0, tzinfo=UTC)) == 0
    # 03:00 UTC is 08:30 in India: the digest joins in.
    kinds = {t["kind"] for t in await listing(api)}
    assert await schedule_due(sm, settings, datetime(2026, 11, 6, 3, 0, tzinfo=UTC)) == 1
    kinds = {t["kind"] for t in await listing(api)}
    assert kinds == {"discover", "daily_digest"}


async def test_a_pass_reads_every_board_builds_the_digest_and_survives_one_bad_board(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID
) -> None:
    settings = settings_at(app, discovery_hour=0, digest_hour=0, task_max_attempts=2)
    app.state.fetcher = FakeWeb({GH: board("Backend Engineer", "Data Engineer")}).fetcher()
    await add_source(api, "acme")
    await add_source(api, "missing")  # this board does not exist
    handlers_ = make_handlers(app.state.fetcher, settings)
    when = now() + timedelta(minutes=1)
    await tick(app.state.sessionmaker, handlers_, settings, when)

    by_status: dict[str, list[dict[str, Any]]] = {}
    for task in await listing(api):
        by_status.setdefault(task["status"], []).append(task)
    assert len(by_status["succeeded"]) == 2  # acme's board and the digest
    (bad,) = by_status["queued"]  # the missing board waits for its retry
    assert "404" in bad["error"] and bad["attempts"] == 1

    candidates = (await api.get("/api/v1/discovery/candidates")).json()["items"]
    assert len(candidates) == 2
    digest = (await api.get("/api/v1/digest/latest")).json()
    assert digest["payload"]["waiting_listings"] == 2 and digest["payload"]["new_listings_24h"] == 2

    # The retry fails again and the task ends as failed, visible on the Tasks screen.
    await tick(app.state.sessionmaker, handlers_, settings, when + timedelta(days=1))
    failed = (await api.get(TASKS, params={"status": "failed"})).json()["items"]
    assert failed and all("404" in t["error"] for t in failed)
    # Running the whole pass again the same day queues and creates nothing new.
    before = len((await api.get("/api/v1/discovery/candidates")).json()["items"])
    await tick(app.state.sessionmaker, handlers_, settings, when)
    assert len((await api.get("/api/v1/discovery/candidates")).json()["items"]) == before


# --- the digest ----------------------------------------------------------------------------


async def test_there_is_no_digest_until_one_is_built(api: AsyncClient) -> None:
    assert (await api.get("/api/v1/digest/latest")).json() is None


async def test_the_digest_lists_due_follow_ups_and_application_counts_and_is_replaced_not_repeated(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID
) -> None:
    from careerpilot.core.clock import today_in
    from careerpilot.modules.digest import service as digest

    job = (await api.post("/api/v1/jobs", json={"company_name": "Acme", "title": "Backend"})).json()
    today = today_in(app.state.settings.timezone)
    await api.patch(
        f"/api/v1/applications/{job['application']['id']}",
        json={"next_followup_on": (today - timedelta(days=1)).isoformat()},
    )
    async with app.state.sessionmaker() as db:
        await digest.build(db, owner_id, today)
        await digest.build(db, owner_id, today)
    latest = (await api.get("/api/v1/digest/latest")).json()
    payload = latest["payload"]
    assert latest["day"] == today.isoformat()
    assert [f["title"] for f in payload["due_followups"]] == ["Backend"]
    assert payload["applications"] == {"New": 1} and payload["failed_tasks_24h"] == 0
    async with app.state.engine.begin() as conn:
        assert (await conn.execute(text("select count(*) from digests"))).scalar_one() == 1


async def test_another_owner_sees_only_their_own_digest(
    app: FastAPI, api: AsyncClient, other_api: AsyncClient
) -> None:
    from careerpilot.core.clock import today_in
    from careerpilot.modules.digest import service as digest

    async with app.state.sessionmaker() as db:
        await digest.build(db, await owner_of(app), today_in(app.state.settings.timezone))
    assert (await api.get("/api/v1/digest/latest")).json() is not None
    assert (await other_api.get("/api/v1/digest/latest")).json() is None


def test_status_names_match_the_screen() -> None:
    assert {s.value for s in TaskStatus} == {"queued", "running", "succeeded", "failed"}


@pytest.mark.parametrize("path", ["/api/v1/tasks", "/api/v1/digest/latest"])
async def test_requires_login(client: AsyncClient, path: str) -> None:
    assert (await client.get(path)).status_code == 401


async def test_the_worker_starts_with_the_app_and_stops_cleanly(
    app: FastAPI, api: AsyncClient
) -> None:
    from careerpilot.main import create_app

    settings = app.state.settings.model_copy(
        update={
            "worker_enabled": True,
            "worker_poll_seconds": 1,
            "discovery_hour": 0,
            "digest_hour": 0,
        }
    )
    live = create_app(settings)
    live.state.fetcher = FakeWeb({GH: board("Backend Engineer")}).fetcher()
    async with live.router.lifespan_context(live):
        await add_source(api)
        for _ in range(40):  # the loop wakes every second; give it a few
            await asyncio.sleep(0.25)
            if (await api.get("/api/v1/digest/latest")).json() is not None:
                break
    assert (await api.get("/api/v1/digest/latest")).json() is not None


async def test_the_nightly_backup_is_queued_only_when_a_key_is_set_and_the_hour_has_come(
    app: FastAPI, api: AsyncClient
) -> None:
    from careerpilot.core.backup import generate_key

    sm = app.state.sessionmaker
    after_2am_ist = datetime(2026, 11, 6, 21, 0, tzinfo=UTC)  # 02:30 the next day in India
    settings = settings_at(app, backup_hour=2, discovery_hour=23, digest_hour=23, backup_key=None)
    assert await schedule_due(sm, settings, after_2am_ist) == 0  # no key: no backups

    settings = settings_at(app, backup_key=generate_key())
    assert await schedule_due(sm, settings, datetime(2026, 11, 6, 19, 0, tzinfo=UTC)) == 0  # 00:30
    assert await schedule_due(sm, settings, after_2am_ist) == 1
    assert await schedule_due(sm, settings, after_2am_ist) == 0  # once a day
    (task,) = [t for t in await listing(api) if t["kind"] == "backup"]
    assert task["key"] == "backup:2026-11-07"


async def test_a_backup_task_without_a_key_fails_with_advice(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID
) -> None:
    settings = settings_at(app, backup_key=None)
    async with app.state.sessionmaker() as db:
        await tasks.enqueue(db, owner_id, TaskKind.BACKUP, "backup:x", {}, max_attempts=1)
        await db.commit()
    await tasks.run_next(app.state.sessionmaker, make_handlers(app.state.fetcher, settings))
    (task,) = [t for t in await listing(api) if t["kind"] == "backup"]
    assert task["status"] == "failed" and "backup-key" in task["error"]
