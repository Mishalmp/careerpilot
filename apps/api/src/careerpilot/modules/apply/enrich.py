"""Finding out what a job pays and how its interviews go, step by step, and saying where each
answer came from. No database: the service hands in the facts and the web helper; this returns
the evidence.

The order, and what each step may use, is in `chain.py`. Money is never converted between
currencies, a page is only opened when the step before it found nothing, and sites that forbid
automation are listed as links but never read.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from careerpilot.core.search import SearchHit
from careerpilot.modules.apply import chain
from careerpilot.modules.apply.chain import PaySource
from careerpilot.modules.apply.enums import InterviewLevel, ListingKind, PayLevel
from careerpilot.modules.apply.matching import requirement_overlap, similar_titles
from careerpilot.modules.apply.pay import PayFigure
from careerpilot.modules.apply.schemas import (
    AlsoListed,
    EvidenceLink,
    InterviewNotes,
    PayEstimate,
    TriedStep,
)
from careerpilot.modules.apply.web import JobWeb

MAX_LISTING_PAGES = 2
MAX_LISTINGS_SHOWN = 6


@dataclass(frozen=True)
class JobFacts:
    title: str
    company: str
    region: str | None
    salary_text: str | None
    est_ctc_lpa: float | None
    jd_text: str | None
    jd_url: str | None
    own_urls: frozenset[str]  # this post's own addresses, so it is not reported as "also listed"
    skills: list[str]


@dataclass(frozen=True)
class PoolEntry:
    """A job in your tracker with an estimated CTC, used for earlier-post and market ranges."""

    company: str
    title: str
    lpa: float
    url: str | None
    job_id: uuid.UUID | None = None  # so a job is never its own earlier post


@dataclass
class Enrichment:
    pay: PayEstimate
    interview: InterviewNotes
    also_listed: list[AlsoListed]


def _found(text: str, count: int, what: str) -> TriedStep:
    return TriedStep(label=text, found=count > 0, note=what)


def _pool_sources(entries: list[PoolEntry]) -> list[PaySource]:
    return [
        PaySource(
            PayFigure("INR", e.lpa * 100_000, None, f"Est. CTC {e.lpa:g} LPA in your tracker"),
            e.url,
            f"{e.company} - {e.title} (your tracker)",
        )
        for e in entries
    ]


def _snippet_pay(hit: SearchHit) -> list[PaySource]:
    return chain.pay_sources(f"{hit.title}. {hit.snippet}", hit.url, hit.title)


async def _pay_from_hits(
    hits: list[SearchHit], web: JobWeb, *, read_pages: bool
) -> tuple[list[PaySource], int]:
    """Figures in the search results, then (if none and allowed) in the pages themselves."""
    usable = [h for h in hits if web.readable(h.url)]
    found = [source for hit in usable for source in _snippet_pay(hit)]
    if found or not read_pages:
        return found, len(usable)
    for hit in usable:
        text = await web.page(hit.url)
        if text:
            found.extend(chain.pay_sources(text, hit.url, hit.title))
        if web.pages_left <= 0:
            break
    return found, len(usable)


async def _listings(
    job: JobFacts, web: JobWeb, skills_of: Callable[[str], set[str]]
) -> tuple[list[AlsoListed], list[PaySource], list[PaySource]]:
    """Where else this company lists this role. Returns the listings, plus pay figures seen on them
    split into the same job and a similar role."""
    if not web.can_search:
        return [], [], []
    hits = await web.search(f"{job.title} {job.company} job")
    if not hits:
        return [], [], []
    candidates: list[SearchHit] = []
    seen: set[str] = set(job.own_urls)
    for hit in hits:
        if hit.url in seen:
            continue
        seen.add(hit.url)
        if not chain.mentions_company(job.company, hit.title, hit.snippet, chain.host_of(hit.url)):
            continue
        if not similar_titles(job.title, chain.role_part(hit.title, job.company)):
            continue
        candidates.append(hit)
    candidates.sort(
        key=lambda h: not chain.same_title(job.title, chain.role_part(h.title, job.company))
    )  # equal titles first
    listings: list[AlsoListed] = []
    same_pay: list[PaySource] = []
    similar_pay: list[PaySource] = []
    pages_read = 0
    for hit in candidates[:MAX_LISTINGS_SHOWN]:
        overlap: float | None = None
        text: str | None = None
        if web.readable(hit.url) and pages_read < MAX_LISTING_PAGES and web.pages_left > 0:
            text = await web.page(hit.url)
            pages_read += 1
            if text:
                overlap = requirement_overlap(job.skills, skills_of(text))
        kind = chain.listing_kind(job.title, chain.role_part(hit.title, job.company), overlap)
        listings.append(
            AlsoListed(
                url=hit.url,
                title=hit.title,
                host=chain.host_of(hit.url),
                kind=kind,
                overlap=None if overlap is None else round(overlap, 2),
                opened=text is not None,
            )
        )
        if web.readable(hit.url):  # a snippet from a blocked site is never used as evidence
            figures = _snippet_pay(hit) + (
                chain.pay_sources(text, hit.url, hit.title) if text else []
            )
            (same_pay if kind is ListingKind.SAME_JOB else similar_pay).extend(figures)
    return listings, same_pay, similar_pay


async def find_pay_for(
    job: JobFacts,
    pool: list[PoolEntry],
    web: JobWeb,
    listings: list[AlsoListed],
    same_pay: list[PaySource],
    similar_pay: list[PaySource],
) -> PayEstimate:
    tried: list[TriedStep] = []

    # 1. this post
    posted = chain.pay_sources(job.salary_text or "", job.jd_url, "This post (salary field)")
    posted += chain.pay_sources(job.jd_text or "", job.jd_url, "This post (description)")
    tried.append(
        _found(
            "This post",
            len(posted),
            "A pay figure is written in the post."
            if posted
            else "The post does not state the pay.",
        )
    )
    if posted:
        return chain.build_pay(PayLevel.POSTED, posted, tried) or chain.no_pay(tried)
    if job.est_ctc_lpa:
        own = PaySource(
            PayFigure("INR", job.est_ctc_lpa * 100_000, None, f"Est. CTC {job.est_ctc_lpa:g} LPA"),
            None,
            "Your tracker entry for this job",
        )
        tried.append(_found("Your own estimate", 1, "You entered an estimated CTC for this job."))
        return chain.build_pay(
            PayLevel.POSTED,
            [own],
            tried,
            label="Your own estimate for this job (not from the post)",
        ) or chain.no_pay(tried)

    # 2. the same job on another site
    n_same = sum(1 for x in listings if x.kind is ListingKind.SAME_JOB)
    tried.append(
        _found(
            "The same job on other sites",
            len(same_pay),
            f"{n_same} listing(s) found; "
            + ("a figure is on them." if same_pay else "none shows a pay figure."),
        )
    )
    if same_pay:
        return chain.build_pay(PayLevel.SAME_JOB_ELSEWHERE, same_pay, tried) or chain.no_pay(tried)

    # 3. an earlier or similar post by the same company
    earlier = _pool_sources(
        [
            e
            for e in pool
            if chain.mentions_company(job.company, e.company) and similar_titles(job.title, e.title)
        ]
    )
    earlier += similar_pay
    searched = False
    if not earlier and web.can_search:
        searched = True
        hits = await web.search(f"{job.title} {job.company} salary")
        company_hits = [
            h
            for h in hits or []
            if chain.mentions_company(job.company, h.title, h.snippet, chain.host_of(h.url))
        ]
        found, _ = await _pay_from_hits(company_hits, web, read_pages=True)
        earlier += found
    tried.append(
        _found(
            "Earlier or similar posts by this company",
            len(earlier),
            (
                "Found in your tracker or on the web."
                if earlier
                else "Nothing in your tracker"
                + (" and nothing on the web." if searched else " (the web was not searched).")
            ),
        )
    )
    if earlier:
        return chain.build_pay(PayLevel.PREVIOUS_POST, earlier, tried) or chain.no_pay(tried)

    # 4. similar roles at other companies
    market = _pool_sources(
        [
            e
            for e in pool
            if not chain.mentions_company(job.company, e.company)
            and similar_titles(job.title, e.title)
        ]
    )
    searched = False
    if not market and web.can_search:
        searched = True
        where = f" {job.region}" if job.region else ""
        hits = await web.search(f"{job.title} salary{where}")
        role_hits = [h for h in hits or [] if similar_titles(job.title, h.title)]
        found, _ = await _pay_from_hits(role_hits, web, read_pages=True)
        market += found
    tried.append(
        _found(
            "Similar roles at other companies",
            len(market),
            "Found in your tracker or on the web."
            if market
            else "Nothing in your tracker"
            + (" and nothing on the web." if searched else " (the web was not searched)."),
        )
    )
    return chain.build_pay(PayLevel.SIMILAR_ROLES, market, tried) or chain.no_pay(tried)


def _points(text: str, url: str | None, title: str) -> list[EvidenceLink]:
    return [
        EvidenceLink(url=url, title=title, quote=sentence)
        for sentence in chain.interview_sentences(text)
    ]


async def _interview_from_hits(hits: list[SearchHit], web: JobWeb) -> list[EvidenceLink]:
    usable = [h for h in hits if web.readable(h.url)]
    points: list[EvidenceLink] = []
    for hit in usable:
        points.extend(_points(f"{hit.title}. {hit.snippet}", hit.url, hit.title))
    if points:
        return points[: chain.MAX_POINTS * 2]
    for hit in usable:
        text = await web.page(hit.url)
        if text:
            points.extend(_points(text, hit.url, hit.title))
        if points or web.pages_left <= 0:
            break
    return points[: chain.MAX_POINTS * 2]


async def find_interview_for(job: JobFacts, web: JobWeb) -> InterviewNotes:
    tried: list[TriedStep] = []

    # 1. this post
    posted = _points(job.jd_text or "", job.jd_url, "This post")
    tried.append(
        _found(
            "This post",
            len(posted),
            "The post describes the process." if posted else "The post says nothing about it.",
        )
    )
    notes = chain.build_interview(InterviewLevel.POSTED, posted, tried)
    if notes:
        return notes

    # 2. this company's process on a page
    company_points: list[EvidenceLink] = []
    searched = False
    if web.can_search:
        searched = True
        hits = await web.search(f"{job.company} interview process {job.title}")
        mine = [
            h
            for h in hits or []
            if chain.mentions_company(job.company, h.title, h.snippet, chain.host_of(h.url))
        ]
        company_points = await _interview_from_hits(mine, web)
    tried.append(
        _found(
            "This company's interview process",
            len(company_points),
            "Described on a page."
            if company_points
            else "Nothing found" + ("." if searched else " (the web was not searched)."),
        )
    )
    notes = chain.build_interview(InterviewLevel.THIS_COMPANY, company_points, tried)
    if notes:
        return notes

    # 3. similar roles elsewhere
    typical: list[EvidenceLink] = []
    searched = False
    if web.can_search:
        searched = True
        hits = await web.search(f"{job.title} interview process rounds questions")
        typical = await _interview_from_hits(
            [h for h in hits or [] if similar_titles(job.title, h.title)], web
        )
    tried.append(
        _found(
            "Similar roles elsewhere",
            len(typical),
            "A typical process is described on a page."
            if typical
            else "Nothing found" + ("." if searched else " (the web was not searched)."),
        )
    )
    return chain.build_interview(
        InterviewLevel.SIMILAR_ROLES, typical, tried
    ) or chain.no_interview(tried)


async def enrich(
    job: JobFacts,
    pool: list[PoolEntry],
    web: JobWeb,
    skills_of: Callable[[str], set[str]],
) -> Enrichment:
    listings, same_pay, similar_pay = await _listings(job, web, skills_of)
    pay = await find_pay_for(job, pool, web, listings, same_pay, similar_pay)
    interview = await find_interview_for(job, web)
    return Enrichment(pay=pay, interview=interview, also_listed=listings)
