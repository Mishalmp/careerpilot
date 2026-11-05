"""Funnel rates and the calibration of the fit score. Pure functions over application progress."""

import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from careerpilot.modules.tracker.progress import Progress

MIN_OUTCOMES = 50  # decided applications before the calibration view means anything
SMALL_SAMPLE = 10  # applications below this: rates are shown with a warning
CHANCE_ORDER = ("good", "possible", "unlikely", "unknown")


@dataclass(frozen=True)
class Funnel:
    tracked: int
    applied: int
    responded: int
    interviewed: int
    offered: int
    rejected: int
    no_response: int

    def _rate(self, count: int) -> float | None:
        return round(100 * count / self.applied, 1) if self.applied else None

    @property
    def response_rate(self) -> float | None:
        return self._rate(self.responded)

    @property
    def interview_rate(self) -> float | None:
        return self._rate(self.interviewed)

    @property
    def offer_rate(self) -> float | None:
        return self._rate(self.offered)

    @property
    def small_sample(self) -> bool:
        return self.applied < SMALL_SAMPLE


def funnel(progress: Iterable[Progress]) -> Funnel:
    rows = list(progress)
    return Funnel(
        tracked=len(rows),
        applied=sum(p.applied for p in rows),
        responded=sum(p.responded for p in rows),
        interviewed=sum(p.interviewed for p in rows),
        offered=sum(p.offered for p in rows),
        rejected=sum(p.rejected for p in rows),
        no_response=sum(p.no_response for p in rows),
    )


def weekly_applications(
    progress: Iterable[Progress], today: date, weeks: int = 8
) -> list[tuple[date, int]]:
    """Applications per week (weeks start on Monday), oldest first, empty weeks included."""
    this_monday = today - timedelta(days=today.weekday())
    starts = [this_monday - timedelta(weeks=n) for n in range(weeks - 1, -1, -1)]
    counts = dict.fromkeys(starts, 0)
    for p in progress:
        if p.applied_on is not None:
            monday = p.applied_on - timedelta(days=p.applied_on.weekday())
            if monday in counts:
                counts[monday] += 1
    return list(counts.items())


@dataclass(frozen=True)
class CalibrationGroup:
    chance: str
    scored: int  # jobs that got this label
    decided: int  # of those, applications with a known outcome
    interviewed: int
    interview_rate: float | None


@dataclass(frozen=True)
class Calibration:
    decided: int
    needed: int
    ready: bool
    groups: list[CalibrationGroup]


def _decided(p: Progress) -> bool:
    """An outcome is known once you were invited, rejected, or never heard back."""
    return p.applied and (p.interviewed or p.rejected or p.no_response)


def calibration(
    scored: Iterable[tuple[uuid.UUID, str, int | None]], progress: Iterable[Progress]
) -> Calibration:
    """Does the chance label predict interviews? Counts per label; a rate only for decided ones."""
    by_job = {p.job_id: p for p in progress}
    per_label: dict[str, list[Progress | None]] = defaultdict(list)
    for job_id, label, _score in scored:
        per_label[label].append(by_job.get(job_id))
    groups: list[CalibrationGroup] = []
    for label in (*CHANCE_ORDER, *sorted(set(per_label) - set(CHANCE_ORDER))):
        if label not in per_label:
            continue
        decided = [p for p in per_label[label] if p is not None and _decided(p)]
        interviewed = sum(1 for p in decided if p.interviewed)
        groups.append(
            CalibrationGroup(
                chance=label,
                scored=len(per_label[label]),
                decided=len(decided),
                interviewed=interviewed,
                interview_rate=round(100 * interviewed / len(decided), 1) if decided else None,
            )
        )
    total = sum(g.decided for g in groups)
    return Calibration(total, MIN_OUTCOMES, total >= MIN_OUTCOMES, groups)
