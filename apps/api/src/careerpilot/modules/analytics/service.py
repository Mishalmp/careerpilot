import uuid
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.analytics import rules
from careerpilot.modules.analytics.schemas import (
    AnalyticsOut,
    CalibrationGroupOut,
    CalibrationOut,
    DayMinutes,
    FunnelOut,
    MockPoint,
    PrepOut,
    WeekOut,
)
from careerpilot.modules.mock import service as mock_service
from careerpilot.modules.prep import service as prep_service
from careerpilot.modules.scoring import service as scoring_service
from careerpilot.modules.tracker import service as tracker_service

STUDY_DAYS = 14
MOCK_POINTS = 10


async def build(db: AsyncSession, owner_id: uuid.UUID, today: date, timezone: str) -> AnalyticsOut:
    progress = await tracker_service.progress(db, owner_id, timezone)
    funnel = rules.funnel(progress)

    since = today - timedelta(days=STUDY_DAYS - 1)
    prep = await prep_service.progress(db, owner_id, since)
    days = [since + timedelta(days=n) for n in range(STUDY_DAYS)]
    minutes = [DayMinutes(day=d, minutes=prep.minutes_by_day.get(d, 0)) for d in days]

    sessions = await mock_service.list_sessions(db, owner_id)
    mocks = [
        MockPoint(day=s.created_at.date(), title=s.title, average=s.average)
        for s in reversed(sessions[:MOCK_POINTS])
        if s.finished and s.average is not None
    ]

    calibration = rules.calibration(await scoring_service.scored_jobs(db, owner_id), progress)
    if calibration.ready:
        explanation = (
            "If the fit score is useful, jobs labelled good should reach interviews more often "
            "than unlikely ones."
        )
    else:
        explanation = (
            f"Only {calibration.decided} of {calibration.needed} outcomes are known. Until then "
            "the figures below are counts, not evidence that the score works."
        )
    return AnalyticsOut(
        funnel=FunnelOut(
            tracked=funnel.tracked,
            applied=funnel.applied,
            responded=funnel.responded,
            interviewed=funnel.interviewed,
            offered=funnel.offered,
            rejected=funnel.rejected,
            no_response=funnel.no_response,
            response_rate=funnel.response_rate,
            interview_rate=funnel.interview_rate,
            offer_rate=funnel.offer_rate,
            small_sample=funnel.small_sample,
        ),
        weekly_applications=[
            WeekOut(week_start=start, applications=count)
            for start, count in rules.weekly_applications(progress, today)
        ],
        prep=PrepOut(
            topics={status.value: count for status, count in prep.topics.items()},
            average_confidence=(
                round(prep.average_confidence, 1) if prep.average_confidence is not None else None
            ),
            minutes_by_day=minutes,
            study_days=sum(1 for m in minutes if m.minutes > 0),
            total_minutes=sum(m.minutes for m in minutes),
        ),
        mocks=mocks,
        calibration=CalibrationOut(
            decided=calibration.decided,
            needed=calibration.needed,
            ready=calibration.ready,
            groups=[CalibrationGroupOut(**vars(g)) for g in calibration.groups],
            explanation=explanation,
        ),
    )
