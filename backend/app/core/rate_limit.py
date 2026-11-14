"""Small in-memory, per-key sliding-window rate limiter.

Enough for a single-process deployment (the Render service runs one
worker). If the backend is ever scaled to several workers, move this to a
shared store, since each process would otherwise keep its own counts.
"""
import time
from collections import defaultdict, deque
from typing import Deque, Dict


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        """Records a hit for `key` and returns False once it is over the limit."""
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window_seconds:
            hits.popleft()
        if len(hits) >= self.max_requests:
            return False
        hits.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()
