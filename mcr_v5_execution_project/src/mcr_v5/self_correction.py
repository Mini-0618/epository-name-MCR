from __future__ import annotations

from mcr_v5.core import LoopContext


class SelfCorrection:
    def repair(self, ctx: LoopContext, immune_report: dict) -> list[dict]:
        patches = []

        if immune_report["risk_level"] in ("medium", "high"):
            patches.append(
                {
                    "type": "prompt_guard",
                    "message": "reduce risk and add verification before next task",
                }
            )

        ctx.emit("self_correction.done", "self_correction", {"patches": len(patches)})
        return patches
