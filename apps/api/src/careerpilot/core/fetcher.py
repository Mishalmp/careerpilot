"""The only door for research code to reach the public web.

Why it exists: research reads pages that someone else controls, and the URL can come from a model
or from page text. Without a guard, a page could make this machine fetch `http://127.0.0.1:5433`,
the cloud metadata address, or a router admin page (SSRF). The guard works like this:

- only `http` and `https`, only ports 80 and 443, no credentials in the URL;
- the host must not be on the policy's blocked list (sites whose terms forbid automation);
- the host is resolved **here**, every address must be public, and the request connects to the
  address that was checked (so the name cannot resolve somewhere else a moment later);
- redirects are followed by hand, and every hop goes through the same checks;
- the body is read in a stream and cut at a size cap; the whole fetch has a deadline;
- no cookies, no proxies from the environment, no credentials of ours are ever sent.

Not done, on purpose: robots.txt and per-host rate limits. Research fetches a handful of pages,
only when asked, from different hosts. Discovery (Phase 5) crawls more and adds both.
"""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Final, Literal

import httpx

USER_AGENT: Final = "CareerPilot/0.1 (personal research tool; single user)"

# Sites whose terms forbid automated access (plan section 9). Matching includes subdomains.
BLOCKED_DOMAINS: Final = frozenset(
    {
        "linkedin.com",
        "indeed.com",
        "glassdoor.com",
        "glassdoor.co.in",
        "naukri.com",
    }
)

ALLOWED_PORTS: Final = frozenset({80, 443})
MAX_REDIRECTS: Final = 4
MAX_BYTES: Final = 1_000_000
TOTAL_TIMEOUT_SECONDS: Final = 20.0
TEXT_TYPES: Final = (
    "text/html",
    "application/xhtml+xml",
    "text/plain",
    "application/json",
    "application/rdap+json",  # domain registration lookups
)
_REDIRECT_STATUSES: Final = frozenset({301, 302, 303, 307, 308})

FetchErrorCode = Literal[
    "bad_url",
    "blocked_domain",
    "blocked_address",
    "unresolvable",
    "too_many_redirects",
    "unsupported_type",
    "http_error",
    "timeout",
    "network",
]

Resolver = Callable[[str, int], Awaitable[list[str]]]


class FetchError(Exception):
    """A fetch that was refused or failed. `code` is stable; the message is safe to show."""

    def __init__(self, code: FetchErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class FetchedPage:
    url: str  # after redirects
    status: int
    content_type: str
    text: str  # visible text for HTML; the decoded body otherwise
    truncated: bool


def is_blocked_domain(host: str) -> bool:
    host = host.lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in BLOCKED_DOMAINS)


# NAT64 and 6to4 embed an IPv4 address that could be internal; the ranges are refused outright.
_EMBEDDED_V4_NETWORKS: Final = (
    ipaddress.IPv6Network("64:ff9b::/96"),
    ipaddress.IPv6Network("2002::/16"),
)


def is_public_address(value: str) -> bool:
    """True only for addresses that are reachable on the public internet."""
    try:
        address = ipaddress.ip_address(value.split("%")[0])  # drop an IPv6 zone id
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return is_public_address(str(address.ipv4_mapped))
        if any(address in network for network in _EMBEDDED_V4_NETWORKS):
            return False
    return address.is_global and not (
        address.is_multicast or address.is_reserved or address.is_unspecified
    )


async def resolve(host: str, port: int) -> list[str]:
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise FetchError("unresolvable", f"Could not resolve {host}.") from exc
    return list(dict.fromkeys(str(info[4][0]) for info in infos))


class Fetcher:
    def __init__(
        self,
        *,
        resolver: Resolver = resolve,
        transport: httpx.AsyncBaseTransport | None = None,
        max_bytes: int = MAX_BYTES,
        timeout_seconds: float = TOTAL_TIMEOUT_SECONDS,
    ) -> None:
        self._resolver = resolver
        self._transport = transport
        self._max_bytes = max_bytes
        self._timeout = timeout_seconds

    async def fetch(self, url: str) -> FetchedPage:
        try:
            async with asyncio.timeout(self._timeout):
                return await self._fetch(url)
        except TimeoutError as exc:
            raise FetchError("timeout", "The page took too long to load.") from exc

    async def _fetch(self, url: str) -> FetchedPage:
        async with httpx.AsyncClient(
            transport=self._transport,
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": USER_AGENT, "Accept": ", ".join(TEXT_TYPES)},
            timeout=httpx.Timeout(self._timeout),
        ) as client:
            current = _parse(url)
            for _ in range(MAX_REDIRECTS + 1):
                page_or_next = await self._hop(client, current)
                if isinstance(page_or_next, FetchedPage):
                    return page_or_next
                current = page_or_next
        raise FetchError("too_many_redirects", "The page redirected too many times.")

    async def _hop(self, client: httpx.AsyncClient, url: httpx.URL) -> "FetchedPage | httpx.URL":
        host, port = url.host, url.port or (443 if url.scheme == "https" else 80)
        if is_blocked_domain(host):
            raise FetchError(
                "blocked_domain", f"{host} does not allow automated access, so it is not fetched."
            )
        addresses = await self._resolver(host, port)
        if not addresses or not all(is_public_address(a) for a in addresses):
            raise FetchError("blocked_address", f"{host} does not resolve to a public address.")

        # Connect to the address we just checked, but keep the real name for Host and TLS.
        pinned = url.copy_with(host=addresses[0])
        extensions = {"sni_hostname": host} if url.scheme == "https" else {}
        try:
            async with client.stream(
                "GET", pinned, headers={"Host": url.netloc.decode("ascii")}, extensions=extensions
            ) as response:
                if response.status_code in _REDIRECT_STATUSES:
                    location = response.headers.get("location")
                    if not location:
                        raise FetchError("http_error", "A redirect had no destination.")
                    return _parse(str(url.join(location)))
                if response.status_code >= 400:
                    raise FetchError("http_error", f"The site answered {response.status_code}.")
                content_type = (
                    response.headers.get("content-type", "").split(";")[0].strip().lower()
                )
                if content_type not in TEXT_TYPES:
                    raise FetchError(
                        "unsupported_type", f"Only text pages are read, not {content_type or '?'}."
                    )
                body = bytearray()
                truncated = False
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > self._max_bytes:
                        del body[self._max_bytes :]
                        truncated = True
                        break
                text = _decode(bytes(body), response.charset_encoding)
                if content_type in ("text/html", "application/xhtml+xml"):
                    text = html_to_text(text)
                return FetchedPage(str(url), response.status_code, content_type, text, truncated)
        except httpx.HTTPError as exc:
            raise FetchError("network", f"Could not load {host}.") from exc


def _parse(value: str) -> httpx.URL:
    try:
        url = httpx.URL(value)
    except httpx.InvalidURL as exc:
        raise FetchError("bad_url", "That is not a valid web address.") from exc
    if url.scheme not in ("http", "https") or not url.host:
        raise FetchError("bad_url", "Only http and https addresses are fetched.")
    if url.userinfo:
        raise FetchError("bad_url", "Addresses with a username or password are not fetched.")
    port = url.port or (443 if url.scheme == "https" else 80)
    if port not in ALLOWED_PORTS:
        raise FetchError("bad_url", "Only ports 80 and 443 are fetched.")
    return url


def _decode(body: bytes, charset: str | None) -> str:
    try:
        return body.decode(charset or "utf-8", errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


_SKIPPED = frozenset({"script", "style", "noscript", "template", "svg"})
_BLOCKS = frozenset(
    {"p", "div", "br", "li", "ul", "ol", "tr", "table", "section", "article", "header", "footer"}
    | {"h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "main", "nav", "title"}
)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIPPED:
            self._skip_depth += 1
        elif tag in _BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


def html_to_text(markup: str) -> str:
    """The text a reader would see: scripts and styles dropped, whitespace collapsed."""
    extractor = _TextExtractor()
    extractor.feed(markup)
    extractor.close()
    lines = (" ".join(line.split()) for line in "".join(extractor.parts).splitlines())
    return "\n".join(line for line in lines if line)
