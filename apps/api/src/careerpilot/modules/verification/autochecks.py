"""Checks that code can do alone: look the company up and record what was found.

Each function returns a `CheckResult`. A lookup that fails is "unknown", not "fail": a flaky
network must not make a genuine company look bad. "Fail" is for a positive finding.
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import quote

import httpx

from careerpilot.core.fetcher import FetchedPage, Fetcher, FetchError
from careerpilot.modules.verification.enums import CheckKey, CheckStatus
from careerpilot.modules.verification.rules import domain_age_status

MIN_HOME_PAGE_CHARS = 200
CAREERS_PATHS = ("/careers", "/jobs", "/careers/", "/join-us", "/work-with-us")
# Pages on these hosts mean the company hires through an applicant-tracking system.
ATS_HOSTS = (
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "workable.com",
    "smartrecruiters.com",
    "myworkdayjobs.com",
    "breezy.hr",
    "recruitee.com",
    "zohorecruit.com",
    "keka.com",
)
_RDAP = "https://rdap.org/domain/"
_DOH = "https://dns.google/resolve?type=MX&name="
# Names like "co.uk" are shared suffixes, not companies; asking about them would return the
# registry's own (old) record. Without a public-suffix list this is the cheap approximation.
_SECOND_LEVEL = frozenset({"co", "com", "org", "net", "gov", "edu", "ac", "ltd", "plc"})


@dataclass(frozen=True)
class CheckResult:
    key: CheckKey
    status: CheckStatus
    note: str
    evidence_url: str | None = None
    evidence_quote: str | None = None  # only set once verified against the page text


def website_host(website: str | None) -> str | None:
    if not website:
        return None
    try:
        host = httpx.URL(website if "//" in website else f"https://{website}").host
    except httpx.InvalidURL:
        return None
    return host.removeprefix("www.") or None


def candidate_domains(host: str) -> list[str]:
    """The host, then its parent: `www.acme.co.in` -> `www.acme.co.in`, `acme.co.in`."""
    labels = host.split(".")
    names = [host] if len(labels) >= 2 else []
    if len(labels) >= 3:
        names.append(".".join(labels[1:]))
    return [n for n in names if not _is_shared_suffix(n)]


def _is_shared_suffix(name: str) -> bool:
    labels = name.split(".")
    return len(labels) == 2 and labels[0] in _SECOND_LEVEL and len(labels[1]) == 2


async def check_website(fetcher: Fetcher, host: str) -> CheckResult:
    url = f"https://{host}/"
    try:
        page = await fetcher.fetch(url)
    except FetchError as exc:
        status = CheckStatus.FAIL if exc.code == "unresolvable" else CheckStatus.UNKNOWN
        message = exc.message
        if status is CheckStatus.FAIL and not await fetcher.network_is_up():
            # Not evidence about the company: this computer cannot look anything up right now.
            status, message = (
                CheckStatus.UNKNOWN,
                "Your network could not look anything up just now.",
            )
        return CheckResult(CheckKey.WEBSITE, status, message, url)
    if len(page.text) < MIN_HOME_PAGE_CHARS:
        return CheckResult(
            CheckKey.WEBSITE, CheckStatus.UNKNOWN, "The home page has almost no text.", page.url
        )
    return CheckResult(
        CheckKey.WEBSITE, CheckStatus.PASS, "Loads over HTTPS with a valid certificate.", page.url
    )


def _registration_date(rdap_json: str) -> date | None:
    try:
        events = json.loads(rdap_json).get("events", [])
        for event in events:
            if event.get("eventAction") == "registration":
                return datetime.fromisoformat(event["eventDate"].replace("Z", "+00:00")).date()
    except (ValueError, KeyError, AttributeError, TypeError):
        return None
    return None


async def check_domain_age(
    fetcher: Fetcher, host: str, today: date
) -> tuple[CheckResult, str | None]:
    """Also returns the name the registry knew, so the mail check asks about the same domain."""
    for name in candidate_domains(host):
        url = _RDAP + quote(name)
        try:
            page = await fetcher.fetch(url)
        except FetchError:
            continue
        registered = _registration_date(page.text)
        if registered is not None:
            status = domain_age_status(registered, today)
            return (
                CheckResult(
                    CheckKey.DOMAIN_AGE, status, f"{name} was registered on {registered}.", page.url
                ),
                name,
            )
    return (
        CheckResult(
            CheckKey.DOMAIN_AGE,
            CheckStatus.UNKNOWN,
            "No registration date found. Some registries do not publish one; check by hand.",
        ),
        None,
    )


def _has_mail_exchanger(doh_json: str) -> bool:
    try:
        answers = json.loads(doh_json).get("Answer", [])
        # Type 15 is MX. A "0 ." record is the "this domain takes no mail" marker.
        return any(
            a.get("type") == 15 and not str(a.get("data", "")).strip().endswith(" .")
            for a in answers
        )
    except (ValueError, AttributeError, TypeError):
        return False


async def check_mail_domain(fetcher: Fetcher, domain: str) -> CheckResult:
    url = _DOH + quote(domain)
    try:
        page = await fetcher.fetch(url)
    except FetchError as exc:
        return CheckResult(CheckKey.MAIL_DOMAIN, CheckStatus.UNKNOWN, exc.message, url)
    if _has_mail_exchanger(page.text):
        return CheckResult(
            CheckKey.MAIL_DOMAIN, CheckStatus.PASS, f"{domain} accepts mail (MX record).", page.url
        )
    return CheckResult(
        CheckKey.MAIL_DOMAIN, CheckStatus.FAIL, f"{domain} has no mail server record.", page.url
    )


async def check_careers_page(fetcher: Fetcher, host: str) -> CheckResult:
    for path in CAREERS_PATHS:
        try:
            page = await fetcher.fetch(f"https://{host}{path}")
        except FetchError:
            continue
        if len(page.text) >= 100:
            note = _careers_note(page)
            return CheckResult(CheckKey.CAREERS_PAGE, CheckStatus.PASS, note, page.url)
    return CheckResult(
        CheckKey.CAREERS_PAGE,
        CheckStatus.UNKNOWN,
        "No careers page at the usual addresses. It may live elsewhere; check by hand.",
    )


def _careers_note(page: FetchedPage) -> str:
    final_host = httpx.URL(page.url).host
    for ats in ATS_HOSTS:
        if final_host == ats or final_host.endswith("." + ats):
            return f"Careers page found; applications run through {ats}."
    return "Careers page found on the company's own site."


async def run_auto_checks(fetcher: Fetcher, website: str | None, today: date) -> list[CheckResult]:
    host = website_host(website)
    if host is None:
        note = "This company has no website saved, so nothing could be looked up."
        return [
            CheckResult(key, CheckStatus.UNKNOWN, note)
            for key in (
                CheckKey.WEBSITE,
                CheckKey.DOMAIN_AGE,
                CheckKey.MAIL_DOMAIN,
                CheckKey.CAREERS_PAGE,
            )
        ]

    async def domain_then_mail() -> list[CheckResult]:
        age, registered = await check_domain_age(fetcher, host, today)
        return [age, await check_mail_domain(fetcher, registered or host)]

    site, domain_and_mail, careers = await asyncio.gather(
        check_website(fetcher, host), domain_then_mail(), check_careers_page(fetcher, host)
    )
    return [site, *domain_and_mail, careers]
