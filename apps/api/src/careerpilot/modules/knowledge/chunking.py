"""Split a Markdown document into passages for retrieval.

Rules, in order of importance:
- A passage stays inside one section, and carries its heading path ("Python > Core questions").
- Headings inside code fences are code comments, not headings.
- Code blocks, tables and lists are never cut in the middle unless one alone is too big.
- A numbered question like "**4. How does a dict work?**" starts a new passage, so one answer is
  not mixed with the next.
- Passages are about 1500 characters (roughly 350 tokens); a tiny tail is merged into the passage
  before it.
"""

import re
from dataclasses import dataclass

MAX_CHARS = 1500
MIN_CHARS = 200

_HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*#*\s*$")
_ITEM_START = re.compile(r"^\*\*(\d+|[A-Z])\.\s")
_LIST_LINE = re.compile(r"^\s*([-*+]|\d+[.)])\s")


@dataclass(frozen=True)
class RawChunk:
    heading_path: str
    text: str


def _blocks(lines: list[str]) -> list[str]:
    """Group a section's lines into paragraphs, fenced code, tables and lists."""
    blocks: list[str] = []
    current: list[str] = []
    current_is_list = False
    in_fence = False

    def flush() -> None:
        if current:
            blocks.append("\n".join(current).strip("\n"))
            current.clear()

    for line in lines:
        if line.lstrip().startswith("```"):
            if not in_fence:
                flush()
            current.append(line)
            in_fence = not in_fence
            if not in_fence:
                flush()
        elif in_fence:
            current.append(line)
        elif not line.strip():
            flush()
        else:
            starts_list = bool(_LIST_LINE.match(line))
            continues = line.startswith((" ", "\t"))
            if current and not continues and starts_list != current_is_list:
                flush()  # a list next to a paragraph is its own block
            if not current:
                current_is_list = starts_list
            current.append(line)
    flush()
    return [b for b in blocks if b.strip()]


def _split_long(block: str, limit: int) -> list[str]:
    """Cut an oversized block on line boundaries (sentence boundaries for one long line)."""
    pieces: list[str] = []
    current = ""
    for line in block.split("\n"):
        parts = [line]
        if len(line) > limit:
            parts = re.split(r"(?<=[.!?])\s+", line)
        for part in parts:
            while len(part) > limit:  # no sentence breaks at all: hard cut
                pieces.append(part[:limit])
                part = part[limit:]
            if current and len(current) + len(part) + 1 > limit:
                pieces.append(current)
                current = part
            else:
                current = f"{current}\n{part}" if current else part
    if current:
        pieces.append(current)
    return pieces


def _pack(blocks: list[str], max_chars: int, min_chars: int) -> list[str]:
    packed: list[str] = []
    current = ""
    for block in blocks:
        for piece in _split_long(block, max_chars) if len(block) > max_chars else [block]:
            starts_item = bool(_ITEM_START.match(piece))
            too_big = len(current) + len(piece) + 2 > max_chars
            if current and (too_big or (starts_item and len(current) >= min_chars)):
                packed.append(current)
                current = piece
            else:
                current = f"{current}\n\n{piece}" if current else piece
    if current:
        if (
            packed
            and len(current) < min_chars
            and len(packed[-1]) + len(current) + 2 <= max_chars * 1.3
        ):
            packed[-1] = f"{packed[-1]}\n\n{current}"
        else:
            packed.append(current)
    return packed


def chunk_markdown(
    markdown: str, *, max_chars: int = MAX_CHARS, min_chars: int = MIN_CHARS
) -> list[RawChunk]:
    sections: list[tuple[str, list[str]]] = [("", [])]
    titles: list[tuple[int, str]] = []
    in_fence = False
    for line in markdown.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        heading = None if in_fence else _HEADING.match(line)
        if heading:
            level, title = len(heading.group(1)), heading.group(2).strip()
            titles = [(lvl, t) for lvl, t in titles if lvl < level] + [(level, title)]
            sections.append((" > ".join(t for _, t in titles), []))
        else:
            sections[-1][1].append(line)

    chunks: list[RawChunk] = []
    for path, lines in sections:
        for text in _pack(_blocks(lines), max_chars, min_chars):
            chunks.append(RawChunk(path, text.strip()))
    return chunks
