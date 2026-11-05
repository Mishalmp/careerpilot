"""Test doubles shared by more than one test file."""

from dataclasses import dataclass
from typing import Any

import httpx

from careerpilot.core.fetcher import Fetcher, FetchError
from careerpilot.core.llm import LlmError, LlmReply


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

    async def complete(self, *, system: str, user: str, max_tokens: int) -> LlmReply:
        self.calls.append({"system": system, "user": user, "max_tokens": max_tokens})
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
            return ["93.184.216.34"]

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
