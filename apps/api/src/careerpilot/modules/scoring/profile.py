"""What job scoring compares a job against. It comes from account setup (the database); this file
is the fallback for people who prefer to keep their profile in `content/private/profile.yaml`."""

from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from careerpilot.core.errors import ProblemError
from careerpilot.modules.tracker.enums import Region

Level = Annotated[str, Field(pattern="^(junior|mid|senior|lead)$")]


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    years_experience: Annotated[float, Field(ge=0, le=60)]
    target_levels: list[Level] = ["junior", "mid"]
    skills: list[str]
    regions: list[Region]
    needs_visa_sponsorship: bool = False
    salary_floor_lpa: Annotated[float, Field(gt=0)] | None = None
    salary_target_lpa: Annotated[float, Field(gt=0)] | None = None


def profile_path(content_dir: Path) -> Path:
    return content_dir / "private" / "profile.yaml"


def load_profile(content_dir: Path) -> Profile:
    path = profile_path(content_dir)
    if not path.exists():
        raise ProblemError(
            409,
            "No profile yet",
            "Finish account setup on the Profile page (or copy content/profile.example.yaml to "
            "content/private/profile.yaml and fill it in).",
        )
    try:
        return Profile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except (ValidationError, yaml.YAMLError) as exc:
        raise ProblemError(
            422, "Profile file is invalid", f"Fix content/private/profile.yaml: {str(exc)[:300]}"
        ) from exc
