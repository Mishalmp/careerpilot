"""The web, with a budget: a few searches and a few pages per job, nothing more.

Search goes through the configured provider; pages only through `core.fetcher.Fetcher` (which
refuses private addresses and the sites that forbid automation). A search hit on one of those sites
may still be shown as a link ("it is also listed on ..."), but its page is never opened and its
snippet is never used as evidence.

Every problem is written into `notes` in plain words instead of being raised, so one slow site
cannot stop the rest of the list.
"""

from careerpilot.core.fetcher import Fetcher, FetchError, is_blocked_domain
from careerpilot.core.search import SearchError, SearchHit, SearchProvider
from careerpilot.modules.apply.chain import host_of

MAX_SEARCHES_PER_JOB = 5
PAGE_TEXT_CHARS = 20_000
HITS_PER_SEARCH = 6


class JobWeb:
    """What may still be spent on one job, and what happened so far."""

    def __init__(
        self,
        provider: SearchProvider | None,
        fetcher: Fetcher | None,
        *,
        max_pages: int,
        max_searches: int = MAX_SEARCHES_PER_JOB,
    ) -> None:
        self._provider = provider
        self._fetcher = fetcher
        self.searches_left = max_searches if provider is not None else 0
        self.pages_left = max_pages if fetcher is not None else 0
        self.notes: list[str] = []
        self.searches_used = 0
        self.pages_used = 0
        self._search_broken = False
        self._pages: dict[str, str | None] = {}

    @property
    def can_search(self) -> bool:
        return self._provider is not None and self.searches_left > 0 and not self._search_broken

    async def search(self, query: str) -> list[SearchHit] | None:
        """The hits, or None when nothing could be searched (the reason is in `notes`)."""
        if self._provider is None:
            return None
        if self._search_broken or self.searches_left <= 0:
            return None
        self.searches_left -= 1
        self.searches_used += 1
        try:
            return await self._provider.search(query, HITS_PER_SEARCH)
        except SearchError as error:
            self._search_broken = True  # one failure ends searching for this job
            self.notes.append(f"Web search stopped: {error}")
            return None

    def readable(self, url: str) -> bool:
        return not is_blocked_domain(host_of(url))

    async def page(self, url: str) -> str | None:
        """The visible text of a page, or None (not allowed, over budget, or it failed)."""
        if url in self._pages:
            return self._pages[url]
        if not self.readable(url) or self._fetcher is None or self.pages_left <= 0:
            return None
        self.pages_left -= 1
        self.pages_used += 1
        try:
            fetched = await self._fetcher.fetch(url)
        except FetchError as error:
            self.notes.append(f"Could not read {host_of(url)}: {error.message}")
            self._pages[url] = None
            return None
        text = fetched.text[:PAGE_TEXT_CHARS]
        self._pages[url] = text or None
        return self._pages[url]
