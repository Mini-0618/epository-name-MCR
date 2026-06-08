from __future__ import annotations

import time
from typing import Any


class SimpleRateLimiter:
    def __init__(self, rate: float, capacity: int) -> None:
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last = time.monotonic()

    def allow(self) -> bool:
        now = time.monotonic()
        elapsed = now - self.last
        self.last = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

        if self.tokens >= 1:
            self.tokens -= 1
            return True

        return False


class RingBuffer:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.data: list[Any] = []

    def put(self, item: Any) -> None:
        self.data.append(item)
        if len(self.data) > self.capacity:
            self.data.pop(0)

    def to_list(self) -> list[Any]:
        return list(self.data)
