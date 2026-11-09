"""A small Telegram Bot API client: send a message, wait for new ones.

Telegram is a fixed first-party host, so this does not go through the page fetcher (which exists to
keep arbitrary web pages from reaching private addresses). What it does guard is the bot token:
the token is part of every request address, so nothing here puts the address, the request or the
response into an error message or a log line (httpx's own request log is switched off below).
"""

import logging
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, ValidationError

# httpx logs "POST https://api.telegram.org/bot<TOKEN>/sendMessage" at INFO. Never let that out.
logging.getLogger("httpx").setLevel(logging.WARNING)

API = "https://api.telegram.org"
MAX_TEXT = 4000  # Telegram's limit is 4096 characters per message


class TelegramError(Exception):
    """A failure worded for the log: it never contains the token or the request address."""


@dataclass(frozen=True)
class Incoming:
    update_id: int
    chat_id: int  # 0 for anything that is not a text message from a private chat
    text: str


class _Chat(BaseModel):
    id: int
    type: str


class _Message(BaseModel):
    chat: _Chat
    text: str | None = None


class _Update(BaseModel):
    update_id: int
    message: _Message | None = None


class _Reply(BaseModel):
    ok: bool = False
    description: str = ""
    result: list[_Update] | bool | dict[str, object] | None = None


def chunks(text: str, size: int = MAX_TEXT) -> list[str]:
    """Split on line breaks so no message passes the limit and no line is cut when avoidable."""
    parts: list[str] = []
    current = ""
    for line in text.split("\n"):
        while len(line) > size:  # one line longer than a whole message
            if current:
                parts.append(current)
                current = ""
            parts.append(line[:size])
            line = line[size:]
        if current and len(current) + 1 + len(line) > size:
            parts.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        parts.append(current)
    return parts


class TelegramClient:
    def __init__(self, token: str, *, http: httpx.AsyncClient | None = None) -> None:
        self._token = token
        self._http = http or httpx.AsyncClient(timeout=httpx.Timeout(40.0), trust_env=False)

    async def _call(self, method: str, payload: dict[str, object]) -> _Reply:
        try:
            response = await self._http.post(f"{API}/bot{self._token}/{method}", json=payload)
        except httpx.HTTPError as exc:
            raise TelegramError(f"Could not reach Telegram ({type(exc).__name__}).") from None
        try:
            reply = _Reply.model_validate_json(response.content)
        except ValidationError:
            reply = _Reply()
        if response.status_code != 200 or not reply.ok:
            raise TelegramError(
                f"Telegram refused {method} ({response.status_code}): {reply.description[:120]}"
            )
        return reply

    async def send(self, chat_id: int, text: str) -> None:
        """Plain text only (no formatting to escape), one message per 4,000 characters."""
        for part in chunks(text):
            await self._call(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": part,
                    "link_preview_options": {"is_disabled": True},
                },
            )

    async def updates(self, offset: int | None, wait_seconds: int) -> list[Incoming]:
        """New updates. Long polling: the call waits up to `wait_seconds` for one to arrive.

        Every update is returned (so the caller can move its offset past it), but only a text
        message from a private chat carries a chat id and text; the rest have chat id 0.
        """
        payload: dict[str, object] = {"timeout": wait_seconds, "allowed_updates": ["message"]}
        if offset is not None:
            payload["offset"] = offset
        reply = await self._call("getUpdates", payload)
        found: list[Incoming] = []
        for update in reply.result if isinstance(reply.result, list) else []:
            message = update.message
            if message is not None and message.chat.type == "private" and message.text:
                found.append(Incoming(update.update_id, message.chat.id, message.text))
            else:
                found.append(Incoming(update.update_id, 0, ""))
        return found
