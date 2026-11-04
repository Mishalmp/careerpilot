import time
from collections import defaultdict, deque

from careerpilot.core.errors import ProblemError


class LoginThrottle:
    """In-memory failed-login limiter, keyed by email.

    Single process, resets on restart. Trade-off: anyone who can reach the API can lock the
    owner out for the window. Acceptable while the API is bound to localhost.
    """

    def __init__(self, max_failures: int, window_seconds: int) -> None:
        self._max = max_failures
        self._window = window_seconds
        self._failures: defaultdict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str, now: float) -> deque[float]:
        failures = self._failures[key]
        while failures and now - failures[0] > self._window:
            failures.popleft()
        if not failures:
            del self._failures[key]
        return failures

    def check(self, key: str) -> None:
        now = time.monotonic()
        failures = self._prune(key, now)
        if len(failures) >= self._max:
            retry_after = max(1, int(self._window - (now - failures[0])))
            raise ProblemError(
                429,
                "Too many failed logins",
                "Try again later.",
                headers={"Retry-After": str(retry_after)},
            )

    def record_failure(self, key: str) -> None:
        self._failures[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)
