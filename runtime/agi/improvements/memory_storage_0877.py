# Auto-improvement #877
# Module: memory_storage
# Improvement: add_memory_ttl
# Description: Add time-to-live for memories
# Timestamp: 2026-06-08T03:20:46.462963+00:00


class MemoryTTL:
    def __init__(self, default_ttl_days=30):
        self.default_ttl = default_ttl_days

    def is_expired(self, memory):
        created = memory.get("created_at")
        if not created:
            return False
        age = (datetime.now() - parse(created)).days
        return age > self.default_ttl

    def filter_expired(self, memories):
        return [m for m in memories if not self.is_expired(m)]

