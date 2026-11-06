"""The learning API: topics, questions, answering with spaced repetition, the review queue.
# covers: REQ-06, REQ-09, REQ-11, REQ-13 (mastery), and owner isolation for every new resource
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from careerpilot.core.errors import ProblemError
from careerpilot.modules.learn import service as learn_service
from careerpilot.modules.learn.schemas import LearnAnswerIn
from careerpilot.modules.learn.service import NEW_PER_DAY

BASE = "/api/v1/learn"


async def topic(api: AsyncClient, title: str = "Transactions", **fields: Any) -> dict[str, Any]:
    response = await api.post(f"{BASE}/topics", json={"title": title, **fields})
    assert response.status_code == 201, response.text
    return response.json()


def mcq(
    topic_id: str, stem: str = "What does a transaction guarantee?", **fields: Any
) -> dict[str, Any]:
    return {
        "topic_id": topic_id,
        "type": "mcq_single",
        "stem": stem,
        "explanation": "Atomicity means all or nothing.",
        "options": [
            {"text": "All or nothing", "is_correct": True, "rationale": "That is atomicity."},
            {"text": "Faster reads", "is_correct": False},
            {"text": "Free storage", "is_correct": False},
        ],
        **fields,
    }


async def question(api: AsyncClient, topic_id: str, **fields: Any) -> dict[str, Any]:
    response = await api.post(f"{BASE}/questions", json=mcq(topic_id, **fields))
    assert response.status_code == 201, response.text
    return response.json()


async def answer(
    api: AsyncClient,
    question_id: str,
    selected: list[int],
    *,
    token: uuid.UUID | None = None,
    **fields: Any,
) -> Any:
    return await api.post(
        f"{BASE}/questions/{question_id}/answer",
        json={"token": str(token or uuid.uuid4()), "selected": selected, **fields},
    )


# --- topics ---------------------------------------------------------------------------------------


async def test_topics_can_be_created_listed_edited_archived_and_deleted(api: AsyncClient) -> None:
    created = await topic(api, "Queues", area="Systems", priority=1)
    assert created["origin"] == "manual"
    assert created["question_count"] == 0
    assert created["mastery"] is None

    listed = (await api.get(f"{BASE}/topics")).json()
    assert [t["title"] for t in listed] == ["Queues"]

    patched = await api.patch(
        f"{BASE}/topics/{created['id']}", json={"status": "learning", "notes": "n"}
    )
    assert patched.json()["status"] == "learning"
    cleared = await api.patch(f"{BASE}/topics/{created['id']}", json={"notes": None})
    assert cleared.json()["notes"] is None

    await api.patch(f"{BASE}/topics/{created['id']}", json={"archived": True})
    assert (await api.get(f"{BASE}/topics")).json() == []
    assert len((await api.get(f"{BASE}/topics", params={"archived": True})).json()) == 1

    assert (await api.delete(f"{BASE}/topics/{created['id']}")).status_code == 204
    assert (await api.delete(f"{BASE}/topics/{created['id']}")).status_code == 404


async def test_duplicate_topic_title_is_a_conflict_ignoring_case(api: AsyncClient) -> None:
    await topic(api, "Indexes")
    again = await api.post(f"{BASE}/topics", json={"title": "indexes"})
    assert again.status_code == 409


async def test_topic_validation(api: AsyncClient) -> None:
    assert (await api.post(f"{BASE}/topics", json={"title": "  "})).status_code == 422
    assert (await api.post(f"{BASE}/topics", json={"title": "x", "priority": 9})).status_code == 422
    assert (await api.post(f"{BASE}/topics", json={"title": "x" * 201})).status_code == 422


# --- questions ------------------------------------------------------------------------------------


async def test_create_and_read_a_question_with_options_and_sources(api: AsyncClient) -> None:
    t = await topic(api)
    body = mcq(
        t["id"],
        sources=[{"url": "https://example.com/a", "quote": "A transaction is atomic."}],
        tags=["SQL", " sql ", "ACID"],
    )
    created = (await api.post(f"{BASE}/questions", json=body)).json()
    assert created["status"] == "verified"
    assert created["origin"] == "manual"
    assert created["tags"] == ["sql", "acid"]
    assert [o["position"] for o in created["options"]] == [0, 1, 2]
    assert created["options"][0]["is_correct"] is True
    assert created["sources"][0]["quote"] == "A transaction is atomic."
    got = (await api.get(f"{BASE}/questions/{created['id']}")).json()
    assert got == created
    assert (await api.get(f"{BASE}/topics")).json()[0]["question_count"] == 1


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        (
            {"options": [{"text": "a", "is_correct": True}, {"text": "b", "is_correct": False}]},
            "between 3 and 5",
        ),
        (
            {"options": [{"text": x, "is_correct": x == "a" or x == "b"} for x in "abc"]},
            "exactly one",
        ),
        ({"stem": "   "}, "cannot be empty"),
        ({"type": "short"}, "Only multiple-choice"),
        ({"type": "practical"}, "practice problem"),
        ({"practice_slug": "two-sum"}, "practice problem"),
        ({"rubric": ["clear"]}, "Only written"),
    ],
)
async def test_invalid_questions_are_rejected_with_a_helpful_message(
    api: AsyncClient, change: dict[str, Any], fragment: str
) -> None:
    t = await topic(api)
    body = mcq(t["id"])
    body.update(change)
    if change.get("type") == "practical":
        body["options"] = []  # so the missing practice problem is the only fault
    response = await api.post(f"{BASE}/questions", json=body)
    assert response.status_code == 422, response.text
    assert fragment in response.json()["detail"]


async def test_written_and_practical_questions_have_no_options(api: AsyncClient) -> None:
    t = await topic(api)
    short = await api.post(
        f"{BASE}/questions",
        json={
            "topic_id": t["id"],
            "type": "short",
            "stem": "Explain a lease.",
            "rubric": ["expiry", "renewal"],
        },
    )
    assert short.status_code == 201
    practical = await api.post(
        f"{BASE}/questions",
        json={
            "topic_id": t["id"],
            "type": "practical",
            "stem": "Two sum",
            "practice_slug": "two-sum",
        },
    )
    assert practical.status_code == 201


async def test_a_question_for_someone_elses_topic_is_not_found(
    api: AsyncClient, other_api: AsyncClient
) -> None:
    theirs = await topic(other_api, "Theirs")
    response = await api.post(f"{BASE}/questions", json=mcq(theirs["id"]))
    assert response.status_code == 404


async def test_list_filters_and_pages(api: AsyncClient) -> None:
    a = await topic(api, "A")
    b = await topic(api, "B")
    for i in range(3):
        await question(api, a["id"], stem=f"Alpha {i}?")
    await question(api, b["id"], stem="Beta?")
    page = (await api.get(f"{BASE}/questions", params={"topic_id": a["id"], "limit": 2})).json()
    assert page["total"] == 3
    assert len(page["items"]) == 2
    rest = (
        await api.get(f"{BASE}/questions", params={"topic_id": a["id"], "limit": 2, "offset": 2})
    ).json()
    assert len(rest["items"]) == 1
    found = (await api.get(f"{BASE}/questions", params={"q": "beta"})).json()
    assert [q["stem"] for q in found["items"]] == ["Beta?"]
    assert (await api.get(f"{BASE}/questions", params={"limit": 101})).status_code == 422


async def test_edit_and_archive_a_question(api: AsyncClient) -> None:
    t = await topic(api)
    q = await question(api, t["id"])
    edited = await api.patch(
        f"{BASE}/questions/{q['id']}", json={"stem": "New wording?", "difficulty": 4}
    )
    assert edited.json()["stem"] == "New wording?"
    await api.patch(f"{BASE}/questions/{q['id']}", json={"status": "archived"})
    assert (await api.get(f"{BASE}/questions")).json()["total"] == 0
    assert (
        await answer(api, q["id"], [0])
    ).status_code == 404  # archived questions cannot be answered


async def test_model_made_questions_cannot_be_verified_without_a_source(
    app: FastAPI, api: AsyncClient
) -> None:
    from careerpilot.modules.learn.enums import QuestionOrigin, QuestionStatus
    from careerpilot.modules.learn.schemas import LearnQuestionCreate

    t = await topic(api)
    async with app.state.sessionmaker() as db:
        owner = (await api.get("/api/v1/auth/me")).json()["user"]["id"]
        with pytest.raises(ProblemError) as info:
            await learn_service.create_question(
                db,
                uuid.UUID(owner),
                LearnQuestionCreate.model_validate(mcq(t["id"])),
                datetime.now(UTC),
                origin=QuestionOrigin.GENERATED,
                status=QuestionStatus.VERIFIED,
            )
        assert "needs a source" in (info.value.detail or "")


# --- answering ------------------------------------------------------------------------------------


async def test_a_right_answer_reveals_the_explanation_and_schedules_the_review(
    api: AsyncClient,
) -> None:
    t = await topic(api)
    q = await question(api, t["id"])
    response = await answer(api, q["id"], [0], confidence=2, seconds=8)
    body = response.json()
    assert response.status_code == 200
    assert body["correct"] is True
    assert body["score"] == 1.0
    assert body["rating"] == "good"
    assert body["graded_by"] == "code"
    assert body["correct_positions"] == [0]
    assert body["explanation"] == "Atomicity means all or nothing."
    assert body["options"][0]["rationale"] == "That is atomicity."
    assert datetime.fromisoformat(body["next_due"]) > datetime.now(UTC)


async def test_a_wrong_answer_is_again_and_comes_back_soon(api: AsyncClient) -> None:
    t = await topic(api)
    q = await question(api, t["id"])
    body = (await answer(api, q["id"], [1], confidence=3)).json()
    assert body["correct"] is False
    assert body["rating"] == "again"
    assert datetime.fromisoformat(body["next_due"]) - datetime.now(UTC) < timedelta(hours=1)


async def test_the_same_token_twice_scores_once(api: AsyncClient) -> None:
    t = await topic(api)
    q = await question(api, t["id"])
    token = uuid.uuid4()
    first = (await answer(api, q["id"], [0], token=token)).json()
    second = await answer(
        api, q["id"], [1], token=token
    )  # a different choice must not change the result
    assert second.status_code == 200
    assert second.json()["already_answered"] is True
    assert second.json()["correct"] is first["correct"]
    assert second.json()["next_due"] == first["next_due"]
    stats = (await api.get(f"{BASE}/stats")).json()
    assert stats["answered_today"] == 1


async def test_two_requests_with_one_token_at_once_score_once(
    app: FastAPI, api: AsyncClient
) -> None:
    t = await topic(api)
    q = await question(api, t["id"])
    token = uuid.uuid4()
    results = await asyncio.gather(*[answer(api, q["id"], [0], token=token) for _ in range(5)])
    assert {r.status_code for r in results} == {200}
    assert sorted(r.json()["already_answered"] for r in results).count(False) == 1
    assert (await api.get(f"{BASE}/stats")).json()["answered_today"] == 1


async def test_a_token_cannot_be_reused_for_another_question(api: AsyncClient) -> None:
    t = await topic(api)
    q1 = await question(api, t["id"], stem="One?")
    q2 = await question(api, t["id"], stem="Two?")
    token = uuid.uuid4()
    assert (await answer(api, q1["id"], [0], token=token)).status_code == 200
    assert (await answer(api, q2["id"], [0], token=token)).status_code == 409


@pytest.mark.parametrize(
    "selected",
    [[], [7], [0, 0], [-1]],
)
async def test_bad_selections_are_rejected(api: AsyncClient, selected: list[int]) -> None:
    t = await topic(api)
    q = await question(api, t["id"])
    response = await answer(api, q["id"], selected)
    assert response.status_code == 422


async def test_multiple_answer_questions_give_partial_credit(api: AsyncClient) -> None:
    t = await topic(api)
    body = mcq(t["id"], type="mcq_multi")
    body["options"] = [
        {"text": "A", "is_correct": True},
        {"text": "B", "is_correct": True},
        {"text": "C", "is_correct": False},
        {"text": "D", "is_correct": False},
    ]
    q = (await api.post(f"{BASE}/questions", json=body)).json()
    half = (await answer(api, q["id"], [0])).json()
    assert half["score"] == 0.5
    assert half["correct"] is False
    full = (await answer(api, q["id"], [0, 1])).json()
    assert full["correct"] is True


async def test_written_questions_are_rated_by_the_learner(api: AsyncClient) -> None:
    t = await topic(api)
    q = (
        await api.post(
            f"{BASE}/questions",
            json={"topic_id": t["id"], "type": "explain", "stem": "Explain idempotency."},
        )
    ).json()
    no_rating = await api.post(
        f"{BASE}/questions/{q['id']}/answer",
        json={"token": str(uuid.uuid4()), "text": "It is safe to repeat."},
    )
    assert no_rating.status_code == 422
    rated = await api.post(
        f"{BASE}/questions/{q['id']}/answer",
        json={
            "token": str(uuid.uuid4()),
            "text": "It is safe to repeat.",
            "self_score": 0.9,
            "confidence": 2,
        },
    )
    assert rated.status_code == 200
    assert rated.json()["graded_by"] == "self"
    assert rated.json()["rating"] == "good"


async def test_answer_input_limits(api: AsyncClient) -> None:
    t = await topic(api)
    q = await question(api, t["id"])
    bad_inputs: list[dict[str, Any]] = [
        {"confidence": 4},
        {"confidence": 0},
        {"seconds": -1},
        {"seconds": 99999},
        {"self_score": 2},
    ]
    for bad in bad_inputs:
        response = await answer(api, q["id"], [0], **bad)
        assert response.status_code == 422, bad


# --- review queue and stats -----------------------------------------------------------------------


async def test_new_questions_appear_in_the_queue_without_answers_and_leave_it_once_answered(
    api: AsyncClient,
) -> None:
    t = await topic(api)
    q = await question(api, t["id"])
    queue = (await api.get(f"{BASE}/review")).json()
    assert queue["due"] == 0
    assert queue["new_available"] == 1
    item = queue["items"][0]
    assert item["id"] == q["id"]
    assert item["is_new"] is True
    assert item["topic_title"] == "Transactions"
    # The learner must not see which option is right before answering.
    assert all(set(o) == {"position", "text"} for o in item["options"])
    assert "explanation" not in item

    await answer(api, q["id"], [0])
    after = (await api.get(f"{BASE}/review")).json()
    assert after["items"] == []  # answered, and not due again yet


async def test_due_reviews_come_before_new_questions_and_topics_are_mixed(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID
) -> None:
    a = await topic(api, "A")
    b = await topic(api, "B")
    answered: list[str] = []
    for i in range(2):
        for t in (a, b):
            q = await question(api, t["id"], stem=f"Old {t['title']}{i}?")
            await answer(api, q["id"], [0], confidence=2)
            answered.append(q["id"])
    fresh = await question(api, a["id"], stem="Brand new?")

    # Pretend two days have passed: every answered card is now due.
    later = datetime.now(UTC) + timedelta(days=60)
    async with app.state.sessionmaker() as db:
        queue = await learn_service.review_queue(db, owner_id, later, "Asia/Kolkata", limit=10)
    ids = [item.id for item in queue.items]
    assert queue.due == 4
    assert str(ids[-1]) == fresh["id"]  # new ones last
    due_topics = [item.topic_title for item in queue.items[:4]]
    assert due_topics[:2] in (["A", "B"], ["B", "A"])  # interleaved, not A A B B


async def test_daily_new_question_allowance(
    app: FastAPI, api: AsyncClient, owner_id: uuid.UUID
) -> None:
    t = await topic(api)
    for i in range(NEW_PER_DAY + 3):
        await question(api, t["id"], stem=f"Q{i}?")
    queue = (await api.get(f"{BASE}/review", params={"limit": 50})).json()
    assert queue["new_available"] == NEW_PER_DAY
    assert len(queue["items"]) == NEW_PER_DAY
    first = queue["items"][0]
    await answer(api, first["id"], [0])
    assert (await api.get(f"{BASE}/stats")).json()["new_today_left"] == NEW_PER_DAY - 1


async def test_stats_and_topic_mastery(api: AsyncClient) -> None:
    t = await topic(api)
    q = await question(api, t["id"])
    await answer(api, q["id"], [0])
    stats = (await api.get(f"{BASE}/stats")).json()
    assert stats["topics"] == 1
    assert stats["questions"] == 1
    assert stats["answered_today"] == 1
    assert stats["streak_days"] == 1
    mastery = (await api.get(f"{BASE}/topics")).json()[0]["mastery"]
    assert mastery is not None
    assert 90 <= mastery <= 100  # just answered, so very likely remembered


async def test_deleting_a_topic_removes_its_questions_cards_and_attempts(api: AsyncClient) -> None:
    t = await topic(api)
    q = await question(api, t["id"])
    await answer(api, q["id"], [0])
    assert (await api.delete(f"{BASE}/topics/{t['id']}")).status_code == 204
    assert (await api.get(f"{BASE}/questions/{q['id']}")).status_code == 404
    assert (await api.get(f"{BASE}/stats")).json()["answered_today"] == 0


# --- owner isolation (every resource) -------------------------------------------------------------


async def test_everything_belongs_to_its_owner(api: AsyncClient, other_api: AsyncClient) -> None:
    t = await topic(api, "Mine")
    q = await question(api, t["id"])
    await answer(api, q["id"], [0])

    assert (await other_api.get(f"{BASE}/topics")).json() == []
    assert (await other_api.get(f"{BASE}/questions")).json() == {"items": [], "total": 0}
    assert (await other_api.get(f"{BASE}/questions/{q['id']}")).status_code == 404
    assert (
        await other_api.patch(f"{BASE}/questions/{q['id']}", json={"stem": "x"})
    ).status_code == 404
    assert (
        await other_api.patch(f"{BASE}/topics/{t['id']}", json={"title": "x"})
    ).status_code == 404
    assert (await other_api.delete(f"{BASE}/questions/{q['id']}")).status_code == 404
    assert (await other_api.delete(f"{BASE}/topics/{t['id']}")).status_code == 404
    assert (await answer(other_api, q["id"], [0])).status_code == 404
    queue = (await other_api.get(f"{BASE}/review")).json()
    assert (queue["due"], queue["new_available"], queue["items"]) == (0, 0, [])
    stats = (await other_api.get(f"{BASE}/stats")).json()
    assert (stats["topics"], stats["questions"], stats["answered_today"]) == (0, 0, 0)
    # The owner's data is untouched.
    assert (await api.get(f"{BASE}/questions/{q['id']}")).status_code == 200


async def test_the_same_token_in_two_accounts_does_not_collide(
    api: AsyncClient, other_api: AsyncClient
) -> None:
    mine = await question(api, (await topic(api))["id"])
    theirs = await question(other_api, (await topic(other_api, "Theirs"))["id"])
    token = uuid.uuid4()
    assert (await answer(api, mine["id"], [0], token=token)).status_code == 200
    second = await answer(other_api, theirs["id"], [0], token=token)
    assert second.status_code == 200
    assert second.json()["already_answered"] is False


async def test_signed_out_requests_are_refused(client: AsyncClient) -> None:
    assert (await client.get(f"{BASE}/topics")).status_code == 401
    assert (await client.get(f"{BASE}/review")).status_code == 401
    assert (await client.post(f"{BASE}/questions/{uuid.uuid4()}/answer", json={})).status_code in (
        401,
        403,
    )


def test_streak_rules() -> None:
    from datetime import date

    today = date(2026, 11, 6)
    assert learn_service.streak(set(), today) == 0
    assert learn_service.streak({today}, today) == 1
    assert (
        learn_service.streak({today, today - timedelta(days=1), today - timedelta(days=2)}, today)
        == 3
    )
    # Studied yesterday but not yet today: the streak is still alive.
    assert learn_service.streak({today - timedelta(days=1), today - timedelta(days=2)}, today) == 2
    # A gap breaks it.
    assert learn_service.streak({today, today - timedelta(days=2)}, today) == 1
    assert learn_service.streak({today - timedelta(days=2)}, today) == 0


def test_answer_in_requires_a_token() -> None:
    with pytest.raises(ValueError):
        LearnAnswerIn.model_validate({"selected": [0]})
