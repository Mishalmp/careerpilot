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
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text, Uuid, func, select
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
    # Millionths of a US dollar (integer, so sums are exact), priced when the call was made.
    cost_micro_usd: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    latency_ms: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text)  # ok | refused | error
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


NO_CREDIT = (
    "The Anthropic account has no credit left, so AI features are paused. Everything that does "
    "not use the model (the daily list, discovery, the tracker, Telegram) keeps working. Add "
    "credit in the Anthropic Console and the AI features resume by themselves."
)
NO_CREDIT_PAUSE_SECONDS = 600.0


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

    async def complete(
        self, *, system: str, user: str, max_tokens: int, model: str | None = None
    ) -> LlmReply: ...


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
        self._no_credit_until = 0.0  # monotonic time before which calls are refused without asking
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=max_retries,
            http_client=http_client,
        )

    async def complete(
        self, *, system: str, user: str, max_tokens: int, model: str | None = None
    ) -> LlmReply:
        if time.monotonic() < self._no_credit_until:
            raise LlmError(402, NO_CREDIT)
        try:
            response = await self._client.messages.create(
                model=model or self.model,
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
            if "credit balance" in str(getattr(exc, "message", "")).lower():
                # Asking again every few seconds cannot help and floods the log: pause for a while.
                self._no_credit_until = time.monotonic() + NO_CREDIT_PAUSE_SECONDS
                raise LlmError(402, NO_CREDIT) from exc
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


def price_of(settings: Settings, model: str) -> tuple[float, float]:
    """Dollars per million tokens (input, output). An unknown model costs as much as the dearest."""
    known = settings.llm_prices.get(model)
    if known is not None:
        return known
    return max(settings.llm_prices.values(), key=lambda p: p[0] + p[1])


def cost_micro_usd(settings: Settings, model: str, input_tokens: int, output_tokens: int) -> int:
    """Price in millionths of a dollar (a price per million tokens is micro-dollars per token)."""
    price_in, price_out = price_of(settings, model)
    return round(input_tokens * price_in + output_tokens * price_out)


def worst_case_micro_usd(settings: Settings, model: str, text: str, max_tokens: int) -> int:
    """What a call could cost at most: every 3 characters count as a token, the whole reply is used.

    Real English is nearer 4 characters a token, so this over-estimates a little on purpose: a
    guard that is too strict wastes a call, one that is too loose wastes money.
    """
    return cost_micro_usd(settings, model, len(text) // 3 + 1, max_tokens)


async def spent_micro_usd(db: AsyncSession, owner_id: uuid.UUID, since: datetime) -> int:
    total = await db.scalar(
        select(func.coalesce(func.sum(LlmCall.cost_micro_usd), 0)).where(
            LlmCall.owner_id == owner_id, LlmCall.created_at >= since
        )
    )
    return int(total or 0)


def day_start(now: datetime | None = None) -> datetime:
    return (now or datetime.now(UTC)).replace(hour=0, minute=0, second=0, microsecond=0)


def month_start(now: datetime | None = None) -> datetime:
    return day_start(now).replace(day=1)


@dataclass(frozen=True)
class Spend:
    today_usd: float
    month_usd: float
    daily_budget_usd: float
    monthly_budget_usd: float


async def spend(
    db: AsyncSession, owner_id: uuid.UUID, settings: Settings, now: datetime | None = None
) -> Spend:
    return Spend(
        today_usd=await spent_micro_usd(db, owner_id, day_start(now)) / 1_000_000,
        month_usd=await spent_micro_usd(db, owner_id, month_start(now)) / 1_000_000,
        daily_budget_usd=settings.llm_daily_budget_usd,
        monthly_budget_usd=settings.llm_monthly_budget_usd,
    )


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
    """Call the model unless a cap would be passed. Every attempt is recorded.

    Three limits are checked first, cheapest first: today's tokens, today's dollars and this
    month's dollars. The dollar checks add the most this call could cost, so the last call before
    a limit cannot overshoot it.
    """
    if await tokens_used_today(db, owner_id) >= settings.llm_daily_token_cap:
        raise ProblemError(
            429,
            "Daily AI limit reached",
            f"Today's {settings.llm_daily_token_cap:,}-token cap is used up. "
            "Raise llm_daily_token_cap to continue.",
        )
    # Cheap model for bulk reading prompts, the main model for everything else.
    light = purpose.split("@")[0] in settings.llm_light_prompts
    model = settings.llm_model_light if light else None
    used_model = model or llm.model
    worst = worst_case_micro_usd(settings, used_model, system + user, max_tokens)
    now = datetime.now(UTC)
    if await spent_micro_usd(db, owner_id, day_start(now)) + worst > round(
        settings.llm_daily_budget_usd * 1_000_000
    ):
        raise ProblemError(
            429,
            "Daily AI budget reached",
            f"Today's ${settings.llm_daily_budget_usd:.2f} AI budget is used up. "
            "It starts again tomorrow, or raise CAREERPILOT_LLM_DAILY_BUDGET_USD.",
        )
    if await spent_micro_usd(db, owner_id, month_start(now)) + worst > round(
        settings.llm_monthly_budget_usd * 1_000_000
    ):
        raise ProblemError(
            429,
            "Monthly AI budget reached",
            f"This month's ${settings.llm_monthly_budget_usd:.2f} AI budget is used up. "
            "Raise CAREERPILOT_LLM_MONTHLY_BUDGET_USD to continue.",
        )
    started = time.perf_counter()
    elapsed = lambda: int((time.perf_counter() - started) * 1000)  # noqa: E731
    try:
        reply = await llm.complete(system=system, user=user, max_tokens=max_tokens, model=model)
    except LlmError as exc:
        db.add(
            LlmCall(
                owner_id=owner_id,
                purpose=purpose,
                model=used_model,
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
            model=used_model,
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            cost_micro_usd=cost_micro_usd(
                settings, used_model, reply.input_tokens, reply.output_tokens
            ),
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
        if reply.output_tokens >= prompt.max_tokens:
            # Cut off for length. Echoing the broken reply back and asking again with the same
            # limit just gets cut off again, so ask for less and send less.
            retry = (
                f"{user}\n\nYour previous reply was cut off because it was too long. Reply again "
                "with only a JSON object that is at most half as long: fewer items, shortest text."
            )
        else:
            retry = (
                f"{user}\n\nYour previous reply could not be used ({problem}).\n"
                f"Previous reply:\n{reply.text[:2000]}\n\n"
                "Reply again with only the corrected JSON object."
            )
        reply = await call_llm(
            db,
            owner_id,
            llm,
            settings,
            purpose=prompt.label + ":repair",
            system=prompt.system,
            user=retry,
            max_tokens=prompt.max_tokens,
        )
    raise AssertionError("unreachable")  # pragma: no cover


class _Pong(BaseModel):
    ok: bool


@dataclass(frozen=True)
class LlmCheck:
    model: str
    tokens: int
    milliseconds: int


async def check_llm(
    db: AsyncSession, owner_id: uuid.UUID, llm: LlmClient, settings: Settings
) -> LlmCheck:
    """One tiny real request through the same door every feature uses, asking for JSON.

    It proves the key, the model name, the request shape and the JSON path work together. Raises
    ProblemError (with the provider's message) if any of that is wrong.
    """
    prompt = Prompt(
        name="llm-check",
        version=1,
        description="A connection test.",
        max_tokens=50,
        system='Reply with exactly this JSON object and nothing else: {"ok": true}',
    )
    before = await tokens_used_today(db, owner_id)
    started = time.perf_counter()
    await call_llm_json(db, owner_id, llm, settings, prompt=prompt, user="ping", schema=_Pong)
    return LlmCheck(
        model=llm.model,
        tokens=await tokens_used_today(db, owner_id) - before,
        milliseconds=int((time.perf_counter() - started) * 1000),
    )
