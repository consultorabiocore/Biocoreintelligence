from collections import defaultdict, deque
from collections.abc import Callable
from datetime import datetime, timedelta, timezone


class RateLimitExceeded(PermissionError):
    pass


class InMemorySlidingWindowLimiter:
    """Development fallback. Production should use a shared Redis/Postgres store."""

    def __init__(
        self,
        *,
        limit: int,
        window: timedelta,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._limit = limit
        self._window = window
        self._clock = clock
        self._events: dict[str, deque[datetime]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = self._clock()
        events = self._events[key]
        threshold = now - self._window
        while events and events[0] <= threshold:
            events.popleft()
        if len(events) >= self._limit:
            raise RateLimitExceeded("Too many authentication attempts")
        events.append(now)
