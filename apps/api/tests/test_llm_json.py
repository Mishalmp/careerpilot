"""Prompt files and the JSON-reply helper (one repair attempt, usage cap, no guessing)."""

import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import text

from careerpilot.core.config import REPO_ROOT, Settings
from careerpilot.core.errors import ProblemError
from careerpilot.core.llm import call_llm_json, parse_json_reply
from careerpilot.core.prompts import Prompt, load_prompt
from tests.fakes import FakeLlm


class Verdict(BaseModel):
    ok: bool
    reason: str


PROMPT = Prompt("demo", 3, "A demo", 300, "Reply with JSON.")


# --- prompt files --------------------------------------------------------------------------


def test_every_prompt_file_loads_and_the_newest_version_wins(tmp_path: Path) -> None:
    for version, body in ((1, "old"), (2, "new"), (10, "newest")):
        folder = tmp_path / "demo"
        folder.mkdir(exist_ok=True)
        (folder / f"v{version}.md").write_text(
            f"---\ndescription: d{version}\nmax_tokens: {version}00\n---\n{body}\n",
            encoding="utf-8",
        )
    assert load_prompt(tmp_path, "demo").system == "newest"  # 10 beats 2, not "10" < "2"
    pinned = load_prompt(tmp_path, "demo", 2)
    assert (pinned.system, pinned.max_tokens, pinned.label) == ("new", 200, "demo@v2")


def test_a_missing_or_headerless_prompt_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt(tmp_path, "nope")
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "v1.md").write_text("no header", encoding="utf-8")
    with pytest.raises(ValueError, match="front matter"):
        load_prompt(tmp_path, "bad")


def test_the_committed_prompts_are_well_formed() -> None:
    folders = [p for p in (REPO_ROOT / "prompts").iterdir() if p.is_dir()]
    assert folders
    for folder in folders:
        prompt = load_prompt(REPO_ROOT / "prompts", folder.name)
        assert prompt.system and prompt.description and prompt.max_tokens > 0


# --- JSON replies --------------------------------------------------------------------------


def test_json_is_found_inside_chatter_and_code_fences() -> None:
    reply = 'Sure! ```json\n{"ok": true, "reason": "fine"}\n``` Hope that helps.'
    assert parse_json_reply(reply, Verdict) == Verdict(ok=True, reason="fine")


@pytest.mark.parametrize("reply", ["", "no json here", "{broken", '{"ok": "maybe", "reason": 1}'])
def test_unusable_replies_raise_value_error(reply: str) -> None:
    with pytest.raises(ValueError, match=r"."):
        parse_json_reply(reply, Verdict)


async def run(app: FastAPI, settings: Settings, owner_id: uuid.UUID, llm: FakeLlm) -> Verdict:
    async with app.state.sessionmaker() as db:
        return await call_llm_json(
            db,
            owner_id,
            llm,
            settings,
            prompt=PROMPT,
            user="Question",
            schema=Verdict,
        )


async def test_a_valid_reply_costs_one_call(
    app: FastAPI, settings: Settings, owner_id: uuid.UUID
) -> None:
    llm = FakeLlm('{"ok": true, "reason": "r"}')
    assert (await run(app, settings, owner_id, llm)).ok
    assert len(llm.calls) == 1
    assert llm.calls[0]["system"] == "Reply with JSON." and llm.calls[0]["max_tokens"] == 300


async def test_one_repair_attempt_is_made_and_shows_the_model_what_was_wrong(
    app: FastAPI, settings: Settings, owner_id: uuid.UUID
) -> None:
    llm = FakeLlm(replies=['{"ok": "maybe"}', '{"ok": false, "reason": "fixed"}'])
    assert (await run(app, settings, owner_id, llm)) == Verdict(ok=False, reason="fixed")
    assert len(llm.calls) == 2
    assert "could not be used" in llm.calls[1]["user"] and '{"ok": "maybe"}' in llm.calls[1]["user"]


async def test_two_bad_replies_fail_cleanly_without_guessing(
    app: FastAPI, settings: Settings, owner_id: uuid.UUID
) -> None:
    llm = FakeLlm("I think it is fine.")
    with pytest.raises(ProblemError) as caught:
        await run(app, settings, owner_id, llm)
    assert caught.value.status == 502
    assert len(llm.calls) == 2


async def test_a_refusal_is_reported_not_retried(
    app: FastAPI, settings: Settings, owner_id: uuid.UUID
) -> None:
    llm = FakeLlm("", refused=True)
    with pytest.raises(ProblemError) as caught:
        await run(app, settings, owner_id, llm)
    assert caught.value.title == "The model declined" and len(llm.calls) == 1


async def test_every_attempt_is_recorded_under_the_prompt_version(
    app: FastAPI, settings: Settings, owner_id: uuid.UUID
) -> None:
    async with app.state.engine.begin() as conn:
        await conn.execute(text("delete from llm_calls"))
    await run(app, settings, owner_id, FakeLlm(replies=["nope", '{"ok": true, "reason": "r"}']))
    async with app.state.engine.begin() as conn:
        purposes = [
            r[0]
            for r in await conn.execute(text("select purpose from llm_calls order by created_at"))
        ]
    assert purposes == ["demo@v3", "demo@v3:repair"]


async def test_the_daily_cap_stops_a_runaway_job(
    app: FastAPI, settings: Settings, owner_id: uuid.UUID
) -> None:
    async with app.state.engine.begin() as conn:
        await conn.execute(text("delete from llm_calls"))
    capped = settings.model_copy(update={"llm_daily_token_cap": 250})
    llm = FakeLlm("not json", input_tokens=100, output_tokens=50)  # each call spends 150

    # 0 used: the call runs (150); 150 < 250 so the repair runs too (300); then the job ends.
    with pytest.raises(ProblemError) as ended:
        await run(app, capped, owner_id, llm)
    assert ended.value.status == 502 and len(llm.calls) == 2

    # The cap is now used up: nothing reaches the model any more.
    with pytest.raises(ProblemError) as blocked:
        await run(app, capped, owner_id, llm)
    assert blocked.value.status == 429 and len(llm.calls) == 2
