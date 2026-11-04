"""Names and URLs normalised so the same job entered twice is recognised as one."""

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit

_LEGAL_SUFFIXES = frozenset(
    {
        "pvt",
        "private",
        "ltd",
        "limited",
        "inc",
        "incorporated",
        "llc",
        "llp",
        "gmbh",
        "corp",
        "corporation",
        "co",
        "plc",
        "ag",
        "bv",
        "sa",
    }
)
_TRACKING_PARAMS = frozenset(
    {"fbclid", "gclid", "ref", "refid", "trk", "trackingid", "src", "source", "utm_source"}
)


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def normalize_company(name: str) -> str:
    """'Mareana Software India Pvt. Ltd.' and 'mareana software india' match."""
    words = re.sub(r"[^\w\s]", " ", name.casefold()).split()
    while len(words) > 1 and words[-1] in _LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)


def canonical_url(url: str | None) -> str:
    """Drop the scheme, fragment and tracking parameters; keep parameters that identify a job."""
    if not url:
        return ""
    parts = urlsplit(url.strip())
    kept = sorted(
        (key, value)
        for key, value in parse_qsl(parts.query)
        if key.lower() not in _TRACKING_PARAMS and not key.lower().startswith("utm_")
    )
    path = parts.path.rstrip("/")
    query = f"?{urlencode(kept)}" if kept else ""
    return f"{parts.netloc.lower()}{path}{query}"


def job_fingerprint(
    company_name: str, title: str, location: str | None, apply_url: str | None
) -> str:
    key = "|".join(
        [
            normalize_company(company_name),
            _squash(title),
            _squash(location or ""),
            canonical_url(apply_url),
        ]
    )
    return hashlib.sha256(key.encode()).hexdigest()
