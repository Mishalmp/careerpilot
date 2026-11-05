"""How far each application got. Pure: built from the history of status changes."""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from careerpilot.modules.tracker.enums import Status
from careerpilot.modules.tracker.workflow import APPLIED, INTERVIEW, OFFER, STAGE


@dataclass(frozen=True)
class Progress:
    job_id: uuid.UUID
    status: Status
    applied_on: date | None  # the date you recorded, else the day it first reached "applied"
    applied: bool
    responded: bool  # an interview, or a rejection after applying
    interviewed: bool
    offered: bool
    rejected: bool
    no_response: bool


def _implies_applied(status: Status) -> bool:
    # A rejection or an accepted offer can only follow an application.
    return STAGE.get(status, -1) >= APPLIED or status in (Status.REJECTED, Status.OFFER_ACCEPTED)


def progress_of(
    job_id: uuid.UUID,
    status: Status,
    applied_on: date | None,
    history: Iterable[tuple[Status, date]],
) -> Progress:
    """`history` is every status change as (status, day); the current status is added."""
    changes = list(history)
    reached = {status, *(s for s, _ in changes)}
    first_applied = min((day for s, day in changes if _implies_applied(s)), default=None)
    applied_date = applied_on or first_applied
    applied = applied_date is not None or any(_implies_applied(s) for s in reached)
    interviewed = any(STAGE.get(s, -1) in (INTERVIEW, OFFER) for s in reached) or (
        Status.OFFER_ACCEPTED in reached
    )
    offered = bool(reached & {Status.OFFER_RECEIVED, Status.OFFER_ACCEPTED})
    rejected = Status.REJECTED in reached and applied
    return Progress(
        job_id=job_id,
        status=status,
        applied_on=applied_date,
        applied=applied,
        responded=interviewed or rejected,
        interviewed=interviewed,
        offered=offered,
        rejected=rejected,
        no_response=applied and not (interviewed or rejected) and Status.NO_RESPONSE in reached,
    )
