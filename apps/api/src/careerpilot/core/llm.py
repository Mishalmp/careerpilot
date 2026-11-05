"""One narrow door to the language model, with a usage cap and an audit trail.

Everything that calls Claude goes through `call_llm`, so the daily token cap and the `llm_calls`
table cover every feature. Features depend on the small `LlmClient` interface, which lets tests
use a fake and lets the provider change (see ADR 0004) without touching the features.
"""

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import anthropic
import httpx2
from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey, Integer, Text, Uuid, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from careerpilot.core.config import Settings
from careerpilot.core.db import Base
from careerpilot.core.errors import ProblemError
from careerpilot.core.prompts import Prompt


class LlmCall(Base):
    """One request to the model. Prompts and answers are deliberately not stored."""

    __tablename__ = "llm_calls"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text)  # ok | refused | error
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


@dataclass(frozen=True)
class LlmReply:
    text: str
    input_tokens: int
    output_tokens: int
    refused: bool = False


class LlmError(Exception):
    """A failure from the provider, already worded for the user."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class LlmClient(Protocol):
    model: str

    async def complete(self, *, system: str, user: str, max_tokens: int) -> LlmReply: ...


class AnthropicClient:
    """Claude through the official SDK. The SDK retries rate limits and server errors itself."""

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float = 60.0,
        *,
        max_retries: int = 2,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        self.model = model
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=max_retries,
            http_client=http_client,
        )

    async def complete(self, *, system: str, user: str, max_tokens: int) -> LlmReply:
        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                # Answering from a handful of passages does not need deep reasoning.
                output_config={"effort": "low"},
            )
        except anthropic.AuthenticationError as exc:
            raise LlmError(
                502, "The Anthropic API key was rejected. Check ANTHROPIC_API_KEY."
            ) from exc
        except anthropic.RateLimitError as exc:
            raise LlmError(429, "Anthropic is rate limiting this key. Try again shortly.") from exc
        except anthropic.APIConnectionError as exc:
            raise LlmError(502, "Could not reach the Anthropic API.") from exc
        except anthropic.APIStatusError as exc:
            raise LlmError(
                502, f"The Anthropic API returned an error ({exc.status_code})."
            ) from exc

        # Thinking blocks may precede the answer; only text blocks are the reply.
        text = "".join(block.text for block in response.content if block.type == "text")
        return LlmReply(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            refused=response.stop_reason == "refusal",
        )


def make_llm(settings: Settings) -> LlmClient | None:
    """None when no key is configured: features then fall back to retrieval-only behaviour."""
    if settings.anthropic_api_key is None:
        return None
    return AnthropicClient(settings.anthropic_api_key.get_secret_value(), settings.llm_model)


async def tokens_used_today(db: AsyncSession, owner_id: uuid.UUID) -> int:
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    total = await db.scalar(
        select(func.coalesce(func.sum(LlmCall.input_tokens + LlmCall.output_tokens), 0)).where(
            LlmCall.owner_id == owner_id, LlmCall.created_at >= start
        )
    )
    return int(total or 0)


async def call_llm(
    db: AsyncSession,
    owner_id: uuid.UUID,
    llm: LlmClient,
    settings: Settings,
    *,
    purpose: str,
    system: str,
    user: str,
    max_tokens: int,
) -> LlmReply:
    """Call the model unless today's token cap is used up. Every attempt is recorded."""
    if await tokens_used_today(db, owner_id) >= settings.llm_daily_token_cap:
        raise ProblemError(
            429,
            "Daily AI limit reached",
            f"Today's {settings.llm_daily_token_cap:,}-token cap is used up. "
            "Raise llm_daily_token_cap to continue.",
        )
    started = time.perf_counter()
    elapsed = lambda: int((time.perf_counter() - started) * 1000)  # noqa: E731
    try:
        reply = await llm.complete(system=system, user=user, max_tokens=max_tokens)
    except LlmError as exc:
        db.add(
            LlmCall(
                owner_id=owner_id,
                purpose=purpose,
                model=llm.model,
                latency_ms=elapsed(),
                status="error",
                error=exc.message,
            )
        )
        await db.commit()
        raise ProblemError(exc.status, "AI request failed", exc.message) from exc
    db.add(
        LlmCall(
            owner_id=owner_id,
            purpose=purpose,
            model=llm.model,
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            latency_ms=elapsed(),
            status="refused" if reply.refused else "ok",
        )
    )
    await db.commit()
    return reply


def parse_json_reply[T: BaseModel](text: str, schema: type[T]) -> T:
    """The first-to-last braces of a reply, validated. Raises ValueError (incl. ValidationError)."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("the reply contains no JSON object")
    return schema.model_validate_json(text[start : end + 1])


async def call_llm_json[T: BaseModel](
    db: AsyncSession,
    owner_id: uuid.UUID,
    llm: LlmClient,
    settings: Settings,
    *,
    prompt: Prompt,
    user: str,
    schema: type[T],
) -> T:
    """Ask for a JSON object and validate it against `schema`, with one repair attempt.

    Both attempts count against the daily cap. If the reply still does not validate, nothing is
    guessed: the caller gets a 502 and stores nothing.
    """
    reply = await call_llm(
        db,
        owner_id,
        llm,
        settings,
        purpose=prompt.label,
        system=prompt.system,
        user=user,
        max_tokens=prompt.max_tokens,
    )
    for attempt in range(2):
        if reply.refused:
            raise ProblemError(502, "The model declined", "It refused to answer this request.")
        try:
            return parse_json_reply(reply.text, schema)
        except ValueError as exc:
            if attempt == 1:
                raise ProblemError(
                    502, "AI reply could not be used", "The model did not return valid JSON twice."
                ) from exc
            problem = str(exc)[:400]
        reply = await call_llm(
            db,
            owner_id,
            llm,
            settings,
            purpose=prompt.label + ":repair",
            system=prompt.system,
            user=(
                f"{user}\n\nYour previous reply could not be used ({problem}).\n"
                f"Previous reply:\n{reply.text[:2000]}\n\n"
                "Reply again with only the corrected JSON object."
            ),
            max_tokens=prompt.max_tokens,
        )
    raise AssertionError("unreachable")  # pragma: no cover
