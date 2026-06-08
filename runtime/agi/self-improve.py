"""
self-improve.py -- ECOSYSTEM Self-Improvement Engine

Tracks success/failure patterns per task type, suggests strategy
adjustments, and auto-adjusts confidence levels based on history.

Reads swarm memory to build per-task-type statistics.
Writes improvement suggestions to improvements.jsonl.

Usage:
    python self-improve.py record <task_type> <success|failure> [metadata_json]
    python self-improve.py suggest
    python self-improve.py patterns
    python self-improve.py confidence <task_type>

Reads:  runtime/swarm/memory.jsonl
Writes: runtime/agi/improve-state.json, runtime/agi/improvements.jsonl
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# -- Paths --
ECOSYSTEM_ROOT = Path(__file__).resolve().parent.parent.parent
MEMORY_PATH = ECOSYSTEM_ROOT / "runtime" / "swarm" / "memory.jsonl"
AGI_DIR = ECOSYSTEM_ROOT / "runtime" / "agi"
STATE_PATH = AGI_DIR / "improve-state.json"
IMPROVEMENTS_PATH = AGI_DIR / "improvements.jsonl"

# -- Confidence thresholds --
HIGH_SUCCESS_THRESHOLD = 0.85    # 85%+ success rate = high confidence
LOW_SUCCESS_THRESHOLD = 0.40     # below 40% = low confidence
MIN_SAMPLES_FOR_CONFIDENCE = 3   # need at least 3 samples to adjust
SUGGESTION_COOLDOWN = 5          # don't repeat same suggestion within 5 records


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
    """Load improvement state from disk."""
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "schema_version": "0.1",
        "task_types": {},
        "total_records": 0,
        "suggestions_generated": 0,
        "last_suggest": None,
    }


def save_state(state: Dict[str, Any]) -> None:
    """Save improvement state to disk."""
    AGI_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def append_improvement(improvement: Dict[str, Any]) -> None:
    """Append an improvement record to improvements.jsonl."""
    AGI_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps(improvement, ensure_ascii=False)
    with open(IMPROVEMENTS_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _safe_name(task_type: str) -> str:
    """Normalize task type name for consistent tracking."""
    return task_type.strip().lower()


class SelfImprove:
    """Tracks task outcomes and suggests improvements."""

    # Auto-fix rules: simple fixes that can be applied automatically
    AUTO_FIX_RULES = {
        "memory_pressure": {
            "check": lambda: AGI_DIR.parent.parent / "runtime" / "swarm" / "memory.jsonl",
            "fix_description": "Archive old memory entries",
            "risk": "low",
            "auto_safe": True,
        },
        "prediction_drift": {
            "check": lambda: AGI_DIR / "prediction-stats.json",
            "fix_description": "Reset prediction stats to recalibrate",
            "risk": "medium",
            "auto_safe": True,
        },
        "quarantine_spike": {
            "check": lambda: AGI_DIR / "feedback-quarantine.jsonl",
            "fix_description": "Clear quarantined feedback after review",
            "risk": "medium",
            "auto_safe": False,  # needs human review
        },
    }

    def __init__(self, improve_path: str = None):
        self.improve_path = Path(improve_path) if improve_path else IMPROVEMENTS_PATH

    def _sync_from_memory(self, state: Dict[str, Any]) -> None:
        """Sync task-type stats from memory.jsonl entries."""
        entries = load_memory_entries()
        for entry in entries:
            successes = entry.get("successes", [])
            failures = entry.get("failures", [])
            for task in successes:
                if task:
                    name = _safe_name(str(task))
                    tt = state["task_types"].setdefault(name, {
                        "success": 0, "failure": 0, "total": 0,
                        "last_outcome": None, "last_recorded": None,
                    })
                    # Only count if not already counted (check by memory_id tracking)
                    mem_id = entry.get("memory_id", "")
                    seen_key = f"_seen_{mem_id}"
                    if not tt.get(seen_key):
                        tt["success"] += 1
                        tt["total"] += 1
                        tt["last_outcome"] = "success"
                        tt[seen_key] = True

            for fail in failures:
                if fail:
                    fail_str = str(fail)
                    # Extract task name before colon if present
                    name = _safe_name(fail_str.split(":")[0] if ":" in fail_str else fail_str)
                    tt = state["task_types"].setdefault(name, {
                        "success": 0, "failure": 0, "total": 0,
                        "last_outcome": None, "last_recorded": None,
                    })
                    mem_id = entry.get("memory_id", "")
                    seen_key = f"_seen_{mem_id}"
                    if not tt.get(seen_key):
                        tt["failure"] += 1
                        tt["total"] += 1
                        tt["last_outcome"] = "failure"
                        tt[seen_key] = True

    def record(self, task_type: str, outcome: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Record a task outcome. outcome must be 'success' or 'failure'."""
        if outcome not in ("success", "failure"):
            raise ValueError(f"outcome must be 'success' or 'failure', got '{outcome}'")

        state = load_state()
        name = _safe_name(task_type)
        now = datetime.now(timezone.utc).isoformat()

        tt = state["task_types"].setdefault(name, {
            "success": 0, "failure": 0, "total": 0,
            "last_outcome": None, "last_recorded": None,
        })

        tt[outcome] = tt.get(outcome, 0) + 1
        tt["total"] = tt.get("total", 0) + 1
        tt["last_outcome"] = outcome
        tt["last_recorded"] = now
        state["total_records"] = state.get("total_records", 0) + 1

        save_state(state)

        record = {
            "task_type": name,
            "outcome": outcome,
            "total": tt["total"],
            "success_rate": round(tt["success"] / tt["total"], 3) if tt["total"] > 0 else 0,
            "metadata": metadata or {},
            "timestamp": now,
        }
        return record

    def suggest(self) -> List[Dict[str, Any]]:
        """Analyze patterns and generate improvement suggestions."""
        state = load_state()
        self._sync_from_memory(state)
        now = datetime.now(timezone.utc).isoformat()
        suggestions = []

        for task_name, stats in state["task_types"].items():
            # Skip internal tracking keys
            if task_name.startswith("_seen_"):
                continue
            total = stats.get("total", 0)
            if total < MIN_SAMPLES_FOR_CONFIDENCE:
                continue

            success = stats.get("success", 0)
            failure = stats.get("failure", 0)
            rate = success / total if total > 0 else 0

            suggestion = None

            if rate < LOW_SUCCESS_THRESHOLD and failure >= 2:
                suggestion = {
                    "task_type": task_name,
                    "type": "high_failure_rate",
                    "severity": "high",
                    "message": f"Task '{task_name}' has {rate:.0%} success rate ({success}/{total}). Investigate root cause or change approach.",
                    "success_rate": round(rate, 3),
                    "total": total,
                    "timestamp": now,
                }
            elif rate < 0.60 and failure >= 3:
                suggestion = {
                    "task_type": task_name,
                    "type": "moderate_failure_rate",
                    "severity": "medium",
                    "message": f"Task '{task_name}' has {rate:.0%} success rate ({success}/{total}). Consider adding validation or retry logic.",
                    "success_rate": round(rate, 3),
                    "total": total,
                    "timestamp": now,
                }
            elif rate >= HIGH_SUCCESS_THRESHOLD and total >= 5:
                suggestion = {
                    "task_type": task_name,
                    "type": "automation_candidate",
                    "severity": "info",
                    "message": f"Task '{task_name}' has {rate:.0%} success rate ({success}/{total}). Candidate for automation or skill promotion.",
                    "success_rate": round(rate, 3),
                    "total": total,
                    "timestamp": now,
                }

            if suggestion:
                # Check cooldown: don't repeat same suggestion too soon
                last_suggestions = state.get("_last_suggestions", {})
                last_for_task = last_suggestions.get(task_name)
                if last_for_task:
                    try:
                        last_dt = datetime.fromisoformat(last_for_task)
                        delta = datetime.fromisoformat(now) - last_dt
                        if delta.total_seconds() < 3600 * SUGGESTION_COOLDOWN:
                            continue
                    except (ValueError, TypeError):
                        pass

                suggestions.append(suggestion)
                append_improvement(suggestion)

                if "_last_suggestions" not in state:
                    state["_last_suggestions"] = {}
                state["_last_suggestions"][task_name] = now
                state["suggestions_generated"] = state.get("suggestions_generated", 0) + 1

        state["last_suggest"] = now
        save_state(state)
        return suggestions

    def get_patterns(self) -> Dict[str, Any]:
        """Return all success/failure patterns."""
        state = load_state()
        self._sync_from_memory(state)
        save_state(state)

        patterns = {}
        for task_name, stats in state["task_types"].items():
            if task_name.startswith("_seen_"):
                continue
            total = stats.get("total", 0)
            success = stats.get("success", 0)
            failure = stats.get("failure", 0)
            rate = success / total if total > 0 else 0

            category = "unknown"
            if total >= MIN_SAMPLES_FOR_CONFIDENCE:
                if rate >= HIGH_SUCCESS_THRESHOLD:
                    category = "strong"
                elif rate >= 0.60:
                    category = "moderate"
                elif rate >= LOW_SUCCESS_THRESHOLD:
                    category = "weak"
                else:
                    category = "failing"
            else:
                category = "insufficient_data"

            patterns[task_name] = {
                "success": success,
                "failure": failure,
                "total": total,
                "success_rate": round(rate, 3),
                "category": category,
                "last_outcome": stats.get("last_outcome"),
                "last_recorded": stats.get("last_recorded"),
            }

        # Sort by total desc
        sorted_patterns = dict(sorted(patterns.items(), key=lambda x: x[1]["total"], reverse=True))

        return {
            "task_types": sorted_patterns,
            "total_task_types": len(sorted_patterns),
            "total_records": state.get("total_records", 0),
            "suggestions_generated": state.get("suggestions_generated", 0),
        }

    def adjust_confidence(self, task_type: str) -> Dict[str, Any]:
        """Get adjusted confidence for a task type based on history."""
        state = load_state()
        self._sync_from_memory(state)
        name = _safe_name(task_type)

        if name not in state["task_types"]:
            return {
                "task_type": name,
                "confidence": 0.5,
                "adjustment": 0.0,
                "reason": "no_history",
                "samples": 0,
            }

        stats = state["task_types"][name]
        total = stats.get("total", 0)
        success = stats.get("success", 0)
        rate = success / total if total > 0 else 0.5

        # Base confidence is 0.5 (neutral)
        # Adjust based on observed success rate
        if total < MIN_SAMPLES_FOR_CONFIDENCE:
            confidence = 0.5
            adjustment = 0.0
            reason = f"insufficient_data ({total} samples)"
        else:
            # Weighted blend: 70% observed rate + 30% prior (0.5)
            confidence = round(0.7 * rate + 0.3 * 0.5, 3)
            adjustment = round(confidence - 0.5, 3)
            if rate >= HIGH_SUCCESS_THRESHOLD:
                reason = f"high_success_rate ({rate:.0%})"
            elif rate < LOW_SUCCESS_THRESHOLD:
                reason = f"low_success_rate ({rate:.0%})"
            else:
                reason = f"moderate_success_rate ({rate:.0%})"

        save_state(state)
        return {
            "task_type": name,
            "confidence": confidence,
            "adjustment": adjustment,
            "reason": reason,
            "samples": total,
            "success_rate": round(rate, 3),
        }

    def apply_fix(self, fix_type: str, dry_run: bool = True) -> Dict[str, Any]:
        """
        Apply an auto-fix for a known issue type.

        Args:
            fix_type: Type of fix to apply (memory_pressure, prediction_drift, etc.)
            dry_run: If True, only report what would be done

        Returns: Result of the fix attempt
        """
        now = datetime.now(timezone.utc).isoformat()

        if fix_type not in self.AUTO_FIX_RULES:
            return {
                "fix_type": fix_type,
                "status": "error",
                "message": f"Unknown fix type: {fix_type}",
                "available_fixes": list(self.AUTO_FIX_RULES.keys()),
            }

        rule = self.AUTO_FIX_RULES[fix_type]

        if not rule["auto_safe"] and dry_run:
            return {
                "fix_type": fix_type,
                "status": "requires_approval",
                "message": f"Fix '{fix_type}' requires human approval (risk: {rule['risk']})",
                "fix_description": rule["fix_description"],
                "dry_run": True,
            }

        # Apply the fix
        result = {
            "fix_type": fix_type,
            "fix_description": rule["fix_description"],
            "risk": rule["risk"],
            "dry_run": dry_run,
            "applied_at": now,
        }

        try:
            target_path = rule["check"]()

            if fix_type == "memory_pressure":
                # Archive old memory entries (move to archive)
                memory_path = target_path
                if memory_path.exists():
                    entries = []
                    for line in memory_path.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if line:
                            try:
                                entries.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue

                    if not dry_run:
                        # Keep only recent 100 entries
                        if len(entries) > 100:
                            archived = entries[:-100]
                            kept = entries[-100:]
                            archive_path = memory_path.with_suffix(".archive.jsonl")
                            archive_path.write_text(
                                "\n".join(json.dumps(e, ensure_ascii=False) for e in archived),
                                encoding="utf-8"
                            )
                            memory_path.write_text(
                                "\n".join(json.dumps(e, ensure_ascii=False) for e in kept) + "\n",
                                encoding="utf-8"
                            )
                            result["status"] = "applied"
                            result["archived_count"] = len(archived)
                            result["kept_count"] = len(kept)
                        else:
                            result["status"] = "no_action_needed"
                            result["message"] = f"Only {len(entries)} entries, below threshold"
                    else:
                        result["status"] = "dry_run"
                        result["would_archive"] = max(0, len(entries) - 100)
                        result["total_entries"] = len(entries)

            elif fix_type == "prediction_drift":
                stats_path = target_path
                if stats_path.exists():
                    if not dry_run:
                        # Reset prediction stats
                        stats_path.write_text(json.dumps({
                            "reset_at": now,
                            "reason": "prediction_drift_fix",
                            "brier_score": None,
                            "accuracy": None,
                            "sample_count": 0,
                        }, indent=2), encoding="utf-8")
                        result["status"] = "applied"
                    else:
                        result["status"] = "dry_run"
                        result["message"] = "Would reset prediction stats"

            elif fix_type == "quarantine_spike":
                quarantine_path = target_path
                if quarantine_path.exists():
                    entries = []
                    for line in quarantine_path.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if line:
                            try:
                                entries.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
                    result["status"] = "requires_approval"
                    result["quarantined_count"] = len(entries)
                    result["message"] = f"{len(entries)} quarantined entries need human review"

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)

        # Log the fix attempt
        append_improvement({
            "type": "auto_fix",
            "fix_type": fix_type,
            "result": result,
            "timestamp": now,
        })

        return result

    def auto_fix_all(self, dry_run: bool = False) -> Dict[str, Any]:
        """Run all auto-fixes and return results. Default: apply fixes."""
        results = {}
        for fix_type in self.AUTO_FIX_RULES:
            results[fix_type] = self.apply_fix(fix_type, dry_run=dry_run)
        return results


def cli():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: self-improve.py <record|suggest|patterns|confidence|fix|auto-fix> [args]")
        sys.exit(1)

    action = sys.argv[1]
    si = SelfImprove()

    if action == "record":
        if len(sys.argv) < 4:
            print("Usage: self-improve.py record <task_type> <success|failure> [metadata_json]")
            sys.exit(1)
        task_type = sys.argv[2]
        outcome = sys.argv[3]
        metadata = None
        if len(sys.argv) > 4:
            try:
                metadata = json.loads(sys.argv[4])
            except json.JSONDecodeError:
                metadata = {"raw": sys.argv[4]}
        result = si.record(task_type, outcome, metadata)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif action == "suggest":
        suggestions = si.suggest()
        print(json.dumps({
            "suggestions": suggestions,
            "count": len(suggestions),
        }, indent=2, ensure_ascii=False))

    elif action == "patterns":
        patterns = si.get_patterns()
        print(json.dumps(patterns, indent=2, ensure_ascii=False))

    elif action == "confidence":
        if len(sys.argv) < 3:
            print("Usage: self-improve.py confidence <task_type>")
            sys.exit(1)
        task_type = sys.argv[2]
        result = si.adjust_confidence(task_type)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif action == "fix":
        if len(sys.argv) < 3:
            print("Usage: self-improve.py fix <fix_type> [--dry-run]")
            print(f"Available fixes: {list(SelfImprove.AUTO_FIX_RULES.keys())}")
            sys.exit(1)
        fix_type = sys.argv[2]
        dry_run = "--dry-run" in sys.argv
        result = si.apply_fix(fix_type, dry_run=dry_run)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif action == "auto-fix":
        dry_run = "--dry-run" in sys.argv
        results = si.auto_fix_all(dry_run=dry_run)
        print(json.dumps(results, indent=2, ensure_ascii=False))

    else:
        print(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
