from __future__ import annotations

from mcr_v5.core import LoopContext


class TaskEngine:
    def execute(self, ctx: LoopContext, goals: list[dict], max_tasks: int = 3) -> list[dict]:
        results = []

        for goal in sorted(goals, key=lambda x: x["priority"], reverse=True)[:max_tasks]:
            results.append(
                {
                    "goal_id": goal["goal_id"],
                    "status": "done",
                    "output": f"executed {goal['goal_id']}",
                }
            )

        ctx.emit("task.executed", "task_engine", {"count": len(results)})
        return results
