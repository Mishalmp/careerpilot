"""Finding skills and experience requirements in job text. Pure functions."""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Vocabulary:
    aliases: dict[str, str]  # lower-case spelling -> canonical name
    patterns: dict[str, re.Pattern[str]]  # canonical name -> pattern for any of its spellings

    def canonical(self, skill: str) -> str:
        """The canonical name; unknown skills are kept as typed (lower-case)."""
        key = " ".join(skill.lower().split())
        return self.aliases.get(key, key)


def load_vocabulary(content_dir: Path) -> Vocabulary:
    raw = yaml.safe_load((content_dir / "skills.yaml").read_text(encoding="utf-8"))
    aliases: dict[str, str] = {}
    patterns: dict[str, re.Pattern[str]] = {}
    for entry in raw["skills"]:
        name = entry["name"]
        spellings = [name, *entry.get("aliases", [])]
        for spelling in spellings:
            aliases[spelling.lower()] = name
        # `exact_case: true` is for short acronyms (SQS, IAM): matched in capitals only.
        exact = bool(entry.get("exact_case"))
        flags = 0 if exact else re.IGNORECASE
        written = [spelling.upper() for spelling in spellings] if exact else spellings
        # A skill name is delimited by anything that cannot be part of a name, so "java" does not
        # match inside "javascript" and "c++" is found even though "+" is not a word character.
        alternatives = "|".join(re.escape(s) for s in sorted(written, key=len, reverse=True))
        patterns[name] = re.compile(rf"(?<![\w+#.])(?:{alternatives})(?![\w+#]|\.\w)", flags)
    return Vocabulary(aliases, patterns)


def skills_in(text: str, vocabulary: Vocabulary) -> set[str]:
    return {name for name, pattern in vocabulary.patterns.items() if pattern.search(text)}


_YEARS = re.compile(
    r"(\d{1,2})\s*(?:\+|plus)?\s*(?:-|to|\u2013)?\s*(?:\d{1,2})?\s*\+?\s*(?:years?|yrs?)\b",
    re.IGNORECASE,
)
_EXPERIENCE_CONTEXT = re.compile(r"experience|exp\b|working|industry|professional", re.IGNORECASE)


def years_required(text: str) -> int | None:
    """The smallest number of years of experience the text asks for, if it states one.

    Only numbers near the word "experience" count, so "10 years of the company" is ignored.
    """
    found: list[int] = []
    for match in _YEARS.finditer(text):
        around = text[max(0, match.start() - 60) : match.end() + 60]
        years = int(match.group(1))
        if _EXPERIENCE_CONTEXT.search(around) and 0 < years <= 25:
            found.append(years)
    return min(found) if found else None


_SENIOR = re.compile(r"\b(?:senior|sr\.?|staff|principal|lead|architect|head of|manager)\b", re.I)
_JUNIOR = re.compile(r"\b(?:junior|jr\.?|intern|trainee|graduate|entry[- ]level|associate)\b", re.I)


def level_of_title(title: str) -> str | None:
    if _SENIOR.search(title):
        return "senior"
    if _JUNIOR.search(title):
        return "junior"
    return None
