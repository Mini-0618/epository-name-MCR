"""
session_manager.py -- ECOSYSTEM Session Lifecycle Manager

Simplified session tracking for daemon processes.
Writes session events to sessions.jsonl for history and diagnostics.

No external dependencies. Thread-safe.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from threading import Lock
from typing import Optional


STALE_THRESHOLD_SECONDS = 30 * 60  # 30 minutes


class SessionManager:
    """
    Track daemon session lifecycle: start, heartbeat, stop.

    Each session event is appended to sessions.jsonl.
    The latest "start" entry without a matching "stop" is the active session.

    Args:
        session_path: Path to sessions.jsonl file.
    """

    def __init__(self, session_path: str):
        self._path = Path(session_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._current: Optional[dict] = None
        # Try to recover an active session on init
        self._recover_active()

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self, session_id: Optional[str] = None) -> dict:
        """
        Start a new session. If one is already active, stop it first.

        Returns the session record.
        """
        with self._lock:
            if self._current is not None:
                self._write_event("stop", reason="superseded")

            sid = session_id or f"ses-{uuid.uuid4().hex[:8]}"
            now = time.time()
            self._current = {
                "session_id": sid,
                "started_at": now,
                "started_at_iso": _iso(now),
                "last_heartbeat": now,
                "status": "active",
            }
            self._write_event("start")
            return _copy(self._current)

    def heartbeat(self) -> Optional[dict]:
        """
        Update heartbeat timestamp for the active session.

        Returns updated session info, or None if no active session.
        """
        with self._lock:
            if self._current is None:
                return None
            now = time.time()
            self._current["last_heartbeat"] = now
            self._write_event("heartbeat")
            return _copy(self._current)

    def stop(self, reason: str = "normal") -> Optional[dict]:
        """
        Stop the current session.

        Returns the final session record, or None if no active session.
        """
        with self._lock:
            if self._current is None:
                return None
            self._current["status"] = "stopped"
            self._current["stopped_at"] = time.time()
            self._current["stop_reason"] = reason
            self._write_event("stop", reason=reason)
            result = _copy(self._current)
            self._current = None
            return result

    def is_alive(self) -> bool:
        """
        Check if the current session is alive (has heartbeat within threshold).

        Returns False if no active session or heartbeat is stale.
        """
        with self._lock:
            if self._current is None:
                return False
            elapsed = time.time() - self._current["last_heartbeat"]
            return elapsed < STALE_THRESHOLD_SECONDS

    def get_current(self) -> Optional[dict]:
        """Return a copy of the current session info, or None."""
        with self._lock:
            if self._current is None:
                return None
            d = _copy(self._current)
            d["alive"] = (time.time() - self._current["last_heartbeat"]) < STALE_THRESHOLD_SECONDS
            d["elapsed_seconds"] = round(time.time() - self._current["started_at"], 1)
            d["heartbeat_age_seconds"] = round(time.time() - self._current["last_heartbeat"], 1)
            return d

    def get_history(self, n: int = 10) -> list[dict]:
        """
        Return the last N session records from the log.

        Each record has: session_id, event, timestamp, plus any extra fields.
        """
        events = self._read_all()
        # Group by session_id, pick unique sessions, return last n
        seen = {}
        for e in events:
            sid = e.get("session_id", "")
            if e.get("event") == "start":
                seen[sid] = e
            elif e.get("event") == "stop" and sid in seen:
                seen[sid]["ended_at_iso"] = e.get("timestamp_iso")
                seen[sid]["stop_reason"] = e.get("reason", "unknown")
                seen[sid]["status"] = "stopped"
            elif e.get("event") == "heartbeat" and sid in seen:
                seen[sid]["last_heartbeat_iso"] = e.get("timestamp_iso")

        sessions = sorted(seen.values(), key=lambda x: x.get("timestamp", 0), reverse=True)
        return sessions[:n]

    # ── Internal ──────────────────────────────────────────────────────────────

    def _write_event(self, event: str, reason: str = "") -> None:
        """Append an event to sessions.jsonl. Caller must hold _lock."""
        now = time.time()
        record = {
            "session_id": self._current["session_id"],
            "event": event,
            "timestamp": now,
            "timestamp_iso": _iso(now),
        }
        if event == "start":
            record["started_at"] = self._current["started_at"]
        elif event == "heartbeat":
            pass  # timestamp is enough
        elif event == "stop":
            record["reason"] = reason
            record["duration_seconds"] = round(now - self._current["started_at"], 1)

        line = json.dumps(record, ensure_ascii=False)
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _read_all(self) -> list[dict]:
        """Read all events from sessions.jsonl."""
        if not self._path.exists():
            return []
        events = []
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return events

    def _recover_active(self) -> None:
        """On init, check if there's an active (un-stopped) session."""
        events = self._read_all()
        # Walk events in reverse to find last start without stop
        active_sid = None
        for e in reversed(events):
            if e.get("event") == "stop":
                break
            if e.get("event") == "start":
                active_sid = e
                break

        if active_sid:
            # Check if it's stale
            age = time.time() - active_sid.get("timestamp", 0)
            if age < STALE_THRESHOLD_SECONDS:
                self._current = {
                    "session_id": active_sid["session_id"],
                    "started_at": active_sid.get("started_at", active_sid.get("timestamp", time.time())),
                    "started_at_iso": active_sid.get("timestamp_iso", ""),
                    "last_heartbeat": active_sid.get("timestamp", time.time()),
                    "status": "active",
                }

    def auto_recover(self) -> dict:
        """
        Auto-recover from stale sessions.
        If a session is stale, stop it and start a new one.
        """
        if not self._current:
            return {"action": "none", "reason": "no active session"}

        age = time.time() - self._current.get("last_heartbeat", 0)
        if age < STALE_THRESHOLD_SECONDS:
            return {"action": "none", "reason": "session is active"}

        # Session is stale, stop it
        self.stop("auto-recover")
        return {"action": "recovered", "reason": f"stale session stopped (age={age:.0f}s)"}


def _iso(ts: float) -> str:
    """Format timestamp as ISO 8601."""
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _copy(d: dict) -> dict:
    """Shallow copy of a dict."""
    return dict(d)


# ── CLI entry point ──────────────────────────────────────────────────────────

def _cli():
    import sys
    if len(sys.argv) < 2:
        print("Usage: session_manager.py <sessions.jsonl> [start|heartbeat|stop|status|history] [args...]")
        sys.exit(1)

    path = sys.argv[1]
    cmd = sys.argv[2] if len(sys.argv) > 2 else "status"
    sm = SessionManager(path)

    if cmd == "start":
        sid = sys.argv[3] if len(sys.argv) > 3 else None
        result = sm.start(sid)
        print(json.dumps(result, indent=2))
    elif cmd == "heartbeat":
        result = sm.heartbeat()
        print(json.dumps(result or {"status": "no active session"}, indent=2))
    elif cmd == "stop":
        reason = sys.argv[3] if len(sys.argv) > 3 else "normal"
        result = sm.stop(reason)
        print(json.dumps(result or {"status": "no active session"}, indent=2))
    elif cmd == "status":
        current = sm.get_current()
        if current:
            print(json.dumps(current, indent=2))
        else:
            print(json.dumps({"status": "no active session"}, indent=2))
    elif cmd == "history":
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        history = sm.get_history(n)
        print(json.dumps(history, indent=2))
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    _cli()
