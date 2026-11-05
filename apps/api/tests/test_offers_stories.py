"""The offer calculator (with stored exchange rates) and the STAR story bank."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from careerpilot.core.clock import today_in
from careerpilot.modules.offers.rules import (
    STALE_RATE_DAYS,
    OfferInput,
    Rate,
    compare,
)
from careerpilot.modules.stories.rules import hints

D = Decimal
TODAY = date(2026, 11, 6)
OFFERS = "/api/v1/offers"
STORIES = "/api/v1/stories"


def offer(**fields: Any) -> OfferInput:
    base: dict[str, Any] = {"name": "Acme", "currency": "INR", "fixed_annual": D(1_500_000)}
    return OfferInput(**(base | fields))


# --- the calculator's rules ----------------------------------------------------------------


def test_rupee_offers_need_no_rate_and_variable_pay_counts_at_the_expected_share() -> None:
    (result,) = compare(
        [
            offer(
                variable_target_annual=D(400_000),
                variable_payout_pct=D(50),
                joining_bonus=D(100_000),
            )
        ],
        {},
        TODAY,
    )
    assert result.guaranteed_cash == D(1_500_000)
    assert result.steady_cash == D(1_700_000)  # 1.5M fixed + half of a 400k target
    assert result.first_year_cash == D(1_800_000)  # plus the one-off bonus
    assert result.steady_cash_inr == D(1_700_000) and result.variable_share_pct == D("11.8")
    assert "Variable pay is counted at 50% of its target." in result.notes
    assert any("clawback" in n for n in result.notes)


def test_a_foreign_offer_is_converted_with_the_stored_rate() -> None:
    rates = {"USD": Rate(D("83.5"), TODAY - timedelta(days=10))}
    (result,) = compare([offer(currency="USD", fixed_annual=D(60_000))], rates, TODAY)
    assert result.steady_cash_inr == D(5_010_000) and not result.notes


def test_a_missing_rate_leaves_rupee_figures_out_instead_of_guessing() -> None:
    (result,) = compare([offer(currency="EUR")], {}, TODAY)
    assert result.steady_cash_inr is None and result.rank is None
    assert result.steady_cash == D(1_500_000)  # the original currency is still shown
    assert any("No EUR rate" in n for n in result.notes)


def test_an_old_rate_is_flagged_with_its_age() -> None:
    old = TODAY - timedelta(days=STALE_RATE_DAYS + 1)
    (result,) = compare([offer(currency="USD")], {"USD": Rate(D(80), old)}, TODAY)
    assert result.steady_cash_inr is not None
    assert any(f"{STALE_RATE_DAYS + 1} days ago" in n for n in result.notes)


def test_offers_are_ranked_by_steady_cash_in_rupees() -> None:
    results = compare(
        [
            offer(name="A", fixed_annual=D(1_800_000)),
            offer(name="B", currency="USD", fixed_annual=D(30_000)),  # 30k * 80 = 2.4M
            offer(name="C", currency="GBP", fixed_annual=D(40_000)),  # no GBP rate: unranked
            offer(name="D", fixed_annual=D(1_200_000)),
        ],
        {"USD": Rate(D(80), TODAY)},
        TODAY,
    )
    by_name = {r.name: r for r in results}
    assert [by_name[n].rank for n in "BADC"] == [1, 2, 3, None]
    assert by_name["B"].behind_best_pct == D("0.0") and by_name["A"].behind_best_pct == D("25.0")
    assert by_name["D"].behind_best_pct == D("50.0")
    assert [r.name for r in results] == ["A", "B", "C", "D"]  # input order is kept


def test_equity_is_kept_out_of_the_cash_totals() -> None:
    (result,) = compare([offer(equity_annual_value=D(500_000))], {}, TODAY)
    assert result.steady_cash_inr == D(1_500_000) and result.equity_annual_inr == D(500_000)
    assert any("Equity is your own estimate" in n for n in result.notes)


def test_notice_period_against_the_requested_joining_date() -> None:
    (late,) = compare([offer(notice_days=60, joining_date=TODAY + timedelta(days=30))], {}, TODAY)
    assert late.earliest_start == TODAY + timedelta(days=60)
    assert any("30 day(s) after the joining date" in n for n in late.notes)
    (fine,) = compare([offer(notice_days=30, joining_date=TODAY + timedelta(days=45))], {}, TODAY)
    assert not any("notice" in n for n in fine.notes)


def test_a_zero_offer_does_not_divide_by_zero() -> None:
    (result,) = compare([offer(fixed_annual=D(0))], {}, TODAY)
    assert result.variable_share_pct is None and result.behind_best_pct == D(0)


# --- the calculator's API ------------------------------------------------------------------


def payload(**fields: Any) -> dict[str, Any]:
    return {"name": "Acme", "currency": "INR", "fixed_annual": "1500000", **fields}


async def test_requires_login(client: AsyncClient) -> None:
    assert (await client.get(f"{OFFERS}/rates")).status_code == 401
    assert (await client.post(f"{OFFERS}/compare", json={"offers": [payload()]})).status_code == 401
    assert (await client.get(STORIES)).status_code == 401


async def test_rates_are_stored_per_currency_with_their_date(
    app: FastAPI, api: AsyncClient
) -> None:
    today = today_in(app.state.settings.timezone)
    body = {"currency": "USD", "to_inr": "83.5", "as_of": (today - timedelta(days=100)).isoformat()}
    stored = (await api.put(f"{OFFERS}/rates", json=body)).json()
    assert stored["currency"] == "USD" and stored["age_days"] == 100 and stored["stale"] is True

    fresh = (
        await api.put(f"{OFFERS}/rates", json=body | {"to_inr": "84", "as_of": today.isoformat()})
    ).json()
    assert fresh["to_inr"] in ("84.000000", "84") and fresh["stale"] is False
    assert len((await api.get(f"{OFFERS}/rates")).json()) == 1  # replaced, not added

    assert (await api.delete(f"{OFFERS}/rates/USD")).status_code == 204
    assert (await api.delete(f"{OFFERS}/rates/USD")).status_code == 404


@pytest.mark.parametrize(
    "bad",
    [
        {"currency": "INR", "to_inr": "1", "as_of": "2026-01-01"},
        {"currency": "USD", "to_inr": "0", "as_of": "2026-01-01"},
        {"currency": "USD", "to_inr": "-5", "as_of": "2026-01-01"},
        {"currency": "USD", "to_inr": "83", "as_of": "2999-01-01"},
        {"currency": "XYZ", "to_inr": "83", "as_of": "2026-01-01"},
    ],
)
async def test_bad_rates_are_refused(api: AsyncClient, bad: dict[str, str]) -> None:
    assert (await api.put(f"{OFFERS}/rates", json=bad)).status_code == 422


async def test_comparing_uses_your_stored_rates_and_nothing_is_saved(
    app: FastAPI, api: AsyncClient
) -> None:
    today = today_in(app.state.settings.timezone)
    await api.put(
        f"{OFFERS}/rates", json={"currency": "USD", "to_inr": "80", "as_of": today.isoformat()}
    )
    response = await api.post(
        f"{OFFERS}/compare",
        json={
            "offers": [
                payload(name="Local", fixed_annual="1800000"),
                payload(
                    name="Abroad",
                    currency="USD",
                    fixed_annual="30000",
                    variable_target_annual="6000",
                    variable_payout_pct="50",
                ),
                payload(name="Unknown", currency="EUR"),
            ]
        },
    )
    body = response.json()
    by_name = {o["name"]: o for o in body["offers"]}
    assert by_name["Abroad"]["rank"] == 1 and Decimal(
        by_name["Abroad"]["steady_cash_inr"]
    ) == Decimal(2_640_000)
    assert by_name["Local"]["rank"] == 2 and by_name["Unknown"]["rank"] is None
    assert "before tax" in body["note"]


@pytest.mark.parametrize(
    "bad",
    [
        {"offers": []},
        {"offers": [payload()] * 7},
        {"offers": [payload(fixed_annual="-1")]},
        {"offers": [payload(variable_payout_pct="500")]},
        {"offers": [payload(notice_days=999)]},
        {"offers": [payload(currency="XYZ")]},
        {"offers": [payload(name="")]},
    ],
)
async def test_nonsense_offers_are_refused(api: AsyncClient, bad: dict[str, Any]) -> None:
    assert (await api.post(f"{OFFERS}/compare", json=bad)).status_code == 422


async def test_rates_belong_to_their_owner(
    app: FastAPI, api: AsyncClient, other_api: AsyncClient
) -> None:
    today = today_in(app.state.settings.timezone).isoformat()
    await api.put(f"{OFFERS}/rates", json={"currency": "USD", "to_inr": "80", "as_of": today})
    assert (await other_api.get(f"{OFFERS}/rates")).json() == []
    assert (await other_api.delete(f"{OFFERS}/rates/USD")).status_code == 404
    other = await other_api.post(f"{OFFERS}/compare", json={"offers": [payload(currency="USD")]})
    assert (
        other.json()["offers"][0]["steady_cash_inr"] is None
    )  # the other owner's rate is not used


# --- stories -------------------------------------------------------------------------------

GOOD: dict[str, Any] = {
    "title": "Fixing the nightly import",
    "situation": "Our nightly import of customer files was failing about once a week and nobody knew why.",
    "task": "I owned the ingestion service and had to make it reliable before the month-end close.",
    "action": "I added run locking and idempotent upserts, wrote a replay command, and set up alerts on failures.",
    "result": "The import has run without a failed night since, and month-end closed on time.",
    "tags": ["Ownership", " reliability ", "ownership"],
    "evidence": "Project note: ingestion hardening, March",
}


def test_a_complete_story_has_no_hints() -> None:
    assert hints(GOOD["situation"], GOOD["task"], GOOD["action"], GOOD["result"], None) == []


def test_hints_point_at_weak_spots() -> None:
    short = hints("Too short.", GOOD["task"], GOOD["action"], GOOD["result"], None)
    assert any("situation is very short" in h for h in short)
    numbers = hints(
        GOOD["situation"],
        GOOD["task"],
        GOOD["action"],
        "Cut failures by 80 percent across the year.",
        None,
    )
    assert any("no evidence" in h for h in numbers)
    assert not any(
        "no evidence" in h
        for h in hints(
            GOOD["situation"],
            GOOD["task"],
            GOOD["action"],
            "Cut failures by 80 percent across the year.",
            "log",
        )
    )
    we = hints(
        GOOD["situation"],
        GOOD["task"],
        "We decided what to do and we did it together as a team on the day.",
        GOOD["result"],
        None,
    )
    assert any('"we"' in h for h in we)


async def test_stories_are_created_tidied_found_and_changed(api: AsyncClient) -> None:
    created = (await api.post(STORIES, json=GOOD)).json()
    assert created["tags"] == ["ownership", "reliability"]  # lower-cased, trimmed, de-duplicated
    assert created["hints"] == [] or all(isinstance(h, str) for h in created["hints"])

    other = dict(
        GOOD,
        title="Mentoring an intern",
        tags=["mentoring"],
        action="I paired with the intern daily, wrote a reading list and reviewed every change they made.",
    )
    await api.post(STORIES, json=other)
    assert {s["title"] for s in (await api.get(STORIES)).json()} == {
        GOOD["title"],
        "Mentoring an intern",
    }
    assert [s["title"] for s in (await api.get(STORIES, params={"tag": "Mentoring"})).json()] == [
        "Mentoring an intern"
    ]
    assert [s["title"] for s in (await api.get(STORIES, params={"q": "nightly"})).json()] == [
        GOOD["title"]
    ]
    assert (
        await api.get(STORIES, params={"q": "%"})
    ).json() == []  # wildcard characters are literal

    patched = await api.patch(
        f"{STORIES}/{created['id']}", json={"result": "Short.", "evidence": None}
    )
    body = patched.json()
    assert (
        body["result"] == "Short." and body["evidence"] is None and body["title"] == GOOD["title"]
    )
    assert any("result is very short" in h for h in body["hints"])

    assert (await api.delete(f"{STORIES}/{created['id']}")).status_code == 204
    assert (await api.delete(f"{STORIES}/{created['id']}")).status_code == 404


@pytest.mark.parametrize("field", ["title", "situation", "task", "action", "result"])
async def test_every_part_of_a_story_is_required(api: AsyncClient, field: str) -> None:
    assert (await api.post(STORIES, json=GOOD | {field: ""})).status_code == 422


async def test_stories_belong_to_their_owner(api: AsyncClient, other_api: AsyncClient) -> None:
    story = (await api.post(STORIES, json=GOOD)).json()
    assert (await other_api.get(STORIES)).json() == []
    assert (
        await other_api.patch(f"{STORIES}/{story['id']}", json={"title": "x"})
    ).status_code == 404
    assert (await other_api.delete(f"{STORIES}/{story['id']}")).status_code == 404
    assert len((await api.get(STORIES)).json()) == 1
