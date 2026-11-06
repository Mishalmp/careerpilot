"""Web search behind one small interface, so the provider can be swapped by a setting.

Providers: SearXNG (free, self-hosted; docs/phase-7 decision D2) and Brave Search (optional, needs a
key). The service address comes from settings, never from page content, so these calls do not go
through the SSRF-guarded fetcher (which would refuse a local SearXNG). Results are only *links*:
every page is then fetched through `core.fetcher.Fetcher`.

unverified against the live services (no network in tests): response shapes follow each provider's
public documentation as understood on 2026-11-06; task R17 proves SearXNG, R01 notes Brave.
"""

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from careerpilot.core.config import Settings

TIMEOUT_SECONDS = 15.0
MAX_RESULTS = 10


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str


class SearchError(Exception):
    """The search service failed. The message is written for the person who sees it."""


class SearchProvider(Protocol):
    name: str

    async def search(self, query: str, limit: int) -> list[SearchHit]: ...


def _hits(rows: Any, *, title: str, url: str, snippet: str, limit: int) -> list[SearchHit]:
    hits: list[SearchHit] = []
    if not isinstance(rows, list):
        return hits
    for row in rows:  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(row, dict):
            continue
        found_url = row.get(url)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        if not isinstance(found_url, str) or not found_url.startswith(("http://", "https://")):
            continue  # only web links; anything else is ignored
        hits.append(
            SearchHit(
                title=str(row.get(title) or found_url)[:200],  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                url=found_url[:2000],
                snippet=str(row.get(snippet) or "")[:500],  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
            )
        )
        if len(hits) >= limit:
            break
    return hits


class SearxngSearch:
    name = "searxng"

    def __init__(self, base_url: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._base = base_url.rstrip("/")
        self._transport = transport

    async def search(self, query: str, limit: int = 5) -> list[SearchHit]:
        try:
            async with httpx.AsyncClient(
                transport=self._transport, timeout=TIMEOUT_SECONDS
            ) as client:
                response = await client.get(
                    f"{self._base}/search", params={"q": query, "format": "json"}
                )
        except httpx.HTTPError as exc:
            raise SearchError("The search service could not be reached.") from exc
        if response.status_code == 403:
            raise SearchError(
                "SearXNG refused the request: JSON output must be enabled in its settings."
            )
        if response.status_code == 429:
            raise SearchError("SearXNG is rate limiting this app (see its limiter settings).")
        if response.status_code != 200:
            raise SearchError(
                f"The search service answered with an error ({response.status_code})."
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise SearchError("The search service did not return JSON.") from exc
        rows = body.get("results") if isinstance(body, dict) else None  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        return _hits(
            rows, title="title", url="url", snippet="content", limit=min(limit, MAX_RESULTS)
        )


class BraveSearch:
    name = "brave"
    ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._key = api_key
        self._transport = transport

    async def search(self, query: str, limit: int = 5) -> list[SearchHit]:
        try:
            async with httpx.AsyncClient(
                transport=self._transport, timeout=TIMEOUT_SECONDS
            ) as client:
                response = await client.get(
                    self.ENDPOINT,
                    params={"q": query, "count": min(limit, MAX_RESULTS)},
                    headers={"X-Subscription-Token": self._key, "Accept": "application/json"},
                )
        except httpx.HTTPError as exc:
            raise SearchError("The search service could not be reached.") from exc
        if response.status_code in (401, 403):
            raise SearchError("Brave Search refused the API key.")
        if response.status_code == 429:
            raise SearchError("Brave Search quota or rate limit reached.")
        if response.status_code != 200:
            raise SearchError(
                f"The search service answered with an error ({response.status_code})."
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise SearchError("The search service did not return JSON.") from exc
        web = body.get("web") if isinstance(body, dict) else None  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        rows = web.get("results") if isinstance(web, dict) else None  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        return _hits(
            rows, title="title", url="url", snippet="description", limit=min(limit, MAX_RESULTS)
        )


def make_search(settings: Settings) -> SearchProvider | None:
    """None when no provider is configured; research then explains how to set one up."""
    if settings.search_provider == "searxng" and settings.searxng_url:
        return SearxngSearch(settings.searxng_url)
    if settings.search_provider == "brave" and settings.brave_api_key:
        return BraveSearch(settings.brave_api_key.get_secret_value())
    return None
