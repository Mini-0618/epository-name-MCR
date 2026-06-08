"""
self-diagnosis.py -- ECOSYSTEM Self-Diagnosis Engine

READ-ONLY health checks across all AGI subsystems:
  - Memory health (size, entry count, staleness)
  - Prediction health (accuracy, sample count, declining trend)
  - Daemon health (run speed, consecutive failures)
  - Skill health (unused skills, failed runs)
  - File system (oversized directories, orphaned files)

Writes diagnosis to runtime/agi/diagnosis.json.
If critical issues found, writes a question to feedback-pending.jsonl.

Usage:
    python self-diagnosis.py diagnose
    python self-diagnosis.py score

No external dependencies -- stdlib only.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# -- Paths --
ECOSYSTEM_ROOT = Path(__file__).resolve().parent.parent.parent
AGI_DIR = ECOSYSTEM_ROOT / "runtime" / "agi"
RUNTIME_DIR = ECOSYSTEM_ROOT / "runtime"
DAEMON_DIR = RUNTIME_DIR / "daemon"
DIAGNOSIS_PATH = AGI_DIR / "diagnosis.json"
FEEDBACK_PENDING_PATH = AGI_DIR / "feedback-pending.jsonl"

# -- Thresholds --
MEMORY_JSONL_MAX_BYTES = 10 * 1024 * 1024   # 10 MB
MEMORY_JSONL_MAX_ENTRIES = 1000
MEMORY_STALE_DAYS = 30
PREDICTION_MIN_SAMPLES = 10
PREDICTION_DECLINE_WINDOW = 20
DAEMON_SLOW_THRESHOLD_S = 300  # 5 min per step
DAEMON_MAX_CONSECUTIVE_FAILURES = 3
SKILL_DIR = RUNTIME_DIR / "skills"
SWARM_MEMORY_PATH = RUNTIME_DIR / "swarm" / "memory.jsonl"
MAX_DIR_SIZE_MB = 500  # warn if any dir exceeds 500 MB


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _file_size(path: Path) -> int:
    """Return file size in bytes, or 0 if not found."""
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _count_lines(path: Path) -> int:
    """Count non-empty lines in a file."""
    if not path.exists():
        return 0
    count = 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
    except OSError:
        pass
    return count


def _dir_size_bytes(path: Path) -> int:
    """Recursively compute directory size in bytes."""
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    entries = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return entries


class SelfDiagnosis:
    """READ-ONLY self-diagnosis engine for the MCR ecosystem."""

    def __init__(self, ecosystem_root: str | Path | None = None):
        self._root = Path(ecosystem_root) if ecosystem_root else ECOSYSTEM_ROOT
        self._agi_dir = self._root / "runtime" / "agi"
        self._runtime_dir = self._root / "runtime"
        self._daemon_dir = self._runtime_dir / "daemon"

    # ------------------------------------------------------------------
    # Individual health checks (each returns a list of issue dicts)
    # ------------------------------------------------------------------

    def _check_memory_health(self) -> List[Dict[str, Any]]:
        """Check memory.jsonl size, entry count, and staleness."""
        issues: List[Dict[str, Any]] = []
        memory_path = self._runtime_dir / "swarm" / "memory.jsonl"

        # Size check
        size = _file_size(memory_path)
        if size > MEMORY_JSONL_MAX_BYTES:
            issues.append({
                "check": "memory_size",
                "severity": "warning",
                "message": f"memory.jsonl is {size // (1024*1024)} MB (threshold: {MEMORY_JSONL_MAX_BYTES // (1024*1024)} MB)",
                "recommendation": "Archive old entries or rotate the file"
            })

        # Entry count check
        entries = _load_jsonl(memory_path)
        count = len(entries)
        if count > MEMORY_JSONL_MAX_ENTRIES:
            issues.append({
                "check": "memory_entry_count",
                "severity": "warning",
                "message": f"memory.jsonl has {count} entries (threshold: {MEMORY_JSONL_MAX_ENTRIES})",
                "recommendation": "Run tier-manager to compact or archive old memories"
            })

        # Staleness check
        now = datetime.now(timezone.utc)
        stale_count = 0
        for entry in entries:
            ts_str = entry.get("written_at") or entry.get("timestamp")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if (now - ts).days > MEMORY_STALE_DAYS:
                        stale_count += 1
                except (ValueError, TypeError):
                    pass
        if stale_count > 0:
            issues.append({
                "check": "memory_staleness",
                "severity": "info",
                "message": f"{stale_count} memory entries older than {MEMORY_STALE_DAYS} days",
                "recommendation": "Consider archiving stale entries via tier-manager"
            })

        return issues

    def _check_feedback_quarantine(self) -> List[Dict[str, Any]]:
        """Check quarantine status of feedback."""
        issues: List[Dict[str, Any]] = []
        stats_path = self._agi_dir / "quarantine-stats.json"

        stats = _load_json(stats_path)
        if not stats:
            return issues

        quarantined = stats.get("quarantined", 0)
        total = stats.get("total_feedback", 0)
        if total > 0 and quarantined > 0:
            rate = quarantined / total
            if rate > 0.5:
                issues.append({
                    "check": "feedback_quarantine_high",
                    "severity": "warning",
                    "message": f"{quarantined}/{total} feedback entries quarantined ({rate:.0%})",
                    "recommendation": "High quarantine rate indicates possible injection attack"
                })
            else:
                issues.append({
                    "check": "feedback_quarantine",
                    "severity": "info",
                    "message": f"{quarantined}/{total} feedback entries quarantined",
                    "recommendation": "Review quarantined entries for false positives"
                })

        # Check pattern issues
        pattern_issues = stats.get("pattern_issues", {})
        for issue_type, count in pattern_issues.items():
            if count > 0:
                issues.append({
                    "check": f"feedback_{issue_type}",
                    "severity": "warning",
                    "message": f"Feedback {issue_type}: {count} issues detected",
                    "recommendation": f"Review {issue_type} in quarantine log"
                })

        return issues

    def _check_prediction_health(self) -> List[Dict[str, Any]]:
        """Check prediction accuracy and sample count."""
        issues: List[Dict[str, Any]] = []
        pred_path = self._agi_dir / "predictions.jsonl"
        stats_path = self._agi_dir / "prediction-stats.json"

        entries = _load_jsonl(pred_path)
        count = len(entries)

        if count < PREDICTION_MIN_SAMPLES:
            issues.append({
                "check": "prediction_samples",
                "severity": "info",
                "message": f"Only {count} prediction samples (minimum: {PREDICTION_MIN_SAMPLES})",
                "recommendation": "Record more predictions to improve calibration"
            })
            return issues

        # Check for declining accuracy using recent window
        if count >= PREDICTION_DECLINE_WINDOW * 2:
            recent = entries[-PREDICTION_DECLINE_WINDOW:]
            older = entries[-(PREDICTION_DECLINE_WINDOW * 2):-PREDICTION_DECLINE_WINDOW]

            def _accuracy(batch: List[Dict]) -> float:
                correct = sum(1 for e in batch if e.get("correct") or e.get("outcome") is True)
                return correct / len(batch) if batch else 0.0

            recent_acc = _accuracy(recent)
            older_acc = _accuracy(older)

            if older_acc > 0 and recent_acc < older_acc * 0.7:
                issues.append({
                    "check": "prediction_decline",
                    "severity": "warning",
                    "message": f"Prediction accuracy declining: {recent_acc:.1%} recent vs {older_acc:.1%} older",
                    "recommendation": "Review prediction patterns and adjust confidence levels"
                })

        # Check stats file for brier score
        stats = _load_json(stats_path)
        if stats:
            brier = stats.get("brier_score")
            if brier is not None and brier > 0.4:
                issues.append({
                    "check": "prediction_brier",
                    "severity": "warning",
                    "message": f"Brier score is {brier:.3f} (threshold: 0.4)",
                    "recommendation": "Predictions are poorly calibrated; review confidence levels"
                })

        return issues

    def _check_daemon_health(self) -> List[Dict[str, Any]]:
        """Check daemon run speed and consecutive failures."""
        issues: List[Dict[str, Any]] = []
        state_path = self._daemon_dir / "state.json"

        state = _load_json(state_path)
        if not state:
            issues.append({
                "check": "daemon_state",
                "severity": "info",
                "message": "No daemon state.json found",
                "recommendation": "Run daemon once to initialize"
            })
            return issues

        # Consecutive failures
        consec_fail = int(state.get("consecutive_failures", 0))
        if consec_fail >= DAEMON_MAX_CONSECUTIVE_FAILURES:
            issues.append({
                "check": "daemon_consecutive_failures",
                "severity": "critical",
                "message": f"Daemon has {consec_fail} consecutive failures",
                "recommendation": "Check daemon reports for root cause and fix failing steps"
            })
        elif consec_fail >= 1:
            issues.append({
                "check": "daemon_consecutive_failures",
                "severity": "warning",
                "message": f"Daemon has {consec_fail} consecutive failure(s)",
                "recommendation": "Monitor daemon runs; fix if pattern persists"
            })

        # Check last run duration from heartbeats
        heartbeats_path = self._daemon_dir / "heartbeats.jsonl"
        hb_entries = _load_jsonl(heartbeats_path)
        if hb_entries:
            last_hb = hb_entries[-1]
            ts_str = last_hb.get("timestamp")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    minutes_ago = (datetime.now(timezone.utc) - ts).total_seconds() / 60
                    if minutes_ago > 120:
                        issues.append({
                            "check": "daemon_staleness",
                            "severity": "warning",
                            "message": f"Last heartbeat was {minutes_ago:.0f} minutes ago",
                            "recommendation": "Daemon may not be running; check loop mode"
                        })
                except (ValueError, TypeError):
                    pass

        return issues

    def _check_skill_health(self) -> List[Dict[str, Any]]:
        """Check for unused or failed skills."""
        issues: List[Dict[str, Any]] = []
        skill_dir = self._runtime_dir / "skills"

        if not skill_dir.exists():
            return issues

        # Check for skill run logs
        transfer_path = skill_dir / "transfer-registry.json"
        if transfer_path.exists():
            try:
                reg = json.loads(transfer_path.read_text(encoding="utf-8"))
                transfers = reg.get("transfers", [])
                never_run = [t for t in transfers if not t.get("last_run")]
                if len(never_run) > 3:
                    issues.append({
                        "check": "skill_unused",
                        "severity": "info",
                        "message": f"{len(never_run)} skills have never been run",
                        "recommendation": "Review unused skills; promote or archive them"
                    })
            except (json.JSONDecodeError, OSError):
                pass

        # Check for failed skill runs in recent events
        events_path = self._runtime_dir / "events.jsonl"
        if events_path.exists():
            failed_skills = []
            try:
                with open(events_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            evt = json.loads(line)
                            if evt.get("event_type") == "executor_result":
                                payload = evt.get("payload", {})
                                if payload.get("status") == "failed" and "skill" in str(payload.get("executor", "")):
                                    failed_skills.append(evt.get("task_id", "unknown"))
                        except json.JSONDecodeError:
                            continue
            except OSError:
                pass
            if failed_skills:
                issues.append({
                    "check": "skill_failures",
                    "severity": "warning",
                    "message": f"{len(failed_skills)} failed skill executions found in events",
                    "recommendation": "Review failed skill logs and fix or remove problematic skills"
                })

        return issues

    def _check_filesystem_health(self) -> List[Dict[str, Any]]:
        """Check for oversized directories and orphaned files."""
        issues: List[Dict[str, Any]] = []

        # Check known directories
        check_dirs = [
            ("runtime/agi/checkpoints", self._agi_dir / "checkpoints"),
            ("runtime/daemon/reports", self._daemon_dir / "reports"),
            ("runtime/daemon/runs", self._daemon_dir / "runs"),
            ("runtime/swarm", self._runtime_dir / "swarm"),
        ]

        for label, dir_path in check_dirs:
            if not dir_path.exists():
                continue
            size_mb = _dir_size_bytes(dir_path) / (1024 * 1024)
            if size_mb > MAX_DIR_SIZE_MB:
                issues.append({
                    "check": f"dir_size_{label.replace('/', '_')}",
                    "severity": "warning",
                    "message": f"{label} is {size_mb:.1f} MB (threshold: {MAX_DIR_SIZE_MB} MB)",
                    "recommendation": f"Archive or clean up old files in {label}"
                })

        # Check for orphaned checkpoint files (checkpoints without matching sessions)
        ckpt_dir = self._agi_dir / "checkpoints"
        if ckpt_dir.exists():
            ckpt_files = list(ckpt_dir.glob("ckpt-*.json"))
            if len(ckpt_files) > 50:
                issues.append({
                    "check": "checkpoint_count",
                    "severity": "info",
                    "message": f"{len(ckpt_files)} checkpoint files in {ckpt_dir}",
                    "recommendation": "Archive old checkpoints to reduce disk usage"
                })

        # Check events.jsonl size
        events_path = self._runtime_dir / "events.jsonl"
        events_size = _file_size(events_path)
        if events_size > 50 * 1024 * 1024:  # 50 MB
            issues.append({
                "check": "events_size",
                "severity": "warning",
                "message": f"events.jsonl is {events_size // (1024*1024)} MB",
                "recommendation": "Rotate or archive events.jsonl"
            })

        return issues

    # ------------------------------------------------------------------
    # Main diagnosis
    # ------------------------------------------------------------------

    def diagnose(self) -> Dict[str, Any]:
        """Run full self-diagnosis. Returns structured result dict."""
        all_issues: List[Dict[str, Any]] = []

        all_issues.extend(self._check_memory_health())
        all_issues.extend(self._check_prediction_health())
        all_issues.extend(self._check_daemon_health())
        all_issues.extend(self._check_skill_health())
        all_issues.extend(self._check_filesystem_health())
        all_issues.extend(self._check_feedback_quarantine())

        # Determine overall severity
        severities = [i["severity"] for i in all_issues]
        if "critical" in severities:
            overall = "critical"
        elif "warning" in severities:
            overall = "warning"
        else:
            overall = "ok"

        # Collect unique recommendations
        recommendations = list(dict.fromkeys(i["recommendation"] for i in all_issues if i.get("recommendation")))

        result = {
            "timestamp": _now_iso(),
            "issues": all_issues,
            "severity": overall,
            "recommendations": recommendations,
            "issue_count": len(all_issues),
            "health_score": self.get_health_score(all_issues),
        }

        # Write diagnosis to disk
        self._agi_dir.mkdir(parents=True, exist_ok=True)
        DIAGNOSIS_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

        # If critical, write to feedback-pending
        if overall == "critical":
            self._write_feedback_question(all_issues)

        return result

    def get_health_score(self, issues: List[Dict[str, Any]] | None = None) -> int:
        """Return 0-100 health score. 100 = perfect, 0 = broken."""
        if issues is None:
            # Re-run diagnosis silently
            issues = []
            issues.extend(self._check_memory_health())
            issues.extend(self._check_prediction_health())
            issues.extend(self._check_daemon_health())
            issues.extend(self._check_skill_health())
            issues.extend(self._check_filesystem_health())

        score = 100
        for issue in issues:
            sev = issue.get("severity", "info")
            if sev == "critical":
                score -= 25
            elif sev == "warning":
                score -= 10
            elif sev == "info":
                score -= 2
        return max(0, score)

    def _write_feedback_question(self, issues: List[Dict[str, Any]]) -> None:
        """Write a critical issue as a feedback question for the human."""
        critical_issues = [i for i in issues if i["severity"] == "critical"]
        if not critical_issues:
            return

        question_id = f"diag-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        details = "; ".join(i["message"] for i in critical_issues)
        recommendations = "; ".join(dict.fromkeys(i["recommendation"] for i in critical_issues))

        entry = {
            "question_id": question_id,
            "timestamp": _now_iso(),
            "source": "self-diagnosis",
            "question": f"Critical issues detected: {details}",
            "options": ["fix now", "ignore", "investigate later"],
            "recommendation": recommendations,
            "status": "pending",
            "response": None,
            "answered_at": None,
        }

        self._agi_dir.mkdir(parents=True, exist_ok=True)
        with open(FEEDBACK_PENDING_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def auto_fix(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Run auto-fix for known issues.
        Integrates with self-improve.py auto-fix.
        """
        # Import self-improve module
        improve_path = self._agi_dir / "self-improve.py"
        if not improve_path.exists():
            return {"status": "error", "message": "self-improve.py not found"}

        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("self_improve", improve_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            si = mod.SelfImprove()
            return si.auto_fix_all(dry_run=dry_run)
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def health_trend(self, history_path: Optional[Path] = None) -> Dict[str, Any]:
        """Analyze health score trend over time."""
        if history_path is None:
            history_path = self._root / "runtime" / "agi" / "diagnosis-history.jsonl"

        if not history_path.exists():
            return {"trend": "no_history", "scores": []}

        scores = []
        try:
            for line in history_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        scores.append(entry.get("health_score", 0))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass

        if len(scores) < 2:
            return {"trend": "insufficient_data", "scores": scores}

        recent = scores[-5:]
        older = scores[-10:-5] if len(scores) >= 10 else scores[:5]

        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)
        delta = recent_avg - older_avg

        if delta > 2:
            trend = "improving"
        elif delta < -2:
            trend = "declining"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "recent_avg": round(recent_avg, 1),
            "older_avg": round(older_avg, 1),
            "delta": round(delta, 1),
            "total_scores": len(scores),
        }


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python self-diagnosis.py <diagnose|score>")
        sys.exit(1)

    action = sys.argv[1]
    diag = SelfDiagnosis()

    if action == "diagnose":
        result = diag.diagnose()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if result["severity"] == "ok" else 1)

    elif action == "score":
        score = diag.get_health_score()
        print(json.dumps({"health_score": score, "timestamp": _now_iso()}, indent=2))
        sys.exit(0)

    else:
        print(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
