"""Telling "that company's site does not exist" from "my own network is down".
# covers: found in the first real run: a DNS outage made a real company's website look fake
"""

from careerpilot.core.fetcher import CONTROL_HOSTS
from careerpilot.modules.apply import company
from careerpilot.modules.verification.autochecks import check_website
from careerpilot.modules.verification.enums import CheckStatus
from careerpilot.modules.verification.schemas import VerificationOut
from tests.fakes import FakeWeb

HOST = "acme-robotics.example"


async def test_a_site_that_does_not_exist_is_a_failed_check_when_the_network_is_fine() -> None:
    fetcher = FakeWeb(dead={HOST}).fetcher()
    assert await fetcher.network_is_up() is True
    assert (await check_website(fetcher, HOST)).status is CheckStatus.FAIL


async def test_when_nothing_resolves_the_check_is_unknown_not_failed() -> None:
    fetcher = FakeWeb(dead={HOST, *CONTROL_HOSTS}).fetcher()
    assert await fetcher.network_is_up() is False
    result = await check_website(fetcher, HOST)
    assert result.status is CheckStatus.UNKNOWN
    assert "network" in result.note


async def test_one_working_control_host_is_enough_to_say_the_network_is_up() -> None:
    fetcher = FakeWeb(dead={HOST, *CONTROL_HOSTS[:-1]}).fetcher()
    assert await fetcher.network_is_up() is True


def _verification(
    verdict: str, passed: int, *, failed: int = 0, flags: list[str] | None = None
) -> VerificationOut:
    checks = [
        {
            "key": key,
            "kind": "check",
            "status": "fail" if i < failed else ("pass" if i < failed + passed else "unknown"),
            "source": "auto",
            "evidence_url": None,
            "evidence_quote": None,
            "note": None,
            "checked_at": None,
        }
        for i, key in enumerate(
            [
                "website",
                "domain_age",
                "mail_domain",
                "careers_page",
                "registration",
                "contact_details",
                "people",
                "independent_mentions",
            ]
        )
    ]
    return VerificationOut.model_validate(
        {
            "job_id": "00000000-0000-0000-0000-000000000001",
            "company_name": "Acme",
            "website": "https://acme.example",
            "verdict": verdict,
            "passed": passed,
            "total": 8,
            "raised_flags": flags or [],
            "needs_review": True,
            "notice": "",
            "ai_available": False,
            "checks": checks,
        }
    )


def test_few_passed_checks_are_called_unverified_not_suspicious() -> None:
    """The verification module says "suspicious" for fewer than three passes; the list must not."""
    summary, held = company.summarise(_verification("suspicious", 1))
    assert summary.verdict == "unverified" and held is None
    assert "nothing was found against it" in summary.note


def test_a_red_flag_or_two_failed_checks_keep_the_word_suspicious_and_hold_the_job() -> None:
    summary, held = company.summarise(_verification("suspicious", 0, flags=["asks_for_money"]))
    assert summary.verdict == "suspicious" and held and "asks for money" in held
    summary, held = company.summarise(_verification("suspicious", 0, failed=2))
    assert summary.verdict == "suspicious" and held and "2 company checks failed" in held


async def test_a_name_that_fails_to_resolve_once_is_tried_again() -> None:
    from careerpilot.core.fetcher import Fetcher, FetchError

    calls: list[str] = []

    async def flaky(host: str, port: int) -> list[str]:
        calls.append(host)
        if len(calls) == 1:
            raise FetchError("unresolvable", f"Could not resolve {host}.")
        return ["93.184.216.34"]

    web = FakeWeb({"acme.example/": "<html><body>" + "hello " * 40 + "</body></html>"})
    inner = web.fetcher()
    fetcher = Fetcher(resolver=flaky, transport=inner._transport)  # pyright: ignore[reportPrivateUsage]
    page = await fetcher.fetch("https://acme.example/")
    assert "hello" in page.text and len(calls) == 2  # the first lookup failed, the second worked


async def test_a_name_that_never_resolves_still_fails_after_the_second_try() -> None:
    import pytest

    from careerpilot.core.fetcher import FetchError

    fetcher = FakeWeb(dead={HOST}).fetcher()
    with pytest.raises(FetchError) as info:
        await fetcher.fetch(f"https://{HOST}/")
    assert info.value.code == "unresolvable"
