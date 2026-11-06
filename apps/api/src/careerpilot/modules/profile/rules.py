"""Reading a CV: role titles and years of experience. Pure functions, no model, no network.

Skills are found by the shared vocabulary in `content/skills.yaml` (via the scoring service), so the
words are defined in one place. These rules only add what the vocabulary cannot say: which job
titles the CV names, and how many years it claims.
"""

import re
from collections import Counter

MAX_TITLES = 8
MAX_YEARS = 40
_LEVEL = r"(?:senior|sr\.?|junior|jr\.?|lead|principal|staff|associate|trainee|intern)"
_AREA = (
    r"(?:python|java|javascript|typescript|node(?:\.js)?|react|angular|full[\s-]?stack|back[\s-]?end|"
    r"front[\s-]?end|software|data|devops|cloud|machine\s+learning|ml|ai|platform|web|mobile|qa|test|"
    r"site\s+reliability|sre|embedded|security)"
)
_ROLE = r"(?:developer|engineer|programmer|architect|sde\s*-?\s*(?:i{1,3}|[123])?|sdet)"
# [level] [area words...] role, for example "Senior Python Full Stack Developer".
_TITLE = re.compile(
    rf"\b(?:{_LEVEL}\s+)?(?:{_AREA}\s+){{0,3}}{_ROLE}\b",
    re.IGNORECASE,
)
_YEARS = re.compile(r"(\d{1,2})(?:\.\d)?\s*\+?\s*(?:years?|yrs?)\b", re.IGNORECASE)
_EXPERIENCE_WORDS = re.compile(r"experience|exp\b|industry|professional|working", re.IGNORECASE)


def _tidy(title: str) -> str:
    words = " ".join(title.split())
    small = {"sde": "SDE", "sdet": "SDET", "ml": "ML", "ai": "AI", "qa": "QA", "sre": "SRE"}
    return " ".join(small.get(w.lower().rstrip("-"), w.capitalize()) for w in words.split())


_LEVEL_PREFIX = re.compile(rf"^{_LEVEL}\s+", re.IGNORECASE)


def _family(title: str) -> str:
    """The role family: seniority words and SDE levels are dropped, so "Senior Python Developer"
    and "Python Developer" count as one title, and "SDE-2" and "SDE II" as "SDE"."""
    title = _LEVEL_PREFIX.sub("", title)
    return (
        "SDE" if title.upper().startswith("SDE") and not title.upper().startswith("SDET") else title
    )


def role_titles(text: str, limit: int = MAX_TITLES) -> list[str]:
    """Job titles named in the CV, most often mentioned first (ties: order of appearance)."""
    counts: Counter[str] = Counter()
    first_seen: dict[str, int] = {}
    for match in _TITLE.finditer(text):
        title = _family(_tidy(match.group(0)))
        if len(title.split()) < 2 and title not in {"SDE", "SDET"}:
            continue  # a bare "Engineer" or "Developer" says nothing about the role
        counts[title] += 1
        first_seen.setdefault(title, match.start())
    ordered = sorted(counts, key=lambda t: (-counts[t], first_seen[t]))
    return ordered[:limit]


def years_experience(text: str) -> int | None:
    """The largest plausible "N years" claim made near the word experience, else None."""
    best: int | None = None
    for line in text.splitlines():
        if not _EXPERIENCE_WORDS.search(line):
            continue
        for match in _YEARS.finditer(line):
            value = int(match.group(1))
            if 0 < value <= MAX_YEARS and (best is None or value > best):
                best = value
    return best


def clean_list(items: list[str], *, limit: int, max_length: int = 60) -> list[str]:
    """Trimmed, de-duplicated (ignoring case), non-empty, bounded: for edits made by hand."""
    seen: dict[str, str] = {}
    for item in items:
        text = " ".join(item.split())[:max_length]
        if text:
            seen.setdefault(text.casefold(), text)
    return list(seen.values())[:limit]
