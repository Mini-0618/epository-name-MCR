from __future__ import annotations

from mcr_v5.core import LoopContext


class FailureAnalyzer:
    def analyze(self, ctx: LoopContext, task_results: list[dict]) -> list[dict]:
        failures = []

        for item in task_results:
            if item.get("status") != "done":
                failures.append(
                    {
                        "goal_id": item.get("goal_id"),
                        "reason": item.get("error", "unknown"),
                    }
                )

        ctx.failures.extend(failures)
        ctx.emit("failure.analyzed", "failure_analyzer", {"count": len(failures)})
        return failures
