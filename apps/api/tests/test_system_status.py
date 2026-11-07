"""The live system status.
# covers: REQ-16 (live system status), B01 (partly)
"""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from httpx import AsyncClient

URL = "/api/v1/system/status"


async def test_status_reports_the_database_tasks_ai_search_and_backups(api: AsyncClient) -> None:
    body = (await api.get(URL)).json()
    assert body["database"]["ok"] is True
    assert body["database"]["revision"]  # the schema version the database is at
    assert set(body["tasks"]) == {"queued", "running", "failed", "succeeded"}
    assert body["ai"]["configured"] is False  # tests run without a key
    assert body["ai"]["tokens_today"] == 0
    assert body["ai"]["daily_cap"] > 0
    assert body["search"] == {"provider": "none", "configured": False}
    assert body["backups"]["key_set"] is False
    assert body["backups"]["last_backup_at"] is None
    assert datetime.fromisoformat(body["checked_at"]) <= datetime.now(UTC) + timedelta(seconds=5)


async def test_status_never_contains_a_secret(app: FastAPI, api: AsyncClient) -> None:
    app.state.settings = app.state.settings.model_copy(
        update={
            "backup_key": "super-secret-backup-key",
            "anthropic_api_key": "sk-secret-api-key",
            "brave_api_key": "secret-brave-key",
        }
    )
    text = (await api.get(URL)).text
    for secret in ("super-secret-backup-key", "sk-secret-api-key", "secret-brave-key"):
        assert secret not in text
    body = (await api.get(URL)).json()
    assert body["ai"]["configured"] is True
    assert body["backups"]["key_set"] is True


async def test_backup_age_comes_from_the_newest_backup_file(
    app: FastAPI, api: AsyncClient, tmp_path: Path
) -> None:
    old = tmp_path / "careerpilot-old.cpbk"
    new = tmp_path / "careerpilot-new.cpbk"
    old.write_bytes(b"x")
    new.write_bytes(b"x")
    two_days_ago = (datetime.now(UTC) - timedelta(days=2)).timestamp()
    os.utime(old, (two_days_ago, two_days_ago))
    five_hours_ago = (datetime.now(UTC) - timedelta(hours=5)).timestamp()
    os.utime(new, (five_hours_ago, five_hours_ago))
    app.state.settings = app.state.settings.model_copy(update={"backup_dir": tmp_path})
    backups = (await api.get(URL)).json()["backups"]
    assert 4.9 <= backups["age_hours"] <= 5.2
    assert backups["last_backup_at"] is not None


async def test_the_search_provider_shows_when_one_is_configured(
    app: FastAPI, api: AsyncClient
) -> None:
    class Fake:
        name = "fake"

    app.state.search = Fake()
    app.state.settings = app.state.settings.model_copy(update={"search_provider": "searxng"})
    assert (await api.get(URL)).json()["search"] == {"provider": "searxng", "configured": True}


async def test_task_counts_follow_the_queue(api: AsyncClient) -> None:
    job = (await api.post("/api/v1/jobs", json={"company_name": "Acme", "title": "Dev"})).json()
    app_search_missing = await api.post(
        "/api/v1/research/runs", json={"job_id": job["job"]["id"] if "job" in job else job["id"]}
    )
    assert app_search_missing.status_code == 409  # no search service: nothing was queued
    assert (await api.get(URL)).json()["tasks"]["queued"] == 0


async def test_status_requires_a_session(client: AsyncClient) -> None:
    assert (await client.get(URL)).status_code == 401


async def test_the_ai_call_log_lists_calls_and_can_show_only_problems(
    app: FastAPI, api: AsyncClient, other_api: AsyncClient
) -> None:
    from sqlalchemy import select

    from careerpilot.core.llm import LlmCall
    from careerpilot.modules.auth.models import User
    from tests.conftest import EMAIL

    async with app.state.sessionmaker() as db:
        mine = await db.scalar(select(User.id).where(User.email == EMAIL))
        assert mine is not None
        for purpose, status, error in (
            ("research-extract", "ok", None),
            ("jd-reading", "error", "The model service is busy."),
        ):
            db.add(
                LlmCall(
                    owner_id=mine,
                    purpose=purpose,
                    model="claude-haiku-5-5",
                    input_tokens=120,
                    output_tokens=30,
                    latency_ms=800,
                    status=status,
                    error=error,
                )
            )
        await db.commit()
    everything = (await api.get("/api/v1/system/ai-calls")).json()
    assert {c["purpose"] for c in everything["items"]} == {"research-extract", "jd-reading"}
    assert everything["tokens_today"] == 300 and everything["daily_cap"] > 0
    problems = (await api.get("/api/v1/system/ai-calls?problems_only=true")).json()["items"]
    assert [c["purpose"] for c in problems] == ["jd-reading"]
    assert problems[0]["error"] == "The model service is busy."
    assert (await other_api.get("/api/v1/system/ai-calls")).json()["items"] == []  # not shared
    assert (await api.get("/api/v1/system/ai-calls?limit=0")).status_code == 422
