"""Hints on a STAR story. Pure: they point at weak spots and never judge truth."""

import re

MIN_PART_WORDS = 8
_NUMBER = re.compile(r"\d")
_WE = re.compile(r"\b(we|our|us)\b", re.IGNORECASE)
_I = re.compile(r"\b(i|my|me)\b", re.IGNORECASE)


def hints(situation: str, task: str, action: str, result: str, evidence: str | None) -> list[str]:
    """Things an interviewer would probe. Empty when the story already covers them."""
    found: list[str] = []
    for name, text in (
        ("situation", situation),
        ("task", task),
        ("action", action),
        ("result", result),
    ):
        if len(text.split()) < MIN_PART_WORDS:
            found.append(f"The {name} is very short. Add what a stranger would need to follow it.")
    if _NUMBER.search(result) and not (evidence or "").strip():
        found.append("The result has a number but no evidence. Only use figures you can defend.")
    if len(_WE.findall(action)) > len(_I.findall(action)):
        found.append('The action says "we" more than "I". Make your own part clear.')
    return found
