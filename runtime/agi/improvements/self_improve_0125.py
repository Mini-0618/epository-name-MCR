# Auto-improvement #125
# Module: self_improve
# Improvement: add_improvement_scoring
# Description: Score improvements by impact
# Timestamp: 2026-06-08T03:20:45.994373+00:00


def score_improvement(improvement):
    impact = improvement.get("impact", 0)
    effort = improvement.get("effort", 1)
    risk = improvement.get("risk", 0.5)
    return (impact * (1 - risk)) / effort

