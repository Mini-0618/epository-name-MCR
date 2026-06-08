from __future__ import annotations

from mcr_v5.core import LoopContext


class ImmuneSystem:
    def patrol(self, ctx: LoopContext) -> dict:
        risk_level = "low"

        if len(ctx.failures) >= 3:
            risk_level = "high"
        elif len(ctx.failures) > 0:
            risk_level = "medium"

        result = {
            "risk_level": risk_level,
            "failure_count": len(ctx.failures),
        }

        ctx.emit("immune.patrol", "immune_system", result)
        return result
