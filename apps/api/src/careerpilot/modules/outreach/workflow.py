"""Which moves between outreach states are allowed. There is deliberately no state that sends."""

from careerpilot.modules.outreach.enums import OutreachStatus as S

TRANSITIONS: dict[S, frozenset[S]] = {
    S.DRAFT: frozenset({S.APPROVED, S.REJECTED}),
    S.APPROVED: frozenset({S.SENT, S.DRAFT, S.REJECTED}),
    S.SENT: frozenset(),  # a sent message is a record; it never changes again
    S.REJECTED: frozenset({S.DRAFT}),
}


def can_move(current: S, target: S) -> bool:
    return target in TRANSITIONS[current]
