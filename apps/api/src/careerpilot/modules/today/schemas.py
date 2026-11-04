from pydantic import BaseModel

from careerpilot.modules.prep.schemas import TodayPrep
from careerpilot.modules.tracker.enums import Status
from careerpilot.modules.tracker.schemas import JobSummary


class StatusCount(BaseModel):
    status: Status
    count: int


class TodayOut(BaseModel):
    pipeline: list[StatusCount]
    due_followups: list[JobSummary]
    prep: TodayPrep
