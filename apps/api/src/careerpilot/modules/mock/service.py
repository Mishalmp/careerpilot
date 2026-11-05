import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.config import Settings
from careerpilot.core.errors import ProblemError
from careerpilot.core.llm import LlmClient, call_llm_json
from careerpilot.core.prompts import data_block, load_prompt
from careerpilot.modules.intel import service as intel_service
from careerpilot.modules.knowledge import service as knowledge_service
from careerpilot.modules.knowledge.embeddings import Embedder
from careerpilot.modules.mock import repository
from careerpilot.modules.mock.models import MockSession
from careerpilot.modules.mock.rules import summarise
from careerpilot.modules.mock.schemas import (
    AnswerMockRequest,
    MockSessionItem,
    MockSessionOut,
    MockSummaryOut,
    MockTopicResultOut,
    MockTurnOut,
    RawEvaluation,
    RawQuestion,
    StartMockRequest,
)
from careerpilot.modules.tracker import service as tracker_service

MAX_JD_CHARS = 3000
MAX_NOTE_CHARS = 600
INTEL_TOPICS = 6
INTEL_QUESTIONS = 3


def _not_found() -> ProblemError:
    return ProblemError(404, "Not found", "Mock interview not found.")


def _need_llm(llm: LlmClient | None) -> LlmClient:
    if llm is None:
        raise ProblemError(
            409, "Needs an API key", "Set ANTHROPIC_API_KEY: the model plays the interviewer."
        )
    return llm


def _current_turn(row: MockSession) -> int | None:
    if row.finished_at is not None:
        return None
    for index, turn in enumerate(row.turns):
        if turn.get("answer") is None:
            return index
    return None


def _out(row: MockSession) -> MockSessionOut:
    summary = summarise(row.turns)
    return MockSessionOut(
        id=row.id,
        job_id=row.job_id,
        title=row.title,
        focus=row.focus,
        total_questions=row.total_questions,
        turns=[MockTurnOut.model_validate(t) for t in row.turns],
        current_turn=_current_turn(row),
        finished=row.finished_at is not None,
        summary=MockSummaryOut(
            average=summary.average,
            answered=summary.answered,
            weak=[MockTopicResultOut(**vars(r)) for r in summary.weak],
            strong=[MockTopicResultOut(**vars(r)) for r in summary.strong],
        )
        if row.finished_at is not None
        else None,
        created_at=row.created_at,
    )


def _topic(value: str) -> str:
    return " ".join(value.lower().split())[:40] or "general"


def _asked(turns: list[dict[str, Any]]) -> str:
    return "Questions already asked:\n" + (
        "\n".join(f"- {t['question']}" for t in turns) if turns else "(none yet)"
    )


# --- reading -------------------------------------------------------------------------------


async def list_sessions(db: AsyncSession, owner_id: uuid.UUID) -> list[MockSessionItem]:
    items: list[MockSessionItem] = []
    for row in await repository.list_recent(db, owner_id):
        summary = summarise(row.turns)
        items.append(
            MockSessionItem(
                id=row.id,
                title=row.title,
                created_at=row.created_at,
                answered=summary.answered,
                total_questions=row.total_questions,
                average=summary.average,
                finished=row.finished_at is not None,
            )
        )
    return items


async def get_session(
    db: AsyncSession, owner_id: uuid.UUID, session_id: uuid.UUID
) -> MockSessionOut:
    row = await repository.get(db, owner_id, session_id)
    if row is None:
        raise _not_found()
    return _out(row)


async def delete_session(db: AsyncSession, owner_id: uuid.UUID, session_id: uuid.UUID) -> None:
    if not await repository.delete_session(db, owner_id, session_id):
        raise _not_found()
    await db.commit()


# --- starting ------------------------------------------------------------------------------


async def start(
    db: AsyncSession,
    owner_id: uuid.UUID,
    data: StartMockRequest,
    *,
    llm: LlmClient | None,
    settings: Settings,
    today: date,
) -> MockSessionOut:
    llm = _need_llm(llm)
    parts: list[str] = []
    focus = data.focus or ""
    title = focus
    if data.job_id is not None:
        job = await tracker_service.get_job(db, owner_id, data.job_id)
        focus = focus or f"{job.title} at {job.company.name}"
        title = f"{job.title} · {job.company.name}"
        if job.jd_text:
            parts.append(data_block("job_description", job.jd_text[:MAX_JD_CHARS]))
        intel = await intel_service.get_intel(db, owner_id, job.id, today=today, ai_available=True)
        facts = [t.key for t in intel.brief.topics[:INTEL_TOPICS]] + [
            q.text for q in intel.brief.likely_questions[:INTEL_QUESTIONS]
        ]
        if facts:
            parts.append(data_block("intel", "\n".join(f"- {fact}" for fact in facts)))
    parts.insert(0, f"Focus: {focus}\n{_asked([])}")

    raw = await call_llm_json(
        db,
        owner_id,
        llm,
        settings,
        prompt=load_prompt(settings.prompts_dir, "mock-question", 1),
        user="\n\n".join(parts),
        schema=RawQuestion,
    )
    row = repository.add(
        db,
        owner_id,
        job_id=data.job_id,
        title=title[:120],
        focus=focus,
        total_questions=data.questions,
        turns=[
            {
                "question": raw.question,
                "topic": _topic(raw.topic),
                "answer": None,
                "score": None,
                "feedback": None,
            }
        ],
    )
    await db.commit()
    await db.refresh(row)
    return _out(row)


# --- answering -----------------------------------------------------------------------------


async def _notes_for(
    db: AsyncSession, owner_id: uuid.UUID, embedder: Embedder, settings: Settings, question: str
) -> str | None:
    """Passages from your own notes about the question, if your notes cover it."""
    found = await knowledge_service.search(db, owner_id, embedder, settings, question, limit=2)
    if not found.confident:
        return None
    return data_block(
        "notes",
        "\n\n".join(f"[{n}] {h.text[:MAX_NOTE_CHARS]}" for n, h in enumerate(found.hits, 1)),
    )


async def answer(
    db: AsyncSession,
    owner_id: uuid.UUID,
    session_id: uuid.UUID,
    data: AnswerMockRequest,
    *,
    llm: LlmClient | None,
    settings: Settings,
    embedder: Embedder,
) -> MockSessionOut:
    llm = _need_llm(llm)
    row = await repository.get(db, owner_id, session_id)
    if row is None:
        raise _not_found()
    current = _current_turn(row)
    if current is None:
        raise ProblemError(409, "This interview is finished", "Start a new one.")
    if data.turn != current:
        raise ProblemError(409, "Out of date", "That question was already answered. Reload.")
    turn = row.turns[current]
    last = current + 1 >= row.total_questions

    sections = [
        f"Question: {turn['question']}\nlast_question: {str(last).lower()}",
        data_block("answer", data.answer),
    ]
    notes = await _notes_for(db, owner_id, embedder, settings, turn["question"])
    if notes:
        sections.append(notes)
    sections.append(_asked(row.turns))
    raw = await call_llm_json(
        db,
        owner_id,
        llm,
        settings,
        prompt=load_prompt(settings.prompts_dir, "mock-evaluate", 1),
        user="\n\n".join(sections),
        schema=RawEvaluation,
    )
    next_question = raw.next_question or ""
    if not last and len(next_question) < 10:
        raise ProblemError(502, "AI reply could not be used", "The next question was missing.")

    # The model call committed, which released any lock. Re-read under a lock and make sure
    # nobody answered this question meanwhile.
    row = await repository.get(db, owner_id, session_id, lock=True)
    if row is None:
        raise _not_found()
    if _current_turn(row) != current:
        raise ProblemError(409, "Out of date", "That question was already answered. Reload.")

    turns = [dict(t) for t in row.turns]
    turns[current] |= {"answer": data.answer, "score": raw.score, "feedback": raw.feedback}
    if last:
        row.finished_at = datetime.now(UTC)
    else:
        turns.append(
            {
                "question": next_question,
                "topic": _topic(raw.next_topic or ""),
                "answer": None,
                "score": None,
                "feedback": None,
            }
        )
    row.turns = turns  # a new list, so the JSON column is seen as changed
    await db.commit()
    await db.refresh(row)
    return _out(row)
