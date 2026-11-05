from enum import StrEnum


class SourceKind(StrEnum):
    PASTED = "pasted"  # text you copied from a page you read yourself
    FETCHED = "fetched"  # a page CareerPilot fetched through the safe fetcher


class ItemKind(StrEnum):
    ROUND = "round"
    TOPIC = "topic"
    QUESTION = "question"
    TIP = "tip"
