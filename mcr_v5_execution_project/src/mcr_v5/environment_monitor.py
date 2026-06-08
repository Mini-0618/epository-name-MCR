from __future__ import annotations

from pathlib import Path

from mcr_v5.core import LoopContext


class EnvironmentMonitor:
    def scan(self, ctx: LoopContext) -> dict:
        root = Path.cwd()
        files = list(root.glob("*.py"))

        result = {
            "cwd": str(root),
            "python_files": [p.name for p in files],
            "file_count": len(files),
        }

        ctx.emit("environment.scanned", "environment_monitor", result)
        return result
