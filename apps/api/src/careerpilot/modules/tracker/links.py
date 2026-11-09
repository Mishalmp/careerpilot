"""Reading a job link without opening it.

LinkedIn, Indeed, Naukri and Glassdoor forbid automated reading, so a link you paste is never
fetched. What it already says is used: the portal from the host, a clean link from the ids in it,
and the title and company when the address spells them (LinkedIn does: `.../senior-python-
developer-at-acme-3812345678`). Anything the address does not say stays unknown and you fill it in.
"""

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

from careerpilot.modules.tracker.enums import Portal

UNKNOWN_COMPANY = "Unknown company"

# host suffix -> portal. The first matching suffix wins, so list longer names first.
_PORTALS: tuple[tuple[str, Portal], ...] = (
    ("naukrigulf.com", Portal.NAUKRIGULF),
    ("naukri.com", Portal.NAUKRI),
    ("linkedin.com", Portal.LINKEDIN),
    ("indeed.com", Portal.INDEED),
    ("glassdoor.com", Portal.GLASSDOOR),
    ("glassdoor.co.in", Portal.GLASSDOOR),
    ("wellfound.com", Portal.WELLFOUND),
    ("instahyre.com", Portal.INSTAHYRE),
    ("bayt.com", Portal.BAYT),
    ("gulftalent.com", Portal.GULFTALENT),
    ("weworkremotely.com", Portal.WE_WORK_REMOTELY),
    ("himalayas.app", Portal.HIMALAYAS),
    ("remote.com", Portal.REMOTE_COM),
)

# Company career systems put the company name in the first path segment.
_BOARDS = (
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "jobs.lever.co",
    "jobs.ashbyhq.com",
    "apply.workable.com",
    "jobs.smartrecruiters.com",
)

_LINKEDIN_VIEW = re.compile(r"/jobs/view/(?:(?P<slug>[^/?#]*?)-)?(?P<id>\d{6,})(?:/|$)")
_NAUKRI_LISTING = re.compile(r"/job-listings-(?P<slug>.+)-(?P<id>\d{8,})/?$")
_EXPERIENCE = re.compile(r"-?\d+-to-\d+-years?$")


@dataclass(frozen=True)
class LinkGuess:
    portal: Portal
    url: str  # cleaned: no tracking parameters
    title: str
    company: str
    company_known: bool  # False when `company` is the placeholder
    title_known: bool


def _words(slug: str) -> str:
    return " ".join(part.capitalize() for part in re.split(r"[-_+]+", slug) if part)


def _portal_of(host: str) -> Portal:
    host = host.lower().rstrip(".")
    for suffix, portal in _PORTALS:
        if host == suffix or host.endswith("." + suffix):
            return portal
    return Portal.OTHER


def _company_from_host(host: str) -> str:
    labels = host.lower().split(".")
    # careers.acme.com -> acme; acme.co.in -> acme
    core = [
        x for x in labels if x not in {"www", "careers", "jobs", "apply", "com", "co", "in", "io"}
    ]
    return _words(core[-1]) if core else UNKNOWN_COMPANY


def guess_link(url: str) -> LinkGuess:
    """What the address alone says about a job. Never fetches anything."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    portal = _portal_of(host)
    query = parse_qs(parts.query)
    title, company, placeholder = "", "", ""
    clean = f"{parts.scheme}://{parts.netloc}{parts.path}"

    if portal is Portal.LINKEDIN:
        target = parts.path
        job_id = (query.get("currentJobId") or [""])[0]
        if match := _LINKEDIN_VIEW.search(target):
            job_id = match.group("id")
            slug = match.group("slug") or ""
            head, sep, tail = slug.rpartition("-at-")
            if sep:
                title, company = _words(head), _words(tail)
            else:
                title = _words(slug)
        if job_id:
            clean = f"https://www.linkedin.com/jobs/view/{job_id}/"
            placeholder = f"Job on LinkedIn ({job_id})"
    elif portal is Portal.INDEED:
        key = (query.get("jk") or query.get("vjk") or [""])[0]
        if key:
            clean = f"https://{host}/viewjob?jk={key}"
            placeholder = f"Job on Indeed ({key[:8]})"
    elif portal is Portal.NAUKRI:
        if match := _NAUKRI_LISTING.search(parts.path):
            # The address joins title, company and place with hyphens and cannot be split safely;
            # keep it whole as the title so you can see which job it is; fix it when you open it.
            title = _words(_EXPERIENCE.sub("", match.group("slug")))[:120]
    elif host in _BOARDS:
        first = next((s for s in parts.path.split("/") if s), "")
        company = _words(first)
    elif portal is Portal.OTHER and host:
        company = _company_from_host(host)

    if portal is Portal.OTHER and not title:
        last = next((s for s in reversed(parts.path.split("/")) if s), "")
        guess = _words(re.sub(r"^\d+-?|-?\d+$", "", last))
        title = guess if len(guess) > 3 and not guess.isdigit() else ""

    return LinkGuess(
        portal=portal,
        url=clean,
        title=title or placeholder or f"Job on {portal.value}",
        company=company or UNKNOWN_COMPANY,
        company_known=bool(company),
        title_known=bool(title),
    )
