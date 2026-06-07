"""
memory-retriever.py -- ECOSYSTEM Memory Retriever

High-level API wrapping MemoryIndex.
Provides search, recent, related, semantic, and LLM context formatting.

No external dependencies. Pure Python.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Import MemoryIndex from same directory
_script_dir = str(Path(__file__).resolve().parent)
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

_mi_mod = __import__("memory-index")
MemoryIndex = _mi_mod.MemoryIndex

# Import ConceptMap for semantic retrieval
try:
    _cm_mod = __import__("concept_map")
    ConceptMap = _cm_mod.ConceptMap
except ImportError:
    ConceptMap = None


def _find_memory_files(ecosystem_root: str) -> List[str]:
    """Find available memory JSONL files, return paths sorted by size."""
    candidates = [
        os.path.join(ecosystem_root, "runtime", "swarm", "memory.jsonl"),
        os.path.join(ecosystem_root, "runtime", "memory", "life-memory.jsonl"),
    ]
    found = []
    for p in candidates:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                count = sum(1 for l in f if l.strip())
            if count > 0:
                found.append(p)
    return found


class MemoryRetriever:
    """
    High-level memory retrieval API.

    Wraps MemoryIndex with convenience methods for search,
    recency, co-access, and LLM prompt context formatting.

    Usage:
        mr = MemoryRetriever("path/to/memory.jsonl")
        results = mr.retrieve("security lab")
        context = mr.context_for("what happened today", max_tokens=2000)
    """

    def __init__(self, memory_path: str = ""):
        self._memory_path = memory_path
        self._index: Optional[MemoryIndex] = None
        self._auto_discover = not memory_path
        self._concept_map = None

    def _ensure_concept_map(self):
        """Lazy-load concept map."""
        if self._concept_map is None and ConceptMap is not None:
            try:
                self._concept_map = ConceptMap()
            except Exception:
                pass

    def _ensure_index(self):
        """Lazy-build the index."""
        if self._index is not None:
            return

        path = self._memory_path
        if self._auto_discover:
            ecosystem_root = str(Path(__file__).resolve().parents[2])
            files = _find_memory_files(ecosystem_root)
            if files:
                path = files[0]

        self._index = MemoryIndex(path)

    def retrieve(
        self,
        query: str,
        tier: Optional[str] = None,
        limit: int = 5,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Retrieve ranked memories matching query."""
        self._ensure_index()
        return self._index.search(query, tier=tier, limit=limit, min_score=min_score)

    def recent(self, tier: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Most recently accessed memories."""
        self._ensure_index()
        return self._index.search("", tier=tier, limit=limit)

    def related(self, memory_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Co-accessed memories."""
        self._ensure_index()
        return self._index.get_related(memory_id, limit=limit)

    def semantic(self, observation: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Concept-based semantic retrieval.

        Resolves observation to concept, then searches for memories
        related to that concept and its associated risks.

        Example: "pacs_detected" → concept "web_admin_interface"
                 → search for memories about web admin interfaces
        """
        self._ensure_index()
        self._ensure_concept_map()

        if self._concept_map is None:
            # Fallback to keyword search
            return self.retrieve(observation, limit=limit)

        # Step 1: Resolve observation to concept
        resolution = self._concept_map.resolve(observation)
        if not resolution:
            # No concept mapping, try keyword search
            return self.retrieve(observation, limit=limit)

        concept = resolution["concept"]

        # Step 2: Search for memories about the concept
        concept_results = self.retrieve(concept, limit=limit)

        # Step 3: Also search for related risks
        inference = self._concept_map.infer(observation)
        risk_results = []
        for risk in inference:
            risk_memories = self.retrieve(risk["risk"], limit=2)
            risk_results.extend(risk_memories)

        # Step 4: Merge and deduplicate
        seen_ids = set()
        merged = []
        for r in concept_results + risk_results:
            r_id = r.get("memory_id") or r.get("content", "")[:50]
            if r_id not in seen_ids:
                seen_ids.add(r_id)
                r["retrieval_source"] = "semantic"
                r["concept"] = concept
                merged.append(r)

        return merged[:limit]

    def context_for(
        self,
        query: str,
        max_tokens: int = 2000,
        tier: Optional[str] = None,
    ) -> str:
        """
        Build formatted text from retrieved memories for LLM prompt injection.
        Returns plain text block with numbered memory entries.
        """
        self._ensure_index()
        results = self._index.search(query, tier=tier, limit=10)

        if not results:
            return "[No relevant memories found]"

        lines = []
        lines.append(f"## Relevant Memories ({len(results)} found)")
        lines.append("")

        token_budget = max_tokens
        for i, r in enumerate(results, 1):
            # Rough token estimate: 1 token ~ 4 chars
            entry_text = f"{i}. [{r['tier']}] (score={r['score']:.2f}) {r['content']}"
            entry_tokens = len(entry_text) // 4
            if token_budget - entry_tokens < 0:
                break
            token_budget -= entry_tokens
            lines.append(entry_text)

        return "\n".join(lines)

    def stats(self) -> Dict[str, Any]:
        """Index statistics."""
        self._ensure_index()
        return self._index.get_stats()

    def rebuild(self):
        """Force rebuild of the index."""
        self._index = None
        self._ensure_index()


# =============================================================================
# CLI
# =============================================================================

def main():
    """CLI entry point."""
    ecosystem_root = str(Path(__file__).resolve().parents[2])
    memory_path = os.path.join(ecosystem_root, "runtime", "swarm", "memory.jsonl")

    mr = MemoryRetriever(memory_path)

    if len(sys.argv) > 1 and sys.argv[1] == "search":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        results = mr.retrieve(query)
        for r in results:
            print(f"  [{r['tier']}] score={r['score']:.3f} | {r['content'][:80]}")
    elif len(sys.argv) > 1 and sys.argv[1] == "recent":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        results = mr.recent(limit=n)
        for r in results:
            print(f"  [{r['tier']}] {r['timestamp']} | {r['content'][:80]}")
    elif len(sys.argv) > 1 and sys.argv[1] == "related":
        mid = sys.argv[2] if len(sys.argv) > 2 else ""
        if mid:
            results = mr.related(mid)
            for r in results:
                print(f"  [{r['tier']}] accesses={r['access_count']} | {r['content'][:80]}")
        else:
            print("Usage: memory-retriever.py related <memory_id>")
    elif len(sys.argv) > 1 and sys.argv[1] == "semantic":
        obs = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        if obs:
            results = mr.semantic(obs)
            for r in results:
                concept = r.get("concept", "")
                source = r.get("retrieval_source", "keyword")
                print(f"  [{r['tier']}] concept={concept} source={source} score={r['score']:.3f} | {r['content'][:80]}")
        else:
            print("Usage: memory-retriever.py semantic <observation>")
    elif len(sys.argv) > 1 and sys.argv[1] == "context":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        print(mr.context_for(query))
    elif len(sys.argv) > 1 and sys.argv[1] == "stats":
        print(json.dumps(mr.stats(), ensure_ascii=False, indent=2))
    else:
        print("Usage: memory-retriever.py [search <query>|recent [n]|related <id>|semantic <obs>|context <query>|stats]")
        print(json.dumps(mr.stats(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
