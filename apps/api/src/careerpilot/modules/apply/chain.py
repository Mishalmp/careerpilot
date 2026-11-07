"""Turning what was found into pay and interview evidence. Pure functions: no network, no database.

Pay and interview information is looked for in a fixed order, best evidence first, and the first
level with an answer is reported together with the levels that had none:

  pay        1 this post          2 the same job on another site
             3 an earlier or similar post by the same company
             4 similar roles at other companies (a market range, not this company)
  interview  1 the post itself    2 this company's process, as described on a page
             3 similar roles elsewhere (typical, not this company)

No model reads any of this: figures and sentences are found by rules, and each is reported with the
words it came from, so there is nothing to hallucinate.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit

from careerpilot.modules.apply import pay as paymod
from careerpilot.modules.apply.enums import InterviewLevel, ListingKind, PayLevel
from careerpilot.modules.apply.matching import title_tokens
from careerpilot.modules.apply.schemas import (
    EvidenceLink,
    InterviewNotes,
    PayEstimate,
    TriedStep,
)

PAY_LABELS: dict[PayLevel, str] = {
    PayLevel.POSTED: "Stated in this post",
    PayLevel.SAME_JOB_ELSEWHERE: "The same job, listed on another site",
    PayLevel.PREVIOUS_POST: "An earlier or similar post by this company",
    PayLevel.SIMILAR_ROLES: "Similar roles at other companies (a market range, not this company)",
}
INTERVIEW_LABELS: dict[InterviewLevel, str] = {
    InterviewLevel.POSTED: "Stated in this post",
    InterviewLevel.THIS_COMPANY: "This company's process, as described on a page",
    InterviewLevel.SIMILAR_ROLES: "Typical for this kind of role (not this company)",
}
SAME_JOB_OVERLAP = 0.6  # skills in common at which two postings are treated as the same job
MAX_EVIDENCE = 5
MAX_POINTS = 3

_LEGAL = frozenset({"pvt", "private", "ltd", "limited", "inc", "llc", "llp", "corp"})
_LEGAL_MORE = frozenset({"corporation", "co", "plc", "gmbh", "ag", "sa"})
_GENERIC_TAIL = frozenset({"technologies", "technology", "solutions", "software", "labs"})
_GENERIC_TAIL_MORE = frozenset({"systems", "services"})
_WORD = re.compile(r"[a-z0-9]+")


def company_key(name: str) -> str:
    """The part of a company name other pages are likely to use: "Acme Technologies Pvt. Ltd" ->
    "acme". Empty when too little is left to match safely."""
    words = _WORD.findall(name.casefold())
    while words and words[-1] in _LEGAL | _LEGAL_MORE:
        words.pop()
    if len(words) > 1 and words[-1] in _GENERIC_TAIL | _GENERIC_TAIL_MORE:
        words.pop()
    key = " ".join(words)
    return key if len(key) >= 3 else ""


def mentions_company(company: str, *texts: str) -> bool:
    key = company_key(company)
    if not key:
        return False
    pattern = re.compile(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])")
    return any(pattern.search(" ".join(_WORD.findall(text.casefold()))) for text in texts)


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").removeprefix("www.")


_TITLE_PARTS = re.compile(r"\s+[-|@–—]\s+|\s+at\s+|,\s+|\s*\|\s*", re.IGNORECASE)


def role_part(listing_title: str, company: str) -> str:
    """The job title inside a page title: "Python Developer - Acme | Naukri" -> "Python Developer".
    The first part that names an engineering role and not the company; the whole title otherwise."""
    for part in _TITLE_PARTS.split(listing_title):
        if title_tokens(part)[1] and not mentions_company(company, part):
            return part
    return listing_title


def same_title(a: str, b: str) -> bool:
    """Equal once level words ("Senior", "II") and punctuation are ignored."""
    words_a, _ = title_tokens(a)
    words_b, _ = title_tokens(b)
    return bool(words_a or words_b) and words_a == words_b


def listing_kind(job_title: str, hit_title: str, overlap: float | None) -> ListingKind:
    """Is a listing of the same company the same job or only a similar one?

    The same job when the pages share most of their skills, or (when the page was not read) the
    titles are equal. Anything else from the same company is a similar role."""
    if overlap is not None:
        return ListingKind.SAME_JOB if overlap >= SAME_JOB_OVERLAP else ListingKind.SIMILAR_ROLE
    return ListingKind.SAME_JOB if same_title(job_title, hit_title) else ListingKind.SIMILAR_ROLE


# --- pay ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PaySource:
    figure: paymod.PayFigure
    url: str | None
    title: str


def pay_sources(text: str, url: str | None, title: str) -> list[PaySource]:
    return [PaySource(figure, url, title) for figure in paymod.find_pay(text)]


def build_pay(
    level: PayLevel,
    sources: Sequence[PaySource],
    tried: list[TriedStep],
    *,
    label: str | None = None,
) -> PayEstimate | None:
    """The estimate for one level, or None when it has no figures. One currency only: rupee
    figures when there are any, otherwise the most common currency. Nothing is converted."""
    if not sources:
        return None
    by_currency: dict[str, list[PaySource]] = {}
    for source in sources:
        by_currency.setdefault(source.figure.currency, []).append(source)
    currency = (
        "INR" if "INR" in by_currency else max(by_currency, key=lambda c: (len(by_currency[c]), c))
    )
    chosen = by_currency[currency]
    if level is PayLevel.POSTED:
        # One post: report its own range as written, not a statistic.
        ends = [v for s in chosen for v in (s.figure.low, s.figure.high) if v is not None]
        low, high = min(ends), max(ends)
        mid, count = (low + high) / 2, 1
    else:
        # Several posts: where the bottoms of the ranges sit and where the tops sit (the middle half
        # when there are at least four posts), and the median of their middles.
        lows = paymod.summarise([s.figure.low for s in chosen])
        highs = paymod.summarise([s.figure.high or s.figure.low for s in chosen])
        mids = paymod.summarise(
            [(s.figure.low + (s.figure.high or s.figure.low)) / 2 for s in chosen]
        )
        if lows is None or highs is None or mids is None:  # unreachable: `chosen` is not empty
            return None
        low, mid, high, count = lows.low, mids.mid, highs.high, mids.n
    seen: set[tuple[str | None, str]] = set()
    evidence: list[EvidenceLink] = []
    for s in chosen:
        if (s.url, s.figure.quote) in seen or len(evidence) >= MAX_EVIDENCE:
            continue
        seen.add((s.url, s.figure.quote))
        evidence.append(EvidenceLink(url=s.url, title=s.title, quote=s.figure.quote))
    return PayEstimate(
        level=level,
        label=label or PAY_LABELS[level],
        currency=currency,
        low=low,
        mid=mid,
        high=high,
        n=count,
        evidence=evidence,
        tried=tried,
    )


def no_pay(tried: list[TriedStep]) -> PayEstimate:
    return PayEstimate(
        level=None,
        label="No pay information found",
        currency=None,
        low=None,
        mid=None,
        high=None,
        n=0,
        evidence=[],
        tried=tried,
    )


# --- interview information ----------------------------------------------------------------

_SENTENCES = re.compile(r"(?<=[.!?])\s+|\n+")
# A sentence must name the process itself ...
_ANCHORS = re.compile(
    r"\b(interviews?|rounds?|screening|assessment|hackerrank|take[- ]home|coding (?:test|challenge)"
    r"|machine coding|online test|selection process|hiring process)\b",
    re.IGNORECASE,
)
# ... and these make it more informative.
_DETAILS = re.compile(
    r"\b(system design|data structures|dsa|algorithms?|live coding|pair programming|whiteboard"
    r"|technical|hr|managerial|manager|panel|behavioural|behavioral|onsite|virtual|stages?"
    r"|low[- ]level design|lld|hld|leetcode|sql|project discussion|coding|design|recruiter"
    r"|phone screen|screening call|assignment|concurrency)\b",
    re.IGNORECASE,
)
_MIN_SENTENCE, _MAX_SENTENCE = 40, 300
MIN_WORDS = 7
# A page title or a marketing line also says "interview" ("Databricks Interview Questions | X").
_NOT_A_DESCRIPTION = re.compile(
    r"\||questions (?:and|&) answers|take a mock interview|friendly reminder|\bfor freshers\b"
    r"|insider insights|read more|sign up|subscribe",
    re.IGNORECASE,
)


def interview_sentences(text: str, limit: int = MAX_POINTS) -> list[str]:
    """The sentences of `text` that best describe an interview process, best first. Each one is
    copied from the text as it stands, so it can always be found on the page it came from."""
    scored: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for position, raw in enumerate(_SENTENCES.split(text)):
        sentence = " ".join(raw.split())
        if not _MIN_SENTENCE <= len(sentence) <= _MAX_SENTENCE or sentence.casefold() in seen:
            continue
        anchors = len({m.group(0).casefold() for m in _ANCHORS.finditer(sentence)})
        if anchors == 0 or len(sentence.split()) < MIN_WORDS or _NOT_A_DESCRIPTION.search(sentence):
            continue
        details = len({m.group(0).casefold() for m in _DETAILS.finditer(sentence)})
        if details == 0:
            continue  # it names the process but says nothing about it
        seen.add(sentence.casefold())
        scored.append((-(2 * anchors + details), position, sentence))
    return [sentence for _, _, sentence in sorted(scored)[:limit]]


def build_interview(
    level: InterviewLevel, points: Sequence[EvidenceLink], tried: list[TriedStep]
) -> InterviewNotes | None:
    if not points:
        return None
    return InterviewNotes(
        level=level,
        label=INTERVIEW_LABELS[level],
        points=list(points)[: MAX_POINTS * 2],
        tried=tried,
    )


def no_interview(tried: list[TriedStep]) -> InterviewNotes:
    return InterviewNotes(
        level=None, label="No interview information found", points=[], tried=tried
    )
