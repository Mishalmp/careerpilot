"""What the company check says, in the words the list shows, and when it holds a job back.

A job is held back only on hard evidence: a raised red flag (asks for money, chat-only hiring, no
interview, a free-mail recruiter), or at least two checks that were looked up and failed. Missing
information never holds a job back: most companies pass only a few of the eight checks without
you adding evidence, so "few passed" alone would hold back almost everything.
"""

from careerpilot.modules.apply.schemas import CompanyCheckSummary
from careerpilot.modules.verification.enums import CheckStatus
from careerpilot.modules.verification.schemas import VerificationOut

FAILED_CHECKS_TO_HOLD = 2


def summarise(check: VerificationOut) -> tuple[CompanyCheckSummary, str | None]:
    """(what to show, why the job is held back or None)."""
    looked_up = [c for c in check.checks if c.kind == "check" and c.status != CheckStatus.UNKNOWN]
    flags = [key.value for key in check.raised_flags]
    failed = [c for c in looked_up if c.status == CheckStatus.FAIL]
    if not looked_up and not flags:
        return (
            CompanyCheckSummary(
                verdict="not_checked",
                passed=0,
                total=check.total,
                flags=[],
                note="Nothing about this company could be checked (no website on file, or it "
                "did not answer). Look at it yourself before you apply.",
            ),
            None,
        )
    reason: str | None = None
    if flags:
        reason = "Red flag raised: " + ", ".join(f.replace("_", " ") for f in flags) + "."
    elif len(failed) >= FAILED_CHECKS_TO_HOLD:
        names = ", ".join(c.key.value.replace("_", " ") for c in failed)
        reason = f"{len(failed)} company checks failed: {names}."
    return (
        CompanyCheckSummary(
            verdict=check.verdict.value,
            passed=check.passed,
            total=check.total,
            flags=flags,
            note=reason or f"{check.passed} of {check.total} checks passed; no red flags.",
        ),
        reason,
    )
