"""The apply policy: a file the owner edits to change how the daily list is chosen.

Looked up in this order: content/private/apply-policy.yaml (yours, not committed), then
content/apply-policy.example.yaml, then the defaults below. A bad file gives a list of plain
problems instead of silently using defaults, so a typo cannot quietly change what is chosen.
There is deliberately no auto-submit setting: the app has no way to submit an application.
"""

from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

Name = Annotated[str, Field(min_length=1, max_length=80)]


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid")  # an unknown key is a typo, not an option

    daily_limit: Annotated[int, Field(ge=1, le=100)] = 3
    # The first this many items of a day are researched on the web (pay, interview, same job
    # elsewhere). The rest are listed from what the post and your tracker already say, so a list
    # of 100 does not mean 500 searches; any of them can be researched later with one click.
    deep_limit: Annotated[int, Field(ge=0, le=100)] = 10
    use_search_profiles: bool = True  # only jobs that fit the searches you described
    # New listings from the boards you follow that fit your searches are copied into the tracker
    # before the list is chosen, up to this many per build (0 = only jobs you added yourself).
    auto_add_limit: Annotated[int, Field(ge=0, le=300)] = 30
    min_match_score: Annotated[int, Field(ge=0, le=100)] = 40
    regions: list[Name] = []  # empty = any region
    work_modes: list[Literal["Remote", "Hybrid", "Onsite"]] = []  # empty = any
    skip_companies: list[Name] = []
    require_apply_link: bool = True
    block_if_company_suspicious: bool = True  # a red flag or two failed checks; see company.py
    max_age_days: Annotated[int, Field(ge=0, le=1000)] = 120  # skip older posts; 0 = any age
    enrich_with_web: bool = True
    max_web_pages_per_job: Annotated[int, Field(ge=0, le=6)] = 3


class PolicyProblem(Exception):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


def load_policy(content_dir: Path) -> tuple[Policy, str]:
    """(the policy, which file it came from). Raises PolicyProblem when the file is wrong."""
    for relative in ("private/apply-policy.yaml", "apply-policy.example.yaml"):
        path = content_dir / relative
        if path.is_file():
            try:
                raw: object = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                raise PolicyProblem([f"{relative} is not valid YAML: {exc}"]) from exc
            if not isinstance(raw, dict):
                raise PolicyProblem([f"{relative} must be a list of settings (key: value)."])
            try:
                return Policy.model_validate(raw), relative
            except ValidationError as exc:
                raise PolicyProblem(
                    [
                        f"{relative}: {'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                        for e in exc.errors()
                    ]
                ) from exc
    return Policy(), "built-in defaults"
