"""Reading a public GitHub profile: which languages your own repositories use. Pure functions.

Only GitHub's public API is used, for the public repositories of the username in your link.
LinkedIn, Naukri and LeetCode are never read (their terms forbid it or they have no public API);
they stay links you can show.
"""

import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, cast
from urllib.parse import urlsplit

_USER = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
_RESERVED = frozenset({"orgs", "settings", "topics", "marketplace", "sponsors", "features"})
MAX_DESCRIPTION_CHARS = 200


def username(url: str) -> str | None:
    """The user in https://github.com/<user>[/...], or None when the link is not a profile."""
    parts = urlsplit(url)
    if (parts.hostname or "").lower() not in ("github.com", "www.github.com"):
        return None
    first = next((p for p in parts.path.split("/") if p), "")
    return first if _USER.match(first) and first.lower() not in _RESERVED else None


@dataclass(frozen=True)
class Repos:
    read: int
    languages: Counter[str]
    text: str  # repository names and descriptions, for the shared skill vocabulary


class GithubReadError(Exception):
    """GitHub answered with something that is not a list of repositories."""


def parse_repos(body: str) -> Repos:
    """Counts the languages of repositories you own (forks are other people's work, so skipped)."""
    try:
        rows: Any = json.loads(body)
    except json.JSONDecodeError as exc:
        raise GithubReadError("GitHub sent a reply that could not be read.") from exc
    if not isinstance(rows, list):
        detail = "GitHub did not return repositories."
        message = cast("dict[str, Any]", rows).get("message") if isinstance(rows, dict) else None
        if isinstance(message, str):
            detail = message
        raise GithubReadError(detail[:200])
    languages: Counter[str] = Counter()
    text: list[str] = []
    read = 0
    for raw in cast("list[Any]", rows):
        row = cast("dict[str, Any]", raw) if isinstance(raw, dict) else {}
        if not row or row.get("fork"):
            continue
        read += 1
        language = row.get("language")
        if isinstance(language, str) and language:
            languages[language] += 1
        for key in ("name", "description"):
            value = row.get(key)
            if isinstance(value, str):
                text.append(value[:MAX_DESCRIPTION_CHARS])
    return Repos(read, languages, "\n".join(text))
