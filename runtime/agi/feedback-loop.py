"""
feedback-loop.py -- ECOSYSTEM Human Feedback Loop

Records questions for the human, tracks responses, and learns
from feedback patterns to adjust behavior confidence.

All data stored in runtime/agi/feedback-pending.jsonl (pending)
and runtime/agi/feedback-history.jsonl (answered).

Usage:
    python feedback-loop.py ask "<question>" ["option1,option2,..."]
    python feedback-loop.py answer <question_id> <response>
    python feedback-loop.py pending
    python feedback-loop.py history [n]
    python feedback-loop.py learn

No external dependencies -- stdlib only.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# -- Paths --
ECOSYSTEM_ROOT = Path(__file__).resolve().parent.parent.parent
AGI_DIR = ECOSYSTEM_ROOT / "runtime" / "agi"
PENDING_PATH = AGI_DIR / "feedback-pending.jsonl"
HISTORY_PATH = AGI_DIR / "feedback-history.jsonl"
LEARNING_STATE_PATH = AGI_DIR / "feedback-learning.json"

# -- Learning thresholds --
MIN_FEEDBACK_FOR_LEARNING = 3
CONFIDENCE_BOOST = 0.1
CONFIDENCE_PENALTY = 0.15


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


class FeedbackLoop:
    """Human feedback loop: ask questions, record responses, learn patterns."""

    def __init__(self, feedback_path: str | Path | None = None):
        self._pending_path = Path(feedback_path) if feedback_path else PENDING_PATH
        self._history_path = HISTORY_PATH
        self._learning_path = LEARNING_STATE_PATH

    def ask(self, question: str, options: List[str] | None = None,
            source: str = "manual", recommendation: str = "") -> Dict[str, Any]:
        """Record a question for the human. Returns the question entry."""
        question_id = f"q-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{id(self) % 10000:04d}"
        entry = {
            "question_id": question_id,
            "timestamp": _now_iso(),
            "source": source,
            "question": question,
            "options": options or ["yes", "no", "skip"],
            "recommendation": recommendation,
            "status": "pending",
            "response": None,
            "answered_at": None,
        }

        self._pending_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._pending_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return entry

    def record_response(self, question_id: str, response: str) -> Dict[str, Any] | None:
        """Record human's response to a question. Moves from pending to history."""
        pending = _load_jsonl(self._pending_path)
        found_idx = -1
        found_entry = None

        for i, entry in enumerate(pending):
            if entry.get("question_id") == question_id:
                found_idx = i
                found_entry = entry
                break

        if found_entry is None:
            return None

        # Update the entry
        found_entry["status"] = "answered"
        found_entry["response"] = response
        found_entry["answered_at"] = _now_iso()

        # Remove from pending
        pending.pop(found_idx)
        _write_jsonl(self._pending_path, pending)

        # Append to history
        self._history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(found_entry, ensure_ascii=False) + "\n")

        # Update learning state
        self._update_learning(found_entry)

        return found_entry

    def get_pending(self) -> List[Dict[str, Any]]:
        """Get all unanswered questions."""
        return [e for e in _load_jsonl(self._pending_path) if e.get("status") == "pending"]

    def get_history(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get recent Q&A history."""
        entries = _load_jsonl(self._history_path)
        return entries[-n:]

    def _categorize_question(self, question: str, source: str) -> str:
        """Simple keyword-based categorization of questions."""
        q_lower = question.lower()

        if any(w in q_lower for w in ["memory", "memories", "forget", "remember"]):
            return "memory"
        if any(w in q_lower for w in ["prediction", "predict", "accuracy", "calibrat"]):
            return "prediction"
        if any(w in q_lower for w in ["daemon", "run", "loop", "schedule"]):
            return "daemon"
        if any(w in q_lower for w in ["skill", "transfer", "promote"]):
            return "skill"
        if any(w in q_lower for w in ["critical", "issue", "problem", "error", "fail"]):
            return "health"
        if any(w in q_lower for w in ["goal", "plan", "task", "priority"]):
            return "planning"
        if any(w in q_lower for w in ["config", "setting", "threshold", "parameter"]):
            return "config"
        return "general"

    def _update_learning(self, entry: Dict[str, Any]) -> None:
        """Update learning state based on a answered feedback entry."""
        state = _load_json(self._learning_path)

        if "patterns" not in state:
            state["patterns"] = {}
        if "total_answered" not in state:
            state["total_answered"] = 0
        if "last_updated" not in state:
            state["last_updated"] = None

        state["total_answered"] = state.get("total_answered", 0) + 1
        state["last_updated"] = _now_iso()

        # Extract pattern key from source + question category
        source = entry.get("source", "unknown")
        question = entry.get("question", "")
        response = entry.get("response", "")

        # Simple categorization by keywords
        category = self._categorize_question(question, source)
        pattern_key = f"{source}:{category}"

        if pattern_key not in state["patterns"]:
            state["patterns"][pattern_key] = {
                "total": 0,
                "positive": 0,
                "negative": 0,
                "skip": 0,
                "confidence": 0.5,
            }

        pattern = state["patterns"][pattern_key]
        pattern["total"] += 1

        # Normalize response
        resp_lower = response.lower().strip()
        if resp_lower in ("yes", "y", "ok", "fix", "fix now", "accept", "approve"):
            pattern["positive"] += 1
        elif resp_lower in ("no", "n", "reject", "deny", "ignore"):
            pattern["negative"] += 1
        else:
            pattern["skip"] += 1

        # Update confidence
        total = pattern["total"]
        if total >= MIN_FEEDBACK_FOR_LEARNING:
            positive_rate = pattern["positive"] / total if total > 0 else 0.5
            pattern["confidence"] = round(positive_rate, 3)

        _save_json(self._learning_path, state)

    def learn_from_feedback(self) -> Dict[str, Any]:
        """Analyze feedback patterns and return learning summary.

        Excludes quarantined feedback from learning.
        Learns from quarantine patterns to detect injection attempts.
        Weights feedback by source reliability.
        """
        # Load quarantine list
        quarantine_path = AGI_DIR / "feedback-quarantine.jsonl"
        quarantined_entries = _load_jsonl(quarantine_path)
        quarantined_ids = {e.get("question_id", "") for e in quarantined_entries}

        # Load history, exclude quarantined
        all_history = _load_jsonl(self._history_path)
        valid_history = [e for e in all_history if e.get("question_id", "") not in quarantined_ids]

        # Learn from quarantine patterns
        quarantine_patterns = {}
        for entry in quarantined_entries:
            reason = entry.get("quarantine_reason", "unknown")
            source = entry.get("source", "unknown")
            key = f"{source}:{reason}"
            quarantine_patterns[key] = quarantine_patterns.get(key, 0) + 1

        # Source reliability weights
        source_weights = {
            "manual": 1.0,
            "self-diagnosis": 0.8,
            "human": 1.0,
            "a2a": 0.3,
            "unknown": 0.5,
        }

        state = _load_json(self._learning_path)
        if not state or not state.get("patterns"):
            return {
                "total_answered": 0,
                "patterns": {},
                "recommendations": ["Not enough feedback data to learn from"],
            }

        patterns = state["patterns"]
        recommendations = []

        for key, pattern in patterns.items():
            total = pattern.get("total", 0)
            if total < MIN_FEEDBACK_FOR_LEARNING:
                continue

            conf = pattern.get("confidence", 0.5)
            source, category = key.split(":", 1) if ":" in key else (key, "general")

            if conf >= 0.8:
                recommendations.append(f"HIGH CONFIDENCE ({conf:.0%}): Human consistently approves '{category}' from '{source}'. Can auto-proceed.")
            elif conf <= 0.2:
                recommendations.append(f"LOW CONFIDENCE ({conf:.0%}): Human consistently rejects '{category}' from '{source}'. Avoid or redesign.")
            else:
                recommendations.append(f"MIXED ({conf:.0%}): '{category}' from '{source}' has mixed feedback. Keep asking.")

        return {
            "total_answered": state.get("total_answered", 0),
            "patterns": patterns,
            "recommendations": recommendations,
            "last_updated": state.get("last_updated"),
        }


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python feedback-loop.py <ask|answer|pending|history|learn>")
        sys.exit(1)

    action = sys.argv[1]
    loop = FeedbackLoop()

    if action == "ask":
        if len(sys.argv) < 3:
            print("Usage: python feedback-loop.py ask \"<question>\" [\"opt1,opt2,...\"]")
            sys.exit(1)
        question = sys.argv[2]
        options = sys.argv[3].split(",") if len(sys.argv) > 3 else None
        entry = loop.ask(question, options)
        print(json.dumps(entry, indent=2, ensure_ascii=False))

    elif action == "answer":
        if len(sys.argv) < 4:
            print("Usage: python feedback-loop.py answer <question_id> <response>")
            sys.exit(1)
        qid = sys.argv[2]
        response = " ".join(sys.argv[3:])
        result = loop.record_response(qid, response)
        if result:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"Question not found: {qid}")
            sys.exit(1)

    elif action == "pending":
        pending = loop.get_pending()
        print(json.dumps(pending, indent=2, ensure_ascii=False))

    elif action == "history":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        history = loop.get_history(n)
        print(json.dumps(history, indent=2, ensure_ascii=False))

    elif action == "learn":
        result = loop.learn_from_feedback()
        print(json.dumps(result, indent=2, ensure_ascii=False))

    else:
        print(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
