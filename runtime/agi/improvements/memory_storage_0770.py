# Auto-improvement #770
# Module: memory_storage
# Improvement: add_memory_dedup
# Description: Deduplicate memories by content hash
# Timestamp: 2026-06-08T03:20:46.395385+00:00


def deduplicate(memories):
    seen = set()
    unique = []
    for m in memories:
        h = hash(m.get("content", ""))
        if h not in seen:
            seen.add(h)
            unique.append(m)
    return unique

