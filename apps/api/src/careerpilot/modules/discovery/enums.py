from enum import StrEnum


class BoardKind(StrEnum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"


class CandidateStatus(StrEnum):
    NEW = "new"
    ACCEPTED = "accepted"  # copied into the tracker
    DISMISSED = "dismissed"
