"""Finding the hiring addresses a company publishes on its own website. No model, no guessing.

Only role addresses (careers@, jobs@, hr@, ...) on the company's own domain are taken, and only
from a page that shows them; the page is kept as the source, which is what makes a contact
"published". Addresses of named people are left alone even when a page lists them. Pages are
read through the safe fetcher (private addresses and the sites that forbid automation are refused).
"""

import re
from urllib.parse import urljoin, urlsplit

from careerpilot.core.fetcher import Fetcher, FetchError

# The part before the @ that marks an address meant for applicants or enquiries.
ROLE_ADDRESSES = frozenset(
    {
        "careers",
        "career",
        "jobs",
        "job",
        "hr",
        "hiring",
        "recruitment",
        "recruiting",
        "recruiter",
        "recruiters",
        "talent",
        "people",
        "join",
        "apply",
        "work",
        "contact",
        "hello",
        "info",
    }
)
PAGES = ("/", "/careers", "/jobs", "/contact", "/contact-us", "/about", "/about-us")
MAX_PAGES = 5
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def site_domain(website: str) -> str | None:
    """`https://www.acme.co.in/x` -> `acme.co.in`: the host without a leading www."""
    host = (urlsplit(website if "//" in website else f"//{website}").hostname or "").lower()
    host = host.removeprefix("www.")
    return host or None


def role_addresses(text: str, domain: str) -> list[str]:
    """Role addresses at `domain` (or a subdomain of it) found in `text`, in order, no repeats."""
    found: list[str] = []
    for match in _EMAIL.findall(text):
        local, _, host = match.lower().rpartition("@")
        on_domain = host == domain or host.endswith("." + domain)
        if on_domain and local in ROLE_ADDRESSES and match.lower() not in found:
            found.append(match.lower())
    return found


async def find_on_site(
    fetcher: Fetcher, website: str, *, max_pages: int = MAX_PAGES
) -> tuple[list[tuple[str, str]], int, list[str]]:
    """(address, page) pairs, pages read, and notes on pages that failed."""
    domain = site_domain(website)
    if domain is None:
        return [], 0, ["The company website is not a usable address."]
    base = f"https://{domain}/"
    found: list[tuple[str, str]] = []
    notes: list[str] = []
    read = 0
    for path in PAGES[:max_pages]:
        url = urljoin(base, path.lstrip("/"))
        try:
            page = await fetcher.fetch(url)
        except FetchError as exc:
            notes.append(f"{url}: {exc.message}")
            continue
        read += 1
        for address in role_addresses(page.text, domain):
            if address not in {a for a, _ in found}:
                found.append((address, page.url))
    return found, read, notes
