"""Learning use cases: topics, questions, answering with spaced repetition, the review queue.

Services own the transaction. The answer flow is idempotent: the client sends a token with each
answer, and sending the same token again returns the stored result instead of scoring twice.
"""

import math
import secrets
import statistics
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.errors import ProblemError
from careerpilot.modules.learn import checkpoint as checkpoint_builder
from careerpilot.modules.learn import repository, rules, scheduler
from careerpilot.modules.learn.enums import (
    AUTO_GRADED,
    GradedBy,
    QuestionOrigin,
    QuestionStatus,
    QuestionType,
    Rating,
    TopicOrigin,
)
from careerpilot.modules.learn.models import (
    LearnAttempt,
    LearnCheckpoint,
    LearnCheckpointItem,
    LearnQuestion,
    LearnReviewCard,
    LearnTopic,
)
from careerpilot.modules.learn.schemas import (
    LearnAnswerIn,
    LearnAnswerOut,
    LearnCheckpointCreate,
    LearnCheckpointItemOut,
    LearnCheckpointOut,
    LearnCheckpointQuestion,
    LearnCheckpointResult,
    LearnCheckpointSave,
    LearnCheckpointSummary,
    LearnOptionOut,
    LearnPublicOption,
    LearnQuestionCreate,
    LearnQuestionOut,
    LearnQuestionToAnswer,
    LearnQuestionUpdate,
    LearnReviewQueue,
    LearnSourceOut,
    LearnStats,
    LearnTopicCreate,
    LearnTopicOut,
    LearnTopicScore,
    LearnTopicUpdate,
)

NEW_PER_DAY = 20  # how many never-seen questions may be started per day (becomes a setting later)
WRITTEN = frozenset({QuestionType.SHORT, QuestionType.EXPLAIN, QuestionType.SCENARIO})


def _not_found(what: str) -> ProblemError:
    return ProblemError(404, "Not found", f"{what} not found.")


def _invalid(error: rules.QuestionInvalidError) -> ProblemError:
    return ProblemError(422, "Question not valid", str(error))


def _card_state(card: LearnReviewCard) -> scheduler.CardState:
    return scheduler.CardState(
        state=card.state,
        step=card.step,
        stability=card.stability,
        difficulty=card.difficulty,
        due=card.due_at,
        last_review=card.last_review_at,
        reps=card.reps,
        lapses=card.lapses,
    )


def _apply_card(card: LearnReviewCard, new: scheduler.CardState, now: datetime) -> None:
    card.state = new.state
    card.step = new.step
    card.stability = new.stability
    card.difficulty = new.difficulty
    card.due_at = new.due
    card.last_review_at = new.last_review
    card.reps = new.reps
    card.lapses = new.lapses
    if card.first_review_at is None:
        card.first_review_at = now


def _start_of_day(timezone: str, now: datetime) -> datetime:
    local = now.astimezone(ZoneInfo(timezone))
    return datetime.combine(
        local.date(), datetime.min.time(), tzinfo=ZoneInfo(timezone)
    ).astimezone(UTC)


# --- topics ---


async def _mastery(db: AsyncSession, owner_id: uuid.UUID, now: datetime) -> dict[uuid.UUID, float]:
    """Mean chance (0 to 100) of remembering the reviewed cards of each topic, right now."""
    by_topic: dict[uuid.UUID, list[float]] = defaultdict(list)
    for topic_id, card in await repository.cards_for_mastery(db, owner_id):
        by_topic[topic_id].append(scheduler.retrievability(_card_state(card), now))
    return {t: round(100 * sum(v) / len(v), 1) for t, v in by_topic.items()}


def _topic_out(topic: LearnTopic, count: int, mastery: float | None) -> LearnTopicOut:
    return LearnTopicOut(
        id=topic.id,
        title=topic.title,
        summary=topic.summary,
        area=topic.area,
        priority=topic.priority,
        status=topic.status,
        origin=topic.origin,
        notes=topic.notes,
        archived=topic.archived,
        question_count=count,
        mastery=mastery,
        updated_at=topic.updated_at,
    )


async def list_topics(
    db: AsyncSession, owner_id: uuid.UUID, now: datetime, *, include_archived: bool = False
) -> list[LearnTopicOut]:
    topics = await repository.list_topics(db, owner_id, include_archived=include_archived)
    counts = await repository.question_counts(db, owner_id)
    mastery = await _mastery(db, owner_id, now)
    return [_topic_out(t, counts.get(t.id, 0), mastery.get(t.id)) for t in topics]


async def create_topic(
    db: AsyncSession,
    owner_id: uuid.UUID,
    data: LearnTopicCreate,
    *,
    origin: TopicOrigin = TopicOrigin.MANUAL,
) -> LearnTopicOut:
    if await repository.find_topic_by_title(db, owner_id, data.title):
        raise ProblemError(409, "Already exists", "You already have a topic with that title.")
    topic = repository.add_topic(db, owner_id, origin=origin, **data.model_dump())
    try:
        await db.commit()
    except IntegrityError:  # two requests raced past the check above
        await db.rollback()
        raise ProblemError(
            409, "Already exists", "You already have a topic with that title."
        ) from None
    await db.refresh(topic)
    return _topic_out(topic, 0, None)


async def ensure_topic(
    db: AsyncSession,
    owner_id: uuid.UUID,
    title: str,
    origin: TopicOrigin,
    summary: str | None = None,
) -> LearnTopic:
    """The owner's topic with this title (any case), created if missing. Does not commit: the
    caller commits, so a topic and whatever depends on it are saved together."""
    clean = " ".join(title.split())[:200]
    existing = await repository.find_topic_by_title(db, owner_id, clean)
    if existing is not None:
        if existing.archived:
            existing.archived = False  # approving something for an archived topic brings it back
        return existing
    topic = repository.add_topic(db, owner_id, title=clean, summary=summary, origin=origin)
    await db.flush()
    return topic


async def update_topic(
    db: AsyncSession,
    owner_id: uuid.UUID,
    topic_id: uuid.UUID,
    data: LearnTopicUpdate,
    now: datetime,
) -> LearnTopicOut:
    topic = await repository.get_topic(db, owner_id, topic_id)
    if topic is None:
        raise _not_found("Topic")
    for field in data.model_fields_set:
        value = getattr(data, field)
        if value is None and field not in ("summary", "area", "notes"):
            continue  # only these may be cleared
        setattr(topic, field, value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ProblemError(
            409, "Already exists", "You already have a topic with that title."
        ) from None
    await db.refresh(topic)
    counts = await repository.question_counts(db, owner_id)
    mastery = await _mastery(db, owner_id, now)
    return _topic_out(topic, counts.get(topic.id, 0), mastery.get(topic.id))


async def delete_topic(db: AsyncSession, owner_id: uuid.UUID, topic_id: uuid.UUID) -> None:
    """Deletes the topic with its questions and history. The UI archives by default instead."""
    if not await repository.delete_topic(db, owner_id, topic_id):
        raise _not_found("Topic")
    await db.commit()


# --- questions ---


def _options_out(question: LearnQuestion) -> list[LearnOptionOut]:
    return [LearnOptionOut.model_validate(o) for o in question.options]


def _question_out(question: LearnQuestion) -> LearnQuestionOut:
    return LearnQuestionOut(
        id=question.id,
        topic_id=question.topic_id,
        type=question.type,
        stem=question.stem,
        explanation=question.explanation,
        difficulty=question.difficulty,
        status=question.status,
        origin=question.origin,
        rubric=question.rubric,
        practice_slug=question.practice_slug,
        tags=list(question.tags or []),
        options=_options_out(question),
        sources=[LearnSourceOut.model_validate(s) for s in question.sources],
        updated_at=question.updated_at,
    )


async def create_question(
    db: AsyncSession,
    owner_id: uuid.UUID,
    data: LearnQuestionCreate,
    now: datetime,
    *,
    origin: QuestionOrigin = QuestionOrigin.MANUAL,
    status: QuestionStatus | None = None,
) -> LearnQuestionOut:
    topic = await repository.get_topic(db, owner_id, data.topic_id)
    if topic is None:
        raise _not_found("Topic")
    try:
        stem = rules.validate_stem(data.stem)
        options = [rules.Option(o.text, o.is_correct) for o in data.options]
        rules.validate_options(data.type, options)
    except rules.QuestionInvalidError as error:
        raise _invalid(error) from None
    if (data.type is QuestionType.PRACTICAL) != (data.practice_slug is not None):
        raise _invalid(
            rules.QuestionInvalidError(
                "A practical question needs a practice problem, and other kinds must not have one."
            )
        )
    if data.rubric and data.type not in WRITTEN:
        raise _invalid(rules.QuestionInvalidError("Only written questions have a rubric."))
    # What you write yourself is trusted. Anything else must be checked by the caller, which
    # passes the status it earned (verified only with a source whose quote was found).
    final_status = status or QuestionStatus.VERIFIED
    if (
        origin is not QuestionOrigin.MANUAL
        and final_status is QuestionStatus.VERIFIED
        and not data.sources
    ):
        raise _invalid(
            rules.QuestionInvalidError(
                "A question that is not your own needs a source to be verified."
            )
        )

    question = repository.add_question(
        db,
        owner_id,
        topic_id=data.topic_id,
        type=data.type,
        stem=stem,
        explanation=data.explanation,
        difficulty=data.difficulty,
        status=final_status,
        origin=origin,
        rubric=data.rubric,
        practice_slug=data.practice_slug,
        tags=data.tags,
    )
    question.options = [
        repository.option(
            owner_id,
            position=i,
            text=" ".join(o.text.split()),
            is_correct=o.is_correct,
            rationale=o.rationale,
        )
        for i, o in enumerate(data.options)
    ]
    question.sources = [
        repository.source(
            owner_id, url=s.url, title=s.title, quote=s.quote, fetched_on=s.fetched_on
        )
        for s in data.sources
    ]
    await db.flush()
    fresh = scheduler.new_card(now)
    repository.add_card(
        db,
        owner_id,
        question_id=question.id,
        state=fresh.state,
        step=fresh.step,
        stability=None,
        difficulty=None,
        due_at=fresh.due,
        reps=0,
        lapses=0,
    )
    await db.commit()
    await db.refresh(question)
    return _question_out(question)


async def get_question(
    db: AsyncSession, owner_id: uuid.UUID, question_id: uuid.UUID
) -> LearnQuestionOut:
    question = await repository.get_question(db, owner_id, question_id)
    if question is None:
        raise _not_found("Question")
    return _question_out(question)


async def list_questions(
    db: AsyncSession,
    owner_id: uuid.UUID,
    *,
    topic_id: uuid.UUID | None,
    status: QuestionStatus | None,
    kind: QuestionType | None,
    query: str | None,
    limit: int,
    offset: int,
) -> tuple[list[LearnQuestionOut], int]:
    rows, total = await repository.list_questions(
        db,
        owner_id,
        topic_id=topic_id,
        status=status,
        kind=kind,
        query=query,
        limit=limit,
        offset=offset,
    )
    return [_question_out(q) for q in rows], total


async def update_question(
    db: AsyncSession, owner_id: uuid.UUID, question_id: uuid.UUID, data: LearnQuestionUpdate
) -> LearnQuestionOut:
    question = await repository.get_question(db, owner_id, question_id)
    if question is None:
        raise _not_found("Question")
    if "topic_id" in data.model_fields_set and data.topic_id is not None:
        if await repository.get_topic(db, owner_id, data.topic_id) is None:
            raise _not_found("Topic")
        question.topic_id = data.topic_id
    if "stem" in data.model_fields_set and data.stem is not None:
        try:
            question.stem = rules.validate_stem(data.stem)
        except rules.QuestionInvalidError as error:
            raise _invalid(error) from None
    if "explanation" in data.model_fields_set:
        question.explanation = data.explanation
    if "difficulty" in data.model_fields_set and data.difficulty is not None:
        question.difficulty = data.difficulty
    if "tags" in data.model_fields_set and data.tags is not None:
        question.tags = list(dict.fromkeys(" ".join(t.lower().split()) for t in data.tags))
    if "status" in data.model_fields_set and data.status is not None:
        needs_source = (
            data.status is QuestionStatus.VERIFIED
            and question.origin is not QuestionOrigin.MANUAL
            and not question.sources
        )
        if needs_source:
            raise _invalid(
                rules.QuestionInvalidError("Only a question with a source can be marked verified.")
            )
        question.status = data.status
    await db.commit()
    await db.refresh(question)
    return _question_out(question)


async def delete_question(db: AsyncSession, owner_id: uuid.UUID, question_id: uuid.UUID) -> None:
    if not await repository.delete_question(db, owner_id, question_id):
        raise _not_found("Question")
    await db.commit()


# --- answering ---


def _to_answer(question: LearnQuestion, topic_title: str, *, is_new: bool) -> LearnQuestionToAnswer:
    return LearnQuestionToAnswer(
        id=question.id,
        topic_id=question.topic_id,
        topic_title=topic_title,
        type=question.type,
        stem=question.stem,
        difficulty=question.difficulty,
        status=question.status,
        options=[LearnPublicOption(position=o.position, text=o.text) for o in question.options],
        rubric=question.rubric,
        practice_slug=question.practice_slug,
        is_new=is_new,
    )


async def review_queue(
    db: AsyncSession, owner_id: uuid.UUID, now: datetime, timezone: str, *, limit: int = 20
) -> LearnReviewQueue:
    """Due reviews first (the ones you are most likely to have forgotten first, topics mixed),
    then new questions up to today's allowance."""
    limit = max(1, min(limit, 50))
    due_total = await repository.count_due(db, owner_id, now)
    started = await repository.started_today(db, owner_id, _start_of_day(timezone, now))
    new_left = max(0, NEW_PER_DAY - started)
    new_total = min(new_left, await repository.count_new(db, owner_id))

    titles = {
        t.id: t.title for t in await repository.list_topics(db, owner_id, include_archived=True)
    }
    due = await repository.due_cards(db, owner_id, now, 200)
    ranked = sorted(due, key=lambda pair: scheduler.retrievability(_card_state(pair[0]), now))
    # Interleave topics: take the weakest card of each topic in turn, so a session is mixed.
    queues: dict[uuid.UUID, list[LearnQuestion]] = defaultdict(list)
    for _, question in ranked:
        queues[question.topic_id].append(question)
    mixed: list[LearnQuestion] = []
    while len(mixed) < limit and any(queues.values()):
        for topic_id in list(queues):
            if queues[topic_id] and len(mixed) < limit:
                mixed.append(queues[topic_id].pop(0))
    items = [_to_answer(q, titles.get(q.topic_id, ""), is_new=False) for q in mixed]
    room = limit - len(items)
    if room > 0 and new_total > 0:
        for _, question in await repository.new_cards(db, owner_id, min(room, new_total)):
            items.append(_to_answer(question, titles.get(question.topic_id, ""), is_new=True))
    return LearnReviewQueue(due=due_total, new_available=new_total, items=items)


def _reveal(
    question: LearnQuestion,
    *,
    correct: bool,
    score: float,
    rating: Rating,
    graded_by: GradedBy,
    due: datetime,
    already: bool,
) -> LearnAnswerOut:
    correct_positions = [o.position for o in question.options if o.is_correct]
    return LearnAnswerOut(
        already_answered=already,
        correct=correct,
        score=score,
        rating=rating,
        graded_by=graded_by,
        correct_positions=correct_positions,
        explanation=question.explanation,
        options=_options_out(question),
        sources=[LearnSourceOut.model_validate(s) for s in question.sources],
        next_due=due,
    )


async def answer(
    db: AsyncSession,
    owner_id: uuid.UUID,
    question_id: uuid.UUID,
    data: LearnAnswerIn,
    now: datetime,
) -> LearnAnswerOut:
    """Mark an answer, update the schedule, and reveal the answer. Safe to repeat with one token."""
    question = await repository.get_question(db, owner_id, question_id)
    if question is None or question.status is QuestionStatus.ARCHIVED:
        raise _not_found("Question")

    existing = await repository.get_attempt_by_token(db, owner_id, data.token)
    if existing is not None:
        return await _replay(db, owner_id, question, existing)

    if question.type in AUTO_GRADED:
        if not data.selected:
            raise ProblemError(
                422, "Choose an answer", "Pick at least one option before answering."
            )
        positions = {o.position for o in question.options}
        if len(set(data.selected)) != len(data.selected) or not set(data.selected) <= positions:
            raise ProblemError(
                422, "Invalid answer", "Those options do not belong to this question."
            )
        marked = rules.grade_mcq(
            frozenset(o.position for o in question.options if o.is_correct),
            frozenset(data.selected),
        )
        score, correct, graded_by = marked.score, marked.correct, GradedBy.CODE
        stored: dict[str, object] = {"selected": sorted(data.selected)}
    else:
        if data.self_score is None:
            raise ProblemError(
                422,
                "Rate your answer",
                "Written answers are rated by you: send how well you did (0 to 1).",
            )
        score = data.self_score
        correct = score >= rules.PASS_SCORE
        graded_by = GradedBy.SELF
        stored = {"text": data.text, "self_score": score}

    seconds_seen = await repository.recent_seconds(db, owner_id, question.type)
    typical = statistics.median(seconds_seen) if len(seconds_seen) >= 5 else None
    rating = rules.rating_from_answer(score, data.confidence, data.seconds, typical)

    card = await repository.get_card(db, owner_id, question.id)
    if card is None:  # a question made before cards existed, or a repaired row
        fresh = scheduler.new_card(now)
        card = repository.add_card(
            db,
            owner_id,
            question_id=question.id,
            state=fresh.state,
            step=fresh.step,
            due_at=fresh.due,
            reps=0,
            lapses=0,
        )
    updated = scheduler.review(_card_state(card), rating, now)
    _apply_card(card, updated, now)
    repository.add_attempt(
        db,
        owner_id,
        question_id=question.id,
        token=data.token,
        answer=stored,
        score=score,
        correct=correct,
        confidence=data.confidence,
        seconds=data.seconds,
        graded_by=graded_by,
        rating=rating,
    )
    try:
        await db.commit()
    except IntegrityError:
        # Two requests with the same token arrived together: the other one won; return its result.
        await db.rollback()
        winner = await repository.get_attempt_by_token(db, owner_id, data.token)
        if winner is None:
            raise
        refreshed = await repository.get_question(db, owner_id, question_id)
        if refreshed is None:
            raise _not_found("Question") from None
        return await _replay(db, owner_id, refreshed, winner)

    return _reveal(
        question,
        correct=correct,
        score=score,
        rating=rating,
        graded_by=graded_by,
        due=updated.due,
        already=False,
    )


async def _replay(
    db: AsyncSession, owner_id: uuid.UUID, question: LearnQuestion, attempt: LearnAttempt
) -> LearnAnswerOut:
    """The stored result of an answer that was already scored."""
    if attempt.question_id != question.id:
        raise ProblemError(
            409, "Token reused", "That answer token was already used for another question."
        )
    card = await repository.get_card(db, owner_id, question.id)
    return _reveal(
        question,
        correct=attempt.correct,
        score=attempt.score,
        rating=attempt.rating,
        graded_by=attempt.graded_by,
        due=card.due_at if card else datetime.now(UTC),
        already=True,
    )


# --- stats ---


def streak(days: set[date], today: date) -> int:
    """Consecutive days with an answer, ending today (or yesterday, so the streak is not lost
    before you have studied today)."""
    cursor = today if today in days else today - timedelta(days=1)
    count = 0
    while cursor in days:
        count += 1
        cursor -= timedelta(days=1)
    return count


async def stats(db: AsyncSession, owner_id: uuid.UUID, now: datetime, timezone: str) -> LearnStats:
    zone = ZoneInfo(timezone)
    today = now.astimezone(zone).date()
    since = _start_of_day(timezone, now - timedelta(days=60))
    attempts = await repository.attempts_since(db, owner_id, since)
    days = {a.astimezone(zone).date() for a in attempts}
    answered_today = sum(1 for a in attempts if a.astimezone(zone).date() == today)
    started = await repository.started_today(db, owner_id, _start_of_day(timezone, now))
    topics = await repository.list_topics(db, owner_id, include_archived=False)
    counts = await repository.question_counts(db, owner_id)
    return LearnStats(
        topics=len(topics),
        questions=sum(counts.values()),
        due_now=await repository.count_due(db, owner_id, now),
        new_today_left=max(0, NEW_PER_DAY - started),
        answered_today=answered_today,
        streak_days=streak(days, today),
    )


# --- checkpoint exams ---

TOPIC_WEIGHT = {1: 3.0, 2: 2.0, 3: 1.0}  # high priority topics get more questions


def _snapshot(question: LearnQuestion, topic_title: str) -> dict[str, Any]:
    return {
        "stem": question.stem,
        "type": question.type.value,
        "topic_title": topic_title,
        "explanation": question.explanation,
        "options": [
            {
                "position": o.position,
                "text": o.text,
                "is_correct": o.is_correct,
                "rationale": o.rationale,
            }
            for o in question.options
        ],
        "sources": [
            {
                "url": s.url,
                "title": s.title,
                "quote": s.quote,
                "fetched_on": s.fetched_on.isoformat() if s.fetched_on else None,
                "reliability": s.reliability,
            }
            for s in question.sources
        ],
    }


def _options_of(item: LearnCheckpointItem) -> list[dict[str, Any]]:
    return list(item.snapshot["options"])


def _grade_item(item: LearnCheckpointItem) -> rules.McqResult:
    correct = frozenset(int(o["position"]) for o in _options_of(item) if o["is_correct"])
    return rules.grade_mcq(correct, frozenset(item.selected or []))


def _item_out(item: LearnCheckpointItem, *, submitted: bool) -> LearnCheckpointItemOut:
    snap = item.snapshot
    options = _options_of(item)
    result = None
    if submitted:
        result = LearnCheckpointResult(
            correct=bool(item.correct),
            score=item.score or 0.0,
            correct_positions=[int(o["position"]) for o in options if o["is_correct"]],
            explanation=snap.get("explanation"),
            options=[
                LearnOptionOut(
                    position=int(o["position"]),
                    text=str(o["text"]),
                    is_correct=bool(o["is_correct"]),
                    rationale=o.get("rationale"),
                )
                for o in options
            ],
            sources=[LearnSourceOut.model_validate(s) for s in snap.get("sources", [])],
        )
    return LearnCheckpointItemOut(
        position=item.position,
        question=LearnCheckpointQuestion(
            type=QuestionType(str(snap["type"])),
            stem=str(snap["stem"]),
            topic_title=str(snap["topic_title"]),
            options=[
                LearnPublicOption(position=int(o["position"]), text=str(o["text"])) for o in options
            ],
        ),
        selected=item.selected,
        flagged=item.flagged,
        result=result,
    )


def _checkpoint_out(checkpoint: LearnCheckpoint, now: datetime) -> LearnCheckpointOut:
    submitted = checkpoint.status == "submitted"
    per_topic = None
    if checkpoint.per_topic is not None:
        per_topic = [LearnTopicScore(topic=t, **v) for t, v in checkpoint.per_topic.items()]
    left = None if submitted else max(0, int((checkpoint.deadline - now).total_seconds()))
    return LearnCheckpointOut(
        id=checkpoint.id,
        status=checkpoint.status,
        size=checkpoint.size,
        minutes=checkpoint.minutes,
        pass_mark=checkpoint.pass_mark,
        started_at=checkpoint.started_at,
        deadline=checkpoint.deadline,
        seconds_left=left,
        submitted_at=checkpoint.submitted_at,
        expired=checkpoint.expired,
        score=checkpoint.score,
        passed=checkpoint.passed,
        notes=list(checkpoint.notes or []),
        per_topic=per_topic,
        items=[_item_out(i, submitted=submitted) for i in checkpoint.items],
    )


async def create_checkpoint(
    db: AsyncSession, owner_id: uuid.UUID, data: LearnCheckpointCreate, now: datetime
) -> LearnCheckpointOut:
    """Build an exam from the questions you have studied and start the clock. If one is already
    running (not expired), that one is returned instead of starting another."""
    active = await repository.active_checkpoint(db, owner_id)
    if active is not None:
        if now <= active.deadline:
            return _checkpoint_out(active, now)
        await _finalize(db, active, now, expired=True)
    rows = await repository.studied_questions(db, owner_id, data.topic_ids)
    if not rows:
        raise ProblemError(
            422,
            "Nothing to examine yet",
            "A checkpoint uses verified multiple-choice questions you have already answered. "
            "Review some questions first.",
        )
    last_seen = await repository.last_in_checkpoint(db, owner_id)
    by_id = {q.id: (q, t) for q, t in rows}
    candidates = [
        checkpoint_builder.Candidate(
            id=str(q.id),
            topic_id=str(t.id),
            type=q.type,
            difficulty=q.difficulty,
            seen_days_ago=(now - last_seen[q.id]).days if q.id in last_seen else None,
        )
        for q, t in rows
    ]
    seed = data.seed if data.seed is not None else secrets.randbelow(2**31)
    spec = checkpoint_builder.Spec(
        size=data.size,
        seed=seed,
        mix={"choice": 1.0},
        topic_weights={str(t.id): TOPIC_WEIGHT[t.priority] for _, t in rows},
    )
    built = checkpoint_builder.build(candidates, spec)
    minutes = data.minutes or max(1, math.ceil(1.5 * len(built.question_ids)))
    checkpoint = repository.add_checkpoint(
        db,
        owner_id,
        size=len(built.question_ids),
        minutes=minutes,
        pass_mark=data.pass_mark,
        seed=seed,
        topic_ids=[str(t) for t in data.topic_ids],
        notes=built.notes,
        started_at=now,
        deadline=now + timedelta(minutes=minutes),
    )
    checkpoint.items = []
    for position, question_id in enumerate(built.question_ids):
        question, topic = by_id[uuid.UUID(question_id)]
        checkpoint.items.append(
            LearnCheckpointItem(
                owner_id=owner_id,
                position=position,
                question_id=question.id,
                topic_id=topic.id,
                snapshot=_snapshot(question, topic.title),
            )
        )
    await db.commit()
    await db.refresh(checkpoint)
    return _checkpoint_out(checkpoint, now)


async def _finalize(
    db: AsyncSession, checkpoint: LearnCheckpoint, now: datetime, *, expired: bool
) -> None:
    """Mark the answers, store the score and per-topic result, and bring weak questions back."""
    total = 0.0
    topics: dict[str, dict[str, Any]] = {}
    for item in checkpoint.items:
        marked = _grade_item(item)
        item.score = marked.score
        item.correct = marked.correct
        total += marked.score
        title = str(item.snapshot["topic_title"])
        entry = topics.setdefault(title, {"correct": 0, "total": 0, "points": 0.0})
        entry["total"] += 1
        entry["correct"] += 1 if marked.correct else 0
        entry["points"] += marked.score
        if not marked.correct:
            card = await repository.get_card(db, checkpoint.owner_id, item.question_id)
            if card is not None and card.reps > 0 and card.due_at > now:
                card.due_at = now  # a missed question is due for review again now
    score = total / len(checkpoint.items) if checkpoint.items else 0.0
    checkpoint.score = round(score, 4)
    checkpoint.passed = score >= checkpoint.pass_mark
    checkpoint.per_topic = {
        title: {
            "correct": v["correct"],
            "total": v["total"],
            "score": round(v["points"] / v["total"], 4),
        }
        for title, v in sorted(topics.items())
    }
    checkpoint.status = "submitted"
    checkpoint.submitted_at = min(now, checkpoint.deadline) if expired else now
    checkpoint.expired = expired
    await db.commit()
    await db.refresh(checkpoint)


async def _load(
    db: AsyncSession, owner_id: uuid.UUID, checkpoint_id: uuid.UUID, now: datetime
) -> LearnCheckpoint:
    checkpoint = await repository.get_checkpoint(db, owner_id, checkpoint_id)
    if checkpoint is None:
        raise _not_found("Checkpoint")
    if checkpoint.status == "in_progress" and now > checkpoint.deadline:
        await _finalize(db, checkpoint, now, expired=True)  # time ran out: score what was saved
    return checkpoint


async def get_checkpoint(
    db: AsyncSession, owner_id: uuid.UUID, checkpoint_id: uuid.UUID, now: datetime
) -> LearnCheckpointOut:
    return _checkpoint_out(await _load(db, owner_id, checkpoint_id, now), now)


async def save_checkpoint_item(
    db: AsyncSession,
    owner_id: uuid.UUID,
    checkpoint_id: uuid.UUID,
    position: int,
    data: LearnCheckpointSave,
    now: datetime,
) -> LearnCheckpointOut:
    checkpoint = await _load(db, owner_id, checkpoint_id, now)
    if checkpoint.status != "in_progress":
        raise ProblemError(
            409, "Time is up", "This checkpoint is finished; answers can no longer change."
        )
    item = next((i for i in checkpoint.items if i.position == position), None)
    if item is None:
        raise _not_found("Question")
    if "selected" in data.model_fields_set and data.selected is not None:
        valid = {int(o["position"]) for o in _options_of(item)}
        if len(set(data.selected)) != len(data.selected) or not set(data.selected) <= valid:
            raise ProblemError(
                422, "Invalid answer", "Those options do not belong to this question."
            )
        item.selected = sorted(data.selected)
    if "flagged" in data.model_fields_set and data.flagged is not None:
        item.flagged = data.flagged
    await db.commit()
    await db.refresh(checkpoint)
    return _checkpoint_out(checkpoint, now)


async def submit_checkpoint(
    db: AsyncSession, owner_id: uuid.UUID, checkpoint_id: uuid.UUID, now: datetime
) -> LearnCheckpointOut:
    """Score the exam. Submitting twice returns the same result."""
    checkpoint = await _load(db, owner_id, checkpoint_id, now)
    if checkpoint.status == "in_progress":
        await _finalize(db, checkpoint, now, expired=False)
    return _checkpoint_out(checkpoint, now)


async def list_checkpoints(
    db: AsyncSession, owner_id: uuid.UUID, limit: int
) -> list[LearnCheckpointSummary]:
    rows = await repository.list_checkpoints(db, owner_id, limit)
    return [
        LearnCheckpointSummary(
            id=c.id,
            status=c.status,
            size=c.size,
            started_at=c.started_at,
            score=c.score,
            passed=c.passed,
        )
        for c in rows
    ]
