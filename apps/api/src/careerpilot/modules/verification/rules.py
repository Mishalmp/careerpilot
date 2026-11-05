"""The rules that turn evidence into a verdict. Pure functions: no database, no network, no model.

The model never decides the verdict. It can only supply evidence, and code checks the evidence.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from careerpilot.modules.verification.enums import (
    CHECKS,
    FLAGS,
    CheckKey,
    CheckStatus,
    VerdictLabel,
)

MIN_DOMAIN_AGE_DAYS = 365


@dataclass(frozen=True)
class Verdict:
    label: VerdictLabel
    passed: int
    raised_flags: tuple[CheckKey, ...]


def compute_verdict(statuses: Mapping[CheckKey, CheckStatus]) -> Verdict:
    """7 to 8 passes: verified; 5 to 6: likely genuine; 3 to 4: needs check; else suspicious.

    A check that is unknown or failed does not count. A raised red flag forces "suspicious"
    whatever the score is, because a polished website is exactly what a scam would have.
    """
    passed = sum(statuses.get(key) == CheckStatus.PASS for key in CHECKS)
    raised = tuple(key for key in FLAGS if statuses.get(key) == CheckStatus.FAIL)
    if raised:
        label = VerdictLabel.SUSPICIOUS
    elif passed >= 7:
        label = VerdictLabel.VERIFIED
    elif passed >= 5:
        label = VerdictLabel.LIKELY_GENUINE
    elif passed >= 3:
        label = VerdictLabel.NEEDS_CHECK
    else:
        label = VerdictLabel.SUSPICIOUS
    return Verdict(label, passed, raised)


def domain_age_status(registered_on: date, today: date) -> CheckStatus:
    old_enough = (today - registered_on).days >= MIN_DOMAIN_AGE_DAYS
    return CheckStatus.PASS if old_enough else CheckStatus.FAIL


# --- red flags found in a job description -------------------------------------------------

_FREE_MAIL = (
    r"(?:gmail|googlemail|yahoo|ymail|outlook|hotmail|live|rediffmail|icloud|proton|protonmail)"
)
FREE_MAIL_ADDRESS = re.compile(rf"[\w.+-]+@{_FREE_MAIL}\.[a-z.]{{2,}}", re.IGNORECASE)

_FLAG_PATTERNS: dict[CheckKey, re.Pattern[str]] = {
    CheckKey.ASKS_FOR_MONEY: re.compile(
        r"\b(?:registration|processing|security|training|joining|refundable|application|"
        r"onboarding|kit|laptop)\s+(?:fee|fees|deposit|charges?|amount)\b"
        r"|\bpay\s+(?:rs\.?|inr|₹|\$)\s*\d",
        re.IGNORECASE,
    ),
    CheckKey.CHAT_ONLY_HIRING: re.compile(
        r"(?:interview|hiring|apply|contact|send\s+(?:your\s+)?(?:cv|resume)|selection)"
        r"[^.\n]{0,60}\b(?:whatsapp|telegram)\b"
        r"|\b(?:whatsapp|telegram)\b[^.\n]{0,60}(?:interview|hiring|apply|resume|cv)",
        re.IGNORECASE,
    ),
    CheckKey.NO_INTERVIEW: re.compile(
        r"\bno\s+interview\b|\bwithout\s+(?:an?\s+)?interview\b|\bdirect\s+(?:joining|selection)\b"
        r"|\binstant\s+(?:offer|joining|selection)\b|\bselected\s+without\b",
        re.IGNORECASE,
    ),
}

# Genuine postings often warn about scams ("we never ask for a registration fee"). A match with
# one of these words nearby is a warning, not an offence. "No interview" is itself a negation, so
# for that flag only scam-warning words count.
_NEGATION = re.compile(
    r"\b(?:no|not|never|nor|without|don'?t|do\s+not|doesn'?t|zero|free\s+of)\b", re.IGNORECASE
)
_SCAM_WORDS = re.compile(r"\b(?:beware|scams?|fraud\w*|fake|avoid|cheat\w*)\b", re.IGNORECASE)
_CONTEXT = 80


def _is_warning(key: CheckKey, text: str, match: re.Match[str]) -> bool:
    around = text[max(0, match.start() - _CONTEXT) : match.end() + _CONTEXT // 2]
    if _SCAM_WORDS.search(around):
        return True
    return key is not CheckKey.NO_INTERVIEW and _NEGATION.search(around) is not None


def scan_job_text(text: str) -> dict[CheckKey, str]:
    """Red flags a job description states outright, each with the exact words that triggered it."""
    found: dict[CheckKey, str] = {}
    for key, pattern in _FLAG_PATTERNS.items():
        for match in pattern.finditer(text):
            if not _is_warning(key, text, match):
                found[key] = _snippet(text, match)
                break
    mail = FREE_MAIL_ADDRESS.search(text)
    if mail:
        found[CheckKey.FREE_MAIL_RECRUITER] = _snippet(text, mail)
    return found


def _snippet(text: str, match: re.Match[str]) -> str:
    """The matched words plus a little context, cut so it stays one readable line."""
    start = max(0, match.start() - 30)
    return " ".join(text[start : match.end() + 30].split())
