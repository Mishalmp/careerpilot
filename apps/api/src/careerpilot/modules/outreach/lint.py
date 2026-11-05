"""Flags AI-sounding or generic outreach drafts. Ported from the standalone `outreach_lint.py`.

It checks form, not truth: a person still verifies every fact and number, and reads the draft
aloud. The same rules as the script, plus a word range per channel.
"""

import difflib
import re
from collections.abc import Sequence
from dataclasses import dataclass

from careerpilot.modules.outreach.enums import Channel

STOCK = (
    "i hope this email finds you well",
    "i am writing to express",
    "i'm writing to express",
    "i am excited to",
    "i'm excited to",
    "i am thrilled",
    "i'm thrilled",
    "passionate about",
    "passion for",
    "proven track record",
    "detail-oriented",
    "results-driven",
    "team player",
    "dynamic",
    "esteemed",
    "cutting-edge",
    "state-of-the-art",
    "leverage",
    "leveraging",
    "delve",
    "synergy",
    "spearhead",
    "seamless",
    "robust solutions",
    "fast-paced",
    "game-changer",
    "unique opportunity",
    "perfect fit",
    "ideal candidate",
    "world-class",
    "thought leader",
    "in today's",
    "in the ever-evolving",
    "i believe i would be",
    "i would be a great",
    "look forward to the opportunity",
    "at your earliest convenience",
    "do not hesitate",
    "kindly",
    "please find attached my resume for your consideration",
    "to whom it may concern",
    "dear sir",
    "dear hiring manager",
)
OPENERS = ("i am writing", "i'm writing", "my name is", "i hope", "greetings", "dear sir")
CONTRACTIONS = re.compile(r"\b\w+['’](s|re|ve|ll|d|t|m)\b", re.IGNORECASE)
# Numbers the lint does not question: today's year and next, and small counts.
DEFAULT_ALLOWED_NUMBERS = frozenset({"1", "2", "3", "10", "15", "20", "31", "2026", "2027"})

# (flag when fewer, flag when more, the range to aim for)
WORD_RANGES: dict[Channel, tuple[int, int, str]] = {
    Channel.EMAIL: (70, 150, "90 to 130"),
    Channel.RECRUITER_MESSAGE: (35, 90, "50 to 70"),
    Channel.REFERRAL_REQUEST: (45, 150, "60 to 120"),
}
SIMILARITY_LIMIT = 0.55


@dataclass(frozen=True)
class LintResult:
    words: int
    flags: list[str]


def _sentences(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", text) if p.strip()]


def lint(
    body: str,
    *,
    subject: str = "",
    company: str = "",
    facts: list[str],
    channel: Channel = Channel.EMAIL,
    allowed_numbers: frozenset[str] = DEFAULT_ALLOWED_NUMBERS,
    others: Sequence[tuple[str, str]] = (),
) -> LintResult:
    """`others` are (name, body) pairs of your other drafts, to catch copy-paste templates."""
    flags: list[str] = []
    words = re.findall(r"[A-Za-z0-9'’-]+", body)
    count = len(words)
    low_limit, high_limit, aim = WORD_RANGES[channel]
    if count < low_limit:
        flags.append(f"too short ({count} words); aim {aim}")
    elif count > high_limit:
        flags.append(f"too long ({count} words); aim {aim}")

    lowered = body.lower()
    flags.extend(f"stock phrase: '{phrase}'" for phrase in STOCK if phrase in lowered)

    lines = [line for line in body.strip().splitlines() if line.strip()]
    if len(lines) > 1 and lines[1].lower().startswith(OPENERS):
        flags.append("generic opening line")
    if "—" in body or "–" in body:
        flags.append("dash used as punctuation (long or en dash); use a comma, full stop or colon")
    if "!" in body:
        flags.append("exclamation mark")

    sentences = _sentences(body)
    long_sentences = [s for s in sentences if len(s.split()) > 28]
    if long_sentences:
        flags.append(f"{len(long_sentences)} sentence(s) over 28 words; shorten")
    if len(sentences) >= 4:
        starts_with_i = sum(
            1 for s in sentences if re.match(r"^(i|i'm|i’m|i've|i’ve)\b", s.lower())
        )
        if starts_with_i / len(sentences) > 0.5:
            flags.append("more than half the sentences start with 'I'")
    if count >= 80 and not CONTRACTIONS.search(body):
        flags.append("no contractions anywhere; reads stiff")

    if company and company.lower() not in lowered:
        flags.append(f"company name '{company}' not mentioned")
    flags.extend(
        f"expected specific detail missing: '{fact}'"
        for fact in facts
        if fact.lower() not in lowered
    )
    if not facts:
        flags.append("no specific fact supplied: nothing to tie this draft to the company or role")

    numbers = set(re.findall(r"\b\d[\d,.]*\b", body))
    unverified = sorted(n for n in numbers if n not in allowed_numbers)
    if unverified:
        flags.append("numbers to verify against real evidence: " + ", ".join(unverified))
    if len(re.findall(r"\b[\w-]+, [\w-]+,? and [\w-]+\b", body)) >= 2:
        flags.append("repeated lists of three; vary the rhythm")

    if subject:
        if len(subject) > 70:
            flags.append("subject longer than 70 characters")
        if re.match(r"(?i)^(application|job application|applying)\b", subject):
            flags.append("generic subject; name the role and one concrete hook")

    mine = re.sub(r"\s+", " ", lowered)
    for name, other in others:
        ratio = difflib.SequenceMatcher(None, mine, re.sub(r"\s+", " ", other.lower())).ratio()
        if ratio > SIMILARITY_LIMIT:
            flags.append(f"{ratio:.0%} similar to {name}: looks like a template")
    return LintResult(count, flags)
