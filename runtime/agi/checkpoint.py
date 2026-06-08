"""
checkpoint.py -- ECOSYSTEM State Snapshot Manager

Periodic state snapshots for crash recovery.
Scans current ecosystem state (daemon, swarm, memory, skills)
and writes timestamped checkpoint files.

Keeps last N checkpoints. Enables restore from any checkpoint.

No external dependencies.
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional


class CheckpointManager:
    """
    Snapshot and restore ECOSYSTEM state.

    Checkpoints are stored as individual JSON files in checkpoint_dir,
    named with ISO timestamps: 20260606T120000Z.json

    Args:
        checkpoint_dir: Directory to store checkpoint files.
        ecosystem_root: Root of the ECOSYSTEM tree (for scanning state).
    """

    def __init__(self, checkpoint_dir: str, ecosystem_root: str):
        self._dir = Path(checkpoint_dir)
        self._root = Path(ecosystem_root)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    def create(self, label: Optional[str] = None) -> dict:
        """
        Create a checkpoint of current ecosystem state.

        Scans: daemon state, swarm memory, AGI state, skills.
        Returns checkpoint metadata.
        """
        now = time.time()
        ts = datetime.fromtimestamp(now, tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        ckpt_id = f"ckpt-{ts}"

        state = self._scan_state()

        checkpoint = {
            "checkpoint_id": ckpt_id,
            "created_at": now,
            "created_at_iso": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
            "label": label or "",
            "ecosystem_root": str(self._root),
            "state": state,
        }

        filename = f"ckpt-{ts}.json"
        if label:
            safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)
            filename = f"ckpt-{ts}_{safe_label}.json"

        filepath = self._dir / filename

        with self._lock:
            tmp = filepath.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(checkpoint, f, indent=2, ensure_ascii=False, default=str)
            tmp.replace(filepath)

        self.cleanup(keep=10)

        return {
            "checkpoint_id": ckpt_id,
            "path": str(filepath),
            "label": label or "",
            "created_at_iso": checkpoint["created_at_iso"],
        }

    def list(self, n: int = 10) -> list[dict]:
        """
        List recent checkpoints (newest first).

        Returns list of checkpoint metadata (without full state).
        """
        files = self._find_checkpoint_files()
        # Sort by name descending (newest first)
        files.sort(reverse=True)
        results = []
        for fp in files[:n]:
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                results.append({
                    "checkpoint_id": data.get("checkpoint_id", fp.stem),
                    "created_at_iso": data.get("created_at_iso", ""),
                    "label": data.get("label", ""),
                    "path": str(fp),
                    "file_size_bytes": fp.stat().st_size,
                })
            except (json.JSONDecodeError, IOError, KeyError):
                results.append({
                    "checkpoint_id": fp.stem,
                    "created_at_iso": "",
                    "label": "(unreadable)",
                    "path": str(fp),
                })
        return results

    def restore(self, checkpoint_id: str) -> dict:
        """
        Load a checkpoint by ID and return its state.

        The caller is responsible for actually applying the state.
        Returns the full checkpoint data.
        """
        filepath = self._find_by_id(checkpoint_id)
        if filepath is None:
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_id}")

        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def cleanup(self, keep: int = 10) -> int:
        """
        Remove old checkpoints, keeping only the most recent `keep` files.

        Returns number of files removed.
        """
        files = self._find_checkpoint_files()
        files.sort(reverse=True)  # newest first

        if len(files) <= keep:
            return 0

        to_remove = files[keep:]
        removed = 0
        with self._lock:
            for fp in to_remove:
                try:
                    fp.unlink()
                    removed += 1
                except IOError:
                    pass
        return removed

    # ── Internal ──────────────────────────────────────────────────────────────

    def _find_checkpoint_files(self) -> list[Path]:
        """Find all checkpoint JSON files in checkpoint_dir."""
        pattern = str(self._dir / "ckpt-*.json")
        return [Path(p) for p in glob.glob(pattern)]

    def _find_by_id(self, checkpoint_id: str) -> Optional[Path]:
        """Find a checkpoint file by its checkpoint_id."""
        for fp in self._find_checkpoint_files():
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("checkpoint_id") == checkpoint_id:
                    return fp
            except (json.JSONDecodeError, IOError):
                pass
        return None

    def _scan_state(self) -> dict:
        """
        Scan current ecosystem state for checkpoint snapshot.

        Reads: daemon state, swarm memory, AGI state files, skills.
        Safe: never throws, returns partial data on read errors.
        """
        state = {}

        # Daemon state
        daemon_state = self._safe_read_json(self._root / "runtime" / "daemon" / "state.json")
        if daemon_state:
            state["daemon"] = daemon_state

        # Daemon heartbeats (last 5)
        hb_path = self._root / "runtime" / "daemon" / "heartbeats.jsonl"
        state["recent_heartbeats"] = self._safe_tail_jsonl(hb_path, 5)

        # Swarm memory count
        memory_path = self._root / "runtime" / "swarm" / "memory.jsonl"
        state["memory_entries"] = self._count_jsonl(memory_path)

        # Swarm tasks count
        tasks_path = self._root / "runtime" / "swarm" / "tasks.jsonl"
        state["task_entries"] = self._count_jsonl(tasks_path)

        # AGI goal generator
        goal_gen = self._safe_read_json(self._root / "runtime" / "agi" / "goal-generator.json")
        if goal_gen:
            state["agi_goals"] = {
                "total_scans": goal_gen.get("total_scans", 0),
                "total_goals": goal_gen.get("total_goals_generated", 0),
            }

        # AGI world model
        world_model = self._safe_read_json(self._root / "runtime" / "agi" / "world-model.json")
        if world_model:
            state["world_model"] = {
                "observations": world_model.get("total_observations", 0),
                "causal_links": world_model.get("total_causal_links", 0),
            }

        # Prediction stats
        pred_stats = self._safe_read_json(self._root / "runtime" / "agi" / "prediction-stats.json")
        if pred_stats:
            state["prediction_stats"] = pred_stats

        # Skills
        skills_dir = self._root / "runtime" / "skills"
        if skills_dir.exists():
            skill_files = list(skills_dir.glob("*.json"))
            state["skill_files"] = [f.name for f in skill_files]

        # Weekly plan
        weekly_plan = self._safe_read_json(self._root / "runtime" / "life" / "weekly-plan.json")
        if weekly_plan:
            state["weekly_plan"] = {
                "plan_id": weekly_plan.get("plan_id", ""),
                "status": weekly_plan.get("status", ""),
            }

        # Registry app count
        registry = self._safe_read_json(self._root / "registry" / "apps.json")
        if registry:
            state["registry_app_count"] = registry.get("app_count", 0)

        return state

    @staticmethod
    def _safe_read_json(path: Path) -> Optional[dict]:
        """Read a JSON file, return None on any error."""
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return None

    @staticmethod
    def _safe_tail_jsonl(path: Path, n: int = 5) -> list:
        """Read last N lines of a JSONL file."""
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                result = []
                for line in lines[-n:]:
                    line = line.strip()
                    if line:
                        try:
                            result.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
                return result
        except IOError:
            pass
        return []

    @staticmethod
    def _count_jsonl(path: Path) -> int:
        """Count non-empty lines in a JSONL file."""
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return sum(1 for line in f if line.strip())
        except IOError:
            pass
        return 0


# ── CLI entry point ──────────────────────────────────────────────────────────

def _cli():
    import sys

    if len(sys.argv) < 3:
        print("Usage: checkpoint.py <checkpoint_dir> <ecosystem_root> [create|list|restore|cleanup] [args...]")
        sys.exit(1)

    ckpt_dir = sys.argv[1]
    eco_root = sys.argv[2]
    cmd = sys.argv[3] if len(sys.argv) > 3 else "list"

    cm = CheckpointManager(ckpt_dir, eco_root)

    if cmd == "create":
        label = sys.argv[4] if len(sys.argv) > 4 else None
        result = cm.create(label)
        print(json.dumps(result, indent=2))
    elif cmd == "list":
        n = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        items = cm.list(n)
        print(json.dumps(items, indent=2))
    elif cmd == "restore":
        if len(sys.argv) < 5:
            print("Usage: checkpoint.py <dir> <root> restore <checkpoint_id>")
            sys.exit(1)
        ckpt_id = sys.argv[4]
        data = cm.restore(ckpt_id)
        print(json.dumps(data, indent=2))
    elif cmd == "cleanup":
        keep = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        removed = cm.cleanup(keep)
        print(json.dumps({"removed": removed, "kept": keep}, indent=2))
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    _cli()
