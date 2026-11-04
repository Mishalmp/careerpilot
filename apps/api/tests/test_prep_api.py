from datetime import date, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from careerpilot.core.clock import today_in
from careerpilot.core.config import Settings
from careerpilot.modules.prep import guides
from careerpilot.modules.prep.curriculum import load_curriculum
from careerpilot.modules.prep.spaced import INTERVAL_DAYS, next_review

PREP = "/api/v1/prep"


def today() -> date:
    return today_in(Settings().timezone)  # pyright: ignore[reportCallIssue]


async def seeded(api: AsyncClient) -> list[dict[str, Any]]:
    assert (await api.post(f"{PREP}/seed")).status_code == 200
    return (await api.get(f"{PREP}/topics")).json()


def test_shipped_curriculum_is_valid(settings: Settings) -> None:
    curriculum = load_curriculum(settings.content_dir)
    assert sum(len(a.topics) for a in curriculum.areas) == 159
    assert len(curriculum.days) == 45


async def test_seed_loads_the_curriculum_and_is_safe_to_repeat(
    api: AsyncClient, settings: Settings
) -> None:
    curriculum = load_curriculum(settings.content_dir)
    topic_count = sum(len(a.topics) for a in curriculum.areas)

    first = (await api.post(f"{PREP}/seed")).json()
    assert first == {
        "topics_added": topic_count,
        "topics_updated": 0,
        "days_added": 45,
        "days_updated": 0,
    }
    second = (await api.post(f"{PREP}/seed")).json()
    assert second == {"topics_added": 0, "topics_updated": 0, "days_added": 0, "days_updated": 0}
    assert len((await api.get(f"{PREP}/topics")).json()) == topic_count
    assert len((await api.get(f"{PREP}/days")).json()) == 45


async def test_reseeding_keeps_your_progress(api: AsyncClient) -> None:
    topic = (await seeded(api))[0]
    await api.patch(f"{PREP}/topics/{topic['id']}", json={"confidence": 4, "notes": "mine"})
    await api.post(f"{PREP}/seed")
    again = next(t for t in (await api.get(f"{PREP}/topics")).json() if t["id"] == topic["id"])
    assert again["confidence"] == 4
    assert again["notes"] == "mine"


async def test_topic_filters(api: AsyncClient) -> None:
    topics = await seeded(api)
    area = topics[0]["area"]
    in_area = (await api.get(f"{PREP}/topics", params={"area": area})).json()
    assert in_area and {t["area"] for t in in_area} == {area}
    assert (await api.get(f"{PREP}/topics", params={"status": "Revised"})).json() == []


@pytest.mark.parametrize(("confidence", "days"), list(INTERVAL_DAYS.items()))
def test_review_interval_grows_with_confidence(confidence: int, days: int) -> None:
    assert next_review(confidence, date(2026, 1, 1)) == date(2026, 1, 1) + timedelta(days=days)


async def test_rating_a_topic_schedules_the_next_review(api: AsyncClient) -> None:
    topic = (await seeded(api))[0]
    rated = (await api.patch(f"{PREP}/topics/{topic['id']}", json={"confidence": 2})).json()
    assert rated["last_reviewed_on"] == today().isoformat()
    assert rated["next_review_on"] == (today() + timedelta(days=3)).isoformat()

    cleared = (await api.patch(f"{PREP}/topics/{topic['id']}", json={"confidence": None})).json()
    assert cleared["next_review_on"] is None
    assert (
        await api.patch(f"{PREP}/topics/{topic['id']}", json={"confidence": 6})
    ).status_code == 422
    assert (
        await api.patch(f"{PREP}/topics/{topic['id']}", json={"status": None})
    ).status_code == 422


async def test_logging_a_session_starts_learning_and_moves_review_date(api: AsyncClient) -> None:
    topic = (await seeded(api))[0]
    url = f"{PREP}/topics/{topic['id']}/sessions"
    response = await api.post(url, json={"minutes": 45, "kind": "learn", "notes": "chapter 1"})
    assert response.status_code == 201
    updated = next(t for t in (await api.get(f"{PREP}/topics")).json() if t["id"] == topic["id"])
    assert updated["status"] == "Learning"
    assert updated["last_reviewed_on"] == today().isoformat()
    assert updated["next_review_on"] is None  # unrated topics have no schedule yet

    await api.patch(f"{PREP}/topics/{topic['id']}", json={"confidence": 5})
    await api.post(url, json={"minutes": 10, "kind": "review"})
    refreshed = next(t for t in (await api.get(f"{PREP}/topics")).json() if t["id"] == topic["id"])
    assert refreshed["next_review_on"] == (today() + timedelta(days=30)).isoformat()


@pytest.mark.parametrize("minutes", [0, -5, 721])
async def test_session_minutes_are_bounded(api: AsyncClient, minutes: int) -> None:
    topic = (await seeded(api))[0]
    response = await api.post(
        f"{PREP}/topics/{topic['id']}/sessions", json={"minutes": minutes, "kind": "learn"}
    )
    assert response.status_code == 422


async def test_future_sessions_are_refused(api: AsyncClient) -> None:
    topic = (await seeded(api))[0]
    tomorrow = (today() + timedelta(days=1)).isoformat()
    response = await api.post(
        f"{PREP}/topics/{topic['id']}/sessions",
        json={"minutes": 30, "kind": "learn", "studied_on": tomorrow},
    )
    assert response.status_code == 422


async def test_today_before_configuring_and_across_the_plan(api: AsyncClient) -> None:
    await seeded(api)
    assert (await api.get(f"{PREP}/today")).json()["phase"] == "not_configured"

    async def phase_for(start: date) -> dict[str, Any]:
        await api.put(f"{PREP}/plan", json={"start_date": start.isoformat()})
        return (await api.get(f"{PREP}/today")).json()

    upcoming = await phase_for(today() + timedelta(days=3))
    assert upcoming["phase"] == "upcoming" and upcoming["day"] is None

    first = await phase_for(today())
    assert first["phase"] == "active" and first["day_number"] == 1
    assert first["day"]["scheduled_on"] == today().isoformat()

    third = await phase_for(today() - timedelta(days=2))
    assert third["day_number"] == 3 and third["day"]["day"] == 3

    last = await phase_for(today() - timedelta(days=44))
    assert last["day_number"] == 45
    finished = await phase_for(today() - timedelta(days=45))
    assert finished["phase"] == "finished" and finished["day"] is None


async def test_days_get_dates_from_the_start_date_and_can_be_marked(api: AsyncClient) -> None:
    await seeded(api)
    start = date(2026, 11, 4)
    await api.put(f"{PREP}/plan", json={"start_date": start.isoformat()})
    days = (await api.get(f"{PREP}/days")).json()
    assert days[0]["scheduled_on"] == "2026-11-04"
    assert days[44]["scheduled_on"] == "2026-12-18"

    done = await api.patch(f"{PREP}/days/1", json={"status": "Done", "notes": "good"})
    assert done.json()["status"] == "Done"
    assert (await api.patch(f"{PREP}/days/99", json={"status": "Done"})).status_code == 404


async def test_due_reviews_appear_on_today(api: AsyncClient) -> None:
    topic = (await seeded(api))[0]
    await api.patch(f"{PREP}/topics/{topic['id']}", json={"confidence": 1})  # due tomorrow
    assert (await api.get(f"{PREP}/today")).json()["due_reviews"] == []
    assert (await api.get(f"{PREP}/topics", params={"due": True})).json() == []


async def test_guides_list_and_read(api: AsyncClient) -> None:
    listing = (await api.get(f"{PREP}/guides")).json()
    names = [g["name"] for g in listing]
    assert "01-python" in names and "08-system-design" in names
    guide = (await api.get(f"{PREP}/guides/01-python")).json()
    assert guide["markdown"].startswith("#")
    assert guide["title"]


@pytest.mark.parametrize("name", ["..%2Fplan", "nope", "01-python.md", "UPPER"])
async def test_unknown_or_malformed_guide_names_are_404(api: AsyncClient, name: str) -> None:
    assert (await api.get(f"{PREP}/guides/{name}")).status_code == 404


@pytest.mark.parametrize(
    "name", ["../plan", "..\\plan", "/etc/passwd", "a/b", "", ".hidden", "plan.md"]
)
def test_guide_names_cannot_escape_the_folder(name: str, settings: Settings) -> None:
    # The HTTP client collapses "../" before sending, so check the reader directly too.
    assert guides.read_guide(settings.content_dir, name) is None


def test_private_guides_are_listed_but_flagged(tmp_path: Any) -> None:
    (tmp_path / "guides").mkdir()
    (tmp_path / "private").mkdir()
    (tmp_path / "guides" / "a-public.md").write_text("# Public\nbody", encoding="utf-8")
    (tmp_path / "private" / "b-secret.md").write_text("# Secret\nbody", encoding="utf-8")
    listing = {g.name: g.private for g in guides.list_guides(tmp_path)}
    assert listing == {"a-public": False, "b-secret": True}
    secret = guides.read_guide(tmp_path, "b-secret")
    assert secret is not None and secret.info.title == "Secret"


async def test_prep_data_is_private_to_each_owner(
    api: AsyncClient, other_api: AsyncClient, app: FastAPI
) -> None:
    topic = (await seeded(api))[0]
    assert (await other_api.get(f"{PREP}/topics")).json() == []
    assert (
        await other_api.patch(f"{PREP}/topics/{topic['id']}", json={"confidence": 3})
    ).status_code == 404
    assert (
        await other_api.post(
            f"{PREP}/topics/{topic['id']}/sessions", json={"minutes": 5, "kind": "learn"}
        )
    ).status_code == 404
