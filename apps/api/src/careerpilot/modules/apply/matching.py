"""How well a job matches you, and whether two job titles are the same kind of role. Pure.

The match score is deliberately simple and explained in words: 60 points for the share of the job's
skills you have, 30 for a role title like one on your CV, 10 for being fresh. It orders a short
list for you to read; it does not decide anything, and it is not the older "fit score".
"""

import re
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date

SKILL_POINTS = 60
TITLE_POINTS = 30
FRESH_POINTS = 10
FRESH_DAYS = 14
_LEVEL = frozenset(
    {"senior", "sr", "junior", "jr", "lead", "principal", "staff", "associate", "trainee", "intern"}
    | {"i", "ii", "iii", "iv", "1", "2", "3", "4", "level", "l1", "l2", "l3", "mid"}
)
_ROLE_WORDS = frozenset("developer engineer programmer sde swe sdet".split())  # noqa: SIM905
_TOKEN = re.compile(r"[a-z0-9+#.]+")
# Words that say little about the field: a "Software Engineer" is close to most engineering titles.
_GENERIC = frozenset(
    {"software", "web", "application", "applications", "systems", "technology"}
    | {"full", "stack", "fullstack"}
)


def title_tokens(title: str) -> tuple[frozenset[str], bool]:
    """(the words that describe the field, whether it names an engineering role at all).
    "Senior Python Backend Developer II" -> ({"python", "backend"}, True)."""
    text = title.casefold().replace("back-end", "backend").replace("front-end", "frontend")
    words = [w for w in _TOKEN.findall(text) if w not in _LEVEL]
    is_role = any(w in _ROLE_WORDS for w in words)
    return frozenset(w for w in words if w not in _ROLE_WORDS and w not in _GENERIC), is_role


def similar_titles(a: str, b: str) -> bool:
    """Same kind of role: both name an engineering role, and their field words overlap, or one of
    them has no field word (a plain "Software Engineer" is close to any engineering title)."""
    fa, ra = title_tokens(a)
    fb, rb = title_tokens(b)
    if not (ra and rb):
        return False
    if not fa or not fb:
        return True
    return len(fa & fb) / min(len(fa), len(fb)) >= 0.5  # share at least half of the shorter one


@dataclass(frozen=True)
class Match:
    score: int
    reasons: list[str]
    job_skills: list[str]
    shared_skills: list[str]


def match(
    *,
    job_title: str,
    job_skills: Collection[str],
    profile_skills: Collection[str],
    profile_titles: Collection[str],
    posted_on: date | None,
    today: date,
) -> Match:
    mine = {s.casefold() for s in profile_skills}
    wanted = sorted({s.casefold() for s in job_skills})
    shared = [s for s in wanted if s in mine]
    reasons: list[str] = []
    if wanted:
        skill_points = round(SKILL_POINTS * len(shared) / len(wanted))
        reasons.append(
            f"You have {len(shared)} of the {len(wanted)} skills it names "
            f"({', '.join(shared) or 'none'})."
        )
    else:
        skill_points = SKILL_POINTS // 2  # nothing to compare: neutral, and say so
        reasons.append(
            "The post names no skills I recognise, so the skill match is a neutral guess."
        )
    title_points = 0
    for title in profile_titles:
        if similar_titles(job_title, title):
            title_points = TITLE_POINTS
            reasons.append(f"The title is like one on your CV ({title}).")
            break
    else:
        reasons.append("The title is not like any role on your CV.")
    if posted_on is None:
        fresh = FRESH_POINTS // 2
        reasons.append("No posting date, so freshness is a neutral guess.")
    elif (today - posted_on).days <= FRESH_DAYS:
        fresh = FRESH_POINTS
        reasons.append(f"Posted {(today - posted_on).days} days ago.")
    else:
        fresh = 0
        reasons.append(f"Posted {(today - posted_on).days} days ago (older than {FRESH_DAYS}).")
    return Match(
        score=min(100, skill_points + title_points + fresh),
        reasons=reasons,
        job_skills=wanted,
        shared_skills=shared,
    )


def requirement_overlap(a: Collection[str], b: Collection[str]) -> float | None:
    """Share of skills two postings have in common (Jaccard). None when neither names any."""
    sa, sb = {s.casefold() for s in a}, {s.casefold() for s in b}
    if not sa and not sb:
        return None
    return len(sa & sb) / len(sa | sb)
