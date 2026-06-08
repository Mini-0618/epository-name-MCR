"""
event_classifier.py -- MCR Event Classifier

Classifies events into four types:
  OBSERVATION - something was observed
  DECISION    - a decision was made
  ACTION      - an action was taken
  OUTCOME     - an action produced a result

Each run automatically forms causal chain receipts.
Compression priority: observations first, outcomes last.

Usage:
    python event_classifier.py classify '{"type": "memory_search", "query": "test"}'
    python event_classifier.py receipt <run_id>
    python event_classifier.py chain <run_id>
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ECOSYSTEM_ROOT = Path(__file__).resolve().parent.parent.parent
AGI_DIR = ECOSYSTEM_ROOT / "runtime" / "agi"
EVENTS_PATH = ECOSYSTEM_ROOT / "runtime" / "events.jsonl"
CLASSIFIER_LOG = AGI_DIR / "event-classifier-log.jsonl"
RECEIPTS_PATH = AGI_DIR / "causal-receipts.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, entry: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


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


# ============================================================
# Event Type Classification
# ============================================================

# Patterns for each event type
EVENT_TYPE_PATTERNS = {
    "OBSERVATION": [
        "observe", "detect", "discover", "find", "scan", "check",
        "monitor", "watch", "read", "query", "search", "lookup",
    ],
    "DECISION": [
        "decide", "choose", "select", "plan", "propose", "suggest",
        "recommend", "evaluate", "assess", "judge", "gate",
    ],
    "ACTION": [
        "execute", "run", "apply", "write", "create", "delete",
        "modify", "update", "install", "deploy", "send", "post",
        "fix", "repair", "promote",
    ],
    "OUTCOME": [
        "result", "output", "response", "complete", "finish",
        "success", "fail", "error", "pass", "blocked",
    ],
}


class EventClassifier:
    """Classifies events and builds causal chain receipts."""

    def __init__(self, ecosystem_root: str | Path | None = None):
        self._root = Path(ecosystem_root) if ecosystem_root else ECOSYSTEM_ROOT
        self._events_path = self._root / "runtime" / "events.jsonl"
        self._receipts_path = self._root / "runtime" / "agi" / "causal-receipts.jsonl"
        self._log_path = self._root / "runtime" / "agi" / "event-classifier-log.jsonl"

    def classify(self, event: Dict[str, Any]) -> str:
        """
        Classify an event into one of four types.

        Returns: OBSERVATION, DECISION, ACTION, or OUTCOME
        """
        # Check event_type field first
        event_type = event.get("event_type", "").lower()
        event_name = event.get("type", "").lower()
        combined = f"{event_type} {event_name}"

        for etype, patterns in EVENT_TYPE_PATTERNS.items():
            for pattern in patterns:
                if pattern in combined:
                    return etype

        # Check payload for clues
        payload = event.get("payload", {})
        if isinstance(payload, dict):
            status = payload.get("status", "").lower()
            if status in ("success", "fail", "error", "pass", "blocked"):
                return "OUTCOME"
            decision = payload.get("decision", "").lower()
            if decision in ("allow", "deny", "block", "pass", "caution"):
                return "DECISION"

        # Default: OBSERVATION (safest assumption)
        return "OBSERVATION"

    def classify_all(self) -> Dict[str, List[Dict]]:
        """Classify all events in events.jsonl."""
        events = _load_jsonl(self._events_path)
        classified = {
            "OBSERVATION": [],
            "DECISION": [],
            "ACTION": [],
            "OUTCOME": [],
        }

        for event in events:
            etype = self.classify(event)
            event["_classified_type"] = etype
            classified[etype].append(event)

        return classified

    def build_receipt(self, run_id: str) -> Dict[str, Any]:
        """
        Build a causal chain receipt for a specific run.

        Receipt format:
        {
            "run_id": "...",
            "chain": [
                {"type": "OBSERVATION", "event": {...}, "timestamp": "..."},
                {"type": "DECISION", "event": {...}, "timestamp": "..."},
                {"type": "ACTION", "event": {...}, "timestamp": "..."},
                {"type": "OUTCOME", "event": {...}, "timestamp": "..."},
            ],
            "complete": true/false,
        }
        """
        events = _load_jsonl(self._events_path)

        # Filter events for this run
        run_events = [e for e in events if e.get("run_id") == run_id or
                      e.get("payload", {}).get("run_id") == run_id]

        if not run_events:
            # Try matching by task_id
            run_events = [e for e in events if e.get("task_id") == run_id or
                          e.get("payload", {}).get("task_id") == run_id]

        # Classify each event
        chain = []
        for event in run_events:
            etype = self.classify(event)
            chain.append({
                "type": etype,
                "event_id": event.get("event_id", ""),
                "event_type": event.get("event_type", ""),
                "timestamp": event.get("timestamp", ""),
                "payload_summary": str(event.get("payload", {}))[:200],
            })

        # Sort by timestamp
        chain.sort(key=lambda x: x.get("timestamp", ""))

        # Check completeness
        has_observation = any(c["type"] == "OBSERVATION" for c in chain)
        has_decision = any(c["type"] == "DECISION" for c in chain)
        has_action = any(c["type"] == "ACTION" for c in chain)
        has_outcome = any(c["type"] == "OUTCOME" for c in chain)

        receipt = {
            "run_id": run_id,
            "chain": chain,
            "chain_length": len(chain),
            "complete": has_observation and has_decision and has_action and has_outcome,
            "has_observation": has_observation,
            "has_decision": has_decision,
            "has_action": has_action,
            "has_outcome": has_outcome,
            "created_at": _now_iso(),
        }

        _append_jsonl(self._receipts_path, receipt)
        return receipt

    def get_compression_priority(self, event_type: str) -> int:
        """
        Get compression priority for an event type.
        Lower number = compress first.

        OBSERVATION (1) -> DECISION (2) -> ACTION (3) -> OUTCOME (4)
        """
        priority = {
            "OBSERVATION": 1,
            "DECISION": 2,
            "ACTION": 3,
            "OUTCOME": 4,
        }
        return priority.get(event_type, 5)

    def get_stats(self) -> Dict[str, Any]:
        """Get classification statistics."""
        classified = self.classify_all()
        return {
            "total_events": sum(len(v) for v in classified.values()),
            "observations": len(classified["OBSERVATION"]),
            "decisions": len(classified["DECISION"]),
            "actions": len(classified["ACTION"]),
            "outcomes": len(classified["OUTCOME"]),
        }


# ============================================================
# CLI
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python event_classifier.py <classify|receipt|chain|stats> [args]")
        sys.exit(1)

    action = sys.argv[1]
    ec = EventClassifier()

    if action == "classify":
        if len(sys.argv) < 3:
            print("Usage: python event_classifier.py classify '<event_json>'")
            sys.exit(1)
        try:
            event = json.loads(sys.argv[2])
            result = ec.classify(event)
            print(json.dumps({"event": event, "classified_as": result}, indent=2))
        except json.JSONDecodeError:
            print("Invalid JSON")
            sys.exit(1)

    elif action == "receipt":
        if len(sys.argv) < 3:
            print("Usage: python event_classifier.py receipt <run_id>")
            sys.exit(1)
        receipt = ec.build_receipt(sys.argv[2])
        print(json.dumps(receipt, indent=2, ensure_ascii=False))

    elif action == "chain":
        if len(sys.argv) < 3:
            print("Usage: python event_classifier.py chain <run_id>")
            sys.exit(1)
        receipt = ec.build_receipt(sys.argv[2])
        print(f"Causal Chain for {sys.argv[2]}:")
        print(f"  Complete: {receipt['complete']}")
        print(f"  Length: {receipt['chain_length']}")
        for item in receipt["chain"]:
            print(f"  [{item['type']:12s}] {item['event_type']} @ {item['timestamp']}")

    elif action == "stats":
        stats = ec.get_stats()
        print(json.dumps(stats, indent=2))

    else:
        print(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
