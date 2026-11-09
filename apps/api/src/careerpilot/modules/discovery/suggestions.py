"""The list of company boards worth following (content/job-boards.yaml), read as data."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from careerpilot.modules.discovery.enums import BoardKind


class SuggestedBoard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["greenhouse", "lever", "ashby"]
    board: str
    company: str
    tags: list[Literal["india", "remote"]]
    roles: int  # open roles when it was checked
    india: int  # of those, in India
    remote: int  # of those, remote

    @property
    def key(self) -> str:
        return f"{self.kind}/{self.board}"


def load_suggestions(content_dir: Path) -> list[SuggestedBoard]:
    """The suggested boards, or an empty list when the file is missing or wrong (never a crash)."""
    path = content_dir / "job-boards.yaml"
    if not path.is_file():
        return []
    try:
        raw: object = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        items = raw.get("boards", []) if isinstance(raw, dict) else []  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        return [SuggestedBoard.model_validate(item) for item in items]  # pyright: ignore[reportUnknownVariableType]
    except (yaml.YAMLError, ValidationError):
        return []


def as_kind(value: str) -> BoardKind:
    return BoardKind(value)
