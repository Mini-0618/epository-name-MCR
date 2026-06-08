# Auto-improvement #261
# Module: memory_retrieval
# Improvement: add_context_ranking
# Description: Rank results by context relevance
# Timestamp: 2026-06-08T03:20:46.077380+00:00


def context_rank(results, context):
    for r in results:
        score = r.get("score", 0)
        if context in r.get("content", ""):
            score *= 1.5
        r["score"] = score
    return sorted(results, key=lambda x: x["score"], reverse=True)

