from __future__ import annotations

from mcr_v5.core import LoopContext


class PatternDetector:
    def detect(self, ctx: LoopContext) -> list[dict]:
        patterns = []

        if len(ctx.failures) >= 2:
            patterns.append(
                {
                    "type": "repeated_failure",
                    "count": len(ctx.failures),
                }
            )

        ctx.emit("pattern.detected", "pattern_detector", {"count": len(patterns)})
        return patterns
