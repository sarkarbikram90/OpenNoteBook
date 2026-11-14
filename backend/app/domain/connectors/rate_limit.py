"""OpenNotebook — Rate limiting for connector calls.

Enforces a minimum interval between operations so connectors respect external
API quotas. The clock and sleep functions are injectable to keep tests
deterministic.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class RateLimiter:
    """Enforce at most ``max_per_second`` operations per second (thread-safe)."""

    def __init__(
        self,
        max_per_second: float,
        *,
        time_func: Callable[[], float] = time.monotonic,
        sleep_func: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_per_second <= 0:
            raise ValueError("max_per_second must be > 0")
        self._min_interval = 1.0 / max_per_second
        self._time = time_func
        self._sleep = sleep_func
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def acquire(self) -> None:
        """Block (if needed) until the next operation is permitted."""
        with self._lock:
            now = self._time()
            if now < self._next_allowed:
                wait = self._next_allowed - now
                self._sleep(wait)
                now = self._next_allowed
            self._next_allowed = now + self._min_interval

    def __enter__(self) -> RateLimiter:
        self.acquire()
        return self

    def __exit__(self, *exc: object) -> None:
        return None
