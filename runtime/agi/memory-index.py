"""
memory-index.py -- ECOSYSTEM Memory Index

Inverted index over memory.jsonl for fast retrieval.
Supports both life-memory.jsonl and swarm/memory.jsonl formats.

Features:
  - Inverted index: {token -> set[mem_id]}
  - Tier index: {tier -> set[mem_id]}
  - Access count tracking
  - Last access tracking
  - Co-access graph (memories accessed in same query)
  - Multi-signal scoring: keyword + tier + frequency + recency + co-access

No external dependencies. Pure Python.
"""

import json
import math
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set


def _tokenize(text: str) -> Set[str]:
    """Split text into lowercase word tokens. Min 2 chars."""
    return {w for w in re.split(r'\W+', text.lower()) if len(w) >= 2}


def _extract_content(entry: dict) -> str:
    """Extract searchable text from a memory entry (either format)."""
    # swarm format: summary + lessons + successes
    parts = []
    if "summary" in entry:
        parts.append(entry["summary"])
    if "lessons" in entry:
        parts.append(entry["lessons"])
    if "successes" in entry:
        parts.extend(entry["successes"])
    if "failures" in entry:
        parts.extend(entry["failures"])
    if "next_suggestions" in entry:
        parts.append(entry["next_suggestions"])
    # life format: record dict
    record = entry.get("record", {})
    if isinstance(record, dict):
        for key in ("user_intent", "summary", "content", "status"):
            val = record.get(key, "")
            if val and isinstance(val, str):
                parts.append(val)
        # target_apps can be string or list
        ta = record.get("target_apps", "")
        if isinstance(ta, list):
            parts.extend(ta)
        elif isinstance(ta, str) and ta:
            parts.append(ta)
    elif isinstance(record, str):
        parts.append(record)
    # generic fallback
    if "content" in entry and isinstance(entry["content"], str):
        parts.append(entry["content"])
    return " ".join(parts)


def _extract_tier(entry: dict) -> str:
    """Determine tier for a memory entry."""
    record = entry.get("record", {})
    if isinstance(record, dict) and "tier" in record:
        t = record["tier"]
        if t in ("working", "episodic", "semantic", "archive"):
            return t
    # Default tier based on source
    source = entry.get("source", "")
    if "life" in source:
        return "episodic"
    if "swarm" in source or "run_id" in entry:
        return "semantic"
    return "episodic"


def _extract_timestamp(entry: dict) -> str:
    """Extract ISO timestamp from entry."""
    for key in ("written_at", "created_at", "timestamp"):
        if key in entry and entry[key]:
            return entry[key]
    return ""


class MemoryIndex:
    """
    Query index over ECOSYSTEM memory.jsonl files.

    Builds inverted index from memory content for fast keyword search,
    tracks tier membership, access frequency, and recency.
    """

    def __init__(self, memory_path: str = ""):
        self._memory_path = memory_path
        self._keyword_index: Dict[str, Set[str]] = defaultdict(set)
        self._tier_index: Dict[str, Set[str]] = defaultdict(set)
        self._memories: Dict[str, dict] = {}
        self._access_count: Dict[str, int] = defaultdict(int)
        self._last_access: Dict[str, str] = {}  # mem_id -> ISO timestamp
        self._coaccess: Dict[str, Set[str]] = defaultdict(set)
        self._tick: int = 0

        if memory_path and os.path.exists(memory_path):
            self.build()

    def build(self):
        """Build index from memory.jsonl file."""
        self._keyword_index.clear()
        self._tier_index.clear()
        self._memories.clear()
        self._access_count.clear()
        self._last_access.clear()
        self._coaccess.clear()
        self._tick = 0

        if not self._memory_path or not os.path.exists(self._memory_path):
            return

        with open(self._memory_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self._index_entry(entry, self._tick)
                self._tick += 1

    def _index_entry(self, entry: dict, tick: int):
        """Index a single memory entry."""
        mid = entry.get("memory_id", "")
        if not mid:
            return

        self._memories[mid] = entry

        # Tier
        tier = _extract_tier(entry)
        self._tier_index[tier].add(mid)

        # Keyword tokens
        content = _extract_content(entry)
        for token in _tokenize(content):
            self._keyword_index[token].add(mid)

        # Timestamp for recency
        ts = _extract_timestamp(entry)
        if ts:
            self._last_access[mid] = ts

    def update(self, memory_entry: dict):
        """Add a single entry to the index incrementally."""
        self._index_entry(memory_entry, self._tick)
        self._tick += 1

    def search(
        self,
        query: str,
        tier: Optional[str] = None,
        limit: int = 5,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Search memories with multi-signal scoring.

        Scoring:
            - keyword match: +1.0 per matching token (normalized by query length)
            - tier bonus: +0.3 if tier matches filter
            - access frequency: +0.1 * log(1 + access_count)
            - recency: +0.2 * recency_factor (more recent = higher)
            - co-access boost: +0.1 * number of co-accessed memories (max 5)
        """
        if not query:
            return self._recent_memories(tier, limit)

        query_tokens = _tokenize(query)
        if not query_tokens:
            return self._recent_memories(tier, limit)

        # Candidates: union of keyword-matched memory IDs
        candidates: Set[str] = set()
        for token in query_tokens:
            candidates.update(self._keyword_index.get(token, set()))

        # Filter by tier
        if tier:
            candidates = candidates & self._tier_index.get(tier, set())

        # Score
        all_timestamps = [v for v in self._last_access.values() if v]
        latest_ts = max(all_timestamps) if all_timestamps else ""
        results = []
        for mid in candidates:
            if mid not in self._memories:
                continue
            minfo = self._memories[mid]

            # Keyword match score
            mem_tokens = _tokenize(_extract_content(minfo))
            overlap = query_tokens & mem_tokens
            keyword_score = len(overlap) / len(query_tokens) if query_tokens else 0

            # Tier bonus
            mem_tier = _extract_tier(minfo)
            tier_bonus = 0.3 if (tier and mem_tier == tier) else 0

            # Access frequency bonus
            freq_bonus = 0.1 * math.log(1 + self._access_count.get(mid, 0))

            # Recency bonus
            recency_bonus = 0.0
            mem_ts = self._last_access.get(mid, "")
            if mem_ts and latest_ts:
                try:
                    mem_dt = datetime.fromisoformat(mem_ts)
                    latest_dt = datetime.fromisoformat(latest_ts)
                    span = (latest_dt - mem_dt).total_seconds()
                    if span >= 0:
                        recency_bonus = 0.2 * (1.0 / (1.0 + span / 86400.0))
                except (ValueError, TypeError):
                    pass

            # Co-access bonus
            coaccess_count = len(self._coaccess.get(mid, set()))
            coaccess_bonus = 0.1 * min(coaccess_count, 5)

            score = keyword_score + tier_bonus + freq_bonus + recency_bonus + coaccess_bonus

            if score >= min_score:
                results.append({
                    "memory_id": mid,
                    "content": _extract_content(minfo)[:300],
                    "tier": mem_tier,
                    "score": round(score, 4),
                    "access_count": self._access_count.get(mid, 0),
                    "timestamp": mem_ts,
                    "coaccess": list(self._coaccess.get(mid, set()))[:5],
                })

        results.sort(key=lambda r: r["score"], reverse=True)

        # Record co-access: all results in this query are co-accessed
        result_ids = [r["memory_id"] for r in results[:limit]]
        for i, mid_i in enumerate(result_ids):
            for mid_j in result_ids[i + 1:]:
                self._coaccess[mid_i].add(mid_j)
                self._coaccess[mid_j].add(mid_i)

        # Bump access counts
        for r in results[:limit]:
            self._access_count[r["memory_id"]] += 1

        return results[:limit]

    def _recent_memories(self, tier: Optional[str], limit: int) -> List[Dict[str, Any]]:
        """Return most recent memories (fallback when no query text)."""
        candidates = list(self._memories.items())
        if tier:
            candidates = [(mid, m) for mid, m in candidates if _extract_tier(m) == tier]

        candidates.sort(
            key=lambda x: self._last_access.get(x[0], ""),
            reverse=True,
        )
        return [
            {
                "memory_id": mid,
                "content": _extract_content(m)[:300],
                "tier": _extract_tier(m),
                "score": 0,
                "access_count": self._access_count.get(mid, 0),
                "timestamp": self._last_access.get(mid, ""),
                "coaccess": list(self._coaccess.get(mid, set()))[:5],
            }
            for mid, m in candidates[:limit]
        ]

    def get_related(self, memory_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get memories co-accessed with the given memory."""
        neighbors = self._coaccess.get(memory_id, set())
        results = []
        for mid in neighbors:
            if mid in self._memories:
                minfo = self._memories[mid]
                results.append({
                    "memory_id": mid,
                    "content": _extract_content(minfo)[:300],
                    "tier": _extract_tier(minfo),
                    "access_count": self._access_count.get(mid, 0),
                })
        results.sort(key=lambda r: r["access_count"], reverse=True)
        return results[:limit]

    def record_access(self, memory_id: str):
        """Record that a memory was accessed (bump count)."""
        self._access_count[memory_id] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Return index statistics."""
        return {
            "total_memories": len(self._memories),
            "tiers": {t: len(ids) for t, ids in self._tier_index.items()},
            "unique_tokens": len(self._keyword_index),
            "total_accesses": sum(self._access_count.values()),
            "coaccess_edges": sum(len(v) for v in self._coaccess.values()) // 2,
            "memory_path": self._memory_path,
        }


# =============================================================================
# CLI
# =============================================================================

def main():
    """CLI entry point."""
    import sys

    ecosystem_root = str(os.path.join(os.path.dirname(__file__), "..", ".."))
    memory_path = os.path.join(ecosystem_root, "runtime", "swarm", "memory.jsonl")
    alt_path = os.path.join(ecosystem_root, "runtime", "memory", "life-memory.jsonl")

    # Use whichever file has more entries
    if os.path.exists(alt_path):
        with open(alt_path, "r", encoding="utf-8") as f:
            alt_count = sum(1 for l in f if l.strip())
        if os.path.exists(memory_path):
            with open(memory_path, "r", encoding="utf-8") as f:
                main_count = sum(1 for l in f if l.strip())
            if alt_count > main_count:
                memory_path = alt_path
        else:
            memory_path = alt_path

    idx = MemoryIndex(memory_path)

    if len(sys.argv) > 1 and sys.argv[1] == "stats":
        print(json.dumps(idx.get_stats(), ensure_ascii=False, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "search":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        results = idx.search(query, limit=5)
        for r in results:
            print(f"  [{r['tier']}] score={r['score']:.3f} | {r['content'][:80]}")
    elif len(sys.argv) > 1 and sys.argv[1] == "related":
        mid = sys.argv[2] if len(sys.argv) > 2 else ""
        if mid:
            results = idx.get_related(mid)
            for r in results:
                print(f"  [{r['tier']}] accesses={r['access_count']} | {r['content'][:80]}")
        else:
            print("Usage: memory-index.py related <memory_id>")
    else:
        print("Usage: memory-index.py [stats|search <query>|related <memory_id>]")
        print(json.dumps(idx.get_stats(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
