import pytest

from careerpilot.modules.tracker.enums import EventType, Status
from careerpilot.modules.tracker.workflow import InvalidTransition, check_transition

S = Status


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.NEW, S.SHORTLISTED),
        (S.SHORTLISTED, S.NEW),  # un-shortlist
        (S.NEW, S.APPLIED_PENDING),
        (S.SHORTLISTED, S.APPLIED_PENDING),
        (S.APPLIED_PENDING, S.FOLLOW_UP_SENT),
        (S.FOLLOW_UP_SENT, S.NO_RESPONSE),
        (S.APPLIED_PENDING, S.TECHNICAL_ROUND),
        (S.TECHNICAL_ROUND, S.HR_ROUND),
        (S.HR_ROUND, S.TECHNICAL_ROUND),  # rounds happen in any order
        (S.MANAGER_ROUND, S.OFFER_RECEIVED),
        (S.OFFER_RECEIVED, S.OFFER_ACCEPTED),
        (S.TECHNICAL_ROUND, S.NO_RESPONSE),  # ghosted after an interview
        (S.APPLIED_PENDING, S.REJECTED),
        (S.NEW, S.WITHDRAWN),
        (S.SHORTLISTED, S.JOB_CLOSED),
        (S.TECHNICAL_ROUND, S.ON_HOLD),
        (S.ON_HOLD, S.APPLIED_PENDING),
        (S.ON_HOLD, S.REJECTED),
    ],
)
def test_allowed_moves(current: Status, target: Status) -> None:
    assert check_transition(current, target, note=None, reopen=False) == EventType.STATUS_CHANGED


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.NEW, S.TECHNICAL_ROUND),
        (S.NEW, S.OFFER_RECEIVED),
        (S.SHORTLISTED, S.INTERVIEW_CONFIRMED),
        (S.APPLIED_PENDING, S.OFFER_RECEIVED),
    ],
)
def test_skipping_stages_needs_a_note(current: Status, target: Status) -> None:
    with pytest.raises(InvalidTransition) as error:
        check_transition(current, target, note=None, reopen=False)
    assert error.value.code == "note_required"
    with pytest.raises(InvalidTransition):
        check_transition(current, target, note="   ", reopen=False)
    assert check_transition(current, target, note="Recruiter called", reopen=False)


@pytest.mark.parametrize(
    ("current", "target", "code"),
    [
        (S.NEW, S.NEW, "same_status"),
        (S.TECHNICAL_ROUND, S.APPLIED_PENDING, "not_allowed"),
        (S.OFFER_RECEIVED, S.TECHNICAL_ROUND, "not_allowed"),
        (S.NEW, S.NO_RESPONSE, "not_allowed"),
        (S.NEW, S.REJECTED, "not_allowed"),
        (S.SHORTLISTED, S.REJECTED, "not_allowed"),
        (S.APPLIED_PENDING, S.OFFER_ACCEPTED, "not_allowed"),
        (S.REJECTED, S.APPLIED_PENDING, "reopen_required"),
        (S.OFFER_ACCEPTED, S.OFFER_RECEIVED, "reopen_required"),
    ],
)
def test_forbidden_moves(current: Status, target: Status, code: str) -> None:
    with pytest.raises(InvalidTransition) as error:
        check_transition(current, target, note="because", reopen=False)
    assert error.value.code == code


def test_reopening_a_final_application() -> None:
    assert (
        check_transition(S.REJECTED, S.APPLIED_PENDING, note="They re-opened the role", reopen=True)
        == EventType.REOPENED
    )
    with pytest.raises(InvalidTransition) as no_reason:
        check_transition(S.REJECTED, S.APPLIED_PENDING, note=None, reopen=True)
    assert no_reason.value.code == "reason_required"
    with pytest.raises(InvalidTransition) as to_final:
        check_transition(S.REJECTED, S.WITHDRAWN, note="x", reopen=True)
    assert to_final.value.code == "not_allowed"


def test_reopen_flag_on_an_open_application_is_refused() -> None:
    with pytest.raises(InvalidTransition) as error:
        check_transition(S.NEW, S.SHORTLISTED, note="x", reopen=True)
    assert error.value.code == "reopen_invalid"
