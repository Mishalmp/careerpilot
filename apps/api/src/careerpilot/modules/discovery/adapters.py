"""Readers for the public job-board endpoints of three applicant-tracking systems.

Terms: all three publish these endpoints for companies' own career pages and answer without a
login (checked by calling them on 2026-11-06; the providers' full terms were not re-read, and
this is not legal advice). We make one request per board per day, send an honest User-Agent, go
through the safe fetcher, and never touch sites whose terms forbid automation (see
`core/fetcher.BLOCKED_DOMAINS`). A board that stops answering is shown as a failure, not retried
in a loop.

Each `parse_*` function is pure and tolerant: an entry that lacks an id, a title or a link is
skipped instead of failing the whole board.
"""

import html
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, cast
from urllib.parse import quote

from careerpilot.core.fetcher import Fetcher, FetchError, html_to_text
from careerpilot.modules.discovery.enums import BoardKind

BOARD_MAX_BYTES = 8_000_000  # a large Ashby board is about 2 MB
MAX_DESCRIPTION = 20_000
TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


class AdapterError(Exception):
    """The board could not be read. The message is safe to show."""


@dataclass(frozen=True)
class RawJob:
    external_id: str
    title: str
    url: str
    apply_url: str | None = None
    location: str | None = None
    description: str | None = None  # None: not in the list, fetched when you accept the job
    published_on: date | None = None
    remote: bool = False


def board_url(kind: BoardKind, token: str) -> str:
    """The one address an adapter may fetch; a validated token cannot change the host."""
    if not TOKEN.match(token):
        raise AdapterError(
            "A board name may only contain letters, digits, dots, dashes and underscores."
        )
    name = quote(token, safe="")
    match kind:
        case BoardKind.GREENHOUSE:
            return f"https://boards-api.greenhouse.io/v1/boards/{name}/jobs"
        case BoardKind.LEVER:
            return f"https://api.lever.co/v0/postings/{name}?mode=json"
        case BoardKind.ASHBY:
            return f"https://api.ashbyhq.com/posting-api/job-board/{name}"


def _get(value: Any, key: str) -> Any:
    """`value[key]` when value is a JSON object, else None."""
    return cast("dict[str, Any]", value).get(key) if isinstance(value, dict) else None


def _text(value: Any) -> str | None:
    # Postgres text cannot hold a NUL character; one bad listing must not fail the whole board.
    return value.replace("\x00", "").strip() or None if isinstance(value, str) else None


def _http(value: Any) -> str | None:
    text = _text(value)
    return text if text and text.startswith(("http://", "https://")) else None


def _day(value: Any) -> date | None:
    """Accepts ISO text or epoch milliseconds."""
    try:
        if isinstance(value, int | float):
            return datetime.fromtimestamp(value / 1000, UTC).date()
        if isinstance(value, str) and value:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except (ValueError, OverflowError, OSError):
        return None
    return None


def _entries(raw: str, key: str | None) -> list[dict[str, Any]]:
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise AdapterError("The board did not return valid JSON (it may be too large).") from exc
    items: Any = _get(data, key) if key else data
    if not isinstance(items, list):
        raise AdapterError("The board returned an unexpected shape.")
    return [cast("dict[str, Any]", i) for i in cast("list[Any]", items) if isinstance(i, dict)]


def parse_greenhouse(raw: str) -> list[RawJob]:
    jobs: list[RawJob] = []
    for item in _entries(raw, "jobs"):
        url = _http(item.get("absolute_url"))
        title = _text(item.get("title"))
        if item.get("id") is None or not title or not url:
            continue
        location = item.get("location")
        jobs.append(
            RawJob(
                external_id=str(item["id"]),
                title=title,
                url=url,
                location=_text(_get(location, "name")),
                published_on=_day(item.get("first_published") or item.get("updated_at")),
            )
        )
    return jobs


def parse_lever(raw: str) -> list[RawJob]:
    jobs: list[RawJob] = []
    for item in _entries(raw, None):
        url = _http(item.get("hostedUrl"))
        title = _text(item.get("text"))
        external_id = _text(item.get("id"))
        if not external_id or not title or not url:
            continue
        categories = item.get("categories")
        jobs.append(
            RawJob(
                external_id=external_id,
                title=title,
                url=url,
                apply_url=_http(item.get("applyUrl")),
                location=_text(_get(categories, "location")),
                description=(_text(item.get("descriptionPlain")) or "")[:MAX_DESCRIPTION] or None,
                published_on=_day(item.get("createdAt")),
                remote=item.get("workplaceType") == "remote",
            )
        )
    return jobs


def parse_ashby(raw: str) -> list[RawJob]:
    jobs: list[RawJob] = []
    for item in _entries(raw, "jobs"):
        url = _http(item.get("jobUrl"))
        title = _text(item.get("title"))
        external_id = _text(item.get("id"))
        if not external_id or not title or not url or item.get("isListed") is False:
            continue
        jobs.append(
            RawJob(
                external_id=external_id,
                title=title,
                url=url,
                apply_url=_http(item.get("applyUrl")),
                location=_text(item.get("location")),
                description=(_text(item.get("descriptionPlain")) or "")[:MAX_DESCRIPTION] or None,
                published_on=_day(item.get("publishedAt")),
                remote=bool(item.get("isRemote")) or item.get("workplaceType") == "Remote",
            )
        )
    return jobs


_PARSERS = {
    BoardKind.GREENHOUSE: parse_greenhouse,
    BoardKind.LEVER: parse_lever,
    BoardKind.ASHBY: parse_ashby,
}


async def fetch_board(fetcher: Fetcher, kind: BoardKind, token: str) -> list[RawJob]:
    try:
        page = await fetcher.fetch(board_url(kind, token), max_bytes=BOARD_MAX_BYTES)
    except FetchError as exc:
        raise AdapterError(exc.message) from exc
    if page.truncated:
        raise AdapterError("The board is larger than the 8 MB limit, so it was not read.")
    return _PARSERS[kind](page.text)


async def fetch_greenhouse_description(
    fetcher: Fetcher, token: str, external_id: str
) -> str | None:
    """Greenhouse lists no descriptions; one job's page has it as escaped HTML."""
    if not TOKEN.match(token) or not external_id.isdigit():
        return None
    url = f"https://boards-api.greenhouse.io/v1/boards/{quote(token, safe='')}/jobs/{external_id}"
    try:
        page = await fetcher.fetch(url)
        content = _get(json.loads(page.text), "content")
    except (FetchError, ValueError):
        return None
    if not isinstance(content, str):
        return None
    return html_to_text(html.unescape(content))[:MAX_DESCRIPTION] or None
