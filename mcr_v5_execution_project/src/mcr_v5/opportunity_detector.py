from __future__ import annotations

from mcr_v5.core import LoopContext


class OpportunityDetector:
    def detect(self, ctx: LoopContext, world_model: dict) -> list[dict]:
        opportunities = []

        if world_model.get("visible_files"):
            opportunities.append(
                {
                    "id": "audit_visible_python_files",
                    "priority": 5,
                    "reason": "python files detected",
                }
            )

        if not opportunities:
            opportunities.append(
                {
                    "id": "create_project_baseline",
                    "priority": 3,
                    "reason": "no obvious files detected",
                }
            )

        ctx.emit("opportunity.detected", "opportunity_detector", {"count": len(opportunities)})
        return opportunities
