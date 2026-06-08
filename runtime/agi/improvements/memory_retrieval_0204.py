# Auto-improvement #204
# Module: memory_retrieval
# Improvement: add_fuzzy_matching
# Description: Add fuzzy string matching for search
# Timestamp: 2026-06-08T03:20:46.043548+00:00


def fuzzy_match(query, text, threshold=0.6):
    q_chars = set(query.lower())
    t_chars = set(text.lower())
    overlap = len(q_chars & t_chars)
    total = len(q_chars | t_chars)
    return overlap / total > threshold

