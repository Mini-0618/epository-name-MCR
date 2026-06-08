from __future__ import annotations

from mcr_v5.core import LoopContext


class GoalGenerator:
    def generate(self, ctx: LoopContext, opportunities: list[dict]) -> list[dict]:
        goals = []

        for item in opportunities:
            goals.append(
                {
                    "goal_id": f"goal_{item['id']}",
                    "source": item["id"],
                    "priority": item["priority"],
                    "description": f"Handle opportunity: {item['reason']}",
                }
            )

        ctx.emit("goal.generated", "goal_generator", {"count": len(goals)})
        return goals
