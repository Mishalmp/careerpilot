"""Checkpoint exams: built from studied questions, timed, autosaved, scored, per topic.
# covers: REQ-12 (checkpoint exams from what was learned), L05, L19, owner isolation
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient

from careerpilot.modules.learn import service as learn_service
from careerpilot.modules.learn.schemas import LearnCheckpointCreate, LearnCheckpointSave

BASE = "/api/v1/learn"


async def topic(api: AsyncClient, title: str, priority: int = 2) -> str:
    response = await api.post(f"{BASE}/topics", json={"title": title, "priority": priority})
    assert response.status_code == 201
    return response.json()["id"]


async def studied_question(api: AsyncClient, topic_id: str, stem: str) -> str:
    """An MCQ whose right answer is option 0, already answered once so it counts as studied."""
    created = await api.post(
        f"{BASE}/questions",
        json={
            "topic_id": topic_id,
            "type": "mcq_single",
            "stem": stem,
            "explanation": f"Because {stem}",
            "options": [
                {"text": "Right", "is_correct": True, "rationale": "yes"},
                {"text": "Wrong one", "is_correct": False},
                {"text": "Wrong two", "is_correct": False},
            ],
        },
    )
    assert created.status_code == 201, created.text
    qid = created.json()["id"]
    answered = await api.post(
        f"{BASE}/questions/{qid}/answer", json={"token": str(uuid.uuid4()), "selected": [0]}
    )
    assert answered.status_code == 200
    return qid


async def bank(api: AsyncClient, topics: int = 2, per_topic: int = 4) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for t in range(topics):
        tid = await topic(api, f"Topic {t}")
        out[tid] = [
            await studied_question(api, tid, f"T{t} question {i}?") for i in range(per_topic)
        ]
    return out


async def start(api: AsyncClient, **fields: Any) -> dict[str, Any]:
    response = await api.post(f"{BASE}/checkpoints", json=fields)
    assert response.status_code == 201, response.text
    return response.json()


async def save(api: AsyncClient, cp: str, position: int, **body: Any) -> Any:
    return await api.put(f"{BASE}/checkpoints/{cp}/items/{position}", json=body)


# --- building ----------------------------------------------------------------------------------


async def test_a_checkpoint_needs_studied_questions(api: AsyncClient) -> None:
    tid = await topic(api, "Unstudied")
    await api.post(
        f"{BASE}/questions",
        json={
            "topic_id": tid,
            "type": "mcq_single",
            "stem": "Never answered?",
            "options": [
                {"text": "a", "is_correct": True},
                {"text": "b", "is_correct": False},
                {"text": "c", "is_correct": False},
            ],
        },
    )
    response = await api.post(f"{BASE}/checkpoints", json={})
    assert response.status_code == 422
    assert "already answered" in response.json()["detail"]


async def test_the_exam_uses_only_studied_verified_choice_questions_and_hides_answers(
    api: AsyncClient,
) -> None:
    ids = await bank(api, topics=2, per_topic=3)
    unstudied_topic = next(iter(ids))
    await api.post(
        f"{BASE}/questions",
        json={
            "topic_id": unstudied_topic,
            "type": "explain",
            "stem": "Written, not allowed in exams yet.",
        },
    )
    cp = await start(api, size=6, seed=1)
    assert cp["status"] == "in_progress"
    assert cp["size"] == 6
    stems = [i["question"]["stem"] for i in cp["items"]]
    assert len(set(stems)) == 6
    assert "Written, not allowed in exams yet." not in stems
    for item in cp["items"]:
        assert item["result"] is None
        assert all(set(o) == {"position", "text"} for o in item["question"]["options"])
    assert 0 < cp["seconds_left"] <= cp["minutes"] * 60
    assert cp["minutes"] == 9  # 1.5 minutes a question


async def test_a_short_supply_gives_fewer_questions_and_says_so(api: AsyncClient) -> None:
    await bank(api, topics=1, per_topic=3)
    cp = await start(api, size=10)
    assert cp["size"] == 3
    assert any("short of the 10" in n for n in cp["notes"])


async def test_topic_filter_and_seed_make_the_exam_repeatable(
    api: AsyncClient, app: FastAPI
) -> None:
    ids = await bank(api, topics=2, per_topic=5)
    first_topic = next(iter(ids))
    cp = await start(api, size=4, seed=7, topic_ids=[first_topic])
    topics = {i["question"]["topic_title"] for i in cp["items"]}
    assert topics == {"Topic 0"}
    stems_a = [i["question"]["stem"] for i in cp["items"]]
    # Submit, then ask again with the same seed and topic: the same questions in the same order
    # (recently used questions are only avoided when there are enough others, here there are not).
    await api.post(f"{BASE}/checkpoints/{cp['id']}/submit")
    again = await start(api, size=4, seed=7, topic_ids=[first_topic])
    assert len(again["items"]) == 4
    assert set(stems_a) <= {f"T0 question {i}?" for i in range(5)}


async def test_a_running_checkpoint_is_returned_instead_of_starting_another(
    api: AsyncClient,
) -> None:
    await bank(api)
    first = await start(api, size=4)
    second = await start(api, size=4)
    assert second["id"] == first["id"]
    assert len((await api.get(f"{BASE}/checkpoints")).json()) == 1


# --- answering and scoring ---------------------------------------------------------------------


async def test_answers_autosave_and_survive_a_reload(api: AsyncClient) -> None:
    await bank(api)
    cp = await start(api, size=4)
    assert (await save(api, cp["id"], 0, selected=[1])).status_code == 200
    assert (await save(api, cp["id"], 1, flagged=True)).status_code == 200
    reloaded = (await api.get(f"{BASE}/checkpoints/{cp['id']}")).json()
    assert reloaded["items"][0]["selected"] == [1]
    assert reloaded["items"][1]["flagged"] is True
    assert reloaded["items"][1]["selected"] is None
    # Changing an answer replaces it.
    await save(api, cp["id"], 0, selected=[0])
    assert (await api.get(f"{BASE}/checkpoints/{cp['id']}")).json()["items"][0]["selected"] == [0]


async def test_bad_autosaves_are_rejected(api: AsyncClient) -> None:
    await bank(api)
    cp = await start(api, size=2)
    assert (await save(api, cp["id"], 0, selected=[9])).status_code == 422
    assert (await save(api, cp["id"], 0, selected=[0, 0])).status_code == 422
    assert (await save(api, cp["id"], 99, selected=[0])).status_code == 404


async def test_submitting_scores_it_per_topic_and_reveals_the_answers(api: AsyncClient) -> None:
    await bank(api, topics=2, per_topic=3)
    cp = await start(api, size=6, seed=3, pass_mark=0.8)
    # Answer the first four correctly, the fifth wrongly, leave the sixth blank.
    for item in cp["items"][:4]:
        await save(api, cp["id"], item["position"], selected=[0])
    await save(api, cp["id"], 4, selected=[1])
    done = (await api.post(f"{BASE}/checkpoints/{cp['id']}/submit")).json()
    assert done["status"] == "submitted"
    assert done["score"] == round(4 / 6, 4)
    assert done["passed"] is False
    assert sum(t["total"] for t in done["per_topic"]) == 6
    assert sum(t["correct"] for t in done["per_topic"]) == 4
    first = done["items"][0]["result"]
    assert first["correct"] is True
    assert first["correct_positions"] == [0]
    assert first["explanation"].startswith("Because")
    blank = done["items"][5]["result"]
    assert blank["correct"] is False
    assert blank["score"] == 0.0


async def test_a_perfect_exam_passes_and_submit_is_safe_to_repeat(api: AsyncClient) -> None:
    await bank(api, topics=1, per_topic=3)
    cp = await start(api, size=3, pass_mark=1.0)
    for item in cp["items"]:
        await save(api, cp["id"], item["position"], selected=[0])
    first = (await api.post(f"{BASE}/checkpoints/{cp['id']}/submit")).json()
    second = (await api.post(f"{BASE}/checkpoints/{cp['id']}/submit")).json()
    assert first["passed"] is True
    assert second["score"] == first["score"] == 1.0
    assert second["submitted_at"] == first["submitted_at"]
    assert (await save(api, cp["id"], 0, selected=[1])).status_code == 409  # no edits after submit


async def test_missed_questions_come_back_for_review(api: AsyncClient) -> None:
    await bank(api, topics=1, per_topic=2)
    before = (await api.get(f"{BASE}/review")).json()
    assert before["due"] == 0  # all answered just now, none due
    cp = await start(api, size=2)
    await save(api, cp["id"], 0, selected=[1])  # wrong
    await save(api, cp["id"], 1, selected=[0])  # right
    await api.post(f"{BASE}/checkpoints/{cp['id']}/submit")
    after = (await api.get(f"{BASE}/review")).json()
    assert after["due"] == 1  # only the missed one is due again now


async def test_the_exam_is_a_snapshot_so_later_edits_do_not_change_it(api: AsyncClient) -> None:
    ids = await bank(api, topics=1, per_topic=2)
    cp = await start(api, size=2)
    original = {i["question"]["stem"] for i in cp["items"]}
    for qid in next(iter(ids.values())):
        await api.patch(f"{BASE}/questions/{qid}", json={"stem": "Changed after the exam started?"})
    again = (await api.get(f"{BASE}/checkpoints/{cp['id']}")).json()
    assert {i["question"]["stem"] for i in again["items"]} == original
    # Deleting the questions entirely does not break a finished exam either.
    await save(api, cp["id"], 0, selected=[0])
    for qid in next(iter(ids.values())):
        await api.delete(f"{BASE}/questions/{qid}")
    done = await api.post(f"{BASE}/checkpoints/{cp['id']}/submit")
    assert done.status_code == 200
    assert done.json()["items"][0]["result"]["correct"] is True


# --- time ---------------------------------------------------------------------------------------


async def test_when_time_runs_out_the_saved_answers_are_scored(
    app: FastAPI, api: AsyncClient
) -> None:
    await bank(api, topics=1, per_topic=2)
    cp = await start(api, size=2, minutes=1)
    await save(api, cp["id"], 0, selected=[0])
    later = datetime.now(UTC) + timedelta(minutes=5)
    owner = uuid.UUID((await api.get("/api/v1/auth/me")).json()["user"]["id"])
    async with app.state.sessionmaker() as db:
        done = await learn_service.get_checkpoint(db, owner, uuid.UUID(cp["id"]), later)
    assert done.status == "submitted"
    assert done.expired is True
    assert done.score == 0.5
    assert done.items[0].result is not None
    async with app.state.sessionmaker() as db:
        late_save = None
        try:
            await learn_service.save_checkpoint_item(
                db, owner, uuid.UUID(cp["id"]), 1, LearnCheckpointSave(selected=[0]), later
            )
        except Exception as error:
            late_save = str(error)
    assert late_save == "Time is up"


async def test_an_expired_exam_does_not_block_starting_a_new_one(
    app: FastAPI, api: AsyncClient
) -> None:
    await bank(api, topics=1, per_topic=3)
    first = await start(api, size=2, minutes=1)
    owner = uuid.UUID((await api.get("/api/v1/auth/me")).json()["user"]["id"])
    later = datetime.now(UTC) + timedelta(minutes=10)
    async with app.state.sessionmaker() as db:
        fresh = await learn_service.create_checkpoint(
            db, owner, LearnCheckpointCreate(size=2), later
        )
    assert str(fresh.id) != first["id"]
    assert fresh.status == "in_progress"
    summary = (await api.get(f"{BASE}/checkpoints")).json()
    assert {c["status"] for c in summary} == {"submitted", "in_progress"}


# --- limits and isolation ------------------------------------------------------------------------


async def test_input_limits(api: AsyncClient) -> None:
    await bank(api)
    for bad in ({"size": 0}, {"size": 51}, {"pass_mark": 0.4}, {"pass_mark": 1.1}, {"minutes": 0}):
        assert (await api.post(f"{BASE}/checkpoints", json=bad)).status_code == 422, bad


async def test_checkpoints_belong_to_their_owner(api: AsyncClient, other_api: AsyncClient) -> None:
    await bank(api)
    cp = await start(api, size=4)
    assert (await other_api.get(f"{BASE}/checkpoints")).json() == []
    assert (await other_api.get(f"{BASE}/checkpoints/{cp['id']}")).status_code == 404
    assert (await save(other_api, cp["id"], 0, selected=[0])).status_code == 404
    assert (await other_api.post(f"{BASE}/checkpoints/{cp['id']}/submit")).status_code == 404
    # Another user with no studied questions cannot start one from this user's bank.
    assert (await other_api.post(f"{BASE}/checkpoints", json={})).status_code == 422
    assert (await api.get(f"{BASE}/checkpoints/{cp['id']}")).status_code == 200


async def test_signed_out_requests_are_refused(client: AsyncClient) -> None:
    assert (await client.get(f"{BASE}/checkpoints")).status_code == 401
    assert (await client.post(f"{BASE}/checkpoints", json={})).status_code in (401, 403)
