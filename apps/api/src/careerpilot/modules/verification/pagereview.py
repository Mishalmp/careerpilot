"""The model reads the company's own pages; code decides what to believe.

Pages are fetched by fixed address (no model-chosen URLs), so there is no tool loop and nothing the
page can talk the model into doing. The model returns a verdict per check with a URL and a quote.
Code then accepts a "pass" or "fail" only if the URL is one of the pages it was shown and the quote
appears in that page's text. Anything else becomes "unknown".
"""

import asyncio
import re
import uuid
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.config import Settings
from careerpilot.core.evidence import quote_appears
from careerpilot.core.fetcher import Fetcher, FetchError
from careerpilot.core.llm import LlmClient, call_llm_json
from careerpilot.core.prompts import data_block, load_prompt
from careerpilot.modules.verification.autochecks import CheckResult
from careerpilot.modules.verification.enums import CheckKey, CheckStatus

PAGE_PATHS = (
    "/",
    "/about",
    "/about-us",
    "/company",
    "/contact",
    "/contact-us",
    "/team",
    "/leadership",
    "/legal",
    "/terms",
    "/privacy",
)
MAX_PAGES = 6
MAX_CHARS_PER_PAGE = 6000
MIN_PAGE_CHARS = 80
CONCURRENT_FETCHES = 3

JUDGED = (CheckKey.REGISTRATION, CheckKey.CONTACT_DETAILS, CheckKey.PEOPLE)

# A quote that is on the page can still prove nothing ("We are a leading company"). For a "pass",
# the quote must also look like the kind of thing the check is about.
_PASS_SHAPES: dict[CheckKey, re.Pattern[str]] = {
    # An identifier: 6+ letters, digits or dashes containing at least four digits (CIN, GSTIN, ...).
    CheckKey.REGISTRATION: re.compile(r"\b(?=[A-Za-z0-9-]*\d{4})[A-Za-z0-9-]{6,}\b"),
    # An email address, a phone number, or a 5-6 digit postal code.
    CheckKey.CONTACT_DETAILS: re.compile(
        r"[\w.+-]+@[\w-]+\.[\w.]+|\+?\d[\d\s().-]{7,}\d|\b\d{5,6}\b"
    ),
    # A person's role.
    CheckKey.PEOPLE: re.compile(
        r"\b(?:ceo|cto|coo|cfo|founder|co-founder|director|president|chief|head of|vp|"
        r"vice president|manager|lead|engineer|partner)\b",
        re.IGNORECASE,
    ),
}


class Finding(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["pass", "fail", "unknown"] = "unknown"
    url: str = ""
    quote: str = ""


class PageReview(BaseModel):
    model_config = ConfigDict(extra="ignore")

    registration: Finding = Finding()
    contact_details: Finding = Finding()
    people: Finding = Finding()


@dataclass(frozen=True)
class Pages:
    texts: dict[str, str]  # final URL -> the text the model was shown


async def gather_pages(fetcher: Fetcher, host: str) -> Pages:
    gate = asyncio.Semaphore(CONCURRENT_FETCHES)

    async def one(path: str) -> tuple[str, str] | None:
        async with gate:
            try:
                page = await fetcher.fetch(f"https://{host}{path}")
            except FetchError:
                return None
        if len(page.text) < MIN_PAGE_CHARS:
            return None
        return page.url, page.text[:MAX_CHARS_PER_PAGE]

    texts: dict[str, str] = {}
    for found in await asyncio.gather(*(one(path) for path in PAGE_PATHS)):
        if found is not None and found[0] not in texts and len(texts) < MAX_PAGES:
            texts[found[0]] = found[1]
    return Pages(texts)


def render_pages(pages: Pages) -> str:
    return "\n\n".join(data_block("page", text, url=url) for url, text in pages.texts.items())


def _supported(key: CheckKey, finding: Finding, pages: Pages) -> bool:
    if finding.url not in pages.texts or not quote_appears(finding.quote, pages.texts[finding.url]):
        return False
    return finding.status != "pass" or _PASS_SHAPES[key].search(finding.quote) is not None


def verify_review(review: PageReview, pages: Pages) -> list[CheckResult]:
    """Keep a pass or fail only when its quote really is on the cited page."""
    results: list[CheckResult] = []
    for key in JUDGED:
        finding: Finding = getattr(review, key.value)
        if finding.status == "unknown":
            results.append(
                CheckResult(key, CheckStatus.UNKNOWN, "Not found on the pages that were read.")
            )
        elif _supported(key, finding, pages):
            results.append(
                CheckResult(
                    key,
                    CheckStatus(finding.status),
                    "Found on the company's own site (read by the model, quote verified).",
                    finding.url,
                    finding.quote.strip(),
                )
            )
        else:
            results.append(
                CheckResult(
                    key,
                    CheckStatus.UNKNOWN,
                    "The model gave a result, but its quote was not on the page or did not show "
                    "what the check needs, so the result was discarded.",
                )
            )
    return results


async def review_pages(
    db: AsyncSession,
    owner_id: uuid.UUID,
    llm: LlmClient,
    settings: Settings,
    pages: Pages,
) -> tuple[PageReview, list[CheckResult]]:
    prompt = load_prompt(settings.prompts_dir, "company-pages", 1)
    review = await call_llm_json(
        db,
        owner_id,
        llm,
        settings,
        prompt=prompt,
        user=render_pages(pages),
        schema=PageReview,
    )
    return review, verify_review(review, pages)
