"""
adaptive-memory.py -- ECOSYSTEM Adaptive Memory (G1-G6)

Standalone module ported from mcr-runtime LayeredMemoryAdapter.
Implements 4-tier memory with adaptive retrieval weights and habit tracking.
Uses MemoryIndex for fast inverted-index retrieval when available.

Tiers:
  working   - active, high weight, recent (accessed in last 10 events)
  episodic  - events, medium weight (accessed 1-10 times)
  semantic  - knowledge, stable weight (accessed 10+ times or manually promoted)
  archive   - old, low weight (not accessed in 50+ events)

Adaptive behavior:
  - Retrieval weights start at 1.0 per tier
  - On successful retrieval: weight += 0.1
  - On failed retrieval: weight -= 0.05
  - Weights bounded: 0.1 <= weight <= 3.0
  - Habit bonus: if same tier used 5+ times in a row, bonus +0.2

No external dependencies. Works with memory.jsonl (JSON lines) format.
"""

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Import MemoryIndex from same directory for fast retrieval
_script_dir = str(Path(__file__).resolve().parent)
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

try:
    _mi_mod = __import__("memory-index")
    MemoryIndex = _mi_mod.MemoryIndex
    _HAS_INDEX = True
except ImportError:
    _HAS_INDEX = False


# =============================================================================
# PARAMETERS
# =============================================================================

TIERS = ("working", "episodic", "semantic", "archive")
DEFAULT_WEIGHT = 1.0
WEIGHT_SUCCESS_DELTA = 0.1
WEIGHT_FAILURE_DELTA = -0.05
WEIGHT_MIN = 0.1
WEIGHT_MAX = 3.0
HABIT_STREAK_THRESHOLD = 5
HABIT_BONUS = 0.2
WORKING_RECENT_EVENTS = 10
EPISODIC_MAX_ACCESS = 10
SEMANTIC_MIN_ACCESS = 10
ARCHIVE_NO_ACCESS_EVENTS = 50


# =============================================================================
# LAYERED MEMORY
# =============================================================================

class LayeredMemory:
    """4-tier memory store: working, episodic, semantic, archive."""

    def __init__(self):
        self.working = []
        self.episodic = []
        self.semantic = []
        self.archive = []

    def get_tier(self, name):
        return {
            "working": self.working,
            "episodic": self.episodic,
            "semantic": self.semantic,
            "archive": self.archive,
        }.get(name, [])

    def all_memories(self):
        return self.working + self.episodic + self.semantic + self.archive

    def counts(self):
        return {
            "working": len(self.working),
            "episodic": len(self.episodic),
            "semantic": len(self.semantic),
            "archive": len(self.archive),
            "total": len(self.all_memories()),
        }


# =============================================================================
# ADAPTIVE RETRIEVAL
# =============================================================================

class AdaptiveRetrieval:
    """
    Tracks retrieval weights per tier and habit patterns.
    Weights drift based on success/failure feedback.
    """

    def __init__(self, state_path=None):
        self.weights = {t: DEFAULT_WEIGHT for t in TIERS}
        self.habits = {
            "streak_tier": None,
            "streak_count": 0,
            "history": [],  # last N tier selections
            "bonuses_applied": 0,
        }
        self.retrieval_log = []  # [{query, tier, success, timestamp}]
        self.state_path = state_path
        if state_path and os.path.exists(state_path):
            self._load_state()

    def record_retrieval(self, tier, success):
        """Record a retrieval event and update weights."""
        self.retrieval_log.append({
            "tier": tier,
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Update weight
        delta = WEIGHT_SUCCESS_DELTA if success else WEIGHT_FAILURE_DELTA
        self.weights[tier] = max(WEIGHT_MIN, min(WEIGHT_MAX, self.weights[tier] + delta))

        # Update habit streak
        self._update_streak(tier)

        # Auto-persist
        if self.state_path:
            self._save_state()

    def _update_streak(self, tier):
        """Track consecutive same-tier usage for habit detection."""
        self.habits["history"].append(tier)
        # Keep last 20
        if len(self.habits["history"]) > 20:
            self.habits["history"] = self.habits["history"][-20:]

        if self.habits["streak_tier"] == tier:
            self.habits["streak_count"] += 1
        else:
            self.habits["streak_tier"] = tier
            self.habits["streak_count"] = 1

        # Apply habit bonus
        if self.habits["streak_count"] == HABIT_STREAK_THRESHOLD:
            self.weights[tier] = min(WEIGHT_MAX, self.weights[tier] + HABIT_BONUS)
            self.habits["bonuses_applied"] += 1

    def weighted_tier_scores(self, tier_counts):
        """Return weighted scores for each tier that has memories."""
        scores = {}
        for t in TIERS:
            if tier_counts.get(t, 0) > 0:
                scores[t] = self.weights[t]
        return scores

    def get_habits(self):
        """Return current habit patterns."""
        return {
            "streak_tier": self.habits["streak_tier"],
            "streak_count": self.habits["streak_count"],
            "recent_history": self.habits["history"][-10:],
            "bonuses_applied": self.habits["bonuses_applied"],
            "pattern_detected": self.habits["streak_count"] >= HABIT_STREAK_THRESHOLD,
        }

    def _save_state(self):
        data = {
            "weights": self.weights,
            "habits": self.habits,
            "log_count": len(self.retrieval_log),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_state(self):
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "weights" in data:
                for t in TIERS:
                    if t in data["weights"]:
                        self.weights[t] = data["weights"][t]
            if "habits" in data:
                self.habits.update(data["habits"])
        except (json.JSONDecodeError, IOError):
            pass  # use defaults


# =============================================================================
# MEMORY STORE -- tier assignment logic
# =============================================================================

class MemoryStore:
    """Stores memories into appropriate tiers based on age and access count."""

    def __init__(self, memory_path):
        self.memory_path = memory_path
        self.memories = []  # loaded from jsonl
        self._load()

    def _load(self):
        """Load memories from JSONL file."""
        self.memories = []
        if not os.path.exists(self.memory_path):
            return
        with open(self.memory_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    self.memories.append(entry)
                except json.JSONDecodeError:
                    continue

    def assign_tier(self, entry, event_index):
        """
        Determine appropriate tier for a memory entry.
        Rules:
          working:  accessed in last WORKING_RECENT_EVENTS events
          episodic: accessed 1-EPISODIC_MAX_ACCESS times
          semantic: accessed SEMANTIC_MIN_ACCESS+ times or manually promoted
          archive:  not accessed in ARCHIVE_NO_ACCESS_EVENTS+ events
        """
        # Check for explicit tier in record
        record = entry.get("record", {})
        if isinstance(record, dict) and "tier" in record:
            tier = record["tier"]
            if tier in TIERS:
                return tier

        # Infer from access patterns
        access_count = entry.get("access_count", 0)
        last_access_idx = entry.get("last_access_idx", event_index)

        age_in_events = event_index - last_access_idx

        if age_in_events > ARCHIVE_NO_ACCESS_EVENTS:
            return "archive"
        if access_count >= SEMANTIC_MIN_ACCESS:
            return "semantic"
        if access_count >= 1 and access_count <= EPISODIC_MAX_ACCESS:
            return "episodic"
        # Default: recent items are working
        if age_in_events <= WORKING_RECENT_EVENTS:
            return "working"
        return "episodic"

    def compress(self, max_entries=100):
        """
        Compress memories by removing duplicates and merging similar entries.
        Keeps the most recent max_entries memories.
        """
        if len(self.memories) <= max_entries:
            return {"compressed": 0, "remaining": len(self.memories)}

        # Sort by timestamp (newest first)
        self.memories.sort(key=lambda m: m.get("timestamp", ""), reverse=True)

        # Keep only the most recent entries
        compressed = self.memories[max_entries:]
        self.memories = self.memories[:max_entries]

        # Save compressed memories
        with open(self.memory_path, "w", encoding="utf-8") as f:
            for entry in self.memories:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return {"compressed": len(compressed), "remaining": len(self.memories)}

    def populate_layers(self, layer_mem, event_count=None):
        """
        Load all memories into LayeredMemory tiers.
        Returns the LayeredMemory with populated tiers.
        """
        total = len(self.memories)
        if event_count is None:
            event_count = total

        for idx, entry in enumerate(self.memories):
            # Compute access info from the entry
            record = entry.get("record", {})
            content = ""
            if isinstance(record, dict):
                content = record.get("user_intent", "")
                if not content:
                    content = record.get("summary", "")
                if not content:
                    content = json.dumps(record, ensure_ascii=False)[:200]
            elif isinstance(record, str):
                content = record

            memory_item = {
                "id": entry.get("memory_id", str(uuid.uuid4())[:8]),
                "content": content,
                "source": entry.get("source", "unknown"),
                "written_at": entry.get("written_at", ""),
                "access_count": entry.get("access_count", 0),
                "last_access_idx": idx,
                "event_index": idx,
            }

            # Attach access_count if present
            if "access_count" not in entry:
                # Estimate: older memories have more implicit accesses
                memory_item["access_count"] = max(0, (total - idx) // 5)

            tier = self.assign_tier(memory_item, event_count)
            target = layer_mem.get_tier(tier)
            if target is not None:
                target.append(memory_item)

        return layer_mem


# =============================================================================
# ADAPTIVE MEMORY -- main API
# =============================================================================

class AdaptiveMemory:
    """
    Main API: 4-tier memory with adaptive retrieval.

    Uses MemoryIndex for fast inverted-index retrieval when available,
    falling back to linear scan otherwise.

    Usage:
        am = AdaptiveMemory("path/to/memory.jsonl", "path/to/state.json")
        am.store(content, tier="working")
        results = am.retrieve("query")
        am.adapt("success")  # or "failure"
    """

    def __init__(self, memory_path, state_path=None):
        self.memory_path = memory_path
        self.state_path = state_path or os.path.join(
            os.path.dirname(memory_path), "adaptive-memory-state.json"
        )
        self.layers = LayeredMemory()
        self.retrieval = AdaptiveRetrieval(self.state_path)
        self.store_obj = MemoryStore(memory_path)
        self._event_count = 0
        self._loaded = False
        self._index = None

    def _ensure_loaded(self):
        if not self._loaded:
            self.layers = LayeredMemory()
            self.store_obj.populate_layers(self.layers, self._event_count or len(self.store_obj.memories))
            self._event_count = len(self.store_obj.memories)
            self._loaded = True
            # Build MemoryIndex for fast retrieval
            if _HAS_INDEX and os.path.exists(self.memory_path):
                self._index = MemoryIndex(self.memory_path)

    def store(self, content, tier=None, metadata=None):
        """
        Store a memory. Auto-assigns tier if tier=None.
        Returns memory id.
        """
        self._ensure_loaded()
        mem_id = "mem-" + str(uuid.uuid4())[:8]
        entry = {
            "id": mem_id,
            "content": content,
            "source": metadata.get("source", "manual") if metadata else "manual",
            "written_at": datetime.now(timezone.utc).isoformat(),
            "access_count": 0,
            "last_access_idx": self._event_count,
            "event_index": self._event_count,
        }

        if tier is None:
            # Auto-tier: new items go to working
            tier = "working"

        target = self.layers.get_tier(tier)
        if target is not None:
            target.append(entry)

        # Append to jsonl
        jsonl_entry = {
            "memory_id": mem_id,
            "written_at": entry["written_at"],
            "source": entry["source"],
            "record": {"content": content, "tier": tier},
            "access_count": 0,
        }
        os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
        with open(self.memory_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(jsonl_entry, ensure_ascii=False) + "\n")

        # Incremental index update
        if self._index is not None:
            self._index.update(jsonl_entry)

        self._event_count += 1
        return mem_id

    def retrieve(self, query, max_results=5):
        """
        Retrieve memories with adaptive weighting.
        Uses MemoryIndex for fast retrieval when available, falls back to linear scan.
        Returns list of {memory, tier, score}.
        """
        self._ensure_loaded()

        # Fast path: use MemoryIndex if available
        if self._index is not None:
            return self._retrieve_via_index(query, max_results)

        # Slow path: linear scan (original behavior)
        return self._retrieve_linear(query, max_results)

    def _retrieve_via_index(self, query, max_results):
        """Fast retrieval using MemoryIndex inverted index."""
        index_results = self._index.search(query, limit=max_results * 2)
        candidates = []
        for r in index_results:
            tier_name = r["tier"]
            weight = self.retrieval.weights.get(tier_name, DEFAULT_WEIGHT)
            # Combine index score with adaptive weight
            score = r["score"] * weight
            candidates.append({
                "memory": {"content": r["content"], "id": r["memory_id"]},
                "tier": tier_name,
                "score": score,
                "weight": weight,
            })
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:max_results]

    def _retrieve_linear(self, query, max_results):
        """Fallback linear scan retrieval."""
        query_lower = query.lower() if query else ""
        query_words = set(query_lower.split()) if query_lower else set()

        candidates = []
        tier_counts = self.layers.counts()

        for tier_name in TIERS:
            tier_mem = self.layers.get_tier(tier_name)
            if not tier_mem:
                continue

            weight = self.retrieval.weights.get(tier_name, DEFAULT_WEIGHT)

            for mem in tier_mem:
                # Score: keyword overlap * tier weight
                content_lower = mem.get("content", "").lower()
                content_words = set(content_lower.split())
                overlap = len(query_words & content_words) if query_words else 0
                base_score = overlap / max(len(query_words), 1) if query_words else 0.5
                # Bonus for recency within tier
                recency_bonus = 0.1 * (1.0 / (1 + self._event_count - mem.get("event_index", 0)))
                score = (base_score + recency_bonus) * weight

                candidates.append({
                    "memory": mem,
                    "tier": tier_name,
                    "score": score,
                    "weight": weight,
                })

        # Sort by score descending
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:max_results]

    def adapt(self, feedback):
        """
        Update weights based on retrieval feedback.
        feedback: "success" or "failure", or dict {"result": "success", "tier": "working"}
        """
        if isinstance(feedback, dict):
            result = feedback.get("result", "failure")
            tier = feedback.get("tier", self.retrieval.habits.get("streak_tier", "working"))
        elif feedback in ("success", "s"):
            result = "success"
            tier = self.retrieval.habits.get("streak_tier", "working")
        else:
            result = "failure"
            tier = self.retrieval.habits.get("streak_tier", "working")

        if tier and tier in TIERS:
            self.retrieval.record_retrieval(tier, result == "success")

    def get_weights(self):
        """Return current retrieval weights per tier."""
        return dict(self.retrieval.weights)

    def get_habits(self):
        """Return habit patterns."""
        return self.retrieval.get_habits()

    def get_stats(self):
        """Return tier counts, weights, habits."""
        self._ensure_loaded()
        stats = {
            "tier_counts": self.layers.counts(),
            "weights": self.get_weights(),
            "habits": self.get_habits(),
            "total_retrievals": len(self.retrieval.retrieval_log),
            "memory_path": self.memory_path,
            "event_count": self._event_count,
            "has_index": self._index is not None,
        }
        if self._index is not None:
            stats["index"] = self._index.get_stats()
        return stats

    def promote(self, memory_id, target_tier):
        """Manually promote a memory to a different tier."""
        self._ensure_loaded()
        for tier_name in TIERS:
            tier_list = self.layers.get_tier(tier_name)
            for i, mem in enumerate(tier_list):
                if mem["id"] == memory_id:
                    tier_list.pop(i)
                    target = self.layers.get_tier(target_tier)
                    if target is not None:
                        mem["access_count"] = mem.get("access_count", 0) + SEMANTIC_MIN_ACCESS
                        target.append(mem)
                    return True
        return False


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """CLI entry point for standalone testing."""
    import sys

    ecosystem_root = str(Path(__file__).resolve().parents[2])
    memory_path = os.path.join(ecosystem_root, "runtime", "memory", "life-memory.jsonl")
    swarm_path = os.path.join(ecosystem_root, "runtime", "swarm", "memory.jsonl")
    state_path = os.path.join(ecosystem_root, "runtime", "agi", "adaptive-memory-state.json")

    # Use whichever memory file has data
    target_memory = memory_path
    if os.path.exists(swarm_path):
        with open(swarm_path, "r", encoding="utf-8") as f:
            swarm_lines = len([l for l in f if l.strip()])
        if swarm_lines > 0:
            target_memory = swarm_path

    am = AdaptiveMemory(target_memory, state_path)

    if len(sys.argv) > 1 and sys.argv[1] == "stats":
        stats = am.get_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "retrieve":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "security"
        results = am.retrieve(query)
        for r in results:
            print(f"  [{r['tier']}] score={r['score']:.3f} w={r['weight']:.2f} | {r['memory']['content'][:80]}")
    elif len(sys.argv) > 1 and sys.argv[1] == "exercise":
        # Exercise the system for G1-G6 verification
        exercise_system(am)
    else:
        print("Usage: adaptive-memory.py [stats|retrieve <query>|exercise]")
        stats = am.get_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))


def exercise_system(am):
    """Run retrieval + feedback cycles to exercise adaptive behavior."""
    queries = [
        ("security lab check", True),
        ("mcr runtime status", True),
        ("multimodal creative tools", False),
        ("knowledge memory workbench", True),
        ("security lab check", True),
        ("security lab check", True),
        ("security lab check", True),
        ("security lab check", True),
        ("security lab check", True),
        ("security lab check", True),
        ("goals and planning", False),
        ("registry validate", True),
    ]

    for query, success in queries:
        results = am.retrieve(query)
        if results:
            feedback = {
                "result": "success" if success else "failure",
                "tier": results[0]["tier"],
            }
        else:
            feedback = {"result": "failure", "tier": "working"}
        am.adapt(feedback)

    stats = am.get_stats()
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
