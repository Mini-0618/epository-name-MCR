from __future__ import annotations

from mcr_v5.core import Event


class EventBus:
    def __init__(self) -> None:
        self.queue: list[Event] = []

    def publish(self, event: Event) -> None:
        self.queue.append(event)

    def drain(self) -> list[Event]:
        events = list(self.queue)
        self.queue.clear()
        return events
