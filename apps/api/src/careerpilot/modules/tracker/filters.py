from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from careerpilot.modules.tracker.enums import Region, Status, WorkMode


@dataclass(frozen=True)
class JobFilters:
    """What a job list can be narrowed by. Shared by the API and the MCP server."""

    statuses: Sequence[Status] | None = None
    query: str | None = None
    region: Region | None = None
    work_mode: WorkMode | None = None
    min_ctc: float | None = None
    followup_due_on: date | None = None
