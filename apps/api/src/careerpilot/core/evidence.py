"""Checking that a quote really appears in a fetched page.

A model asked to quote evidence may invent it. Every quote that ends up stored passes through
`quote_appears` against the text the fetcher actually returned for the cited URL.

Matching ignores things that change how text is typed but not what it says: letter case, runs of
whitespace, curly versus straight quotes, dash styles and invisible characters. It does NOT allow
paraphrase, reordering, or joining two passages with "...".
"""

import re
import unicodedata

MIN_QUOTE_CHARS = 12  # shorter strings match almost anything ("contact", "team")
MAX_QUOTE_CHARS = 300

_PUNCTUATION = str.maketrans(
    {
        "‘": "'",  # noqa: RUF001
        "’": "'",  # noqa: RUF001
        "“": '"',
        "”": '"',
        "–": "-",  # noqa: RUF001
        "—": "-",
        "−": "-",  # noqa: RUF001
        "…": "...",
    }
)
_INVISIBLE = re.compile("[​-‏⁠﻿­]")
_SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_PUNCTUATION)
    return _SPACES.sub(" ", _INVISIBLE.sub("", text)).strip().casefold()


def quote_appears(quote: str, page_text: str) -> bool:
    needle = normalize(quote)
    if not MIN_QUOTE_CHARS <= len(needle) <= MAX_QUOTE_CHARS:
        return False
    return needle in normalize(page_text)
