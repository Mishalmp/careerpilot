import logging
from typing import Any

import structlog

SENSITIVE_KEYS = frozenset(
    {
        "password",
        "authorization",
        "cookie",
        "set-cookie",
        "token",
        "csrf_token",
        "api_key",
        "secret",
    }
)


def redact_sensitive(_: Any, __: str, event_dict: structlog.typing.EventDict) -> Any:
    """Top-level keys only: log fields, never raw request bodies or headers."""
    for key in event_dict:
        if key.lower() in SENSITIVE_KEYS:
            event_dict[key] = "[redacted]"
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_sensitive,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelNamesMapping()[level]),
        cache_logger_on_first_use=True,
    )
