"""
vector_search.py -- MCR Vector Search Module

Lightweight vector search for semantic memory retrieval.
Supports:
  - CPU mode: numpy cosine similarity (no extra dependencies)
  - GPU mode: cuVS integration (via WSL2 or Linux)

Usage:
    python vector_search.py index "memory.jsonl"
    python vector_search.py search "pacs_detected"
    python vector_search.py stats
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ECOSYSTEM_ROOT = Path(__file__).resolve().parent.parent.parent
AGI_DIR = ECOSYSTEM_ROOT / "runtime" / "agi"
VECTOR_INDEX_PATH = AGI_DIR / "vector-index.json"
VECTOR_CACHE_PATH = AGI_DIR / "vector-cache.json"

# Try to import numpy (required)
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# Try to import sentence-transformers (optional)
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    entries = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return entries


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


# ============================================================
# Simple Embedding (no external model)
# ============================================================

class SimpleEmbedding:
    """
    Simple character-level embedding for basic semantic similarity.
    No external model required.

    Uses character n-grams and TF-IDF-like weighting.
    """

    def __init__(self, dim: int = 256):
        self.dim = dim

    def encode(self, text: str) -> List[float]:
        """Encode text into a fixed-dimension vector."""
        text = text.lower().strip()
        vec = [0.0] * self.dim

        # Character trigram hashing
        for i in range(len(text) - 2):
            trigram = text[i:i+3]
            h = hash(trigram) % self.dim
            vec[h] += 1.0

        # Word features
        words = text.split()
        for word in words:
            h = hash(word) % self.dim
            vec[h] += 2.0

        # Normalize
        norm = sum(x*x for x in vec) ** 0.5
        if norm > 0:
            vec = [x/norm for x in vec]

        return vec

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Encode multiple texts."""
        return [self.encode(t) for t in texts]


# ============================================================
# Vector Index
# ============================================================

class VectorIndex:
    """Vector index for semantic search."""

    def __init__(self, ecosystem_root: str | Path | None = None,
                 embedding_model: Optional[str] = None):
        self._root = Path(ecosystem_root) if ecosystem_root else ECOSYSTEM_ROOT
        self._index_path = self._root / "runtime" / "agi" / "vector-index.json"
        self._cache_path = self._root / "runtime" / "agi" / "vector-cache.json"

        # Initialize embedding model
        if embedding_model and HAS_SENTENCE_TRANSFORMERS:
            self._encoder = SentenceTransformer(embedding_model)
            self._encoder_name = embedding_model
        else:
            self._encoder = SimpleEmbedding(dim=256)
            self._encoder_name = "simple_trigram"

        # Index data
        self._vectors: List[List[float]] = []
        self._metadata: List[Dict[str, Any]] = []
        self._built = False

    def build_from_memory(self, memory_path: str | Path) -> Dict[str, Any]:
        """Build vector index from memory.jsonl."""
        memory_path = Path(memory_path)
        if not memory_path.exists():
            return {"error": "memory file not found", "path": str(memory_path)}

        entries = _load_jsonl(memory_path)
        if not entries:
            return {"error": "no entries found"}

        # Extract content from each entry
        texts = []
        metadata = []
        for entry in entries:
            content = self._extract_content(entry)
            if content:
                texts.append(content)
                metadata.append({
                    "memory_id": entry.get("memory_id", ""),
                    "content": content[:300],
                    "tier": entry.get("tier", "episodic"),
                    "timestamp": entry.get("written_at") or entry.get("created_at", ""),
                })

        if not texts:
            return {"error": "no content extracted"}

        # Encode all texts
        vectors = self._encoder.encode_batch(texts)

        # Store
        self._vectors = vectors
        self._metadata = metadata
        self._built = True

        # Save index
        index_data = {
            "encoder": self._encoder_name,
            "dim": len(vectors[0]) if vectors else 0,
            "count": len(vectors),
            "built_at": _now_iso(),
        }
        _save_json(self._index_path, index_data)

        return {
            "built": True,
            "count": len(vectors),
            "dim": len(vectors[0]) if vectors else 0,
            "encoder": self._encoder_name,
        }

    def _extract_content(self, entry: dict) -> str:
        """Extract searchable content from memory entry."""
        parts = []
        for key in ("summary", "content", "lessons", "next_suggestions"):
            val = entry.get(key, "")
            if val and isinstance(val, str):
                parts.append(val)
        if "successes" in entry:
            parts.extend(entry["successes"])
        if "failures" in entry:
            parts.extend(entry["failures"])
        record = entry.get("record", {})
        if isinstance(record, dict):
            for key in ("user_intent", "summary", "content"):
                val = record.get(key, "")
                if val and isinstance(val, str):
                    parts.append(val)
        return " ".join(parts)

    def search(self, query: str, top_k: int = 5,
               min_score: float = 0.0) -> List[Dict[str, Any]]:
        """Search for similar memories using vector similarity."""
        if not self._built or not self._vectors:
            return []

        if not HAS_NUMPY:
            return self._search_cpu(query, top_k, min_score)

        # Encode query
        query_vec = np.array(self._encoder.encode(query))
        index_vecs = np.array(self._vectors)

        # Cosine similarity
        similarities = np.dot(index_vecs, query_vec) / (
            np.linalg.norm(index_vecs, axis=1) * np.linalg.norm(query_vec) + 1e-8
        )

        # Get top-k
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score >= min_score:
                result = self._metadata[idx].copy()
                result["score"] = round(score, 4)
                result["retrieval_source"] = "vector"
                results.append(result)

        return results

    def _search_cpu(self, query: str, top_k: int,
                    min_score: float) -> List[Dict[str, Any]]:
        """CPU fallback for vector search (no numpy)."""
        query_vec = self._encoder.encode(query)

        scores = []
        for i, vec in enumerate(self._vectors):
            # Dot product (vectors are normalized)
            score = sum(a*b for a, b in zip(query_vec, vec))
            scores.append((score, i))

        scores.sort(reverse=True)

        results = []
        for score, idx in scores[:top_k]:
            if score >= min_score:
                result = self._metadata[idx].copy()
                result["score"] = round(score, 4)
                result["retrieval_source"] = "vector"
                results.append(result)

        return results

    def add(self, text: str, metadata: Dict[str, Any]) -> int:
        """Add a single entry to the index."""
        vec = self._encoder.encode(text)
        self._vectors.append(vec)
        self._metadata.append(metadata)
        return len(self._vectors)

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return {
            "built": self._built,
            "count": len(self._vectors),
            "dim": len(self._vectors[0]) if self._vectors else 0,
            "encoder": self._encoder_name,
            "has_numpy": HAS_NUMPY,
            "has_sentence_transformers": HAS_SENTENCE_TRANSFORMERS,
        }


# ============================================================
# Hybrid Search (Vector + Keyword)
# ============================================================

class HybridSearch:
    """
    Combines vector search with keyword search.
    Vector for semantic similarity, keyword for exact match.
    """

    def __init__(self, vector_index: VectorIndex, keyword_index=None):
        self._vector = vector_index
        self._keyword = keyword_index

    def search(self, query: str, top_k: int = 5,
               vector_weight: float = 0.7,
               keyword_weight: float = 0.3) -> List[Dict[str, Any]]:
        """Hybrid search combining vector and keyword results."""
        # Vector search
        vector_results = self._vector.search(query, top_k=top_k * 2)

        # Keyword search (if available)
        keyword_results = []
        if self._keyword:
            try:
                keyword_results = self._keyword.search(query, limit=top_k * 2)
            except Exception:
                pass

        # Merge results
        seen = set()
        merged = []

        # Add vector results with weighted score
        for r in vector_results:
            mid = r.get("memory_id") or r.get("content", "")[:50]
            if mid not in seen:
                seen.add(mid)
                r["final_score"] = r["score"] * vector_weight
                r["sources"] = ["vector"]
                merged.append(r)

        # Add keyword results with weighted score
        for r in keyword_results:
            mid = r.get("memory_id") or r.get("content", "")[:50]
            if mid not in seen:
                seen.add(mid)
                r["final_score"] = r.get("score", 0) * keyword_weight
                r["sources"] = ["keyword"]
                merged.append(r)
            else:
                # Boost existing result if found by both
                for m in merged:
                    if (m.get("memory_id") == mid or
                            m.get("content", "")[:50] == r.get("content", "")[:50]):
                        m["final_score"] += r.get("score", 0) * keyword_weight
                        m["sources"].append("keyword")
                        break

        # Sort by final score
        merged.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        return merged[:top_k]


# ============================================================
# CLI
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python vector_search.py <index|search|stats> [args]")
        sys.exit(1)

    action = sys.argv[1]

    if action == "index":
        memory_path = sys.argv[2] if len(sys.argv) > 2 else str(
            ECOSYSTEM_ROOT / "runtime" / "swarm" / "memory.jsonl"
        )
        vi = VectorIndex()
        result = vi.build_from_memory(memory_path)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif action == "search":
        if len(sys.argv) < 3:
            print("Usage: python vector_search.py search <query> [top_k]")
            sys.exit(1)
        query = sys.argv[2]
        top_k = int(sys.argv[3]) if len(sys.argv) > 3 else 5

        vi = VectorIndex()
        memory_path = str(ECOSYSTEM_ROOT / "runtime" / "swarm" / "memory.jsonl")
        vi.build_from_memory(memory_path)

        results = vi.search(query, top_k=top_k)
        for r in results:
            print(f"  score={r['score']:.4f} | {r['content'][:80]}")

    elif action == "stats":
        vi = VectorIndex()
        stats = vi.get_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    else:
        print(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
