"""
knowledge-consolidator.py -- MCR Knowledge Consolidation

Merges similar memories to keep the knowledge base clean.
Uses Jaccard similarity on tokenized content to detect duplicates.
Archives redundant entries while keeping the most recent representative.

No external dependencies. Works with memory.jsonl (JSON lines) format.
"""

import json
import os
import re
import sys
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path


# =============================================================================
# PARAMETERS
# =============================================================================
DEFAULT_THRESHOLD = 0.8
ARCHIVE_SUFFIX = ".archived"
CONSOLIDATION_LOG = "consolidation-log.jsonl"


# =============================================================================
# TOKENIZER
# =============================================================================

def tokenize(text):
    """Split text into lowercase tokens, stripping punctuation."""
    if not text:
        return set()
    # Lowercase, split on whitespace and punctuation
    tokens = re.findall(r"[a-z0-9_一-鿿]+", text.lower())
    return set(tokens)


def jaccard_similarity(set_a, set_b):
    """Jaccard index: |intersection| / |union|."""
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


# =============================================================================
# KNOWLEDGE CONSOLIDATOR
# =============================================================================

class KnowledgeConsolidator:
    """
    Finds and merges duplicate memories in a JSONL memory file.

    Strategy:
      1. Tokenize each memory's content (summary or record fields)
      2. Pairwise Jaccard similarity to find duplicate groups
      3. Within each group: keep the most recent entry, archive the rest
      4. Archive = move lines to a separate .archived file
      5. Log all actions to consolidation-log.jsonl
    """

    def __init__(self, memory_path):
        self.memory_path = memory_path
        self.archive_path = memory_path + ARCHIVE_SUFFIX
        self.log_path = os.path.join(
            os.path.dirname(memory_path), CONSOLIDATION_LOG
        )
        self._memories = []
        self._tokens = []
        self._load()

    def _load(self):
        """Load all memories from JSONL."""
        self._memories = []
        self._tokens = []
        if not os.path.exists(self.memory_path):
            return
        with open(self.memory_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    self._memories.append(entry)
                    content = self._extract_content(entry)
                    self._tokens.append(tokenize(content))
                except json.JSONDecodeError:
                    continue

    def _extract_content(self, entry):
        """Extract searchable text from a memory entry."""
        # Try summary first
        if "summary" in entry and entry["summary"]:
            return str(entry["summary"])
        # Try record field
        record = entry.get("record", {})
        if isinstance(record, dict):
            # Prefer user_intent, then summary, then content
            for key in ("user_intent", "summary", "content", "text"):
                if key in record and record[key]:
                    return str(record[key])
            return json.dumps(record, ensure_ascii=False)[:300]
        if isinstance(record, str):
            return record
        # Fallback: serialize whole entry
        return json.dumps(entry, ensure_ascii=False)[:300]

    def _parse_timestamp(self, entry):
        """Parse created_at or written_at into datetime, or epoch fallback."""
        for key in ("created_at", "written_at"):
            ts = entry.get(key, "")
            if ts:
                try:
                    # Handle ISO format with timezone
                    return datetime.fromisoformat(ts)
                except (ValueError, TypeError):
                    pass
        return datetime.min.replace(tzinfo=timezone.utc)

    def find_duplicates(self, threshold=DEFAULT_THRESHOLD):
        """
        Find groups of memories with similar content.

        Returns list of groups, each group is a list of indices into
        self._memories where pairwise Jaccard > threshold.
        """
        n = len(self._memories)
        if n < 2:
            return []

        # Union-Find for grouping
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        # Compare all pairs
        for i in range(n):
            if not self._tokens[i]:
                continue
            for j in range(i + 1, n):
                if not self._tokens[j]:
                    continue
                sim = jaccard_similarity(self._tokens[i], self._tokens[j])
                if sim >= threshold:
                    union(i, j)

        # Collect groups
        groups_map = {}
        for i in range(n):
            root = find(i)
            if root not in groups_map:
                groups_map[root] = []
            groups_map[root].append(i)

        # Only return groups with 2+ members
        groups = [indices for indices in groups_map.values() if len(indices) >= 2]
        return groups

    def consolidate(self, dry_run=True, threshold=DEFAULT_THRESHOLD):
        """
        Merge similar memories: keep the most recent in each group,
        archive the rest.

        Returns dict with:
          - groups_found: number of duplicate groups
          - total_duplicates: total entries in duplicate groups
          - archived: number of entries archived (or would archive)
          - kept: number of entries kept
        """
        groups = self.find_duplicates(threshold)

        if not groups:
            return {
                "groups_found": 0,
                "total_duplicates": 0,
                "archived": 0,
                "kept": len(self._memories),
                "dry_run": dry_run,
            }

        # Determine which indices to archive
        archive_indices = set()
        keep_indices = set()

        for group in groups:
            # Sort by timestamp descending; keep the newest
            sorted_group = sorted(
                group,
                key=lambda idx: self._parse_timestamp(self._memories[idx]),
                reverse=True,
            )
            keep_indices.add(sorted_group[0])
            for idx in sorted_group[1:]:
                archive_indices.add(idx)

        if dry_run:
            # Log what would happen
            self._log_consolidation(groups, archive_indices, keep_indices, dry_run=True)
            return {
                "groups_found": len(groups),
                "total_duplicates": sum(len(g) for g in groups),
                "archived": len(archive_indices),
                "kept": len(self._memories) - len(archive_indices),
                "dry_run": True,
            }

        # Actually consolidate
        archived_entries = []
        kept_entries = []
        for idx, entry in enumerate(self._memories):
            if idx in archive_indices:
                archived_entries.append(entry)
            else:
                kept_entries.append(entry)

        # Backup original
        backup_path = self.memory_path + ".bak"
        shutil.copy2(self.memory_path, backup_path)

        # Write kept entries back
        with open(self.memory_path, "w", encoding="utf-8") as f:
            for entry in kept_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Append archived entries to archive file
        with open(self.archive_path, "a", encoding="utf-8") as f:
            for entry in archived_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Log consolidation
        self._log_consolidation(groups, archive_indices, keep_indices, dry_run=False)

        return {
            "groups_found": len(groups),
            "total_duplicates": sum(len(g) for g in groups),
            "archived": len(archived_entries),
            "kept": len(kept_entries),
            "dry_run": False,
            "backup_path": backup_path,
            "archive_path": self.archive_path,
        }

    def _log_consolidation(self, groups, archive_indices, keep_indices, dry_run):
        """Append consolidation event to log."""
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "memory_path": self.memory_path,
            "dry_run": dry_run,
            "groups_found": len(groups),
            "total_duplicates": sum(len(g) for g in groups),
            "archived": len(archive_indices),
            "kept": len(keep_indices),
            "groups": [
                {
                    "size": len(g),
                    "kept_idx": sorted(
                        g,
                        key=lambda i: self._parse_timestamp(self._memories[i]),
                        reverse=True,
                    )[0],
                    "archived_idxs": sorted(
                        g,
                        key=lambda i: self._parse_timestamp(self._memories[i]),
                        reverse=True,
                    )[1:],
                }
                for g in groups
            ],
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    def get_stats(self):
        """Return consolidation stats."""
        groups = self.find_duplicates()
        duplicate_count = sum(len(g) for g in groups)
        unique_count = len(self._memories) - duplicate_count + len(groups)

        # Count archived entries
        archived_count = 0
        if os.path.exists(self.archive_path):
            with open(self.archive_path, "r", encoding="utf-8") as f:
                archived_count = sum(1 for line in f if line.strip())

        return {
            "total_memories": len(self._memories),
            "unique_memories": max(0, unique_count),
            "duplicates_found": duplicate_count,
            "consolidated": 0,
            "archived": archived_count,
            "groups": len(groups),
        }

    def auto_consolidate(self, max_age_days=30, threshold=DEFAULT_THRESHOLD):
        """
        Auto-consolidate old memories.
        Only processes memories older than max_age_days.
        Groups by content similarity, keeps one representative per group.
        """
        if not self._memories:
            return {"processed": 0, "archived": 0, "reason": "no memories"}

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=max_age_days)

        # Split into old and recent
        old_indices = []
        recent_indices = []
        for idx, entry in enumerate(self._memories):
            ts = self._parse_timestamp(entry)
            # Make both tz-aware or both naive for comparison
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts < cutoff:
                old_indices.append(idx)
            else:
                recent_indices.append(idx)

        if len(old_indices) < 2:
            return {
                "processed": len(old_indices),
                "archived": 0,
                "reason": f"only {len(old_indices)} old memories (need 2+)",
                "old_count": len(old_indices),
                "recent_count": len(recent_indices),
            }

        # Build sub-list of old memories
        old_tokens = [self._tokens[i] for i in old_indices]
        n = len(old_indices)

        # Union-Find on old memories
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for i in range(n):
            if not old_tokens[i]:
                continue
            for j in range(i + 1, n):
                if not old_tokens[j]:
                    continue
                sim = jaccard_similarity(old_tokens[i], old_tokens[j])
                if sim >= threshold:
                    union(i, j)

        # Collect groups
        groups_map = {}
        for i in range(n):
            root = find(i)
            if root not in groups_map:
                groups_map[root] = []
            groups_map[root].append(i)

        groups = [g for g in groups_map.values() if len(g) >= 2]

        if not groups:
            return {
                "processed": len(old_indices),
                "archived": 0,
                "reason": "no similar old memories found",
                "old_count": len(old_indices),
                "recent_count": len(recent_indices),
            }

        # Determine archive indices (within old_indices)
        archive_set = set()
        for group in groups:
            sorted_group = sorted(
                group,
                key=lambda local_idx: self._parse_timestamp(
                    self._memories[old_indices[local_idx]]
                ),
                reverse=True,
            )
            for local_idx in sorted_group[1:]:
                archive_set.add(old_indices[local_idx])

        # Perform consolidation
        kept_entries = []
        archived_entries = []
        for idx, entry in enumerate(self._memories):
            if idx in archive_set:
                archived_entries.append(entry)
            else:
                kept_entries.append(entry)

        # Backup and write
        backup_path = self.memory_path + ".bak"
        shutil.copy2(self.memory_path, backup_path)

        with open(self.memory_path, "w", encoding="utf-8") as f:
            for entry in kept_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        with open(self.archive_path, "a", encoding="utf-8") as f:
            for entry in archived_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Log
        log_entry = {
            "timestamp": now.isoformat(),
            "memory_path": self.memory_path,
            "mode": "auto_consolidate",
            "max_age_days": max_age_days,
            "old_count": len(old_indices),
            "recent_count": len(recent_indices),
            "groups_found": len(groups),
            "archived": len(archived_entries),
            "kept": len(kept_entries),
        }
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        return {
            "processed": len(old_indices),
            "archived": len(archived_entries),
            "kept": len(kept_entries),
            "groups_merged": len(groups),
            "old_count": len(old_indices),
            "recent_count": len(recent_indices),
        }


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """CLI entry point."""
    ecosystem_root = str(Path(__file__).resolve().parents[2])
    swarm_path = os.path.join(ecosystem_root, "runtime", "swarm", "memory.jsonl")
    life_path = os.path.join(ecosystem_root, "runtime", "memory", "life-memory.jsonl")

    # Use whichever memory file exists
    memory_path = swarm_path
    if not os.path.exists(swarm_path) and os.path.exists(life_path):
        memory_path = life_path

    if not os.path.exists(memory_path):
        print(json.dumps({"error": "no memory file found", "checked": [swarm_path, life_path]}))
        sys.exit(1)

    consolidator = KnowledgeConsolidator(memory_path)

    if len(sys.argv) < 2:
        print("Usage: knowledge-consolidator.py [stats|find-duplicates|consolidate|auto-consolidate]")
        stats = consolidator.get_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "stats":
        stats = consolidator.get_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    elif cmd == "find-duplicates":
        threshold = float(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_THRESHOLD
        groups = consolidator.find_duplicates(threshold)
        result = {
            "groups": len(groups),
            "total_duplicates": sum(len(g) for g in groups),
            "threshold": threshold,
            "details": [],
        }
        for g in groups:
            sorted_g = sorted(
                g,
                key=lambda i: consolidator._parse_timestamp(consolidator._memories[i]),
                reverse=True,
            )
            group_info = {
                "size": len(g),
                "keep": consolidator._extract_content(consolidator._memories[sorted_g[0]])[:80],
                "archive": [
                    consolidator._extract_content(consolidator._memories[i])[:80]
                    for i in sorted_g[1:]
                ],
            }
            result["details"].append(group_info)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "consolidate":
        dry_run = True
        threshold = DEFAULT_THRESHOLD
        for arg in sys.argv[2:]:
            if arg == "--execute":
                dry_run = False
            elif arg == "--dry-run":
                dry_run = True
            else:
                try:
                    threshold = float(arg)
                except ValueError:
                    pass
        result = consolidator.consolidate(dry_run=dry_run, threshold=threshold)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "auto-consolidate":
        max_age = 30
        threshold = DEFAULT_THRESHOLD
        for arg in sys.argv[2:]:
            if arg.startswith("--age="):
                max_age = int(arg.split("=")[1])
            else:
                try:
                    threshold = float(arg)
                except ValueError:
                    pass
        result = consolidator.auto_consolidate(max_age_days=max_age, threshold=threshold)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        print("Usage: knowledge-consolidator.py [stats|find-duplicates|consolidate|auto-consolidate]")
        sys.exit(1)


if __name__ == "__main__":
    main()
