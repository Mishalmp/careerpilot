"""Markdown guides read from disk. Names come from a directory listing, never from a raw path."""

import re
from dataclasses import dataclass
from pathlib import Path

_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True)
class GuideInfo:
    name: str
    title: str
    private: bool


@dataclass(frozen=True)
class Guide:
    info: GuideInfo
    markdown: str


def _dirs(content_dir: Path) -> list[tuple[Path, bool]]:
    return [(content_dir / "guides", False), (content_dir / "private", True)]


def _title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def list_guides(content_dir: Path) -> list[GuideInfo]:
    found = [
        GuideInfo(path.stem, _title(path), private)
        for directory, private in _dirs(content_dir)
        if directory.is_dir()
        for path in directory.glob("*.md")
        if _NAME.match(path.stem)
    ]
    return sorted(found, key=lambda info: info.name)


def read_guide(content_dir: Path, name: str) -> Guide | None:
    if not _NAME.match(name):
        return None
    for directory, private in _dirs(content_dir):
        path = directory / f"{name}.md"
        if path.is_file():
            return Guide(GuideInfo(name, _title(path), private), path.read_text(encoding="utf-8"))
    return None
