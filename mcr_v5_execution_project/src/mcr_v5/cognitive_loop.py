from __future__ import annotations

from mcr_v5.core import LoopContext


class CognitiveLoop:
    def reflect(self, ctx: LoopContext) -> dict:
        reflection = {
            "events": len(ctx.events),
            "failures": len(ctx.failures),
            "steps": len(ctx.steps),
            "summary": "cycle reflected",
        }

        ctx.emit("cognitive.reflected", "cognitive_loop", reflection)
        return reflection
