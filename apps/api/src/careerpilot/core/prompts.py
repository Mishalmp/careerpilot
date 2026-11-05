"""Prompts live as files under `prompts/<name>/vN.md`, never inline in code.

A file has a small YAML header (`description`, `max_tokens`) and the system prompt as its body.
Changing a prompt means adding the next version file, so an old `llm_calls.purpose` such as
`company-pages@v1` always points at the exact text that was used. Tests pin the version they expect.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_FILE = re.compile(r"^v(\d+)\.md$")
_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)


@dataclass(frozen=True)
class Prompt:
    name: str
    version: int
    description: str
    max_tokens: int
    system: str

    @property
    def label(self) -> str:
        """What is stored in `llm_calls.purpose`."""
        return f"{self.name}@v{self.version}"


def load_prompt(prompts_dir: Path, name: str, version: int | None = None) -> Prompt:
    """The given version, or the newest one when none is given."""
    folder = prompts_dir / name
    if version is None:
        found = [int(m.group(1)) for p in folder.glob("v*.md") if (m := _FILE.match(p.name))]
        if not found:
            raise FileNotFoundError(f"No prompt named {name!r} in {prompts_dir}")
        version = max(found)
    raw = (folder / f"v{version}.md").read_text(encoding="utf-8")
    parts = _FRONT_MATTER.match(raw.replace("\r\n", "\n"))
    if parts is None:
        raise ValueError(f"{name} v{version} has no front matter")
    header = yaml.safe_load(parts.group(1))
    return Prompt(
        name=name,
        version=version,
        description=str(header["description"]),
        max_tokens=int(header["max_tokens"]),
        system=parts.group(2).strip(),
    )


def data_block(tag: str, text: str, **attributes: str) -> str:
    """Untrusted text wrapped as `<tag ...>...</tag>` so the model can tell data from instructions.

    A literal closing tag inside the text is defused, so the text cannot end its own block early.
    """
    safe = text.replace(f"</{tag}", f"<\\/{tag}")
    attrs = "".join(f' {name}="{value}"' for name, value in attributes.items())
    return f"<{tag}{attrs}>\n{safe}\n</{tag}>"
