# Auto-improvement #34
# Module: feedback_learning
# Improvement: add_feedback_weighting
# Description: Weight feedback by source reliability
# Timestamp: 2026-06-08T03:20:45.938399+00:00


def weight_feedback(feedback):
    weights = {"manual": 1.0, "self-diagnosis": 0.8, "a2a": 0.3}
    for f in feedback:
        source = f.get("source", "unknown")
        f["weight"] = weights.get(source, 0.5)
    return feedback

