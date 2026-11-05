"""The verdict rule, red-flag scanning and quote verification: all pure, so tested exhaustively."""

from datetime import date

import pytest

from careerpilot.core.evidence import normalize, quote_appears
from careerpilot.modules.verification.enums import (
    CHECKS,
    FLAGS,
    CheckKey,
    CheckStatus,
    VerdictLabel,
)
from careerpilot.modules.verification.rules import (
    compute_verdict,
    domain_age_status,
    scan_job_text,
)

PASS, FAIL, UNKNOWN = CheckStatus.PASS, CheckStatus.FAIL, CheckStatus.UNKNOWN


def passing(count: int) -> dict[CheckKey, CheckStatus]:
    return {key: PASS if index < count else UNKNOWN for index, key in enumerate(CHECKS)}


# --- the verdict follows the rule ----------------------------------------------------------


@pytest.mark.parametrize(
    ("passed", "label"),
    [
        (8, VerdictLabel.VERIFIED),
        (7, VerdictLabel.VERIFIED),
        (6, VerdictLabel.LIKELY_GENUINE),
        (5, VerdictLabel.LIKELY_GENUINE),
        (4, VerdictLabel.NEEDS_CHECK),
        (3, VerdictLabel.NEEDS_CHECK),
        (2, VerdictLabel.SUSPICIOUS),
        (1, VerdictLabel.SUSPICIOUS),
        (0, VerdictLabel.SUSPICIOUS),
    ],
)
def test_the_score_maps_to_the_documented_label(passed: int, label: VerdictLabel) -> None:
    verdict = compute_verdict(passing(passed))
    assert (verdict.label, verdict.passed) == (label, passed)


def test_failed_and_unknown_checks_both_count_as_not_passed() -> None:
    statuses = {key: FAIL for key in CHECKS} | {CheckKey.WEBSITE: PASS}
    assert compute_verdict(statuses).passed == 1


def test_missing_checks_count_as_not_passed() -> None:
    assert compute_verdict({}).label is VerdictLabel.SUSPICIOUS


@pytest.mark.parametrize("flag", FLAGS)
def test_any_raised_flag_forces_suspicious_even_with_a_perfect_score(flag: CheckKey) -> None:
    verdict = compute_verdict(passing(8) | {flag: FAIL})
    assert verdict.label is VerdictLabel.SUSPICIOUS
    assert verdict.raised_flags == (flag,) and verdict.passed == 8


def test_cleared_or_unknown_flags_do_not_change_the_score_label() -> None:
    statuses = passing(8) | {FLAGS[0]: PASS, FLAGS[1]: UNKNOWN}
    assert compute_verdict(statuses).label is VerdictLabel.VERIFIED


def test_flags_are_not_counted_as_checks() -> None:
    assert compute_verdict({flag: PASS for flag in FLAGS}).passed == 0
    assert len(CHECKS) == 8 and len(FLAGS) == 4


def test_domain_age_threshold_is_one_year() -> None:
    today = date(2026, 11, 5)
    assert domain_age_status(date(2025, 11, 5), today) is PASS
    assert domain_age_status(date(2025, 11, 6), today) is FAIL
    assert domain_age_status(date(2010, 1, 1), today) is PASS


# --- red flags stated in a job description -------------------------------------------------


@pytest.mark.parametrize(
    ("text", "flag", "words"),
    [
        (
            "Selected candidates must pay a refundable security deposit of 5000.",
            CheckKey.ASKS_FOR_MONEY,
            "security deposit",
        ),
        (
            "A one-time registration fee applies before onboarding.",
            CheckKey.ASKS_FOR_MONEY,
            "registration fee",
        ),
        ("Pay Rs. 2000 to confirm your seat.", CheckKey.ASKS_FOR_MONEY, "Pay Rs. 2000"),
        (
            "Interview will be on WhatsApp only. Send your resume there.",
            CheckKey.CHAT_ONLY_HIRING,
            "WhatsApp",
        ),
        ("Contact our HR on Telegram to apply.", CheckKey.CHAT_ONLY_HIRING, "Telegram"),
        ("No interview needed, direct joining for all.", CheckKey.NO_INTERVIEW, "No interview"),
        (
            "You will be selected without an interview.",
            CheckKey.NO_INTERVIEW,
            "without an interview",
        ),
        ("Instant offer letter on registration.", CheckKey.NO_INTERVIEW, "Instant offer"),
        (
            "Send your CV to hr.recruiter123@gmail.com today.",
            CheckKey.FREE_MAIL_RECRUITER,
            "hr.recruiter123@gmail.com",
        ),
        ("Mail jobs@Yahoo.co.in", CheckKey.FREE_MAIL_RECRUITER, "jobs@Yahoo.co.in"),
    ],
)
def test_outright_red_flags_are_found_with_their_words(
    text: str, flag: CheckKey, words: str
) -> None:
    found = scan_job_text(text)
    assert flag in found
    assert words in found[flag]


@pytest.mark.parametrize(
    "text",
    [
        "We never ask candidates for a registration fee. Beware of fraudulent offers.",
        "Our hiring process is free of charges: no processing fee at any stage.",
        "Scam alert: nobody from us will ask you to pay a security deposit.",
        "Do not share your resume on WhatsApp or Telegram; apply only through this page.",
        "Be careful of fake offers that promise a job with no interview.",
        "We build backend services in Python and Go. Four interview rounds. Apply on our site.",
        "Contact careers@acme.example for questions.",
        "Our Telegram bot for deploy alerts is written in Go.",
    ],
)
def test_warnings_and_ordinary_text_do_not_raise_flags(text: str) -> None:
    assert scan_job_text(text) == {}


def test_each_flag_is_reported_once_with_the_first_offending_words() -> None:
    found = scan_job_text("Pay registration fee now. Later: another security deposit.")
    assert list(found) == [CheckKey.ASKS_FOR_MONEY]
    assert "registration fee" in found[CheckKey.ASKS_FOR_MONEY]


# --- quote verification --------------------------------------------------------------------

PAGE = """
About Acme Robotics

Acme Robotics Private Limited is registered in India (CIN: U29100KA2016PTC089321).
Our office:   14th Floor,
Prestige Tower, MG Road, Bengaluru 560001.
"""


@pytest.mark.parametrize(
    "quote",
    [
        "CIN: U29100KA2016PTC089321",
        "Acme Robotics Private Limited is registered in India",
        "our office: 14th floor, prestige tower, mg road",  # case and line breaks differ
        "14th   Floor,\n Prestige Tower",
        "Acme Robotics Private Limited",  # no-break space  # noqa: RUF001
    ],
)
def test_real_quotes_are_accepted(quote: str) -> None:
    assert quote_appears(quote, PAGE)


@pytest.mark.parametrize(
    "quote",
    [
        "CIN: U29100KA2016PTC000000",  # one wrong digit: fabricated
        "Acme Robotics is a registered company in India",  # paraphrase
        "registered in India ... Bengaluru 560001",  # two passages joined
        "Prestige Tower, Mumbai",
        "contact",  # too short to mean anything
        "",
        " " * 20,
        "x" * 400,
    ],
)
def test_fabricated_paraphrased_joined_or_trivial_quotes_are_rejected(quote: str) -> None:
    assert not quote_appears(quote, PAGE)


def test_typographic_variants_still_match() -> None:
    page = "We’re hiring — “backend engineers” in Pune…"  # noqa: RUF001
    assert quote_appears('We\'re hiring - "backend engineers" in Pune...', page)


def test_invisible_characters_do_not_hide_or_fake_a_match() -> None:
    page = "Reg​istered office: Pune"
    assert quote_appears("Registered office: Pune", page)
    assert normalize("A­B") == "ab"


def test_a_quote_is_checked_against_the_given_text_only() -> None:
    assert not quote_appears("Acme Robotics Private Limited", "Some other company's page text")
