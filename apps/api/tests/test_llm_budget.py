"""Dollar budgets: priced per model, checked before each call, shown on the status page."""

import uuid

import pytest
from fastapi import FastAPI
from sqlalchemy import text

from careerpilot.core.config import Settings
from careerpilot.core.errors import ProblemError
from careerpilot.core.llm import call_llm, cost_micro_usd, price_of, worst_case_micro_usd
from tests.fakes import FakeLlm


async def ask(
    app: FastAPI, settings: Settings, owner_id: uuid.UUID, llm: FakeLlm, *, purpose: str = "demo"
) -> None:
    async with app.state.sessionmaker() as db:
        await call_llm(
            db, owner_id, llm, settings, purpose=purpose, system="s", user="hello", max_tokens=100
        )


async def clear(app: FastAPI) -> None:
    async with app.state.engine.begin() as conn:
        await conn.execute(text("delete from llm_calls"))


def test_prices_are_per_model_and_an_unknown_model_costs_like_the_dearest(
    settings: Settings,
) -> None:
    assert cost_micro_usd(settings, "claude-haiku-5-5", 1_000_000, 1_000_000) == 600_000
    assert cost_micro_usd(settings, "claude-sonnet-5-5", 1_000, 100) == 3_000  # $0.003
    assert price_of(settings, "some-new-model") == (2.0, 10.0)
    # worst case: 300 characters -> 101 tokens in, plus the whole max_tokens out
    assert worst_case_micro_usd(settings, "claude-haiku-5-5", "x" * 300, 1000) == round(
        101 * 0.10 + 1000 * 0.50
    )


async def test_each_call_is_priced_with_the_model_that_ran(
    app: FastAPI, settings: Settings, owner_id: uuid.UUID
) -> None:
    await clear(app)
    llm = FakeLlm("ok", input_tokens=1000, output_tokens=100)
    await ask(app, settings, owner_id, llm, purpose="jd-reading@v1")  # light prompt -> Haiku
    async with app.state.engine.begin() as conn:
        rows = (await conn.execute(text("select model, cost_micro_usd from llm_calls"))).all()
    assert [r[0] for r in rows] == [settings.llm_model_light]
    assert rows[0][1] == cost_micro_usd(settings, settings.llm_model_light, 1000, 100) == 150


async def test_the_daily_dollar_budget_stops_the_next_call_before_it_is_sent(
    app: FastAPI, settings: Settings, owner_id: uuid.UUID
) -> None:
    await clear(app)
    # one fake call = 3,000 + 1,000 micro-dollars at the fake model's (unknown -> dearest) price
    tight = settings.model_copy(update={"llm_daily_budget_usd": 0.003})
    llm = FakeLlm("ok", input_tokens=1000, output_tokens=100)
    await ask(app, tight, owner_id, llm)
    assert len(llm.calls) == 1
    with pytest.raises(ProblemError) as blocked:
        await ask(app, tight, owner_id, llm)
    assert blocked.value.status == 429 and blocked.value.title == "Daily AI budget reached"
    assert len(llm.calls) == 1  # nothing reached the model


async def test_the_monthly_budget_stops_calls_even_when_today_is_fine(
    app: FastAPI, settings: Settings, owner_id: uuid.UUID
) -> None:
    await clear(app)
    async with app.state.engine.begin() as conn:
        await conn.execute(
            text(
                "insert into llm_calls (id, owner_id, purpose, model, input_tokens, output_tokens,"
                " cost_micro_usd, latency_ms, status, created_at) values (gen_random_uuid(),"
                " :o, 'old', 'x', 0, 0, 11999500, 1, 'ok', date_trunc('month', now()))"
            ),
            {"o": owner_id},
        )
    llm = FakeLlm("ok")
    # the month started with $11.9995 already spent; today itself is empty
    with pytest.raises(ProblemError) as blocked:
        await ask(app, settings, owner_id, llm)
    assert blocked.value.title == "Monthly AI budget reached" and not llm.calls
    roomy = settings.model_copy(update={"llm_monthly_budget_usd": 30})
    await ask(app, roomy, owner_id, llm)
    assert len(llm.calls) == 1


async def test_a_failed_call_costs_nothing(
    app: FastAPI, settings: Settings, owner_id: uuid.UUID
) -> None:
    from careerpilot.core.llm import LlmError

    await clear(app)
    llm = FakeLlm(error=LlmError(502, "down"))
    with pytest.raises(ProblemError):
        await ask(app, settings, owner_id, llm)
    async with app.state.engine.begin() as conn:
        cost = await conn.scalar(text("select coalesce(sum(cost_micro_usd), 0) from llm_calls"))
    assert cost == 0
