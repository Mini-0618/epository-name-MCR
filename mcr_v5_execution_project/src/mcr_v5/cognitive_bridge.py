from __future__ import annotations

from mcr_v5.core import LoopContext


class CognitiveBridge:
    def build_world_model(self, ctx: LoopContext, environment: dict) -> dict:
        model = {
            "project_type": "local_runtime",
            "visible_files": environment.get("python_files", []),
            "confidence": 0.75,
        }

        ctx.emit("world_model.updated", "cognitive_bridge", model)
        return model
