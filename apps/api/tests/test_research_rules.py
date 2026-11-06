"""Pure research rules and the search providers' parsing (with a fake transport).
# covers: REQ-07 (bounded research), REQ-08 (no invented sources), H21-style host rules
"""

import httpx
import pytest

from careerpilot.core.search import BraveSearch, SearchError, SearchHit, SearxngSearch
from careerpilot.modules.research import rules


def hit(url: str, title: str = "t") -> SearchHit:
    return SearchHit(title=title, url=url, snippet="")


def test_the_plan_is_deterministic_bounded_and_has_no_repeats() -> None:
    plan = rules.plan_queries("Python Full Stack Developer", "Acme")
    assert plan == rules.plan_queries("Python Full Stack Developer", "Acme")
    assert 1 <= len(plan) <= rules.MAX_QUERIES
    assert len({q.casefold() for q in plan}) == len(plan)
    assert plan[0] == "Python Full Stack Developer interview questions"
    assert any("Acme" in q for q in plan)
    assert len(rules.plan_queries("x", "y", limit=3)) == 3


def test_extra_whitespace_in_names_is_tidied() -> None:
    assert rules.plan_queries("  SDE   2 ", "  Big   Co")[0] == "SDE 2 interview questions"


def test_selection_drops_blocked_sites_repeats_and_social_pages() -> None:
    hits = [
        hit("https://www.linkedin.com/jobs/view/1"),
        hit("https://www.glassdoor.com/Interview/x"),
        hit("https://example.com/a"),
        hit("https://example.com/a/"),  # the same page with a trailing slash
        hit("https://example.com/a?utm_source=x"),  # the same page with tracking
        hit("https://www.reddit.com/r/learnprogramming/x"),
        hit("http://localhost:8080/secret"),
        hit("https://blog.acme.dev/post"),
    ]
    chosen = [h.url for h in rules.select_pages(hits, 10)]
    assert chosen == ["https://blog.acme.dev/post", "https://example.com/a"]


def test_selection_prefers_engineering_sources_and_caps_one_site() -> None:
    hits = [hit(f"https://spam.example/p{i}") for i in range(5)] + [
        hit("https://engineering.acme.com/hiring", "Interview process"),
        hit("https://docs.python.org/3/tutorial"),
    ]
    chosen = [h.url for h in rules.select_pages(hits, 10)]
    assert chosen[0] == "https://engineering.acme.com/hiring"
    assert chosen.count("https://spam.example/p0") == 1
    assert sum(u.startswith("https://spam.example") for u in chosen) == rules.MAX_PER_HOST


def test_selection_respects_the_page_budget_and_empty_input() -> None:
    hits = [hit(f"https://site{i}.example/x") for i in range(20)]
    assert len(rules.select_pages(hits, 5)) == 5
    assert rules.select_pages([], 5) == []


def test_relevance_is_higher_for_text_that_mentions_the_role() -> None:
    on_topic = rules.relevance(
        "How do you design a REST API in Python?", "api design", "Python Backend Developer", "Acme"
    )
    off_topic = rules.relevance("Best pizza toppings", "food", "Python Backend Developer", "Acme")
    assert on_topic > off_topic
    assert 0 <= off_topic <= on_topic <= 100


def test_dedupe_ignores_case_spacing_and_punctuation_but_not_meaning_or_kind() -> None:
    a = rules.dedupe_key("question", "What is a   transaction?")
    assert a == rules.dedupe_key("question", "what is a transaction")
    assert a != rules.dedupe_key("question", "What is an index?")
    assert a != rules.dedupe_key("topic", "What is a transaction?")


# --- providers ---------------------------------------------------------------------------------


def transport(status: int, body: object) -> httpx.MockTransport:
    return httpx.MockTransport(lambda request: httpx.Response(status, json=body))


async def test_searxng_parses_results_and_ignores_non_web_links() -> None:
    body = {
        "results": [
            {"title": "A", "url": "https://a.example/x", "content": "about a"},
            {"title": "B", "url": "javascript:alert(1)", "content": "bad"},
            {"title": "C", "url": "ftp://c.example/x"},
            "not a dict",
            {"title": "D", "url": "https://d.example/y"},
        ]
    }
    found = await SearxngSearch("http://localhost:8080", transport(200, body)).search("q", 5)
    assert [h.url for h in found] == ["https://a.example/x", "https://d.example/y"]
    assert found[0].snippet == "about a"


async def test_searxng_sends_the_query_and_json_format() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"results": []})

    await SearxngSearch("http://localhost:8080/", httpx.MockTransport(handler)).search(
        "python interview", 3
    )
    assert seen[0].url.path == "/search"
    assert seen[0].url.params["q"] == "python interview"
    assert seen[0].url.params["format"] == "json"


@pytest.mark.parametrize(
    ("status", "fragment"),
    [(403, "JSON output"), (429, "rate limiting"), (500, "answered with an error")],
)
async def test_searxng_errors_have_plain_messages(status: int, fragment: str) -> None:
    with pytest.raises(SearchError, match=fragment):
        await SearxngSearch("http://x", transport(status, {})).search("q", 3)


async def test_search_services_that_are_down_or_send_junk_raise_search_errors() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(SearchError, match="could not be reached"):
        await SearxngSearch("http://x", httpx.MockTransport(boom)).search("q", 3)
    junk = httpx.MockTransport(lambda r: httpx.Response(200, text="<html>not json</html>"))
    with pytest.raises(SearchError, match="did not return JSON"):
        await SearxngSearch("http://x", junk).search("q", 3)


async def test_brave_parses_results_and_sends_the_key() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "web": {"results": [{"title": "T", "url": "https://t.example", "description": "d"}]}
            },
        )

    found = await BraveSearch("secret-key", httpx.MockTransport(handler)).search("q", 3)
    assert [h.url for h in found] == ["https://t.example"]
    assert seen[0].headers["X-Subscription-Token"] == "secret-key"


@pytest.mark.parametrize(("status", "fragment"), [(401, "refused the API key"), (429, "quota")])
async def test_brave_errors(status: int, fragment: str) -> None:
    with pytest.raises(SearchError, match=fragment):
        await BraveSearch("k", transport(status, {})).search("q", 3)
