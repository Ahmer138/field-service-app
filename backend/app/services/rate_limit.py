from __future__ import annotations

from collections import defaultdict, deque
from math import ceil
from threading import Lock
from time import monotonic


class RateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, *, scope: str, identifier: str, limit: int, window_seconds: int) -> int | None:
        now = monotonic()
        bucket_key = f"{scope}:{identifier}"

        with self._lock:
            bucket = self._buckets[bucket_key]
            cutoff = now - window_seconds

            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= limit:
                return max(1, ceil(bucket[0] + window_seconds - now))

            bucket.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


rate_limiter = RateLimiter()
