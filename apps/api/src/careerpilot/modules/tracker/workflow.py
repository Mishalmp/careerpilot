"""Application status rules. Pure functions: no database, easy to test exhaustively.

Statuses fall into stages. Within a stage any order is allowed (rounds really do come in any
order). Moving forward past the next stage needs a note. Moving backwards is not allowed.
Terminal statuses can only be left by an explicit, explained reopen.
"""

from careerpilot.modules.tracker.enums import EventType, Status

PRE, APPLIED, INTERVIEW, OFFER = 0, 1, 2, 3

STAGE: dict[Status, int] = {
    Status.NEW: PRE,
    Status.SHORTLISTED: PRE,
    Status.APPLIED_PENDING: APPLIED,
    Status.FOLLOW_UP_SENT: APPLIED,
    Status.NO_RESPONSE: APPLIED,
    Status.INTERVIEW_CONFIRMED: INTERVIEW,
    Status.TECHNICAL_ROUND: INTERVIEW,
    Status.NEXT_ROUND: INTERVIEW,
    Status.HR_ROUND: INTERVIEW,
    Status.MANAGER_ROUND: INTERVIEW,
    Status.OFFER_RECEIVED: OFFER,
}
TERMINAL = frozenset({Status.OFFER_ACCEPTED, Status.REJECTED, Status.WITHDRAWN, Status.JOB_CLOSED})
NOT_YET_APPLIED = frozenset({Status.NEW, Status.SHORTLISTED})


class InvalidTransition(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def check_transition(
    current: Status, target: Status, *, note: str | None, reopen: bool
) -> EventType:
    """Return the event type for a legal move, or raise InvalidTransition."""
    note = (note or "").strip()
    if current == target:
        raise InvalidTransition("same_status", f"Already in '{current.value}'.")

    if current in TERMINAL:
        if not reopen:
            raise InvalidTransition(
                "reopen_required", f"'{current.value}' is final. Reopen it explicitly to change it."
            )
        if target in TERMINAL:
            raise InvalidTransition(
                "not_allowed", "A reopened application must go to an open status."
            )
        if not note:
            raise InvalidTransition("reason_required", "Say why you are reopening it.")
        return EventType.REOPENED

    if reopen:
        raise InvalidTransition("reopen_invalid", "Only a final application can be reopened.")

    if target == Status.OFFER_ACCEPTED:
        if current != Status.OFFER_RECEIVED:
            raise InvalidTransition(
                "not_allowed", "An offer can only be accepted after it is received."
            )
        return EventType.STATUS_CHANGED

    if target == Status.REJECTED and current in NOT_YET_APPLIED:
        raise InvalidTransition(
            "not_allowed", "You cannot be rejected before applying. Use Withdrawn or Job Closed."
        )

    if target in TERMINAL or target == Status.ON_HOLD or current == Status.ON_HOLD:
        return EventType.STATUS_CHANGED

    if target == Status.NO_RESPONSE and STAGE[current] in (APPLIED, INTERVIEW):
        return EventType.STATUS_CHANGED
    if target == Status.NO_RESPONSE:
        raise InvalidTransition("not_allowed", "No Response only applies after you have applied.")

    jump = STAGE[target] - STAGE[current]
    if jump < 0:
        raise InvalidTransition(
            "not_allowed", f"Cannot move back from '{current.value}' to '{target.value}'."
        )
    if jump > 1 and not note:
        raise InvalidTransition(
            "note_required", f"Skipping from '{current.value}' to '{target.value}' needs a note."
        )
    return EventType.STATUS_CHANGED
