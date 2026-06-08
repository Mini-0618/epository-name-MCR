"""
Real State Checker - Checks actual filesystem state of registered MCR apps.

Unlike registry validate (which checks if manifests parse), this checks:
- File existence, count, total size
- Last modification time
- Git status (clean/dirty/no-git)
- README and manifest presence
- Disk free space
- Anomaly detection vs previous state

Usage:
    python real-state-checker.py check-all          # Check all apps, print summary
    python real-state-checker.py check-all --json    # JSON output
    python real-state-checker.py check <app_id>      # Check single app
    python real-state-checker.py ecosystem           # Ecosystem-wide health
    python real-state-checker.py ecosystem --json    # JSON output
    python real-state-checker.py anomalies           # Detect anomalies vs history
    python real-state-checker.py anomalies --json    # JSON output
    python real-state-checker.py history              # Show state history
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path


def _find_ecosystem_root():
    """Walk up from this file to find the ECOSYSTEM root."""
    p = Path(__file__).resolve().parent
    while p != p.parent:
        if (p / "registry" / "apps.json").exists():
            return str(p)
        p = p.parent
    return str(Path(__file__).resolve().parent.parent.parent)


ECOSYSTEM_ROOT = _find_ecosystem_root()
REGISTRY_PATH = os.path.join(ECOSYSTEM_ROOT, "registry", "apps.json")
HISTORY_PATH = os.path.join(ECOSYSTEM_ROOT, "runtime", "agi", "real-state-history.json")
ANOMALIES_PATH = os.path.join(ECOSYSTEM_ROOT, "runtime", "agi", "anomalies.jsonl")


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _days_ago(dt_str):
    """Parse an ISO timestamp and return how many days ago it was."""
    if not dt_str:
        return 9999
    try:
        # Handle various formats
        dt_str = dt_str.rstrip("Z").split("+")[0].split(".")[0]
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return 9999


def _dir_size_bytes(path):
    """Recursively sum file sizes under path."""
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _file_count(path):
    """Count files recursively under path."""
    count = 0
    try:
        for _, _, filenames in os.walk(path):
            count += len(filenames)
    except OSError:
        pass
    return count


def _last_modified_iso(path):
    """Get the most recent modification time of any file under path."""
    latest = 0.0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    mt = os.path.getmtime(fp)
                    if mt > latest:
                        latest = mt
                except OSError:
                    pass
    except OSError:
        pass
    if latest == 0.0:
        return None
    return datetime.fromtimestamp(latest, tz=timezone.utc).isoformat()


def _git_status(app_root):
    """Check git status of an app directory.

    Returns: "clean", "dirty", "no-git", or "error"
    """
    git_dir = os.path.join(app_root, ".git")
    if not os.path.exists(git_dir):
        return "no-git"
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=app_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return "error"
        output = result.stdout.strip()
        return "dirty" if output else "clean"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return "error"


def _has_readme(app_root):
    """Check if app has a README file."""
    for name in ["README.md", "README.rst", "README.txt", "README"]:
        if os.path.exists(os.path.join(app_root, name)):
            return True
    return False


def _has_manifest(app_root):
    """Check if app has a manifest file."""
    for name in ["mcr.app.json", "package.json", "pyproject.toml", "Cargo.toml"]:
        if os.path.exists(os.path.join(app_root, name)):
            return True
    return False


def _disk_free_mb(path):
    """Get free disk space in MB for the drive containing path."""
    try:
        usage = os.statvfs(path) if hasattr(os, "statvfs") else None
    except OSError:
        usage = None
    if usage:
        return round((usage.f_bavail * usage.f_frsize) / (1024 * 1024), 1)
    # Windows fallback
    try:
        import shutil
        total, used, free = shutil.disk_usage(path)
        return round(free / (1024 * 1024), 1)
    except Exception:
        return 0.0


def _classify_health(exists, file_count, last_modified_iso, git_stat):
    """Classify app health based on real state.

    Rules:
      - healthy:  exists, has files, modified in last 7 days
      - warning:  exists but no files, or not modified in 30+ days
      - critical: doesn't exist, or git dirty with uncommitted changes
    """
    if not exists:
        return "critical"
    if git_stat == "dirty":
        return "critical"
    if file_count == 0:
        return "warning"
    days = _days_ago(last_modified_iso)
    if days > 30:
        return "warning"
    return "healthy"


def load_registry():
    """Load registry/apps.json."""
    if not os.path.exists(REGISTRY_PATH):
        raise FileNotFoundError(f"Registry not found: {REGISTRY_PATH}")
    with open(REGISTRY_PATH, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_history():
    """Load previous state history."""
    if not os.path.exists(HISTORY_PATH):
        return {}
    with open(HISTORY_PATH, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_history(data):
    """Save state history."""
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def append_anomaly(anomaly):
    """Append a single anomaly record to anomalies.jsonl."""
    os.makedirs(os.path.dirname(ANOMALIES_PATH), exist_ok=True)
    with open(ANOMALIES_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(anomaly, ensure_ascii=False) + "\n")


class RealStateChecker:
    """Checks real filesystem state of registered MCR apps."""

    def __init__(self, ecosystem_root=None):
        self.ecosystem_root = ecosystem_root or ECOSYSTEM_ROOT
        self.registry = None

    def _ensure_registry(self):
        if self.registry is None:
            self.registry = load_registry()

    def check_app(self, app_id, app_root):
        """Check real state of a single app.

        Args:
            app_id: The app identifier (e.g. "anvil.one")
            app_root: The filesystem path to the app root

        Returns:
            dict with real state data
        """
        exists = os.path.isdir(app_root)
        fc = _file_count(app_root) if exists else 0
        size_bytes = _dir_size_bytes(app_root) if exists else 0
        size_mb = round(size_bytes / (1024 * 1024), 2)
        last_mod = _last_modified_iso(app_root) if exists else None
        git_stat = _git_status(app_root) if exists else "no-git"
        has_rm = _has_readme(app_root) if exists else False
        has_mf = _has_manifest(app_root) if exists else False
        health = _classify_health(exists, fc, last_mod, git_stat)

        return {
            "app_id": app_id,
            "exists": exists,
            "file_count": fc,
            "total_size_mb": size_mb,
            "last_modified": last_mod,
            "git_status": git_stat,
            "has_readme": has_rm,
            "has_manifest": has_mf,
            "health": health,
        }

    def check_all_apps(self):
        """Check all registered apps.

        Returns:
            list of per-app state dicts
        """
        self._ensure_registry()
        results = []
        for app in self.registry.get("apps", []):
            app_id = app.get("id", "unknown")
            app_root = app.get("root", "")
            results.append(self.check_app(app_id, app_root))
        return results

    def check_ecosystem(self):
        """Check overall ecosystem health.

        Returns:
            dict with ecosystem-wide stats
        """
        app_states = self.check_all_apps()
        healthy = sum(1 for a in app_states if a["health"] == "healthy")
        warning = sum(1 for a in app_states if a["health"] == "warning")
        critical = sum(1 for a in app_states if a["health"] == "critical")
        total_size = sum(a["total_size_mb"] for a in app_states)
        disk_free = _disk_free_mb(self.ecosystem_root)

        issues = []
        for a in app_states:
            if a["health"] == "critical":
                if not a["exists"]:
                    issues.append(f"CRITICAL: {a['app_id']} directory missing")
                elif a["git_status"] == "dirty":
                    issues.append(f"CRITICAL: {a['app_id']} has uncommitted changes")
            elif a["health"] == "warning":
                if a["file_count"] == 0:
                    issues.append(f"WARNING: {a['app_id']} has no files")
                elif a["last_modified"]:
                    days = _days_ago(a["last_modified"])
                    if days > 30:
                        issues.append(f"WARNING: {a['app_id']} not modified in {days} days")

        return {
            "total_apps": len(app_states),
            "healthy": healthy,
            "warning": warning,
            "critical": critical,
            "total_size_mb": round(total_size, 2),
            "disk_free_mb": disk_free,
            "issues": issues,
            "checked_at": _now_iso(),
        }

    def detect_anomalies(self, current, previous):
        """Compare current state with previous, detect significant changes.

        Args:
            current: dict of {app_id: state_dict} from current check
            previous: dict of {app_id: state_dict} from history

        Returns:
            list of anomaly dicts
        """
        anomalies = []

        for app_id, cur in current.items():
            prev = previous.get(app_id)

            if prev is None:
                # New app appeared
                anomalies.append({
                    "type": "new_app",
                    "app_id": app_id,
                    "detail": f"New app detected: {app_id}",
                    "timestamp": _now_iso(),
                })
                continue

            # File count changed significantly (>20% or >100 files)
            prev_fc = prev.get("file_count", 0)
            cur_fc = cur.get("file_count", 0)
            if prev_fc > 0:
                fc_change_pct = abs(cur_fc - prev_fc) / prev_fc * 100
                if fc_change_pct > 20 or abs(cur_fc - prev_fc) > 100:
                    anomalies.append({
                        "type": "file_count_changed",
                        "app_id": app_id,
                        "detail": f"File count: {prev_fc} -> {cur_fc} ({fc_change_pct:.0f}% change)",
                        "previous": prev_fc,
                        "current": cur_fc,
                        "timestamp": _now_iso(),
                    })

            # Size changed significantly (>50% or >100MB)
            prev_size = prev.get("total_size_mb", 0)
            cur_size = cur.get("total_size_mb", 0)
            if prev_size > 0:
                size_change_pct = abs(cur_size - prev_size) / prev_size * 100
                if size_change_pct > 50 or abs(cur_size - prev_size) > 100:
                    anomalies.append({
                        "type": "size_changed",
                        "app_id": app_id,
                        "detail": f"Size: {prev_size:.1f}MB -> {cur_size:.1f}MB ({size_change_pct:.0f}% change)",
                        "previous": prev_size,
                        "current": cur_size,
                        "timestamp": _now_iso(),
                    })

            # Health degraded
            prev_health = prev.get("health", "unknown")
            cur_health = cur.get("health", "unknown")
            health_rank = {"healthy": 0, "warning": 1, "critical": 2, "unknown": 1}
            if health_rank.get(cur_health, 1) > health_rank.get(prev_health, 1):
                anomalies.append({
                    "type": "health_degraded",
                    "app_id": app_id,
                    "detail": f"Health: {prev_health} -> {cur_health}",
                    "previous": prev_health,
                    "current": cur_health,
                    "timestamp": _now_iso(),
                })

            # Git status changed
            prev_git = prev.get("git_status", "unknown")
            cur_git = cur.get("git_status", "unknown")
            if prev_git != cur_git:
                anomalies.append({
                    "type": "git_status_changed",
                    "app_id": app_id,
                    "detail": f"Git: {prev_git} -> {cur_git}",
                    "previous": prev_git,
                    "current": cur_git,
                    "timestamp": _now_iso(),
                })

            # App disappeared
            if prev.get("exists", True) and not cur.get("exists", True):
                anomalies.append({
                    "type": "app_disappeared",
                    "app_id": app_id,
                    "detail": f"App directory no longer exists: {app_id}",
                    "timestamp": _now_iso(),
                })

        # Check for apps that disappeared from registry
        for app_id in previous:
            if app_id not in current:
                anomalies.append({
                    "type": "app_removed",
                    "app_id": app_id,
                    "detail": f"App removed from registry: {app_id}",
                    "timestamp": _now_iso(),
                })

        return anomalies


# ---- CLI ----

def _print_apps_table(app_states):
    """Print app states as a human-readable table."""
    print(f"{'App ID':<25} {'Health':<10} {'Files':>6} {'Size MB':>8} {'Git':<8} {'Last Modified':<22}")
    print("-" * 85)
    for a in app_states:
        health_color = {"healthy": "OK", "warning": "WARN", "critical": "CRIT"}
        h = health_color.get(a["health"], "???")
        lm = (a["last_modified"] or "never")[:19]
        print(f"{a['app_id']:<25} {h:<10} {a['file_count']:>6} {a['total_size_mb']:>8.1f} {a['git_status']:<8} {lm:<22}")


def _print_ecosystem(eco):
    """Print ecosystem summary."""
    print("Ecosystem Health")
    print("-" * 40)
    print(f"  Total apps  : {eco['total_apps']}")
    print(f"  Healthy     : {eco['healthy']}")
    print(f"  Warning     : {eco['warning']}")
    print(f"  Critical    : {eco['critical']}")
    print(f"  Total size  : {eco['total_size_mb']:.1f} MB")
    print(f"  Disk free   : {eco['disk_free_mb']:.1f} MB")
    print(f"  Checked at  : {eco['checked_at']}")
    if eco["issues"]:
        print()
        print("  Issues:")
        for issue in eco["issues"]:
            prefix = "!!!" if issue.startswith("CRITICAL") else "  !"
            print(f"    {prefix} {issue}")


def main():
    args = sys.argv[1:]
    use_json = "--json" in args
    args = [a for a in args if a != "--json"]

    if not args:
        print("Usage: real-state-checker.py <check-all|check|ecosystem|anomalies|history> [--json]")
        sys.exit(1)

    command = args[0]
    checker = RealStateChecker()

    if command == "check-all":
        results = checker.check_all_apps()
        if use_json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            _print_apps_table(results)

        # Save to history
        history = load_history()
        snapshot = {
            "checked_at": _now_iso(),
            "apps": {a["app_id"]: a for a in results},
        }
        history["last_check"] = snapshot
        # Keep rolling window of last 50 snapshots
        if "snapshots" not in history:
            history["snapshots"] = []
        history["snapshots"].append(snapshot)
        history["snapshots"] = history["snapshots"][-50:]
        save_history(history)

    elif command == "check":
        if len(args) < 2:
            print("Usage: real-state-checker.py check <app_id> [--json]")
            sys.exit(1)
        app_id = args[1]
        checker._ensure_registry()
        app = None
        for a in checker.registry.get("apps", []):
            if a["id"] == app_id:
                app = a
                break
        if not app:
            print(f"App not found: {app_id}")
            sys.exit(1)
        result = checker.check_app(app_id, app["root"])
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            _print_apps_table([result])

    elif command == "ecosystem":
        eco = checker.check_ecosystem()
        if use_json:
            print(json.dumps(eco, indent=2, ensure_ascii=False))
        else:
            _print_ecosystem(eco)

        # Save ecosystem snapshot to history
        history = load_history()
        history["last_ecosystem"] = eco
        save_history(history)

    elif command == "anomalies":
        # Run current check
        current_results = checker.check_all_apps()
        current_map = {a["app_id"]: a for a in current_results}

        # Load previous
        history = load_history()
        prev_snapshot = history.get("last_check", {})
        prev_map = prev_snapshot.get("apps", {})

        # Detect anomalies
        anomalies = checker.detect_anomalies(current_map, prev_map)

        if use_json:
            print(json.dumps(anomalies, indent=2, ensure_ascii=False))
        else:
            if not anomalies:
                print("No anomalies detected.")
            else:
                print(f"Anomalies Detected: {len(anomalies)}")
                print("-" * 60)
                for a in anomalies:
                    print(f"  [{a['type']}] {a['detail']}")

        # Append anomalies to jsonl
        for a in anomalies:
            append_anomaly(a)

        # Also update history with current state
        snapshot = {
            "checked_at": _now_iso(),
            "apps": current_map,
        }
        history["last_check"] = snapshot
        if "snapshots" not in history:
            history["snapshots"] = []
        history["snapshots"].append(snapshot)
        history["snapshots"] = history["snapshots"][-50:]
        save_history(history)

    elif command == "history":
        history = load_history()
        if use_json:
            print(json.dumps(history, indent=2, ensure_ascii=False))
        else:
            snapshots = history.get("snapshots", [])
            if not snapshots:
                print("No history recorded yet.")
            else:
                print(f"State History: {len(snapshots)} snapshots")
                print("-" * 50)
                for s in snapshots[-10:]:
                    apps = s.get("apps", {})
                    hc = sum(1 for a in apps.values() if a.get("health") == "healthy")
                    wc = sum(1 for a in apps.values() if a.get("health") == "warning")
                    cc = sum(1 for a in apps.values() if a.get("health") == "critical")
                    print(f"  {s.get('checked_at', '?')[:19]}  H={hc} W={wc} C={cc}")

    else:
        print(f"Unknown command: {command}")
        print("Commands: check-all, check <id>, ecosystem, anomalies, history")
        sys.exit(1)


if __name__ == "__main__":
    main()
