from __future__ import annotations

from mcr_v5.core import LoopContext


class GlobalWorkspace:
    def broadcast(self, ctx: LoopContext, reflection: dict) -> dict:
        salience = 0.5

        if reflection.get("failures", 0) > 0:
            salience += 0.2

        signal = {
            "salience": salience,
            "message": reflection.get("summary", ""),
        }

        ctx.emit("workspace.broadcast", "global_workspace", signal)
        return signal
