"""
decision_boundary.py -- MCR Decision Boundary System

Three channels:
  AUTONOMOUS - system acts without human approval
  ADVISORY   - system acts but notifies human
  GATE       - system must get human approval before acting

16 rules covering common MCR operations.
Unknown operations default to GATE (safe fallback).

Usage:
    python decision_boundary.py check "memory_search"
    python decision_boundary.py check "network_scan"
    python decision_boundary.py list
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ECOSYSTEM_ROOT = Path(__file__).resolve().parent.parent.parent
AGI_DIR = ECOSYSTEM_ROOT / "runtime" / "agi"
BOUNDARY_LOG = AGI_DIR / "decision-boundary-log.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, entry: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ============================================================
# Decision Channels
# ============================================================

CHANNEL_AUTONOMOUS = "AUTONOMOUS"
CHANNEL_ADVISORY = "ADVISORY"
CHANNEL_GATE = "GATE"


# ============================================================
# Decision Rules (16 rules)
# ============================================================

DECISION_RULES = [
    # AUTONOMOUS: safe, read-only, internal operations
    {
        "rule_id": "R001",
        "action_pattern": "memory_search",
        "channel": CHANNEL_AUTONOMOUS,
        "reason": "Internal memory search, no side effects",
    },
    {
        "rule_id": "R002",
        "action_pattern": "memory_read",
        "channel": CHANNEL_AUTONOMOUS,
        "reason": "Internal memory read, no side effects",
    },
    {
        "rule_id": "R003",
        "action_pattern": "status_check",
        "channel": CHANNEL_AUTONOMOUS,
        "reason": "Internal status check, no side effects",
    },
    {
        "rule_id": "R004",
        "action_pattern": "pattern_detect",
        "channel": CHANNEL_AUTONOMOUS,
        "reason": "Internal pattern detection, no side effects",
    },
    {
        "rule_id": "R005",
        "action_pattern": "reflection",
        "channel": CHANNEL_AUTONOMOUS,
        "reason": "Internal reflection, no side effects",
    },
    {
        "rule_id": "R006",
        "action_pattern": "health_check",
        "channel": CHANNEL_AUTONOMOUS,
        "reason": "Internal health check, no side effects",
    },
    {
        "rule_id": "R007",
        "action_pattern": "prediction_review",
        "channel": CHANNEL_AUTONOMOUS,
        "reason": "Internal prediction review, no side effects",
    },
    {
        "rule_id": "R008",
        "action_pattern": "concept_resolve",
        "channel": CHANNEL_AUTONOMOUS,
        "reason": "Internal concept resolution, no side effects",
    },

    # ADVISORY: acts but notifies human
    {
        "rule_id": "R009",
        "action_pattern": "auto_fix",
        "channel": CHANNEL_ADVISORY,
        "reason": "Auto-fix applies changes, human should be notified",
    },
    {
        "rule_id": "R010",
        "action_pattern": "memory_write",
        "channel": CHANNEL_ADVISORY,
        "reason": "Memory write modifies state, notify human",
    },
    {
        "rule_id": "R011",
        "action_pattern": "goal_propose",
        "channel": CHANNEL_ADVISORY,
        "reason": "Goal proposal, human should review",
    },
    {
        "rule_id": "R012",
        "action_pattern": "report_generate",
        "channel": CHANNEL_ADVISORY,
        "reason": "Report generation, notify human",
    },
    {
        "rule_id": "R013",
        "action_pattern": "skill_promote",
        "channel": CHANNEL_ADVISORY,
        "reason": "Skill promotion, human should review",
    },

    # GATE: must get human approval
    {
        "rule_id": "R014",
        "action_pattern": "network_scan",
        "channel": CHANNEL_GATE,
        "reason": "External scanning requires explicit authorization",
    },
    {
        "rule_id": "R015",
        "action_pattern": "external_command",
        "channel": CHANNEL_GATE,
        "reason": "External command execution requires approval",
    },
    {
        "rule_id": "R016",
        "action_pattern": "file_delete",
        "channel": CHANNEL_GATE,
        "reason": "File deletion requires approval",
    },
]


class DecisionBoundary:
    """Decision boundary system with three channels."""

    def __init__(self, ecosystem_root: str | Path | None = None):
        self._root = Path(ecosystem_root) if ecosystem_root else ECOSYSTEM_ROOT
        self._log_path = self._root / "runtime" / "agi" / "decision-boundary-log.jsonl"
        self._rules = DECISION_RULES.copy()
        self._approvals: Dict[str, Dict] = {}  # pending approvals

    def check(self, action: str) -> Dict[str, Any]:
        """
        Check which channel an action belongs to.

        Returns: {channel, rule_id, reason, needs_approval}
        """
        # Search for matching rule
        for rule in self._rules:
            if rule["action_pattern"] in action.lower() or action.lower() in rule["action_pattern"]:
                result = {
                    "action": action,
                    "channel": rule["channel"],
                    "rule_id": rule["rule_id"],
                    "reason": rule["reason"],
                    "needs_approval": rule["channel"] == CHANNEL_GATE,
                    "notifies_human": rule["channel"] == CHANNEL_ADVISORY,
                    "checked_at": _now_iso(),
                }
                _append_jsonl(self._log_path, result)
                return result

        # Unknown action: default to GATE (safe fallback)
        result = {
            "action": action,
            "channel": CHANNEL_GATE,
            "rule_id": "DEFAULT",
            "reason": "Unknown action, defaulting to GATE for safety",
            "needs_approval": True,
            "notifies_human": False,
            "checked_at": _now_iso(),
        }
        _append_jsonl(self._log_path, result)
        return result

    def approve(self, action: str, approver: str, evidence: str = "") -> Dict[str, Any]:
        """Record human approval for a GATE action."""
        approval = {
            "action": action,
            "approver": approver,
            "evidence": evidence,
            "approved_at": _now_iso(),
            "expires_at": None,  # TODO: add expiry
        }
        self._approvals[action] = approval
        _append_jsonl(self._log_path, {"type": "approval", **approval})
        return approval

    def revoke(self, action: str, reason: str = "") -> Dict[str, Any]:
        """Revoke a previous approval."""
        if action in self._approvals:
            del self._approvals[action]
            result = {"action": action, "revoked_at": _now_iso(), "reason": reason}
            _append_jsonl(self._log_path, {"type": "revocation", **result})
            return result
        return {"action": action, "error": "no approval found"}

    def is_approved(self, action: str) -> bool:
        """Check if an action has been approved."""
        return action in self._approvals

    def list_rules(self) -> List[Dict[str, Any]]:
        """List all decision rules."""
        return self._rules

    def list_approvals(self) -> Dict[str, Any]:
        """List all pending approvals."""
        return self._approvals


# ============================================================
# CLI
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python decision_boundary.py <check|approve|revoke|list|approvals> [args]")
        sys.exit(1)

    action = sys.argv[1]
    db = DecisionBoundary()

    if action == "check":
        if len(sys.argv) < 3:
            print("Usage: python decision_boundary.py check <action>")
            sys.exit(1)
        result = db.check(sys.argv[2])
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif action == "approve":
        if len(sys.argv) < 4:
            print("Usage: python decision_boundary.py approve <action> <approver> [evidence]")
            sys.exit(1)
        evidence = sys.argv[4] if len(sys.argv) > 4 else ""
        result = db.approve(sys.argv[2], sys.argv[3], evidence)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif action == "revoke":
        if len(sys.argv) < 3:
            print("Usage: python decision_boundary.py revoke <action> [reason]")
            sys.exit(1)
        reason = sys.argv[3] if len(sys.argv) > 3 else ""
        result = db.revoke(sys.argv[2], reason)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif action == "list":
        rules = db.list_rules()
        print(json.dumps(rules, indent=2, ensure_ascii=False))

    elif action == "approvals":
        approvals = db.list_approvals()
        print(json.dumps(approvals, indent=2, ensure_ascii=False))

    else:
        print(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
