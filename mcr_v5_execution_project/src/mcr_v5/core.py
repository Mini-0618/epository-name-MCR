from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Event:
    type: str
    source: str
    payload: dict[str, Any]
    created_at: float = field(default_factory=time.time)


@dataclass
class LoopContext:
    cycle_id: str
    state: dict[str, Any] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)
    skills: list[dict[str, Any]] = field(default_factory=list)

    def emit(self, event_type: str, source: str, payload: dict[str, Any]) -> None:
        self.events.append(Event(type=event_type, source=source, payload=payload))

    def step(self, name: str, system: str, ok: bool, detail: dict[str, Any]) -> None:
        self.steps.append(
            {
                "name": name,
                "system": system,
                "ok": ok,
                "detail": detail,
                "time": time.time(),
            }
        )
