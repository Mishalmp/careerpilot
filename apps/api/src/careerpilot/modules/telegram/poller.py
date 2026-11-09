"""Waits for your messages and answers them; also how the worker sends you the daily list."""

import asyncio
import contextlib
import uuid
from collections.abc import Awaitable, Callable

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from careerpilot.core.clock import today_in
from careerpilot.core.config import Settings
from careerpilot.core.telegram import TelegramClient, TelegramError
from careerpilot.modules.apply import service as apply_service
from careerpilot.modules.telegram import service

log = structlog.get_logger()
LONG_POLL_SECONDS = 25

# Finds whose chat this is. The app has one user; the worker (which may read the user table)
# supplies this, because modules may not reach into each other's internals.
OwnerLookup = Callable[[AsyncSession], Awaitable[uuid.UUID | None]]


def make_client(settings: Settings) -> TelegramClient | None:
    """None unless both the bot token and your chat id are set."""
    if settings.telegram_bot_token is None or settings.telegram_chat_id is None:
        return None
    return TelegramClient(settings.telegram_bot_token.get_secret_value())


async def notify_queue_ready(
    db: AsyncSession, owner_id: uuid.UUID, settings: Settings, client: TelegramClient | None
) -> None:
    """Send the new list to your chat.

    A Telegram problem is logged, never raised: it must not fail a build that already worked.
    """
    if client is None or settings.telegram_chat_id is None:
        return
    try:
        queue = await apply_service.get_queue(db, owner_id, settings, today_in(settings.timezone))
        await client.send(settings.telegram_chat_id, service.queue_ready_message(queue.items))
    except TelegramError as exc:
        log.warning("telegram_notify_failed", error=str(exc))


async def poll_loop(
    sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    stop: asyncio.Event,
    owner_of: OwnerLookup,
    client: TelegramClient | None = None,
) -> None:
    client = client or make_client(settings)
    chat_id = settings.telegram_chat_id
    if client is None or chat_id is None:
        return
    log.info("telegram_started")
    offset: int | None = None
    delay = 5.0
    try:  # messages sent while the app was off are dropped: a stale /approve must not run later
        backlog = await client.updates(-1, 0)
        if backlog:
            offset = backlog[-1].update_id + 1
    except TelegramError as exc:
        log.warning("telegram_backlog_failed", error=str(exc))
    while not stop.is_set():
        fetch = asyncio.ensure_future(client.updates(offset, LONG_POLL_SECONDS))
        waiter = asyncio.ensure_future(stop.wait())
        await asyncio.wait({fetch, waiter}, return_when=asyncio.FIRST_COMPLETED)
        if not fetch.done():
            fetch.cancel()
            waiter.cancel()
            break
        waiter.cancel()
        try:
            incoming = fetch.result()
            delay = 5.0
        except TelegramError as exc:
            log.warning("telegram_poll_failed", error=str(exc))
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=delay)
            delay = min(delay * 2, 120.0)
            continue
        for message in incoming:
            offset = message.update_id + 1
            if message.chat_id != chat_id:  # strangers (and non-text updates) get no reply
                continue
            await _answer(sessionmaker, settings, client, owner_of, message.text)
    log.info("telegram_stopped")


async def _answer(
    sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    client: TelegramClient,
    owner_of: OwnerLookup,
    text: str,
) -> None:
    assert settings.telegram_chat_id is not None  # noqa: S101 - checked by the caller
    try:
        async with sessionmaker() as db:
            owner = await owner_of(db)
            if owner is None:
                return
            reply = await service.handle(
                db, owner, text, settings, today=today_in(settings.timezone)
            )
        await client.send(settings.telegram_chat_id, reply)
    except TelegramError as exc:
        log.warning("telegram_reply_failed", error=str(exc))
    except Exception:
        log.exception("telegram_command_failed")
        with contextlib.suppress(TelegramError):
            await client.send(settings.telegram_chat_id, "Something went wrong with that command.")
