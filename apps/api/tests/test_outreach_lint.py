"""The outreach linter (ported from the standalone script) and the approval state machine."""

import pytest

from careerpilot.modules.outreach.enums import Channel, OutreachStatus
from careerpilot.modules.outreach.lint import lint
from careerpilot.modules.outreach.workflow import TRANSITIONS, can_move

GOOD_BACKEND = """\
Hi,

Your backend posting mentions per-customer data isolation, which is something I've spent the last year on. I work mostly in Python with FastAPI and PostgreSQL.

On our platform each customer gets their own database. I helped design the provisioning and migration side, so a new account is ready without manual steps, and credentials are encrypted with KMS. I'm still learning where that model gets expensive, and I'd like to see how you handle it at Fabrikam Cloud.

I'm serving my notice period until 31 December and can join in January. Resume attached. Could you tell me who owns hiring for this team, or pass this along?

Regards,
Sam"""
GOOD_SUBJECT = "Backend (Python) role: multi-tenant API experience"

BAD_AI = """\
Dear Hiring Manager,

I hope this email finds you well. I am writing to express my keen interest in the Software Engineer position at your esteemed organization. I am a passionate and detail-oriented professional with a proven track record of leveraging cutting-edge technologies to deliver robust solutions in a fast-paced environment!

I have 5 years of experience building scalable, secure, and high-performance applications, and I increased system efficiency by 40% — a testament to my dedication. I believe I would be a perfect fit for this unique opportunity.

Please find attached my resume for your consideration. I look forward to the opportunity to discuss how my skills can contribute to your dynamic team. Do not hesitate to contact me at your earliest convenience.

Kind regards,
Sam"""


def flags_of(body: str, **kwargs: object) -> list[str]:
    defaults: dict[str, object] = {
        "facts": ["per-customer data isolation"],
        "company": "Fabrikam Cloud",
    }
    return lint(body, **(defaults | kwargs)).flags  # type: ignore[arg-type]


def test_a_specific_human_draft_passes_clean() -> None:
    result = lint(
        GOOD_BACKEND,
        subject=GOOD_SUBJECT,
        company="Fabrikam Cloud",
        facts=["per-customer data isolation"],
    )
    assert result.flags == []
    assert 90 <= result.words <= 130


def test_an_ai_sounding_draft_trips_many_flags() -> None:
    found = lint(
        BAD_AI,
        subject="Application for Software Engineer Position",
        company="Fabrikam Cloud",
        facts=["per-customer data isolation"],
    ).flags
    text = "\n".join(found)
    for expected in (
        "stock phrase: 'i hope this email finds you well'",
        "stock phrase: 'proven track record'",
        "stock phrase: 'perfect fit'",
        "stock phrase: 'esteemed'",
        "exclamation mark",
        "dash used as punctuation",
        "generic opening line",
        "no contractions anywhere",
        "company name 'Fabrikam Cloud' not mentioned",
        "expected specific detail missing: 'per-customer data isolation'",
        "numbers to verify against real evidence: 40, 5",
        "generic subject",
    ):
        assert expected in text, expected
    assert len(found) >= 20


def test_word_ranges_depend_on_the_channel() -> None:
    short = "Hi Priya, I saw the data role and worked on similar pipelines at my current job. Could you point me to the hiring manager? Thanks, Sam"
    assert any("too short" in f for f in flags_of(short, channel=Channel.EMAIL))
    short_ok = " ".join(["word"] * 55)
    assert not any("too" in f for f in flags_of(short_ok, channel=Channel.RECRUITER_MESSAGE))
    assert any(
        "too long" in f
        for f in flags_of(short_ok + " " * 1 + "x " * 50, channel=Channel.RECRUITER_MESSAGE)
    )


def test_numbers_are_questioned_unless_allowed() -> None:
    body = GOOD_BACKEND + "\nWe cut costs by 37%."
    assert "numbers to verify against real evidence: 37" in "\n".join(flags_of(body))
    allowed = flags_of(body, allowed_numbers=frozenset({"37", "31"}))
    assert not any("numbers to verify" in f for f in allowed)


def test_a_draft_without_any_fact_is_flagged() -> None:
    assert any("no specific fact" in f for f in flags_of(GOOD_BACKEND, facts=[]))


def test_a_draft_copied_from_another_is_flagged_as_a_template() -> None:
    flags = flags_of(
        GOOD_BACKEND, others=[("another draft", GOOD_BACKEND.replace("Fabrikam", "Contoso"))]
    )
    assert any("similar to another draft" in f for f in flags)
    different = flags_of(
        GOOD_BACKEND, others=[("another draft", "Totally unrelated text about gardening.")]
    )
    assert not any("similar" in f for f in different)


def test_long_sentences_and_first_person_openings_are_flagged() -> None:
    long_one = "I " + "really " * 30 + "like this role."
    assert any("over 28 words" in f for f in flags_of(long_one + " " + GOOD_BACKEND))
    all_i = "I built it. I ran it. I fixed it. I shipped it. I tested it."
    assert any("start with 'I'" in f for f in flags_of(all_i))


def test_repeated_lists_of_three_and_long_subjects() -> None:
    triads = "We use Python, Go, and Rust. Also Redis, Kafka, and NATS. " + GOOD_BACKEND
    assert any("lists of three" in f for f in flags_of(triads))
    assert any("subject longer" in f for f in flags_of(GOOD_BACKEND, subject="x" * 71))


# --- state machine -------------------------------------------------------------------------


def test_the_allowed_moves() -> None:
    S = OutreachStatus
    assert can_move(S.DRAFT, S.APPROVED) and can_move(S.DRAFT, S.REJECTED)
    assert can_move(S.APPROVED, S.SENT) and can_move(S.APPROVED, S.DRAFT)
    assert can_move(S.REJECTED, S.DRAFT)
    assert not can_move(S.DRAFT, S.SENT)  # never straight to sent: it must be approved first
    assert not can_move(S.REJECTED, S.APPROVED)
    assert TRANSITIONS[S.SENT] == frozenset()  # a sent message is a record


@pytest.mark.parametrize("status", list(OutreachStatus))
def test_nothing_can_move_to_itself(status: OutreachStatus) -> None:
    assert not can_move(status, status)
