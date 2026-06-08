"""
auth_audit.py -- MCR Authorization Audit Layer

Every external operation has an authorization record:
  - Who approved it
  - What was approved
  - What evidence supports it
  - When it expires
  - Can it be revoked

Supports emergency operations with post-hoc audit.

Usage:
    python auth_audit.py record "network_scan" "user" "authorized target: 127.0.0.1"
    python auth_audit.py check "network_scan"
    python auth_audit.py revoke "network_scan" "no longer needed"
    python auth_audit.py report
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

ECOSYSTEM_ROOT = Path(__file__).resolve().parent.parent.parent
AGI_DIR = ECOSYSTEM_ROOT / "runtime" / "agi"
AUTH_LOG = AGI_DIR / "auth-audit-log.jsonl"
AUTH_STATE = AGI_DIR / "auth-audit-state.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


class AuthAudit:
    """Authorization audit layer for external operations."""

    def __init__(self, ecosystem_root: str | Path | None = None):
        self._root = Path(ecosystem_root) if ecosystem_root else ECOSYSTEM_ROOT
        self._log_path = self._root / "runtime" / "agi" / "auth-audit-log.jsonl"
        self._state_path = self._root / "runtime" / "agi" / "auth-audit-state.json"
        self._state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        state = _load_json(self._state_path)
        if not state:
            state = {"authorizations": {}, "revocations": []}
        return state

    def _save_state(self) -> None:
        _save_json(self._state_path, self._state)

    def record(self, operation: str, approver: str, evidence: str,
               expires_hours: Optional[int] = None,
               emergency: bool = False) -> Dict[str, Any]:
        """
        Record an authorization.

        Args:
            operation: What operation is being authorized
            approver: Who approved it (user, admin, system)
            evidence: Evidence supporting the authorization
            expires_hours: Hours until authorization expires (None = no expiry)
            emergency: If True, this is a post-hoc authorization
        """
        now = datetime.now(timezone.utc)
        expires_at = None
        if expires_hours:
            expires_at = (now + timedelta(hours=expires_hours)).isoformat()

        auth_id = f"auth-{now.strftime('%Y%m%d-%H%M%S')}-{hash(operation) % 10000:04d}"

        authorization = {
            "auth_id": auth_id,
            "operation": operation,
            "approver": approver,
            "evidence": evidence,
            "authorized_at": _now_iso(),
            "expires_at": expires_at,
            "emergency": emergency,
            "revoked": False,
            "revoked_at": None,
            "revoke_reason": None,
        }

        # Store in state
        self._state["authorizations"][operation] = authorization
        self._save_state()

        # Log
        _append_jsonl(self._log_path, {"type": "authorization", **authorization})

        return authorization

    def check(self, operation: str) -> Dict[str, Any]:
        """
        Check if an operation is authorized.

        Returns: {authorized, auth_id, approver, evidence, expired, revoked}
        """
        auth = self._state["authorizations"].get(operation)

        if not auth:
            return {
                "authorized": False,
                "operation": operation,
                "reason": "no authorization found",
            }

        # Check if revoked
        if auth.get("revoked"):
            return {
                "authorized": False,
                "operation": operation,
                "auth_id": auth["auth_id"],
                "reason": f"authorization revoked: {auth.get('revoke_reason', 'unknown')}",
            }

        # Check if expired
        if auth.get("expires_at"):
            expires = datetime.fromisoformat(auth["expires_at"])
            if datetime.now(timezone.utc) > expires:
                return {
                    "authorized": False,
                    "operation": operation,
                    "auth_id": auth["auth_id"],
                    "reason": "authorization expired",
                }

        return {
            "authorized": True,
            "operation": operation,
            "auth_id": auth["auth_id"],
            "approver": auth["approver"],
            "evidence": auth["evidence"],
            "emergency": auth.get("emergency", False),
            "expires_at": auth.get("expires_at"),
        }

    def revoke(self, operation: str, reason: str = "") -> Dict[str, Any]:
        """Revoke an authorization."""
        auth = self._state["authorizations"].get(operation)

        if not auth:
            return {"operation": operation, "error": "no authorization found"}

        auth["revoked"] = True
        auth["revoked_at"] = _now_iso()
        auth["revoke_reason"] = reason
        self._save_state()

        revocation = {
            "type": "revocation",
            "operation": operation,
            "auth_id": auth["auth_id"],
            "reason": reason,
            "revoked_at": _now_iso(),
        }
        _append_jsonl(self._log_path, revocation)

        return revocation

    def emergency_record(self, operation: str, reason: str) -> Dict[str, Any]:
        """
        Record an emergency authorization (post-hoc).
        Used when action was taken without prior approval.
        """
        return self.record(
            operation=operation,
            approver="emergency",
            evidence=f"Emergency action taken: {reason}",
            emergency=True,
        )

    def list_active(self) -> List[Dict[str, Any]]:
        """List all active (non-expired, non-revoked) authorizations."""
        active = []
        for op, auth in self._state["authorizations"].items():
            if auth.get("revoked"):
                continue
            if auth.get("expires_at"):
                expires = datetime.fromisoformat(auth["expires_at"])
                if datetime.now(timezone.utc) > expires:
                    continue
            active.append({"operation": op, **auth})
        return active

    def generate_report(self) -> Dict[str, Any]:
        """Generate an audit report."""
        all_auths = self._state["authorizations"]
        active = self.list_active()
        revoked = [a for a in all_auths.values() if a.get("revoked")]
        emergency = [a for a in all_auths.values() if a.get("emergency")]

        return {
            "total_authorizations": len(all_auths),
            "active": len(active),
            "revoked": len(revoked),
            "emergency": len(emergency),
            "active_authorizations": active,
            "revoked_authorizations": revoked,
            "emergency_authorizations": emergency,
            "generated_at": _now_iso(),
        }


# ============================================================
# CLI
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python auth_audit.py <record|check|revoke|emergency|list|report> [args]")
        sys.exit(1)

    action = sys.argv[1]
    audit = AuthAudit()

    if action == "record":
        if len(sys.argv) < 5:
            print("Usage: python auth_audit.py record <operation> <approver> <evidence> [expires_hours]")
            sys.exit(1)
        expires = int(sys.argv[5]) if len(sys.argv) > 5 else None
        result = audit.record(sys.argv[2], sys.argv[3], sys.argv[4], expires)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif action == "check":
        if len(sys.argv) < 3:
            print("Usage: python auth_audit.py check <operation>")
            sys.exit(1)
        result = audit.check(sys.argv[2])
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif action == "revoke":
        if len(sys.argv) < 3:
            print("Usage: python auth_audit.py revoke <operation> [reason]")
            sys.exit(1)
        reason = sys.argv[3] if len(sys.argv) > 3 else ""
        result = audit.revoke(sys.argv[2], reason)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif action == "emergency":
        if len(sys.argv) < 4:
            print("Usage: python auth_audit.py emergency <operation> <reason>")
            sys.exit(1)
        result = audit.emergency_record(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif action == "list":
        active = audit.list_active()
        print(json.dumps(active, indent=2, ensure_ascii=False))

    elif action == "report":
        report = audit.generate_report()
        print(json.dumps(report, indent=2, ensure_ascii=False))

    else:
        print(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
