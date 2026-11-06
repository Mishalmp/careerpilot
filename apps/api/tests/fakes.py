"""Test doubles shared by more than one test file."""

import ipaddress
from dataclasses import dataclass
from typing import Any

import httpx

from careerpilot.core.fetcher import Fetcher, FetchError
from careerpilot.core.llm import LlmError, LlmReply
from careerpilot.core.search import SearchError, SearchHit


class FakeLlm:
    """Answers with canned text and records what it was sent.

    Give `replies` to return different text on successive calls (the last one repeats).
    """

    model = "fake-model"

    def __init__(
        self,
        text: str = "",
        *,
        replies: list[str] | None = None,
        input_tokens: int = 100,
        output_tokens: int = 50,
        refused: bool = False,
        error: LlmError | None = None,
    ) -> None:
        self.replies = replies or [text]
        self.refused, self.error = refused, error
        self.input_tokens, self.output_tokens = input_tokens, output_tokens
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self, *, system: str, user: str, max_tokens: int, model: str | None = None
    ) -> LlmReply:
        self.calls.append(
            {"system": system, "user": user, "max_tokens": max_tokens, "model": model}
        )
        if self.error:
            raise self.error
        text = self.replies[min(len(self.calls), len(self.replies)) - 1]
        return LlmReply(text, self.input_tokens, self.output_tokens, self.refused)


@dataclass(frozen=True)
class Redirect:
    location: str


class FakeWeb:
    """A pretend internet for the fetcher: pages keyed by "host/path[?query]".

    A value is the page body, or (body, content_type), or (body, content_type, status). Hosts
    in `dead` do not resolve. Every request is recorded in `requests`.
    """

    def __init__(
        self,
        pages: dict[str, str | tuple[str, str] | tuple[str, str, int] | Redirect] | None = None,
        *,
        dead: set[str] | None = None,
    ) -> None:
        self.pages = pages or {}
        self.dead = dead or set()
        self.requests: list[str] = []

    def fetcher(self) -> Fetcher:
        async def resolver(host: str, port: int) -> list[str]:
            if host in self.dead:
                raise FetchError("unresolvable", f"Could not resolve {host}.")
            try:
                ipaddress.ip_address(host)
            except ValueError:
                return ["93.184.216.34"]
            return [host]  # like getaddrinfo, a literal address resolves to itself

        return Fetcher(resolver=resolver, transport=httpx.MockTransport(self._handle))

    def _handle(self, request: httpx.Request) -> httpx.Response:
        host = request.headers["host"]
        key = (
            host
            + request.url.path
            + (f"?{request.url.query.decode()}" if request.url.query else "")
        )
        self.requests.append(key)
        page = self.pages.get(key)
        if page is None:
            return httpx.Response(404, text="not found", headers={"content-type": "text/plain"})
        if isinstance(page, Redirect):
            return httpx.Response(302, headers={"location": page.location})
        body, content_type, status = (
            (page, "text/html", 200)
            if isinstance(page, str)
            else (*page, 200)
            if len(page) == 2
            else page
        )
        return httpx.Response(status, text=body, headers={"content-type": content_type})


class FakeSearch:
    name = "fake"

    def __init__(
        self,
        hits: list[SearchHit] | None = None,
        *,
        fail_after: int | None = None,
        answers: dict[str, list[SearchHit]] | None = None,
    ) -> None:
        self.hits = hits if hits is not None else []
        self.answers = answers or {}  # a query containing the key gets these hits
        self.fail_after = fail_after
        self.queries: list[str] = []

    async def search(self, query: str, limit: int) -> list[SearchHit]:
        if self.fail_after is not None and len(self.queries) >= self.fail_after:
            raise SearchError("The search service could not be reached.")
        self.queries.append(query)
        for fragment, answer in self.answers.items():
            if fragment in query:
                return list(answer)
        return list(self.hits)


async def run_worker(app: Any) -> bool:
    """Run one due background task with the app's fake search, model and web. False if none."""
    from careerpilot.modules.tasks import service as tasks
    from careerpilot.worker import make_handlers

    handlers = make_handlers(
        app.state.fetcher, app.state.settings, llm=app.state.llm, search=app.state.search
    )
    return await tasks.run_next(app.state.sessionmaker, handlers)
