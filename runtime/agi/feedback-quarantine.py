"""
feedback-quarantine.py -- ECOSYSTEM Feedback Quarantine System

Prevents A2A / feedback injection from polluting MCR learning.

Checks:
  1. answer events must have corresponding ask_id / task_id / execution_id
  2. Answers without evidence chain -> quarantined
  3. Repeated templates, abnormal concentration, FAILED ratio spikes -> suspicious
  4. learn / agi-readiness excludes quarantined feedback

Usage:
    python feedback-quarantine.py scan
    python feedback-quarantine.py stats
    python feedback-quarantine.py inject-test <count>

No external dependencies -- stdlib only.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# -- Paths --
ECOSYSTEM_ROOT = Path(__file__).resolve().parent.parent.parent
AGI_DIR = ECOSYSTEM_ROOT / "runtime" / "agi"
RUNTIME_DIR = ECOSYSTEM_ROOT / "runtime"
HISTORY_PATH = AGI_DIR / "feedback-history.jsonl"
PENDING_PATH = AGI_DIR / "feedback-pending.jsonl"
EVENTS_PATH = RUNTIME_DIR / "events.jsonl"
QUARANTINE_PATH = AGI_DIR / "feedback-quarantine.jsonl"
QUARANTINE_STATS_PATH = AGI_DIR / "quarantine-stats.json"

# -- Thresholds --
FAILED_RATIO_SPIKE = 0.8       # >80% FAILED -> suspicious
TEMPLATE_REPEAT_MIN = 5        # same response >=5 times -> suspicious
CONCENTRATION_MIN = 10         # same source >=10 in short window -> suspicious
EVIDENCE_CHAIN_FIELDS = ["ask_id", "task_id", "execution_id", "question_id"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _write_jsonl(path: Path, entries: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(e, ensure_ascii=False) for e in entries]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _append_jsonl(path: Path, entry: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class FeedbackQuarantine:
    """Detects and quarantines injected or suspicious feedback."""

    def __init__(self, ecosystem_root: str | Path | None = None):
        self._root = Path(ecosystem_root) if ecosystem_root else ECOSYSTEM_ROOT
        self._agi_dir = self._root / "runtime" / "agi"
        self._history_path = self._agi_dir / "feedback-history.jsonl"
        self._pending_path = self._agi_dir / "feedback-pending.jsonl"
        self._events_path = self._root / "runtime" / "events.jsonl"
        self._quarantine_path = self._agi_dir / "feedback-quarantine.jsonl"
        self._stats_path = self._agi_dir / "quarantine-stats.json"

    # ------------------------------------------------------------------
    # Evidence chain check
    # ------------------------------------------------------------------

    def _has_evidence_chain(self, entry: Dict[str, Any],
                            valid_question_ids: set) -> Tuple[bool, str]:
        """Check if an answer entry has a valid evidence chain."""
        # Check 1: Is the source "manual" or "self-diagnosis"? (trusted)
        source = entry.get("source", "")
        if source in ("manual", "self-diagnosis", "human"):
            return True, f"trusted_source_{source}"

        # Check 2: Does it have a question_id that matches a pending question?
        qid = entry.get("question_id", "")
        if qid and qid in valid_question_ids:
            return True, "matched_pending_question"

        # Check 3: Does it have ask_id / task_id / execution_id?
        for field in EVIDENCE_CHAIN_FIELDS:
            if field == "question_id":
                continue  # question_id alone is not evidence
            val = entry.get(field)
            if val and isinstance(val, str) and len(val) > 0:
                return True, f"has_{field}"

        return False, "no_evidence_chain"

    # ------------------------------------------------------------------
    # Pattern detection
    # ------------------------------------------------------------------

    def _detect_repeated_templates(self, entries: List[Dict[str, Any]]) -> List[str]:
        """Detect repeated response templates."""
        responses = [e.get("response", "").strip().lower() for e in entries if e.get("response")]
        counter = Counter(responses)
        suspicious = []
        for response, count in counter.items():
            if count >= TEMPLATE_REPEAT_MIN and response:
                suspicious.append(f"template_repeat: '{response[:50]}' x{count}")
        return suspicious

    def _detect_concentration(self, entries: List[Dict[str, Any]]) -> List[str]:
        """Detect abnormal concentration from single source."""
        sources = [e.get("source", "unknown") for e in entries]
        counter = Counter(sources)
        suspicious = []
        for source, count in counter.items():
            if count >= CONCENTRATION_MIN:
                suspicious.append(f"concentration: source='{source}' x{count}")
        return suspicious

    def _detect_failed_spike(self, entries: List[Dict[str, Any]]) -> List[str]:
        """Detect FAILED ratio spikes in responses."""
        responses = [e.get("response", "").strip().upper() for e in entries if e.get("response")]
        if not responses:
            return []
        failed_count = sum(1 for r in responses if r in ("FAILED", "FAIL", "NO", "REJECT", "DENY"))
        ratio = failed_count / len(responses)
        if ratio >= FAILED_RATIO_SPIKE and len(responses) >= 5:
            return [f"failed_spike: {ratio:.0%} FAILED ({failed_count}/{len(responses)})"]
        return []

    # ------------------------------------------------------------------
    # Main scan
    # ------------------------------------------------------------------

    def scan(self) -> Dict[str, Any]:
        """Scan all feedback, quarantine suspicious entries."""
        # Load all feedback
        history = _load_jsonl(self._history_path)
        pending = _load_jsonl(self._pending_path)
        all_feedback = history + pending

        # Build set of valid question_ids from pending
        valid_question_ids = {e.get("question_id", "") for e in pending if e.get("question_id")}

        # Load existing quarantine to avoid re-quarantining
        existing_quarantine = _load_jsonl(self._quarantine_path)
        quarantined_ids = {e.get("question_id", "") for e in existing_quarantine}

        new_quarantined = []
        clean_feedback = []
        issues = []

        # Check each feedback entry
        for entry in all_feedback:
            qid = entry.get("question_id", "")

            # Skip already quarantined
            if qid in quarantined_ids:
                new_quarantined.append(entry)
                continue

            # Check evidence chain
            has_chain, reason = self._has_evidence_chain(entry, valid_question_ids)
            if not has_chain:
                entry["quarantine_reason"] = reason
                entry["quarantined_at"] = _now_iso()
                new_quarantined.append(entry)
                issues.append(f"quarantined: {qid} ({reason})")
                continue

            # Check for suspicious patterns (only on answered entries)
            if entry.get("status") == "answered":
                response = entry.get("response", "").strip().upper()
                if response in ("FAILED", "FAIL"):
                    # Count how many FAILED responses from same source
                    source = entry.get("source", "unknown")
                    same_source_failed = sum(
                        1 for e in all_feedback
                        if e.get("source") == source
                        and e.get("response", "").strip().upper() in ("FAILED", "FAIL")
                    )
                    if same_source_failed >= TEMPLATE_REPEAT_MIN:
                        entry["quarantine_reason"] = f"failed_template_from_{source}"
                        entry["quarantined_at"] = _now_iso()
                        new_quarantined.append(entry)
                        issues.append(f"suspicious: {qid} (failed template from {source})")
                        continue

            clean_feedback.append(entry)

        # Run pattern detection on all feedback
        template_issues = self._detect_repeated_templates(all_feedback)
        concentration_issues = self._detect_concentration(all_feedback)
        failed_issues = self._detect_failed_spike(all_feedback)
        issues.extend(template_issues)
        issues.extend(concentration_issues)
        issues.extend(failed_issues)

        # Write quarantine log
        if new_quarantined:
            _write_jsonl(self._quarantine_path, new_quarantined)

        # Compute stats
        stats = {
            "timestamp": _now_iso(),
            "total_feedback": len(all_feedback),
            "quarantined": len(new_quarantined),
            "clean": len(clean_feedback),
            "issues": issues,
            "quarantine_rate": len(new_quarantined) / len(all_feedback) if all_feedback else 0,
            "pattern_issues": {
                "template_repeats": len(template_issues),
                "concentration": len(concentration_issues),
                "failed_spikes": len(failed_issues),
            }
        }

        _save_json(self._stats_path, stats)
        return stats

    # ------------------------------------------------------------------
    # Clean feedback for learning
    # ------------------------------------------------------------------

    def get_clean_feedback(self) -> List[Dict[str, Any]]:
        """Return only non-quarantined feedback for learning."""
        history = _load_jsonl(self._history_path)
        quarantine = _load_jsonl(self._quarantine_path)
        quarantined_ids = {e.get("question_id", "") for e in quarantine}
        return [e for e in history if e.get("question_id", "") not in quarantined_ids]

    def get_quarantined(self) -> List[Dict[str, Any]]:
        """Return all quarantined entries."""
        return _load_jsonl(self._quarantine_path)

    def get_stats(self) -> Dict[str, Any]:
        """Return quarantine statistics."""
        stats = _load_json(self._stats_path)
        if not stats:
            stats = self.scan()
        return stats

    # ------------------------------------------------------------------
    # Inject test (for validation)
    # ------------------------------------------------------------------

    def inject_test(self, count: int = 1000) -> Dict[str, Any]:
        """Inject fake FAILED feedback and verify quarantine catches it."""
        print(f"[TEST] Injecting {count} fake 'all tasks FAILED' feedback entries...")

        # Inject into a temporary test file
        test_path = self._agi_dir / "feedback-test-injected.jsonl"
        injected = []
        for i in range(count):
            entry = {
                "question_id": f"injected-{i:06d}",
                "timestamp": _now_iso(),
                "source": "a2a-injection",
                "question": f"Task {i} result",
                "options": ["success", "failed"],
                "recommendation": "",
                "status": "answered",
                "response": "FAILED",
                "answered_at": _now_iso(),
            }
            injected.append(entry)

        _write_jsonl(test_path, injected)
        print(f"[TEST] Wrote {count} entries to {test_path}")

        # Now run quarantine scan on these
        # Temporarily add injected entries to history for scanning
        original_history = _load_jsonl(self._history_path)
        test_history = original_history + injected
        _write_jsonl(self._history_path, test_history)

        # Run scan
        stats = self.scan()
        print(f"[TEST] Scan result: {stats['quarantined']} quarantined, {stats['clean']} clean")

        # Restore original history
        _write_jsonl(self._history_path, original_history)

        # Clean up test file
        test_path.unlink(missing_ok=True)

        return {
            "injected": count,
            "quarantined": stats["quarantined"],
            "clean": stats["clean"],
            "quarantine_rate": stats["quarantine_rate"],
            "issues": stats["issues"][:10],  # first 10 issues
            "pass": stats["quarantined"] >= count * 0.9,  # at least 90% caught
        }


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python feedback-quarantine.py <scan|stats|inject-test> [count]")
        sys.exit(1)

    action = sys.argv[1]
    fq = FeedbackQuarantine()

    if action == "scan":
        stats = fq.scan()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        sys.exit(0 if stats["quarantined"] == 0 else 1)

    elif action == "stats":
        stats = fq.get_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    elif action == "inject-test":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
        result = fq.inject_test(count)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if result["pass"] else 1)

    else:
        print(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
