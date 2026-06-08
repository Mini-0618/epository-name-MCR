# Auto-improvement #367
# Module: memory_storage
# Improvement: add_memory_compression
# Description: Compress similar memories into summaries
# Timestamp: 2026-06-08T03:20:46.144901+00:00


def compress_similar(memories, threshold=0.8):
    groups = []
    for m in memories:
        added = False
        for g in groups:
            if similarity(m, g[0]) > threshold:
                g.append(m)
                added = True
                break
        if not added:
            groups.append([m])
    return [summarize(g) for g in groups]

