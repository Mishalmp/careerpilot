"""Funnel, weekly pace, prep progress and the calibration of the fit score."""

import uuid
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from careerpilot.core.clock import today_in
from careerpilot.modules.analytics.rules import (
    MIN_OUTCOMES,
    calibration,
    funnel,
    weekly_applications,
)
from careerpilot.modules.tracker.enums import Status
from careerpilot.modules.tracker.progress import Progress, progress_of
from tests.test_tracker_api import add_job, move

ANALYTICS = "/api/v1/analytics"
S = Status


CHANGED_ON = date(2026, 11, 3)


def p(status: Status, history: list[Status], applied_on: date | None = None) -> Progress:
    """`history` lists the statuses; each is given the same day of change."""
    return progress_of(uuid.uuid4(), status, applied_on, [(s, CHANGED_ON) for s in history])


# --- how far an application got ------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "history", "flags"),
    [
        (S.NEW, [S.NEW], dict(applied=False, interviewed=False, offered=False)),
        (
            S.SHORTLISTED,
            [S.NEW, S.SHORTLISTED],
            dict(applied=False, interviewed=False, offered=False),
        ),
        (S.APPLIED_PENDING, [S.NEW, S.APPLIED_PENDING], dict(applied=True, responded=False)),
        (
            S.NO_RESPONSE,
            [S.APPLIED_PENDING, S.NO_RESPONSE],
            dict(applied=True, no_response=True, responded=False),
        ),
        (
            S.TECHNICAL_ROUND,
            [S.APPLIED_PENDING, S.TECHNICAL_ROUND],
            dict(applied=True, interviewed=True, responded=True),
        ),
        (
            S.REJECTED,
            [S.APPLIED_PENDING, S.REJECTED],
            dict(applied=True, rejected=True, responded=True, interviewed=False),
        ),
        (S.REJECTED, [S.TECHNICAL_ROUND, S.REJECTED], dict(rejected=True, interviewed=True)),
        (S.OFFER_RECEIVED, [S.HR_ROUND, S.OFFER_RECEIVED], dict(offered=True, interviewed=True)),
        (
            S.OFFER_ACCEPTED,
            [S.OFFER_RECEIVED, S.OFFER_ACCEPTED],
            dict(offered=True, interviewed=True, applied=True),
        ),
        (S.WITHDRAWN, [S.NEW, S.WITHDRAWN], dict(applied=False)),
        (S.JOB_CLOSED, [S.APPLIED_PENDING, S.JOB_CLOSED], dict(applied=True, responded=False)),
    ],
)
def test_progress_is_read_from_the_status_history(
    status: Status, history: list[Status], flags: dict[str, bool]
) -> None:
    result = p(status, history)
    for name, expected in flags.items():
        assert getattr(result, name) is expected, name


def test_a_recorded_application_date_counts_as_applied_even_without_history() -> None:
    assert p(S.NEW, [], applied_on=date(2026, 11, 1)).applied
    assert not p(S.NEW, []).applied


def test_the_day_you_applied_comes_from_the_history_when_none_was_recorded() -> None:
    history = [
        (S.NEW, date(2026, 10, 1)),
        (S.APPLIED_PENDING, date(2026, 10, 20)),
        (S.REJECTED, date(2026, 10, 30)),
    ]
    assert progress_of(uuid.uuid4(), S.REJECTED, None, history).applied_on == date(2026, 10, 20)
    recorded = progress_of(uuid.uuid4(), S.REJECTED, date(2026, 10, 18), history)
    assert recorded.applied_on == date(2026, 10, 18)  # a date you recorded wins
    assert progress_of(uuid.uuid4(), S.NEW, None, [(S.NEW, date(2026, 10, 1))]).applied_on is None


def test_a_reopened_application_keeps_what_already_happened() -> None:
    result = p(S.APPLIED_PENDING, [S.APPLIED_PENDING, S.REJECTED, S.APPLIED_PENDING])
    assert result.rejected and result.responded  # the rejection happened


# --- funnel and pace -----------------------------------------------------------------------


def test_rates_are_shares_of_applications_and_absent_when_there_are_none() -> None:
    empty = funnel([])
    assert (empty.applied, empty.response_rate, empty.interview_rate, empty.offer_rate) == (
        0,
        None,
        None,
        None,
    )
    rows = [
        p(S.NEW, [S.NEW]),
        p(S.TECHNICAL_ROUND, [S.APPLIED_PENDING, S.TECHNICAL_ROUND]),
        p(S.REJECTED, [S.APPLIED_PENDING, S.REJECTED]),
        p(S.NO_RESPONSE, [S.APPLIED_PENDING, S.NO_RESPONSE]),
    ]
    result = funnel(rows)
    assert (result.tracked, result.applied, result.responded, result.interviewed) == (4, 3, 2, 1)
    assert (result.response_rate, result.interview_rate, result.offer_rate) == (66.7, 33.3, 0.0)
    assert result.small_sample  # fewer than 10 applications


def test_weekly_pace_covers_every_week_including_empty_ones() -> None:
    today = date(2026, 11, 6)  # a Friday; that week starts Monday 2 November
    rows = [
        p(S.APPLIED_PENDING, [], date(2026, 11, 2)),
        p(S.APPLIED_PENDING, [], date(2026, 11, 6)),
        p(S.APPLIED_PENDING, [], date(2026, 10, 20)),
        p(S.APPLIED_PENDING, [], date(2025, 1, 1)),  # outside the window
        p(S.NEW, []),
    ]
    weeks = weekly_applications(rows, today, weeks=4)
    assert [w[0] for w in weeks] == [
        date(2026, 10, 12),
        date(2026, 10, 19),
        date(2026, 10, 26),
        date(2026, 11, 2),
    ]
    assert [w[1] for w in weeks] == [0, 1, 0, 2]


# --- calibration ---------------------------------------------------------------------------


def test_calibration_compares_labels_but_says_when_there_are_too_few_outcomes() -> None:
    interviewed = p(S.TECHNICAL_ROUND, [S.APPLIED_PENDING, S.TECHNICAL_ROUND])
    rejected = p(S.REJECTED, [S.APPLIED_PENDING, S.REJECTED])
    pending = p(S.APPLIED_PENDING, [S.APPLIED_PENDING])
    scored = [
        (interviewed.job_id, "good", 80),
        (rejected.job_id, "good", 78),
        (pending.job_id, "good", 90),  # no outcome yet: counted as scored, not as decided
        (uuid.uuid4(), "unlikely", 30),  # scored but not in the tracker's progress
    ]
    result = calibration(scored, [interviewed, rejected, pending])
    good, unlikely = result.groups
    assert (good.chance, good.scored, good.decided, good.interviewed, good.interview_rate) == (
        "good",
        3,
        2,
        1,
        50.0,
    )
    assert (unlikely.scored, unlikely.decided, unlikely.interview_rate) == (1, 0, None)
    assert result.decided == 2 and result.needed == MIN_OUTCOMES and not result.ready


def test_calibration_is_ready_at_fifty_decided_outcomes() -> None:
    rows = [
        p(S.TECHNICAL_ROUND, [S.APPLIED_PENDING, S.TECHNICAL_ROUND]) for _ in range(MIN_OUTCOMES)
    ]
    result = calibration([(r.job_id, "possible", 60) for r in rows], rows)
    assert result.ready and result.groups[0].interview_rate == 100.0


# --- the endpoint --------------------------------------------------------------------------


async def test_requires_login(client: AsyncClient) -> None:
    assert (await client.get(ANALYTICS)).status_code == 401


async def test_an_empty_account_has_zeros_and_no_rates(api: AsyncClient) -> None:
    body = (await api.get(ANALYTICS)).json()
    assert body["funnel"]["applied"] == 0 and body["funnel"]["response_rate"] is None
    assert len(body["weekly_applications"]) == 8 and len(body["prep"]["minutes_by_day"]) == 14
    assert body["prep"]["total_minutes"] == 0 and body["mocks"] == []
    assert body["calibration"]["ready"] is False and "of 50" in body["calibration"]["explanation"]
    assert "not a forecast" in body["note"]


async def test_the_funnel_follows_real_status_changes(api: AsyncClient) -> None:
    jobs: dict[str, dict[str, Any]] = {}
    for name in ("interview", "rejected", "silent", "untouched"):
        jobs[name] = await add_job(api, company_name=f"{name.title()} Co")
    for name, steps in {
        "interview": ["Applied - Pending", "Interview Confirmed"],
        "rejected": ["Applied - Pending", "Rejected"],
        "silent": ["Applied - Pending", "No Response"],
    }.items():
        for step in steps:
            assert (await move(api, jobs[name], step)).status_code == 200, (name, step)

    body = (await api.get(ANALYTICS)).json()
    # Moving to "applied" is what makes it count in this week's pace (no date was typed in).
    assert sum(w["applications"] for w in body["weekly_applications"]) == 3
    assert body["weekly_applications"][-1]["applications"] == 3
    funnel_ = body["funnel"]
    assert (funnel_["tracked"], funnel_["applied"], funnel_["responded"]) == (4, 3, 2)
    assert (funnel_["interviewed"], funnel_["rejected"], funnel_["no_response"]) == (1, 1, 1)
    assert funnel_["response_rate"] == 66.7 and funnel_["small_sample"] is True


async def test_prep_progress_counts_topics_and_study_minutes(
    app: FastAPI, api: AsyncClient
) -> None:
    assert (await api.post("/api/v1/prep/seed")).status_code == 200
    topics = (await api.get("/api/v1/prep/topics")).json()
    today = today_in(app.state.settings.timezone)
    for minutes, days_ago in ((30, 0), (45, 0), (20, 3), (60, 40)):  # the last is outside 14 days
        response = await api.post(
            f"/api/v1/prep/topics/{topics[0]['id']}/sessions",
            json={
                "minutes": minutes,
                "kind": "learn",
                "studied_on": (today - timedelta(days=days_ago)).isoformat(),
            },
        )
        assert response.status_code == 201, response.text
    prep = (await api.get(ANALYTICS)).json()["prep"]
    assert prep["total_minutes"] == 95 and prep["study_days"] == 2
    assert prep["minutes_by_day"][-1] == {"day": today.isoformat(), "minutes": 75}
    assert sum(prep["topics"].values()) == 159


async def test_calibration_uses_stored_scores_and_outcomes(
    api: AsyncClient,
    content: Any,
) -> None:
    job = await add_job(api, jd_text="Python, SQL and PostgreSQL role.", region="India")
    await api.post(f"/api/v1/jobs/{job['id']}/score", params={"ai": "false"})
    for step in ("Applied - Pending", "Interview Confirmed"):
        await move(api, job, step)
    calibration_ = (await api.get(ANALYTICS)).json()["calibration"]
    assert calibration_["decided"] == 1 and calibration_["ready"] is False
    (group,) = calibration_["groups"]
    assert group["scored"] == 1 and group["interviewed"] == 1 and group["interview_rate"] == 100.0


async def test_each_owner_sees_only_their_own_numbers(
    api: AsyncClient, other_api: AsyncClient
) -> None:
    await add_job(api)
    assert (await api.get(ANALYTICS)).json()["funnel"]["tracked"] == 1
    assert (await other_api.get(ANALYTICS)).json()["funnel"]["tracked"] == 0
