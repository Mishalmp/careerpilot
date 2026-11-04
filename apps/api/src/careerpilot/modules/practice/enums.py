from enum import StrEnum


class Language(StrEnum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    SQL = "sql"


class Difficulty(StrEnum):
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"


class Kind(StrEnum):
    FUNCTION = "function"
    SQL = "sql"


class ProgressStatus(StrEnum):
    UNSOLVED = "unsolved"
    ATTEMPTED = "attempted"
    SOLVED = "solved"


class Compare(StrEnum):
    """How a function's result is compared with the expected value."""

    EXACT = "exact"
    UNORDERED = "unordered"  # same items in any order
    UNORDERED_NESTED = "unordered_nested"  # groups of items, in any order, each in any order
    FLOAT = "float"  # numbers within 1e-6
