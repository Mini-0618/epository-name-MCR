from __future__ import annotations

import json
from pathlib import Path

from mcr_v5.core import LoopContext


class SleepConsolidator:
    def __init__(self, path: str = "runtime_logs/sleep_memory.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def consolidate(self, ctx: LoopContext) -> dict:
        memory = {
            "cycle_id": ctx.cycle_id,
            "events": len(ctx.events),
            "steps": len(ctx.steps),
            "failures": len(ctx.failures),
            "skills": len(ctx.skills),
        }

        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(memory, ensure_ascii=False) + "\n")

        ctx.emit("sleep.consolidated", "sleep_consolidator", memory)
        return memory
