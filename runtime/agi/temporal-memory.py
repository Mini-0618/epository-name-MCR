"""
temporal-memory.py -- ECOSYSTEM Temporal Memory

ADD-only memory with valid_at/invalid_at time windows.
Adapted from mcr-runtime temporal_memory.py for ECOSYSTEM.

Features:
  - Works with memory.jsonl format
  - Tracks validity windows (valid_at, expires_at)
  - Auto-archives expired memories
  - Links related memories across time (succession chains)
  - ADD-only: never overwrite, only retire

No external dependencies. Pure Python.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# -- Defaults --

DEFAULT_MEMORY_PATH = Path(__file__).parent.parent / "memory" / "temporal-memory.jsonl"
DEFAULT_ARCHIVE_PATH = Path(__file__).parent.parent / "memory" / "temporal-archive.jsonl"
DEFAULT_TTL = 86400 * 30  # 30 days


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_ts() -> float:
    return time.time()


class TemporalMemory:
    """
    ADD-only temporal memory with validity windows.

    Each memory has:
      - valid_at: when the memory became valid
      - expires_at: when it should be auto-archived (optional)
      - superseded_by: ID of the memory that replaced this one
      - related_ids: IDs of related memories

    Writes to temporal-memory.jsonl, archives to temporal-archive.jsonl.

    Usage:
        tm = TemporalMemory("runtime/memory/temporal-memory.jsonl")
        mid = tm.add("MCR uses event sourcing", importance=0.8)
        active = tm.get_active()
        tm.retire(mid, reason="replaced by new info")
    """

    def __init__(self, memory_path: str | Path | None = None):
        self._path = Path(memory_path) if memory_path else DEFAULT_MEMORY_PATH
        self._archive_path = DEFAULT_ARCHIVE_PATH
        self._memories: Dict[str, dict] = {}
        self._loaded = False

    # -- Load --

    def _ensure_loaded(self):
        if self._loaded:
            return
        self._loaded = True
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        mid = entry.get("memory_id", "")
                        if mid:
                            self._memories[mid] = entry
                    except (json.JSONDecodeError, TypeError):
                        continue
        except OSError:
            pass

    def _save_entry(self, entry: dict):
        """Append a single entry to the JSONL file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _rewrite_file(self):
        """Rewrite the entire file from in-memory state."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            for entry in self._memories.values():
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _archive_entry(self, entry: dict):
        """Write an entry to the archive file."""
        self._archive_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._archive_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # -- Core API --

    def add(
        self,
        content: str,
        valid_at: float | None = None,
        expires_at: float | None = None,
        metadata: dict | None = None,
        importance: float = 0.5,
        namespace: str = "default",
        source: str = "",
        related_to: str | None = None,
    ) -> str:
        """
        Add a temporal memory.

        Args:
            content: memory content text
            valid_at: when this becomes valid (Unix timestamp, default: now)
            expires_at: when this expires (Unix timestamp, optional)
            metadata: arbitrary metadata dict
            importance: 0.0-1.0 importance score
            namespace: partition key
            source: source identifier
            related_to: ID of a related memory to link

        Returns:
            memory_id
        """
        self._ensure_loaded()
        now = valid_at or _now_ts()
        mid = f"tm-{uuid.uuid4().hex[:12]}"

        entry = {
            "memory_id": mid,
            "content": content,
            "valid_at": now,
            "expires_at": expires_at,
            "superseded_by": None,
            "namespace": namespace,
            "importance": importance,
            "source": source,
            "related_ids": [related_to] if related_to else [],
            "metadata": metadata or {},
            "created_at": _now_iso(),
            "status": "active",
        }

        self._memories[mid] = entry
        self._save_entry(entry)

        # Link back: if related_to exists, add this id to its related_ids
        if related_to and related_to in self._memories:
            related = self._memories[related_to]
            if mid not in related.get("related_ids", []):
                related.setdefault("related_ids", []).append(mid)
                self._rewrite_file()

        return mid

    def get_active(self, now: float | None = None, namespace: str | None = None) -> List[dict]:
        """
        Get currently valid memories.

        Args:
            now: current timestamp (default: time.time())
            namespace: optional namespace filter

        Returns:
            List of active memory entries.
        """
        self._ensure_loaded()
        now = now or _now_ts()
        results = []

        for entry in self._memories.values():
            if entry.get("status") != "active":
                continue
            if entry.get("superseded_by"):
                continue
            valid_at = entry.get("valid_at", 0)
            expires_at = entry.get("expires_at")

            if now < valid_at:
                continue
            if expires_at is not None and now >= expires_at:
                continue
            if namespace and entry.get("namespace") != namespace:
                continue

            results.append(entry)

        # Sort by importance, then recency
        results.sort(key=lambda e: (e.get("importance", 0.5), e.get("valid_at", 0)), reverse=True)
        return results

    def get_expired(self, now: float | None = None, namespace: str | None = None) -> List[dict]:
        """
        Get expired or superseded memories.

        Args:
            now: current timestamp (default: time.time())
            namespace: optional namespace filter

        Returns:
            List of expired memory entries.
        """
        self._ensure_loaded()
        now = now or _now_ts()
        results = []

        for entry in self._memories.values():
            if entry.get("status") == "archived":
                if namespace and entry.get("namespace") != namespace:
                    continue
                results.append(entry)
                continue
            if entry.get("superseded_by"):
                if namespace and entry.get("namespace") != namespace:
                    continue
                results.append(entry)
                continue
            expires_at = entry.get("expires_at")
            if expires_at is not None and now >= expires_at:
                if namespace and entry.get("namespace") != namespace:
                    continue
                results.append(entry)

        return results

    def retire(self, memory_id: str, reason: str = "") -> bool:
        """
        Manually retire a memory.

        Args:
            memory_id: ID of the memory to retire
            reason: reason for retirement

        Returns:
            True if retired, False if not found.
        """
        self._ensure_loaded()
        entry = self._memories.get(memory_id)
        if not entry:
            return False

        entry["status"] = "archived"
        entry["superseded_by"] = reason or "manual_retire"
        entry["retired_at"] = _now_iso()
        self._rewrite_file()
        self._archive_entry(entry)
        return True

    def supersede(self, old_id: str, new_content: str, **kwargs) -> Optional[str]:
        """
        Replace a memory with a new one. Retires the old, creates the new.

        Args:
            old_id: ID of the memory to replace
            new_content: content for the new memory
            **kwargs: additional args passed to add()

        Returns:
            new memory_id, or None if old_id not found.
        """
        self._ensure_loaded()
        old = self._memories.get(old_id)
        if not old:
            return None

        # Create new memory linked to old
        new_id = self.add(
            new_content,
            namespace=old.get("namespace", "default"),
            importance=old.get("importance", 0.5),
            source=old.get("source", ""),
            related_to=old_id,
            **kwargs,
        )

        # Retire old
        old["superseded_by"] = new_id
        old["status"] = "archived"
        old["retired_at"] = _now_iso()
        self._rewrite_file()

        return new_id

    def chain(self, memory_id: str) -> List[dict]:
        """
        Get the succession chain for a memory.

        Follows superseded_by links forward, then related_ids backward
        to find the full history.

        Returns:
            List of memory entries in the chain, oldest first.
        """
        self._ensure_loaded()
        chain = []
        visited = set()
        current_id = memory_id

        # Follow superseded_by forward
        while current_id and current_id not in visited:
            visited.add(current_id)
            entry = self._memories.get(current_id)
            if not entry:
                break
            chain.append(entry)
            current_id = entry.get("superseded_by")
            # Only follow if superseded_by is a memory_id (not a reason string)
            if current_id and current_id not in self._memories:
                break

        # Also find predecessors via related_ids
        for mid, entry in self._memories.items():
            if mid in visited:
                continue
            related = entry.get("related_ids", [])
            superseded = entry.get("superseded_by")
            if superseded == memory_id or memory_id in related:
                if mid not in visited:
                    # Prepend predecessor
                    chain.insert(0, entry)
                    visited.add(mid)

        return chain

    def auto_archive_expired(self, now: float | None = None) -> int:
        """
        Auto-archive all expired memories.

        Args:
            now: current timestamp

        Returns:
            Number of memories archived.
        """
        self._ensure_loaded()
        now = now or _now_ts()
        archived = 0

        for entry in list(self._memories.values()):
            if entry.get("status") != "active":
                continue
            expires_at = entry.get("expires_at")
            if expires_at is not None and now >= expires_at:
                entry["status"] = "archived"
                entry["superseded_by"] = "auto_expired"
                entry["retired_at"] = _now_iso()
                self._archive_entry(entry)
                archived += 1

        if archived:
            self._rewrite_file()

        return archived

    def search(self, query: str, limit: int = 10, active_only: bool = True) -> List[dict]:
        """
        Search temporal memories by keyword.

        Args:
            query: search text
            limit: max results
            active_only: only search active memories

        Returns:
            List of matching entries sorted by relevance.
        """
        self._ensure_loaded()
        query_tokens = set(query.lower().split())
        if not query_tokens:
            return self.get_active()[:limit] if active_only else list(self._memories.values())[:limit]

        results = []
        for entry in self._memories.values():
            if active_only and entry.get("status") != "active":
                continue
            if active_only and entry.get("superseded_by"):
                continue

            content = entry.get("content", "").lower()
            content_tokens = set(content.split())
            overlap = len(query_tokens & content_tokens)
            if overlap > 0:
                score = overlap * entry.get("importance", 0.5)
                results.append((score, entry))

        results.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in results[:limit]]

    # -- Stats --

    def summary(self) -> dict:
        """Return summary statistics."""
        self._ensure_loaded()
        total = len(self._memories)
        active = sum(1 for e in self._memories.values()
                     if e.get("status") == "active" and not e.get("superseded_by"))
        expired = sum(1 for e in self._memories.values()
                      if e.get("status") == "archived" or e.get("superseded_by"))
        namespaces = set(e.get("namespace", "default") for e in self._memories.values())
        return {
            "total_memories": total,
            "active_memories": active,
            "expired_memories": expired,
            "namespaces": list(namespaces),
            "memory_path": str(self._path),
            "archive_path": str(self._archive_path),
        }

    def get_memory(self, memory_id: str) -> Optional[dict]:
        """Get a specific memory by ID."""
        self._ensure_loaded()
        return self._memories.get(memory_id)


# =============================================================================
# CLI
# =============================================================================

def main():
    """CLI entry point."""
    args = sys.argv[1:]
    ecosystem_root = str(Path(__file__).parent.parent.parent)

    default_path = Path(ecosystem_root) / "runtime" / "memory" / "temporal-memory.jsonl"

    if not args:
        print("Usage: temporal-memory.py <summary|active|expired|add <text>|retire <id>|chain <id>|auto-archive|search <query>>")
        sys.exit(1)

    cmd = args[0]
    tm = TemporalMemory(str(default_path))

    if cmd == "summary":
        print(json.dumps(tm.summary(), ensure_ascii=False, indent=2))

    elif cmd == "active":
        n = int(args[1]) if len(args) > 1 else 20
        active = tm.get_active()
        if not active:
            print("No active temporal memories.")
        else:
            for e in active[:n]:
                expires = e.get("expires_at")
                exp_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(expires)) if expires else "never"
                print(f"  [{e['memory_id']}] imp={e.get('importance', 0.5):.1f} expires={exp_str} | {e.get('content', '')[:80]}")
            print(f"\nShowing {min(n, len(active))} of {len(active)} active memories.")

    elif cmd == "expired":
        n = int(args[1]) if len(args) > 1 else 20
        expired = tm.get_expired()
        if not expired:
            print("No expired temporal memories.")
        else:
            for e in expired[:n]:
                reason = e.get("superseded_by", "unknown")
                print(f"  [{e['memory_id']}] reason={reason} | {e.get('content', '')[:80]}")
            print(f"\nShowing {min(n, len(expired))} of {len(expired)} expired memories.")

    elif cmd == "add":
        if len(args) < 2:
            print("Usage: temporal-memory.py add <text> [--ttl <seconds>] [--importance <0-1>]")
            sys.exit(1)
        text = args[1]
        ttl = None
        importance = 0.5
        i = 2
        while i < len(args):
            if args[i] == "--ttl" and i + 1 < len(args):
                ttl = int(args[i + 1])
                i += 2
            elif args[i] == "--importance" and i + 1 < len(args):
                importance = float(args[i + 1])
                i += 2
            else:
                i += 1
        expires_at = (time.time() + ttl) if ttl else None
        mid = tm.add(text, expires_at=expires_at, importance=importance)
        print(f"Added: {mid}")

    elif cmd == "retire":
        if len(args) < 2:
            print("Usage: temporal-memory.py retire <memory_id> [reason]")
            sys.exit(1)
        mid = args[1]
        reason = args[2] if len(args) > 2 else "manual"
        if tm.retire(mid, reason):
            print(f"Retired: {mid}")
        else:
            print(f"Not found: {mid}")
            sys.exit(1)

    elif cmd == "chain":
        if len(args) < 2:
            print("Usage: temporal-memory.py chain <memory_id>")
            sys.exit(1)
        mid = args[1]
        chain = tm.chain(mid)
        if not chain:
            print(f"No chain found for: {mid}")
        else:
            print(f"Chain for {mid} ({len(chain)} entries):")
            for e in chain:
                status = e.get("status", "unknown")
                superseded = e.get("superseded_by", "")
                marker = f" -> {superseded}" if superseded else ""
                print(f"  [{e['memory_id']}] {status}{marker} | {e.get('content', '')[:60]}")

    elif cmd == "auto-archive":
        count = tm.auto_archive_expired()
        print(f"Archived {count} expired memories.")

    elif cmd == "search":
        if len(args) < 2:
            print("Usage: temporal-memory.py search <query>")
            sys.exit(1)
        query = " ".join(args[1:])
        results = tm.search(query)
        if not results:
            print("No matching memories.")
        else:
            for e in results:
                print(f"  [{e['memory_id']}] imp={e.get('importance', 0.5):.1f} | {e.get('content', '')[:80]}")

    else:
        print(f"Unknown command: {cmd}")
        print("Commands: summary, active, expired, add, retire, chain, auto-archive, search")
        sys.exit(1)


if __name__ == "__main__":
    main()
