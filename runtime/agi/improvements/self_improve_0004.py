# Auto-improvement #4
# Module: self_improve
# Improvement: add_pattern_detection
# Description: Detect recurring failure patterns
# Timestamp: 2026-06-08T03:20:45.920857+00:00


def detect_patterns(failures):
    patterns = {}
    for f in failures:
        key = f.get("type", "unknown")
        patterns[key] = patterns.get(key, 0) + 1
    return {k: v for k, v in patterns.items() if v >= 3}

