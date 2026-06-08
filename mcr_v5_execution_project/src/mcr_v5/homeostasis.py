from __future__ import annotations

from mcr_v5.core import LoopContext


class Homeostasis:
    def regulate(self, ctx: LoopContext, signal: dict) -> dict:
        salience = signal.get("salience", 0.5)

        policy = {
            "max_tasks_next_cycle": 1 if salience > 0.7 else 3,
            "energy_mode": "conserve" if salience > 0.7 else "normal",
        }

        ctx.emit("homeostasis.regulated", "homeostasis", policy)
        return policy
