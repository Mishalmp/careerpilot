"""Telegram: the client never leaks the token, only your chat is answered, nothing is sent out.
# covers: Telegram front door (docs/phase-7/14): commands reuse the web app's services, a stranger
# is ignored, old messages are dropped on start, and no command can send or submit anything
"""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from careerpilot.core.clock import today_in
from careerpilot.core.config import Settings
from careerpilot.core.telegram import MAX_TEXT, Incoming, TelegramClient, TelegramError, chunks
from careerpilot.modules.telegram import poller, service
from tests.test_apply_api import build, queue, setup_basic

TOKEN = "123456:SECRET-TOKEN-VALUE"
CHAT = 4242


# --- the client -----------------------------------------------------------------------------


def client_for(handler: httpx.MockTransport) -> TelegramClient:
    return TelegramClient(TOKEN, http=httpx.AsyncClient(transport=handler))


async def test_messages_are_sent_as_plain_text_without_previews() -> None:
    seen: list[dict[str, object]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/bot{TOKEN}/sendMessage"
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "result": {}})

    await client_for(httpx.MockTransport(respond)).send(CHAT, "hello <b>not bold</b>")
    assert seen == [
        {
            "chat_id": CHAT,
            "text": "hello <b>not bold</b>",
            "link_preview_options": {"is_disabled": True},
        }
    ]  # no parse_mode: nothing in a job title can break or format the message


def test_long_text_is_split_below_the_limit_on_line_breaks() -> None:
    text = "\n".join(f"line {n} " + "x" * 90 for n in range(200))
    parts = chunks(text)
    assert len(parts) > 1 and all(len(p) <= MAX_TEXT for p in parts)
    assert "\n".join(parts) == text
    assert [len(p) for p in chunks("y" * (MAX_TEXT * 2 + 5))] == [MAX_TEXT, MAX_TEXT, 5]


async def test_an_error_never_contains_the_token() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})

    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom " + str(request.url))

    for transport in (httpx.MockTransport(refuse), httpx.MockTransport(broken)):
        with pytest.raises(TelegramError) as caught:
            await client_for(transport).send(CHAT, "hi")
        assert TOKEN not in str(caught.value) and "SECRET" not in repr(caught.value.__cause__)


async def test_updates_keep_private_text_and_skip_the_rest() -> None:
    body: dict[str, Any] = {
        "ok": True,
        "result": [
            {
                "update_id": 1,
                "message": {"chat": {"id": CHAT, "type": "private"}, "text": "/today"},
            },
            {"update_id": 2, "message": {"chat": {"id": -100, "type": "group"}, "text": "/today"}},
            {"update_id": 3, "message": {"chat": {"id": CHAT, "type": "private"}}},  # a photo
            {"update_id": 4, "edited_message": {}},
        ],
    }
    client = client_for(httpx.MockTransport(lambda r: httpx.Response(200, json=body)))
    got = await client.updates(None, 0)
    assert got == [
        Incoming(1, CHAT, "/today"),
        Incoming(2, 0, ""),
        Incoming(3, 0, ""),
        Incoming(4, 0, ""),
    ]  # every update is returned so the offset can move past it


# --- commands -------------------------------------------------------------------------------


async def run(app: FastAPI, owner_id: uuid.UUID, text: str) -> str:
    async with app.state.sessionmaker() as db:
        return await service.handle(
            db, owner_id, text, app.state.settings, today=today_in(app.state.settings.timezone)
        )


async def test_today_lists_the_ready_jobs_with_codes_and_links(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID, content: Path
) -> None:
    await setup_basic(app, api, content)
    await build(app, api)
    reply = await run(app, owner_id, "/today")
    first = (await queue(api))["items"][0]
    assert f"[{first['id'].replace('-', '')[:6]}]" in reply
    assert "https://acme.example/apply" in reply or "https://globex.example/apply" in reply
    assert "Marketing Manager" not in reply


async def test_approve_and_applied_by_code_move_the_job_but_send_nothing(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID, content: Path
) -> None:
    ids = await setup_basic(app, api, content)
    await build(app, api)
    item = next(i for i in (await queue(api))["items"] if i["job_id"] == ids["good"])
    code = item["id"].replace("-", "")[:6]

    said = await run(app, owner_id, f"/approve {code}")
    assert said.startswith(f"[{code}]") and "approved" in said.lower()
    job = (await api.get(f"/api/v1/jobs/{ids['good']}")).json()
    assert job["application"]["status"] == "Shortlisted"

    applied = await run(app, owner_id, f"/applied {code}")
    assert "applied" in applied.lower()
    job = (await api.get(f"/api/v1/jobs/{ids['good']}")).json()
    assert job["application"]["status"] == "Applied - Pending"
    assert job["application"]["email_mode"] != "Sent"  # nothing was emailed


async def test_a_wrong_or_ambiguous_code_changes_nothing(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID, content: Path
) -> None:
    await setup_basic(app, api, content)
    await build(app, api)
    assert "Give the code" in await run(app, owner_id, "/approve zzz")
    assert "No job with code" in await run(app, owner_id, "/approve ffffff")
    assert "Give the code" in await run(app, owner_id, "/approve 12")  # too short to be safe
    assert all(
        i["status"] == "ready" for i in (await queue(api))["items"] if i["status"] != "blocked"
    )


async def test_a_forwarded_link_is_saved_and_commands_never_reach_the_model(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID
) -> None:
    from tests.fakes import FakeLlm

    llm = FakeLlm("{}")
    app.state.llm = llm
    reply = await run(
        app, owner_id, "look https://www.linkedin.com/jobs/view/data-engineer-at-zeta-3700000009/"
    )
    assert "saved: Data Engineer - Zeta" in reply
    assert "already saved" in await run(
        app, owner_id, "/links https://www.linkedin.com/jobs/view/3700000009/"
    )
    for command in ("/help", "/status", "/spend", "/today", "/nonsense"):
        await run(app, owner_id, command)
    assert llm.calls == []


async def test_status_and_spend_show_the_budget(app: FastAPI, owner_id: uuid.UUID) -> None:
    assert "this month" in await run(app, owner_id, "/spend")
    assert "jobs ready" in await run(app, owner_id, "/status")
    assert "/approve" in await run(app, owner_id, "/help")


async def test_there_is_no_command_that_sends_or_submits() -> None:
    names = {w for w in service.HELP.split() if w.startswith("/")}
    assert names.isdisjoint({"/send", "/submit", "/email", "/delete", "/settings"})
    assert "Nothing is ever sent or submitted" in service.HELP


# --- the poller -----------------------------------------------------------------------------


class ScriptedClient:
    """Plays back batches of messages, records replies, then stops the loop."""

    def __init__(self, batches: list[list[Incoming]], stop: asyncio.Event) -> None:
        self.batches, self.stop = batches, stop
        self.sent: list[tuple[int, str]] = []
        self.offsets: list[int | None] = []

    async def updates(self, offset: int | None, wait_seconds: int) -> list[Incoming]:
        self.offsets.append(offset)
        if not self.batches:
            self.stop.set()
            await asyncio.sleep(0)
            return []
        return self.batches.pop(0)

    async def send(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


async def test_only_your_chat_is_answered_and_old_messages_are_dropped(
    app: FastAPI, owner_id: uuid.UUID
) -> None:
    stop = asyncio.Event()
    settings: Settings = app.state.settings.model_copy(update={"telegram_chat_id": CHAT})
    scripted = ScriptedClient(
        [
            [Incoming(10, CHAT, "/approve aaaaaa")],  # sent while the app was off: dropped
            [Incoming(11, 999, "/today"), Incoming(12, CHAT, "/help"), Incoming(13, 0, "")],
        ],
        stop,
    )

    async def owner_of(db: AsyncSession) -> uuid.UUID | None:
        return owner_id

    sm: async_sessionmaker[AsyncSession] = app.state.sessionmaker
    await poller.poll_loop(sm, settings, stop, owner_of, client=scripted)  # type: ignore[arg-type]
    assert [chat for chat, _ in scripted.sent] == [CHAT]  # the stranger got nothing
    assert "CareerPilot commands" in scripted.sent[0][1]
    assert scripted.offsets[:2] == [-1, 11]  # backlog skipped, then continued after message 10
    assert scripted.offsets[2] == 14


async def test_nothing_runs_without_both_token_and_chat_id(app: FastAPI) -> None:
    settings: Settings = app.state.settings
    assert settings.telegram_bot_token is None and poller.make_client(settings) is None
    with_token = settings.model_copy(update={"telegram_bot_token": TOKEN})
    assert poller.make_client(with_token) is None  # a token without a chat id is not enough


async def test_the_new_list_is_sent_to_your_chat_when_ready(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID, content: Path
) -> None:
    await setup_basic(app, api, content)
    await build(app, api)
    stop = asyncio.Event()
    scripted = ScriptedClient([], stop)
    settings: Settings = app.state.settings.model_copy(update={"telegram_chat_id": CHAT})
    async with app.state.sessionmaker() as db:
        await poller.notify_queue_ready(db, owner_id, settings, scripted)  # type: ignore[arg-type]
    assert scripted.sent and scripted.sent[0][0] == CHAT
    assert "Your apply list is ready" in scripted.sent[0][1]
