from __future__ import annotations

import json
from pathlib import Path

from mcr_v5.core import LoopContext


class ProvenanceRecorder:
    def __init__(self, path: str = "runtime_logs/provenance.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, ctx: LoopContext, data: dict) -> None:
        row = {
            "cycle_id": ctx.cycle_id,
            "data": data,
        }

        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

        ctx.emit("provenance.recorded", "provenance", {"path": str(self.path)})
