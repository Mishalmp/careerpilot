from enum import StrEnum


class BoardKind(StrEnum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    # Public job feeds that list many companies (each job names its own company). Free, no key.
    REMOTEOK = "remoteok"
    REMOTIVE = "remotive"
    ARBEITNOW = "arbeitnow"
    HIMALAYAS = "himalayas"
    WEWORKREMOTELY = "weworkremotely"


class CandidateStatus(StrEnum):
    NEW = "new"
    ACCEPTED = "accepted"  # copied into the tracker
    DISMISSED = "dismissed"
