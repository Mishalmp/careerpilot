"""Which model each prompt uses, and that the audit log records the model really used.
# covers: REQ-20 (cost control: cheap model for bulk reading, main model for judgement)
"""

import uuid

from fastapi import FastAPI
from sqlalchemy import select

from careerpilot.core.llm import LlmCall, call_llm
from tests.fakes import FakeLlm


async def run(app: FastAPI, owner: uuid.UUID, purpose: str, llm: FakeLlm) -> None:
    async with app.state.sessionmaker() as db:
        await call_llm(
            db, owner, llm, app.state.settings, purpose=purpose, system="s", user="u", max_tokens=50
        )


async def test_bulk_reading_prompts_use_the_light_model_and_judgement_uses_the_default(
    app: FastAPI, owner_id: uuid.UUID
) -> None:
    llm = FakeLlm("ok")
    await run(app, owner_id, "research-extract@v2", llm)
    await run(app, owner_id, "research-extract@v2:repair", llm)  # a repair call stays cheap too
    await run(app, owner_id, "ask-notes@v1", llm)
    await run(app, owner_id, "mock-evaluate@v1", llm)
    assert [c["model"] for c in llm.calls] == ["claude-haiku-5-5", "claude-haiku-5-5", None, None]

    async with app.state.sessionmaker() as db:
        rows = (await db.scalars(select(LlmCall).order_by(LlmCall.created_at))).all()
    assert [r.model for r in rows] == [
        "claude-haiku-5-5",
        "claude-haiku-5-5",
        "fake-model",  # the client's own default
        "fake-model",
    ]


async def test_the_light_list_is_a_setting_not_code(app: FastAPI, owner_id: uuid.UUID) -> None:
    app.state.settings = app.state.settings.model_copy(
        update={"llm_light_prompts": ["ask-notes"], "llm_model_light": "some-other-model"}
    )
    llm = FakeLlm("ok")
    await run(app, owner_id, "ask-notes@v1", llm)
    await run(app, owner_id, "research-extract@v2", llm)
    assert [c["model"] for c in llm.calls] == ["some-other-model", None]
