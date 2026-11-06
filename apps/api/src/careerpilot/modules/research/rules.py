"""Pure rules for the research run: which searches to make, which pages to read, how relevant a
finding looks. No network, database or model, so each rule is table-testable.
"""

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from careerpilot.core.fetcher import is_blocked_domain
from careerpilot.core.search import SearchHit

MAX_QUERIES = 8
MAX_PER_HOST = 2
PAGE_TEXT_CHARS = 12_000  # what one page may add to a model request
_WORD = re.compile(r"[a-z0-9+#.]{2,}")
_STOP = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "for",
        "with",
        "on",
        "at",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "by",
        "from",
        "this",
        "that",
        "it",
        "you",
        "your",
        "we",
        "our",
        "they",
        "their",
        "about",
        "how",
        "what",
        "why",
        "when",
        "who",
        "can",
        "will",
        "would",
        "should",
        "could",
        "do",
        "does",
    }
)
# Hosts whose pages tend to be about the work itself rather than about selling something.
_GOOD_HINTS = (
    "engineering",
    "eng.",
    "blog",
    "docs.",
    "developer",
    "github.",
    "dev.to",
    "stackoverflow",
)
_BAD_HINTS = (
    "pinterest.",
    "facebook.",
    "twitter.",
    "x.com",
    "instagram.",
    "youtube.",
    "tiktok.",
    "reddit.",
)


def plan_queries(title: str, company: str, *, limit: int = MAX_QUERIES) -> list[str]:
    """Search phrases for a role, most useful first. Templates: the same job gives the same plan."""
    role = " ".join(title.split())
    firm = " ".join(company.split())
    candidates = [
        f"{role} interview questions",
        f"{role} interview topics to prepare",
        f"{role} technical interview questions and answers",
        f"{firm} engineering blog",
        f"{firm} interview process {role}",
        f"{role} system design interview",
        f"{role} coding interview practice questions",
        f"{role} skills required what to study",
    ]
    seen: set[str] = set()
    plan: list[str] = []
    for query in candidates:
        key = query.casefold()
        if key not in seen:
            seen.add(key)
            plan.append(query)
    return plan[:limit]


def _normal_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def _score(hit: SearchHit) -> int:
    host = (urlsplit(hit.url).hostname or "").lower()
    score = 0
    if any(h in host for h in _GOOD_HINTS):
        score += 2
    if any(h in host for h in _BAD_HINTS):
        score -= 5
    if "interview" in hit.title.casefold():
        score += 1
    return score


def select_pages(hits: Sequence[SearchHit], limit: int) -> list[SearchHit]:
    """Pages worth reading: no repeats, no blocked sites, at most two per site, best first.

    Order is deterministic: higher score first, then the order the search returned them.
    """
    seen: set[str] = set()
    candidates: list[tuple[int, int, SearchHit]] = []
    for position, hit in enumerate(hits):
        host = (urlsplit(hit.url).hostname or "").lower()
        if not host or is_blocked_domain(host) or hit.url.startswith("http://localhost"):
            continue
        key = _normal_url(hit.url)
        if key in seen:
            continue
        seen.add(key)
        score = _score(hit)
        if score < 0:
            continue
        candidates.append((-score, position, hit))
    candidates.sort(key=lambda item: (item[0], item[1]))
    per_host: dict[str, int] = {}
    chosen: list[SearchHit] = []
    for _, _, hit in candidates:
        host = (urlsplit(hit.url).hostname or "").lower()
        if per_host.get(host, 0) >= MAX_PER_HOST:
            continue
        per_host[host] = per_host.get(host, 0) + 1
        chosen.append(hit)
        if len(chosen) >= limit:
            break
    return chosen


def words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.casefold()) if w not in _STOP}


def relevance(text: str, topic: str, role: str, company: str) -> int:
    """A rough 0 to 100 from shared words with the role (a heuristic, not a model's opinion)."""
    wanted = words(role) | words(company)
    found = words(text) | words(topic)
    if not wanted:
        return 40
    overlap = len(wanted & found) / len(wanted)
    return round(35 + 65 * overlap)


def dedupe_key(kind: str, text: str) -> str:
    """The same question worded with different spacing or case counts as one finding."""
    normal = " ".join(_WORD.findall(text.casefold()))
    return hashlib.sha256(f"{kind}:{normal}".encode()).hexdigest()[:32]


@dataclass(frozen=True)
class Budgets:
    searches: int
    pages: int
    tokens: int

    def as_dict(self) -> dict[str, int]:
        return {"searches": self.searches, "pages": self.pages, "tokens": self.tokens}
