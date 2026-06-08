"""
tier-manager.py -- ECOSYSTEM Memory Tier Manager

Manages memory tier transitions based on access patterns:
  - working: default tier for new memories
  - episodic: accessed 3+ times
  - semantic: accessed 10+ times
  - archive: not accessed in 50+ events

Auto-promotes based on access count.
Auto-archives based on inactivity.
Decay buffer: batch transitions to avoid thrashing.

Usage:
    python tier-manager.py evaluate
    python tier-manager.py stats
    python tier-manager.py pending
    python tier-manager.py promote <memory_id> <tier> [reason]
    python tier-manager.py demote <memory_id> <tier> [reason]

Reads:  runtime/swarm/memory.jsonl
Writes: runtime/agi/tier-state.json, runtime/agi/tier-transitions.jsonl
"""
from __future__ import annotations
import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# -- Paths --
ECOSYSTEM_ROOT = Path(__file__).resolve().parent.parent.parent
MEMORY_PATH = ECOSYSTEM_ROOT / "runtime" / "swarm" / "memory.jsonl"
AGI_DIR = ECOSYSTEM_ROOT / "runtime" / "agi"
STATE_PATH = AGI_DIR / "tier-state.json"
TRANSITIONS_PATH = AGI_DIR / "tier-transitions.jsonl"

# -- Tier thresholds --
PROMOTE_TO_EPISODIC = 3    # access_count >= 3 -> episodic
PROMOTE_TO_SEMANTIC = 10   # access_count >= 10 -> semantic
ARCHIVE_AFTER_EVENTS = 50  # not accessed in 50+ events -> archive
MIN_ARCHIVE_POOL = 3       # never archive below this count

TIERS = ["working", "episodic", "semantic", "archive"]
TIER_RANK = {t: i for i, t in enumerate(TIERS)}


def load_memory_entries() -> List[Dict[str, Any]]:
    """Read all memory entries from memory.jsonl."""
    if not MEMORY_PATH.exists():
        return []
    entries = []
    for line in MEMORY_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def load_state() -> Dict[str, Any]:
    """Load tier state from disk."""
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "schema_version": "0.1",
        "memories": {},
        "total_transitions": 0,
        "last_evaluated": None,
    }


def save_state(state: Dict[str, Any]) -> None:
    """Save tier state to disk."""
    AGI_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def append_transition(transition: Dict[str, Any]) -> None:
    """Append a transition record to tier-transitions.jsonl."""
    AGI_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps(transition, ensure_ascii=False)
    with open(TRANSITIONS_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def init_memory_entry(state: Dict[str, Any], memory_id: str, event_index: int) -> Dict[str, Any]:
    """Initialize tracking for a memory if not present."""
    if memory_id not in state["memories"]:
        state["memories"][memory_id] = {
            "tier": "working",
            "access_count": 0,
            "first_seen_event": event_index,
            "last_access_event": event_index,
            "manual_override": False,
        }
    return state["memories"][memory_id]


class TierManager:
    """Evaluates and manages memory tier transitions."""

    def __init__(self, memory_path: str = None, transitions_path: str = None):
        self.memory_path = Path(memory_path) if memory_path else MEMORY_PATH
        self.transitions_path = Path(transitions_path) if transitions_path else TRANSITIONS_PATH

    def evaluate(self) -> List[Dict[str, Any]]:
        """Evaluate all memories for tier transitions. Returns list of transitions made."""
        entries = load_memory_entries()
        state = load_state()
        transitions = []
        now = datetime.now(timezone.utc).isoformat()
        total_events = len(entries)

        # Sync memory entries into state
        for i, entry in enumerate(entries):
            mem_id = entry.get("memory_id", "")
            if not mem_id:
                continue
            init_memory_entry(state, mem_id, i)

        # Evaluate each memory for transitions
        mem_state = state["memories"]
        archive_count = sum(1 for m in mem_state.values() if m["tier"] == "archive")

        for mem_id, info in mem_state.items():
            current_tier = info["tier"]
            if info.get("manual_override"):
                continue

            access_count = info["access_count"]
            last_access = info["last_access_event"]
            events_since_access = total_events - last_access

            target_tier = None
            reason = ""

            # Auto-promote based on access count
            if current_tier == "working" and access_count >= PROMOTE_TO_EPISODIC:
                target_tier = "episodic"
                reason = f"access_count={access_count}>={PROMOTE_TO_EPISODIC}"
            elif current_tier == "episodic" and access_count >= PROMOTE_TO_SEMANTIC:
                target_tier = "semantic"
                reason = f"access_count={access_count}>={PROMOTE_TO_SEMANTIC}"

            # Auto-archive based on inactivity (only for non-working tiers)
            if target_tier is None and current_tier in ("episodic", "semantic"):
                if events_since_access >= ARCHIVE_AFTER_EVENTS:
                    if archive_count + 1 > MIN_ARCHIVE_POOL or current_tier != "archive":
                        target_tier = "archive"
                        reason = f"events_since_access={events_since_access}>={ARCHIVE_AFTER_EVENTS}"

            if target_tier and TIER_RANK[target_tier] != TIER_RANK[current_tier]:
                transition = {
                    "memory_id": mem_id,
                    "from_tier": current_tier,
                    "to_tier": target_tier,
                    "reason": reason,
                    "access_count": access_count,
                    "events_since_access": events_since_access,
                    "timestamp": now,
                }
                transitions.append(transition)
                append_transition(transition)

                info["tier"] = target_tier
                state["total_transitions"] = state.get("total_transitions", 0) + 1
                if target_tier == "archive":
                    archive_count += 1

        state["last_evaluated"] = now
        save_state(state)
        return transitions

    def promote(self, memory_id: str, to_tier: str, reason: str = "manual") -> Dict[str, Any]:
        """Manually promote a memory to a specific tier."""
        if to_tier not in TIERS:
            raise ValueError(f"Invalid tier: {to_tier}. Must be one of {TIERS}")

        state = load_state()
        if memory_id not in state["memories"]:
            # Initialize from memory entries
            entries = load_memory_entries()
            for i, e in enumerate(entries):
                if e.get("memory_id") == memory_id:
                    init_memory_entry(state, memory_id, i)
                    break
            if memory_id not in state["memories"]:
                raise ValueError(f"Memory {memory_id} not found")

        info = state["memories"][memory_id]
        from_tier = info["tier"]
        now = datetime.now(timezone.utc).isoformat()

        transition = {
            "memory_id": memory_id,
            "from_tier": from_tier,
            "to_tier": to_tier,
            "reason": f"manual: {reason}",
            "timestamp": now,
        }
        append_transition(transition)

        info["tier"] = to_tier
        info["manual_override"] = True
        state["total_transitions"] = state.get("total_transitions", 0) + 1
        save_state(state)
        return transition

    def demote(self, memory_id: str, to_tier: str, reason: str = "manual") -> Dict[str, Any]:
        """Manually demote a memory to a specific tier."""
        return self.promote(memory_id, to_tier, reason)

    def get_distribution(self) -> Dict[str, Any]:
        """Return tier distribution stats."""
        state = load_state()
        entries = load_memory_entries()
        mem_state = state.get("memories", {})

        distribution = {t: 0 for t in TIERS}
        for info in mem_state.values():
            tier = info.get("tier", "working")
            distribution[tier] = distribution.get(tier, 0) + 1

        # Count any entries not yet tracked
        tracked_ids = set(mem_state.keys())
        untracked = sum(1 for e in entries if e.get("memory_id", "") not in tracked_ids)
        distribution["untracked"] = untracked

        return {
            "total_memories": len(entries),
            "tracked": len(mem_state),
            "distribution": distribution,
            "total_transitions": state.get("total_transitions", 0),
            "last_evaluated": state.get("last_evaluated"),
        }

    def get_pending(self) -> List[Dict[str, Any]]:
        """Return memories that would transition if evaluated now."""
        entries = load_memory_entries()
        state = load_state()
        pending = []
        total_events = len(entries)

        for i, entry in enumerate(entries):
            mem_id = entry.get("memory_id", "")
            if not mem_id:
                continue
            info = init_memory_entry(state, mem_id, i)

            if info.get("manual_override"):
                continue

            current_tier = info["tier"]
            access_count = info["access_count"]
            last_access = info["last_access_event"]
            events_since_access = total_events - last_access

            would_promote = None
            would_archive = None

            if current_tier == "working" and access_count >= PROMOTE_TO_EPISODIC:
                would_promote = "episodic"
            elif current_tier == "episodic" and access_count >= PROMOTE_TO_SEMANTIC:
                would_promote = "semantic"

            if current_tier in ("episodic", "semantic") and events_since_access >= ARCHIVE_AFTER_EVENTS:
                would_archive = "archive"

            if would_promote or would_archive:
                pending.append({
                    "memory_id": mem_id,
                    "current_tier": current_tier,
                    "access_count": access_count,
                    "events_since_access": events_since_access,
                    "would_promote_to": would_promote,
                    "would_archive_to": would_archive,
                })

        return pending


def cli():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: tier-manager.py <evaluate|stats|pending|promote|demote> [args]")
        sys.exit(1)

    action = sys.argv[1]
    tm = TierManager()

    if action == "evaluate":
        transitions = tm.evaluate()
        print(json.dumps({
            "transitions": transitions,
            "count": len(transitions),
        }, indent=2, ensure_ascii=False))

    elif action == "stats":
        dist = tm.get_distribution()
        print(json.dumps(dist, indent=2, ensure_ascii=False))

    elif action == "pending":
        pending = tm.get_pending()
        print(json.dumps({
            "pending": pending,
            "count": len(pending),
        }, indent=2, ensure_ascii=False))

    elif action == "promote":
        if len(sys.argv) < 4:
            print("Usage: tier-manager.py promote <memory_id> <tier> [reason]")
            sys.exit(1)
        mem_id = sys.argv[2]
        tier = sys.argv[3]
        reason = sys.argv[4] if len(sys.argv) > 4 else "manual"
        result = tm.promote(mem_id, tier, reason)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif action == "demote":
        if len(sys.argv) < 4:
            print("Usage: tier-manager.py demote <memory_id> <tier> [reason]")
            sys.exit(1)
        mem_id = sys.argv[2]
        tier = sys.argv[3]
        reason = sys.argv[4] if len(sys.argv) > 4 else "manual"
        result = tm.demote(mem_id, tier, reason)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    else:
        print(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
