from datetime import date

from pydantic import BaseModel

NOTE = (
    "Counts come from your status history. With few applications the rates swing a lot: treat "
    "them as a diary of what happened, not a forecast."
)


class FunnelOut(BaseModel):
    tracked: int
    applied: int
    responded: int  # an interview or a rejection
    interviewed: int
    offered: int
    rejected: int
    no_response: int
    response_rate: float | None  # percent of applications
    interview_rate: float | None
    offer_rate: float | None
    small_sample: bool


class WeekOut(BaseModel):
    week_start: date
    applications: int


class DayMinutes(BaseModel):
    day: date
    minutes: int


class PrepOut(BaseModel):
    topics: dict[str, int]  # topics per status
    average_confidence: float | None
    minutes_by_day: list[DayMinutes]  # the last 14 days, zeros included
    study_days: int
    total_minutes: int


class MockPoint(BaseModel):
    day: date
    title: str
    average: float


class CalibrationGroupOut(BaseModel):
    chance: str
    scored: int
    decided: int
    interviewed: int
    interview_rate: float | None


class CalibrationOut(BaseModel):
    decided: int
    needed: int
    ready: bool  # enough decided applications for the comparison to mean anything
    groups: list[CalibrationGroupOut]
    explanation: str


class AnalyticsOut(BaseModel):
    funnel: FunnelOut
    weekly_applications: list[WeekOut]
    prep: PrepOut
    mocks: list[MockPoint]
    calibration: CalibrationOut
    note: str = NOTE
