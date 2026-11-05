"""The SSRF suite: every way the fetcher could be talked into reaching something it must not.

No real network is used: a fake resolver decides what each name "resolves" to and a mock
transport plays the web server. The default resolver is exercised only on literal and local names.
"""

import asyncio
import gzip
import ipaddress
from collections.abc import Callable

import httpx
import pytest

from careerpilot.core.fetcher import (
    FetchedPage,
    Fetcher,
    FetchError,
    html_to_text,
    is_blocked_domain,
    is_public_address,
)

PUBLIC = "93.184.216.34"

Handler = Callable[[httpx.Request], httpx.Response]


def html(body: str, status: int = 200, content_type: str = "text/html; charset=utf-8") -> Handler:
    return lambda request: httpx.Response(status, text=body, headers={"content-type": content_type})


def fetcher_for(
    handler: Handler | Callable[[httpx.Request], object],
    answers: dict[str, list[str]] | None = None,
    **options: object,
) -> Fetcher:
    """A fetcher whose DNS answers come from `answers` (default: every name is public)."""

    async def resolver(host: str, port: int) -> list[str]:
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            return [host]  # like getaddrinfo, a literal address resolves to itself
        return (answers or {}).get(host, [PUBLIC])

    return Fetcher(resolver=resolver, transport=httpx.MockTransport(handler), **options)  # type: ignore[arg-type]


async def refused(fetcher: Fetcher, url: str) -> FetchError:
    with pytest.raises(FetchError) as caught:
        await fetcher.fetch(url)
    return caught.value


# --- addresses -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "127.1.2.3",
        "10.0.0.5",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",  # cloud metadata
        "100.64.0.1",  # carrier-grade NAT
        "100.100.100.200",  # Alibaba metadata
        "0.0.0.0",  # noqa: S104
        "224.0.0.1",
        "255.255.255.255",
        "::1",
        "::",
        "fe80::1",
        "fe80::1%eth0",
        "fd00:ec2::254",  # AWS IPv6 metadata
        "::ffff:127.0.0.1",  # IPv4-mapped loopback
        "::ffff:10.0.0.1",
        "::ffff:169.254.169.254",
        "64:ff9b::7f00:1",  # NAT64 wrapping 127.0.0.1
        "2002:7f00:1::",  # 6to4 wrapping 127.0.0.1
        "not-an-ip",
        "",
    ],
)
def test_internal_addresses_are_not_public(address: str) -> None:
    assert not is_public_address(address)


@pytest.mark.parametrize("address", [PUBLIC, "8.8.8.8", "1.1.1.1", "2606:4700:4700::1111"])
def test_public_addresses_are_public(address: str) -> None:
    assert is_public_address(address)


@pytest.mark.parametrize(
    "host", ["linkedin.com", "www.linkedin.com", "in.indeed.com", "GLASSDOOR.COM", "naukri.com."]
)
def test_blocked_domains(host: str) -> None:
    assert is_blocked_domain(host)


@pytest.mark.parametrize("host", ["example.com", "notlinkedin.com", "linkedin.com.example.org"])
def test_lookalike_domains_are_not_blocked(host: str) -> None:
    assert not is_blocked_domain(host)


# --- the address the URL names -------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/",
        "gopher://example.com/",
        "javascript:alert(1)",
        "//example.com/",
        "example.com",
        "http://",
        "http://user:pass@example.com/",
        "http://example.com:5433/",
        "http://example.com:22/",
        "https://example.com:8443/",
    ],
)
async def test_urls_that_are_not_plain_web_addresses_are_refused(url: str) -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200)

    error = await refused(fetcher_for(handler), url)
    assert error.code == "bad_url"
    assert not called


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://127.0.0.1:80/",
        "http://localhost/",
        "http://[::1]/",
        "http://169.254.169.254/latest/meta-data/",
        "http://0.0.0.0/",
        "http://192.168.0.1/admin",
    ],
)
async def test_the_default_resolver_refuses_local_destinations(url: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("a request was made")

    error = await refused(Fetcher(transport=httpx.MockTransport(handler)), url)
    assert error.code == "blocked_address"


async def test_alternative_spellings_of_loopback_never_reach_the_network() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("a request was made")

    # Decimal and hex forms: how the name is read is up to the OS; either way nothing is fetched.
    for url in ("http://2130706433/", "http://0x7f000001/", "http://017700000001/"):
        error = await refused(Fetcher(transport=httpx.MockTransport(handler)), url)
        assert error.code in ("blocked_address", "unresolvable", "bad_url")


async def test_a_name_resolving_to_an_internal_address_is_refused() -> None:
    fetcher = fetcher_for(html("secret"), {"internal.example": ["10.0.0.7"]})
    assert (await refused(fetcher, "https://internal.example/")).code == "blocked_address"


async def test_one_internal_answer_among_public_ones_refuses_the_name() -> None:
    fetcher = fetcher_for(html("x"), {"mixed.example": [PUBLIC, "127.0.0.1"]})
    assert (await refused(fetcher, "https://mixed.example/")).code == "blocked_address"


async def test_a_name_with_no_answers_is_refused() -> None:
    fetcher = fetcher_for(html("x"), {"empty.example": []})
    assert (await refused(fetcher, "https://empty.example/")).code == "blocked_address"


async def test_blocked_domains_are_refused_before_any_lookup() -> None:
    looked_up: list[str] = []

    async def resolver(host: str, port: int) -> list[str]:
        looked_up.append(host)
        return [PUBLIC]

    fetcher = Fetcher(resolver=resolver, transport=httpx.MockTransport(html("x")))
    for url in (
        "https://www.linkedin.com/jobs/1",
        "https://in.indeed.com/",
        "https://glassdoor.com",
    ):
        assert (await refused(fetcher, url)).code == "blocked_domain"
    assert looked_up == []


# --- connecting to the address that was checked --------------------------------------------


async def test_the_request_connects_to_the_checked_address_and_keeps_the_real_name() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["connect_to"] = request.url.host
        seen["host_header"] = request.headers["host"]
        seen["sni"] = request.extensions.get("sni_hostname")
        seen["cookie"] = request.headers.get("cookie")
        seen["authorization"] = request.headers.get("authorization")
        seen["agent"] = request.headers["user-agent"]
        return httpx.Response(200, text="<p>hi</p>", headers={"content-type": "text/html"})

    page = await fetcher_for(handler).fetch("https://careers.example.com/about")
    assert seen["connect_to"] == PUBLIC
    assert seen["host_header"] == "careers.example.com"
    assert seen["sni"] == "careers.example.com"
    assert seen["cookie"] is None and seen["authorization"] is None
    assert str(seen["agent"]).startswith("CareerPilot/")
    assert page.url == "https://careers.example.com/about"


async def test_a_name_that_changes_its_answer_cannot_change_where_the_request_goes() -> None:
    # DNS rebinding: public on the first lookup, internal on the next. We look up once per hop
    # and connect to that answer, so the second answer is never used for the first request.
    answers = iter([[PUBLIC], ["127.0.0.1"], ["127.0.0.1"]])
    connected: list[str] = []

    async def resolver(host: str, port: int) -> list[str]:
        return next(answers)

    def handler(request: httpx.Request) -> httpx.Response:
        connected.append(request.url.host)
        return httpx.Response(200, text="ok", headers={"content-type": "text/plain"})

    fetcher = Fetcher(resolver=resolver, transport=httpx.MockTransport(handler))
    await fetcher.fetch("http://rebind.example/")
    assert connected == [PUBLIC]


# --- redirects -----------------------------------------------------------------------------


def redirecting(*locations: str) -> Handler:
    hops = iter(locations)

    def handler(request: httpx.Request) -> httpx.Response:
        try:
            return httpx.Response(302, headers={"location": next(hops)})
        except StopIteration:
            return httpx.Response(200, text="done", headers={"content-type": "text/plain"})

    return handler


async def test_a_redirect_to_an_internal_address_is_refused() -> None:
    for target in (
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:80/",
        "http://[::1]/",
    ):
        fetcher = fetcher_for(redirecting(target))
        assert (await refused(fetcher, "https://good.example/")).code == "blocked_address"


async def test_a_redirect_to_a_name_that_resolves_internally_is_refused() -> None:
    fetcher = fetcher_for(
        redirecting("https://sneaky.example/x"), {"sneaky.example": ["192.168.1.10"]}
    )
    assert (await refused(fetcher, "https://good.example/")).code == "blocked_address"


@pytest.mark.parametrize("target", ["file:///etc/passwd", "ftp://example.com/", "gopher://x/"])
async def test_a_redirect_to_another_scheme_is_refused(target: str) -> None:
    fetcher = fetcher_for(redirecting(target))
    assert (await refused(fetcher, "https://good.example/")).code == "bad_url"


async def test_a_redirect_to_a_blocked_domain_is_refused() -> None:
    fetcher = fetcher_for(redirecting("https://www.linkedin.com/company/x"))
    assert (await refused(fetcher, "https://good.example/")).code == "blocked_domain"


async def test_a_redirect_to_an_odd_port_is_refused() -> None:
    fetcher = fetcher_for(redirecting("http://good.example:5433/"))
    assert (await refused(fetcher, "https://good.example/")).code == "bad_url"


async def test_relative_redirects_are_followed_and_the_final_address_is_reported() -> None:
    fetcher = fetcher_for(redirecting("/careers", "https://other.example/jobs"))
    page = await fetcher.fetch("https://good.example/")
    assert page.url == "https://other.example/jobs"
    assert page.text == "done"


async def test_redirect_loops_stop() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "/again"})

    assert (
        await refused(fetcher_for(handler), "https://loop.example/")
    ).code == "too_many_redirects"


async def test_a_redirect_without_a_destination_is_an_error() -> None:
    fetcher = fetcher_for(lambda request: httpx.Response(302))
    assert (await refused(fetcher, "https://good.example/")).code == "http_error"


# --- what comes back -----------------------------------------------------------------------


async def test_a_large_body_is_cut_at_the_cap() -> None:
    fetcher = fetcher_for(html("a" * 5000, content_type="text/plain"), max_bytes=1000)
    page = await fetcher.fetch("https://big.example/")
    assert page.truncated
    assert len(page.text) == 1000


async def test_a_compression_bomb_is_cut_at_the_cap_after_decompressing() -> None:
    bomb = gzip.compress(b"a" * 30_000_000)
    assert len(bomb) < 100_000

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=bomb, headers={"content-encoding": "gzip", "content-type": "text/plain"}
        )

    page = await fetcher_for(handler, max_bytes=2000).fetch("https://bomb.example/")
    assert page.truncated
    assert len(page.text) == 2000


@pytest.mark.parametrize("kind", ["application/pdf", "image/png", "application/zip", ""])
async def test_only_text_pages_are_read(kind: str) -> None:
    fetcher = fetcher_for(
        lambda r: httpx.Response(200, content=b"%PDF", headers={"content-type": kind})
    )
    assert (await refused(fetcher, "https://files.example/x")).code == "unsupported_type"


@pytest.mark.parametrize("status", [403, 404, 500])
async def test_error_statuses_are_reported(status: int) -> None:
    error = await refused(fetcher_for(html("nope", status)), "https://good.example/")
    assert error.code == "http_error"
    assert str(status) in error.message


async def test_network_failures_are_reported_without_leaking_details() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused to 93.184.216.34")

    error = await refused(fetcher_for(handler), "https://down.example/")
    assert error.code == "network"
    assert PUBLIC not in error.message


async def test_a_slow_server_hits_the_deadline() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(2)
        return httpx.Response(200, text="late", headers={"content-type": "text/plain"})

    error = await refused(fetcher_for(handler, timeout_seconds=0.05), "https://slow.example/")
    assert error.code == "timeout"


async def test_html_comes_back_as_visible_text() -> None:
    page = await fetcher_for(
        html(
            "<html><head><title>Acme | About</title><style>p{color:red}</style></head>"
            "<body><script>steal()</script><h1>About us</h1><p>We make   anvils &amp; rockets.</p>"
            "<ul><li>Founded 2014</li><li>Pune</li></ul></body></html>"
        )
    ).fetch("https://acme.example/about")
    assert isinstance(page, FetchedPage)
    assert page.text == "Acme | About\nAbout us\nWe make anvils & rockets.\nFounded 2014\nPune"
    assert "steal" not in page.text and "color" not in page.text


def test_unclosed_tags_and_scripts_do_not_break_extraction() -> None:
    assert html_to_text("<div><p>one<p>two<script>x") == "one\ntwo"
    assert html_to_text("") == ""
