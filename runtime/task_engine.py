"""
MCR Task Engine — load, route, run, verify tasks.

Phase 2 of MCR foundation build.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# Add SDK to path
import sys
_sdk_path = str(Path(__file__).resolve().parent.parent / "sdk" / "python")
if _sdk_path not in sys.path:
    sys.path.insert(0, _sdk_path)

from mcr_sdk import AppManifest, AppRegistry, TaskManifest, MCRClient
from mcr_sdk.permissions import PermissionCatalog


# ─── Task Router ────────────────────────────────────────────────────────────

KEYWORD_ROUTES = {
    "security": ("security_lab", "Hermes-Sec"),
    "dvwa": ("security_lab", "Hermes-Sec"),
    "sec": ("security_lab", "Hermes-Sec"),
    "media": ("media", "Hermes-Media"),
    "video": ("media", "Hermes-Media"),
    "story": ("media", "Hermes-Media"),
}


def route_task(task: TaskManifest, registry: AppRegistry) -> tuple[str, str, str]:
    """Route a task to an app. Returns (route, target_agent, reason).

    Priority:
    1. If task.app_id matches a registered app, use it directly
    2. Fallback to keyword matching
    3. Final fallback: runtime/Hermes-MCR
    """
    # Direct app_id match
    app = registry.get(task.app_id)
    if app:
        return (task.app_id, app.name, f"direct match: app_id={task.app_id}")

    # Keyword fallback
    goal_lower = task.goal.lower()
    for keyword, (route, agent) in KEYWORD_ROUTES.items():
        if keyword in goal_lower:
            return (route, agent, f"keyword match: '{keyword}'")

    # Default
    return ("runtime", "Hermes-MCR", "default route")


# ─── Permission Gate ────────────────────────────────────────────────────────

DENY_KEYWORDS = [
    "delete", "remove", "rm ", "format",
    "network", "api call",
    "install", "pip install", "npm install",
    "secret", "token", "credential",
    "clean c:", "system32",
]


@dataclass
class PermissionResult:
    decision: str  # "allow" or "deny"
    action: str
    reason: str


def check_permission(task: TaskManifest, app: Optional[AppManifest],
                     catalog: PermissionCatalog) -> PermissionResult:
    """Check if a task is allowed to run.

    1. Check deny keywords in goal
    2. Check permissions subset (task vs app)
    """
    goal_lower = task.goal.lower()

    # Deny keyword check
    for kw in DENY_KEYWORDS:
        if kw in goal_lower:
            return PermissionResult(
                decision="deny",
                action="blocked_task",
                reason=f"deny keyword matched: '{kw}'"
            )

    # Permission subset check
    if app:
        ok, denied = catalog.check_subset(task.permissions, app.permissions)
        if not ok:
            return PermissionResult(
                decision="deny",
                action="insufficient_permissions",
                reason=f"task needs {denied} but app doesn't grant them"
            )

    # Risk-based check
    if task.risk_level == "high":
        return PermissionResult(
            decision="deny",
            action="high_risk_task",
            reason="high-risk tasks require owner confirmation"
        )

    return PermissionResult(
        decision="allow",
        action="run_task",
        reason="low/medium risk, permissions ok"
    )


# ─── Task Runner ────────────────────────────────────────────────────────────

@dataclass
class TaskResult:
    task_id: str
    status: str  # "success", "blocked", "timeout", "error"
    executor: str
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    outputs: dict[str, Any] = field(default_factory=dict)


def run_task(task: TaskManifest, app: Optional[AppManifest],
             permission: PermissionResult,
             root_dir: Optional[str] = None) -> TaskResult:
    """Execute a task in sandbox. Returns TaskResult.

    v4.0: Uses CodeSandbox instead of shell=True.
    Three-layer defense: static analysis -> restricted execution -> audit.
    """
    if permission.decision == "deny":
        return TaskResult(
            task_id=task.task_id,
            status="blocked",
            executor=task.executor,
            stderr=permission.reason,
        )

    # Use sandbox for safe execution
    try:
        from sandbox import CodeSandbox, SandboxPolicy
    except ImportError:
        # Fallback to legacy execution if sandbox not available
        return _run_task_legacy(task, app, permission, root_dir)

    # Build sandbox policy from task metadata
    policy = SandboxPolicy(
        max_timeout_seconds=task.timeout_seconds,
        filesystem_root=root_dir or (app.root if app else None),
        security_level="standard",  # 只警告不拦截，不卡正常开发
    )

    sandbox = CodeSandbox(policy=policy)

    # Build command
    if task.command:
        if task.executor == "python":
            cmd = task.command
        elif task.executor == "node":
            cmd = task.command
        elif task.executor == "shell":
            cmd = task.command
        else:
            cmd = task.command
    else:
        # Default: use app entrypoint
        if app and app.entrypoints.get("run"):
            cmd = app.entrypoints["run"]
        else:
            return TaskResult(
                task_id=task.task_id,
                status="error",
                executor=task.executor,
                stderr="no command and no app entrypoint",
            )

    # Set working directory
    cwd = root_dir or (app.root if app else None) or os.getcwd()

    # Inject MCR_TASK env var
    env = {"MCR_TASK": json.dumps(task.to_dict(), ensure_ascii=False)}

    # Execute in sandbox
    sandbox_result = sandbox.execute(
        code=cmd,
        language=task.executor,
        task_id=task.task_id,
        cwd=cwd,
        env=env,
    )

    return TaskResult(
        task_id=sandbox_result.task_id,
        status=sandbox_result.status,
        executor=sandbox_result.executor,
        exit_code=sandbox_result.exit_code,
        stdout=sandbox_result.stdout,
        stderr=sandbox_result.stderr,
        duration_seconds=sandbox_result.duration_seconds,
    )


def _run_task_legacy(task: TaskManifest, app: Optional[AppManifest],
                     permission: PermissionResult,
                     root_dir: Optional[str] = None) -> TaskResult:
    """Legacy execution (shell=True). Only used if sandbox import fails."""
    # Build command
    if task.command:
        cmd = task.command
    elif app and app.entrypoints.get("run"):
        cmd = app.entrypoints["run"]
    else:
        return TaskResult(
            task_id=task.task_id, status="error",
            executor=task.executor, stderr="no command",
        )

    cwd = root_dir or (app.root if app else None) or os.getcwd()
    env = os.environ.copy()
    env["MCR_TASK"] = json.dumps(task.to_dict(), ensure_ascii=False)

    start = time.time()
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=task.timeout_seconds, cwd=cwd, env=env,
        )
        return TaskResult(
            task_id=task.task_id,
            status="success" if result.returncode == 0 else "error",
            executor=task.executor,
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_seconds=time.time() - start,
        )
    except subprocess.TimeoutExpired:
        return TaskResult(
            task_id=task.task_id, status="timeout",
            executor=task.executor,
            duration_seconds=task.timeout_seconds,
            stderr=f"timed out after {task.timeout_seconds}s",
        )
    except Exception as e:
        return TaskResult(
            task_id=task.task_id, status="error",
            executor=task.executor, stderr=str(e),
        )


# ─── Task Verifier ──────────────────────────────────────────────────────────

def verify_task(task: TaskManifest, result: TaskResult) -> dict[str, Any]:
    """Verify task outputs against expected_outputs.

    Returns verification report dict.
    """
    # For now, check that the task didn't fail
    if result.status == "blocked":
        return {
            "status": "fail",
            "reason": "task was blocked",
            "detail": result.stderr,
        }

    if result.status == "timeout":
        return {
            "status": "fail",
            "reason": "task timed out",
            "detail": result.stderr,
        }

    if result.status == "error":
        return {
            "status": "fail",
            "reason": "task errored",
            "detail": result.stderr,
            "exit_code": result.exit_code,
        }

    # Check expected outputs exist (by name, not by file)
    # For now, success = pass
    return {
        "status": "pass",
        "task_id": task.task_id,
        "executor": result.executor,
        "exit_code": result.exit_code,
        "duration_seconds": result.duration_seconds,
    }


# ─── Full Pipeline ──────────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    task: TaskManifest
    route: tuple[str, str, str]
    permission: PermissionResult
    execution: TaskResult
    verification: dict[str, Any]
    events_written: int = 0


def run_pipeline(task_path: str | Path,
                 ecosystem_root: Optional[str] = None,
                 wal_path: Optional[str] = None,
                 write_events: bool = True) -> PipelineResult:
    """Run the full task pipeline: load -> route -> permission -> execute -> verify -> emit events.

    This is the main entrypoint for task execution.
    """
    # Resolve paths
    eco_root = ecosystem_root or str(Path(__file__).resolve().parent.parent)
    apps_dir = Path(eco_root) / "apps"
    perms_path = Path(eco_root) / "registry" / "permissions.json"
    wal = wal_path or str(Path(eco_root) / "runtime" / "events.jsonl")

    # Load
    task = TaskManifest.load(task_path)
    registry = AppRegistry.from_directory(apps_dir)
    catalog = PermissionCatalog()
    catalog.load(perms_path)

    app = registry.get(task.app_id)

    # Route
    route = route_task(task, registry)

    # Permission check
    perm = check_permission(task, app, catalog)

    # Execute
    exec_result = run_task(task, app, perm)

    # Verify
    verification = verify_task(task, exec_result)

    # Emit events
    events_count = 0
    if write_events:
        client = MCRClient(wal)

        # task_routed
        client.emit("task_routed", {
            "task_id": task.task_id,
            "route": route[0],
            "target_agent": route[1],
            "reason": route[2],
        })
        events_count += 1

        # permission_decision
        client.emit("permission_decision", {
            "requested_action": task.goal,
            "scope": task.app_id,
            "decision": perm.decision,
            "reason": perm.reason,
            "agent_id": route[1],
        })
        events_count += 1

        # executor_result
        client.emit("executor_result", {
            "task_id": task.task_id,
            "executor": exec_result.executor,
            "status": exec_result.status,
            "exit_code": exec_result.exit_code,
            "duration_seconds": exec_result.duration_seconds,
            "summary": exec_result.stdout[:500] if exec_result.stdout else exec_result.stderr[:500],
        })
        events_count += 1

        # audit_report_generated
        client.emit("audit_report_generated", {
            "task_id": task.task_id,
            "verification": verification,
        })
        events_count += 1

    return PipelineResult(
        task=task,
        route=route,
        permission=perm,
        execution=exec_result,
        verification=verification,
        events_written=events_count,
    )


# ─── CLI ────────────────────────────────────────────────────────────────────

def main():
    """Task Engine CLI."""
    import argparse
    parser = argparse.ArgumentParser(description="MCR Task Engine")
    sub = parser.add_subparsers(dest="command")

    # task run <path>
    run_p = sub.add_parser("run", help="Run a task from manifest")
    run_p.add_argument("task_path", help="Path to task JSON")
    run_p.add_argument("--ecosystem", help="ECOSYSTEM root path")
    run_p.add_argument("--no-events", action="store_true", help="Don't write events")

    # task validate <path>
    val_p = sub.add_parser("validate", help="Validate a task manifest")
    val_p.add_argument("task_path", help="Path to task JSON")
    val_p.add_argument("--ecosystem", help="ECOSYSTEM root path")

    args = parser.parse_args()

    if args.command == "run":
        result = run_pipeline(
            args.task_path,
            ecosystem_root=args.ecosystem,
            write_events=not args.no_events,
        )
        print(json.dumps({
            "task_id": result.task.task_id,
            "route": result.route,
            "permission": result.permission.decision,
            "status": result.execution.status,
            "exit_code": result.execution.exit_code,
            "verification": result.verification,
            "events_written": result.events_written,
        }, indent=2, ensure_ascii=False))

    elif args.command == "validate":
        eco_root = args.ecosystem or str(Path(__file__).resolve().parent.parent)
        task = TaskManifest.load(args.task_path)
        apps_dir = Path(eco_root) / "apps"
        registry = AppRegistry.from_directory(apps_dir)
        app = registry.get(task.app_id)
        errors = TaskManifest.validate(task, app)
        if errors:
            print(f"FAIL: {len(errors)} errors")
            for e in errors:
                print(f"  - {e}")
            sys.exit(1)
        else:
            print("PASS")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
