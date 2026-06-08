from __future__ import annotations

import json
from pathlib import Path

from mcr_v5.core import LoopContext


class EvolutionEngine:
    def __init__(self, path: str = "runtime_logs/skills.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def evolve(self, ctx: LoopContext, failures: list[dict], patterns: list[dict]) -> list[dict]:
        skills = []

        if not failures:
            skills.append(
                {
                    "skill": "stable_cycle",
                    "reason": "cycle completed without failures",
                }
            )
        else:
            skills.append(
                {
                    "skill": "failure_avoidance",
                    "reason": f"{len(failures)} failures observed",
                }
            )

        for skill in skills:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(skill, ensure_ascii=False) + "\n")

        ctx.skills.extend(skills)
        ctx.emit("evolution.skills_updated", "evolution", {"count": len(skills)})
        return skills
