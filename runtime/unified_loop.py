"""
Unified Cognitive Loop — connects all MCR capabilities into one autonomous flow.

v4.0: Now uses cognitive_bridge to integrate world_model and cognitive_loop.
The brain actually participates in decisions, not just reads/writes JSONL.

Flow:
  environment scan → world_model.predict → opportunity detection → goal generation →
  world_model.gate → goal execution → provenance recording → failure analysis →
  self correction → cognitive_loop.tick → repeat
"""

import json
import argparse
import time
import importlib.util
import sys
from pathlib import Path
from datetime import datetime

ECOSYSTEM_ROOT = Path(__file__).parent.parent
RUNTIME_DIR = ECOSYSTEM_ROOT / "runtime"
LOOP_LOG = RUNTIME_DIR / ".wal" / "cognitive" / "unified_loop.jsonl"

# Import cognitive bridge (the brain)
sys.path.insert(0, str(RUNTIME_DIR))
try:
    from cognitive_bridge import WorldModel, CognitiveLoop, _get_engine
    COGNITIVE_AVAILABLE = True
except ImportError:
    COGNITIVE_AVAILABLE = False


def load_module(name, path):
    """Dynamically load a Python module."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def log_step(step, data):
    """Log a loop step."""
    entry = {
        "step": step,
        "timestamp": datetime.now().isoformat(),
        "data": data
    }
    LOOP_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOOP_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def run_cycle(dry_run=False):
    """Run one complete cognitive cycle.

    v4.0: Now integrates world_model predictions and gates.
    """
    cycle_start = datetime.now()
    results = {
        "cycle_start": cycle_start.isoformat(),
        "steps": {},
        "status": "running",
        "cognitive_active": COGNITIVE_AVAILABLE
    }

    # Initialize world model if available
    wm = None
    if COGNITIVE_AVAILABLE and WorldModel:
        try:
            wm = WorldModel(
                action_log_path=str(RUNTIME_DIR / ".wal" / "cognitive" / "action_log.jsonl"),
                world_state_path=str(RUNTIME_DIR / ".wal" / "cognitive" / "world_state.json")
            )
        except Exception:
            pass

    # Step 1: Environment Scan
    try:
        env_mod = load_module("env_monitor", RUNTIME_DIR / "environment_monitor.py")
        env_status = env_mod.scan_environment()
        results["steps"]["environment"] = {
            "cpu": env_status.get("system", {}).get("cpu_percent"),
            "memory": env_status.get("system", {}).get("memory_percent"),
            "ports_checked": len(env_status.get("ports", [])),
            "open_ports": [p["port"] for p in env_status.get("ports", []) if p["open"]]
        }
        log_step("environment", results["steps"]["environment"])
    except Exception as e:
        results["steps"]["environment"] = {"error": str(e)[:100]}

    # Step 2: World Model Prediction (what do we expect this cycle?)
    if wm:
        try:
            prediction = wm.predict({"command": "unified_cycle", "action_type": "cycle"})
            results["steps"]["prediction"] = {
                "success_probability": prediction.success_probability,
                "risk_level": prediction.risk_level,
                "confidence": prediction.confidence
            }
            log_step("prediction", results["steps"]["prediction"])
        except Exception as e:
            results["steps"]["prediction"] = {"error": str(e)[:100]}

    # Step 3: Opportunity Detection
    try:
        opp_mod = load_module("opportunity_detector", RUNTIME_DIR / "opportunity_detector.py")
        opps = opp_mod.scan_for_opportunities()
        results["steps"]["opportunities"] = {
            "found": opps.get("opportunities_found", 0),
            "details": opps.get("opportunities", [])
        }
        log_step("opportunities", results["steps"]["opportunities"])
    except Exception as e:
        results["steps"]["opportunities"] = {"error": str(e)[:100]}

    # Step 4: Goal Generation
    try:
        goal_mod = load_module("goal_generator", RUNTIME_DIR / "goal_generator.py")
        goals = goal_mod.generate_goals()
        results["steps"]["goals"] = {
            "generated": goals.get("new_goals_generated", 0),
            "total": goals.get("existing_goals", 0) + goals.get("new_goals_generated", 0)
        }
        log_step("goals", results["steps"]["goals"])
    except Exception as e:
        results["steps"]["goals"] = {"error": str(e)[:100]}

    # Step 5: Goal Execution with World Model Gate
    executed = []
    blocked = []
    if not dry_run:
        try:
            all_goals = goal_mod.get_goals(status="proposed")
            for goal in all_goals:
                if goal.get("priority", 0) >= 2:
                    # Gate through world model before executing
                    if wm:
                        gate_pred = wm.predict({
                            "command": f"execute_goal:{goal.get('title', 'unknown')}",
                            "action_type": "goal_execution"
                        })
                        gate_decision = wm.gate(gate_pred)
                        if gate_decision.decision == "BLOCK":
                            blocked.append({
                                "goal_id": goal["id"],
                                "reason": gate_decision.reason,
                                "risk": gate_pred.risk_level
                            })
                            continue
                    goal_mod.approve_goal(goal["id"])
                    executed.append(goal["id"])
            results["steps"]["execution"] = {
                "approved": len(executed),
                "blocked": len(blocked),
                "goal_ids": executed,
                "blocked_details": blocked
            }
            log_step("execution", results["steps"]["execution"])
        except Exception as e:
            results["steps"]["execution"] = {"error": str(e)[:100]}
    else:
        results["steps"]["execution"] = {"skipped": "dry_run"}

    # Step 6: Provenance Recording
    try:
        prov_mod = load_module("provenance", RUNTIME_DIR / "provenance.py")
        cycle_event = prov_mod.create_provenance_event(
            "unified_cycle",
            {
                "environment": results["steps"].get("environment", {}),
                "opportunities": results["steps"].get("opportunities", {}).get("found", 0),
                "goals_generated": results["steps"].get("goals", {}).get("generated", 0),
                "goals_executed": len(executed),
                "goals_blocked": len(blocked)
            }
        )
        results["steps"]["provenance"] = {
            "event_id": cycle_event.get("event_id"),
            "chain_hash": cycle_event.get("provenance", {}).get("chain_hash", "")[:16]
        }
        log_step("provenance", results["steps"]["provenance"])
    except Exception as e:
        results["steps"]["provenance"] = {"error": str(e)[:100]}

    # Step 7: Failure Analysis
    try:
        fail_mod = load_module("failure_analyzer", RUNTIME_DIR / "failure_analyzer.py")
        failures = fail_mod.analyze(50)
        results["steps"]["failures"] = {
            "total": failures.get("total_failures", 0),
            "rate": failures.get("failure_rate", 0)
        }
        log_step("failures", results["steps"]["failures"])
    except Exception as e:
        results["steps"]["failures"] = {"error": str(e)[:100]}

    # Step 8: Pattern Detection
    try:
        pattern_mod = load_module("pattern_detector", RUNTIME_DIR / "pattern_detector.py")
        patterns = pattern_mod.analyze(100)
        results["steps"]["patterns"] = {
            "high_freq_events": len(patterns.get("high_frequency_events", {})),
            "idle_periods": len(patterns.get("idle_periods", [])),
            "error_clusters": len(patterns.get("error_clusters", []))
        }
        log_step("patterns", results["steps"]["patterns"])
    except Exception as e:
        results["steps"]["patterns"] = {"error": str(e)[:100]}

    # Step 9: Immune System Patrol
    try:
        immune_mod = load_module("immune_system", RUNTIME_DIR / "immune_system.py")
        immune_result = immune_mod.patrol()
        results["steps"]["immune"] = {
            "detected": immune_result["summary"]["detected"],
            "fixed": immune_result["summary"]["fixed"],
            "skipped": immune_result["summary"]["skipped"]
        }
        log_step("immune", results["steps"]["immune"])
    except Exception as e:
        results["steps"]["immune"] = {"error": str(e)[:100]}

    # Step 10: Self Correction (legacy)
    try:
        correct_mod = load_module("self_correction", RUNTIME_DIR / "self_correction.py")
        corrections = correct_mod.run_corrections()
        results["steps"]["corrections"] = {
            "applied": corrections.get("fixes_applied", 0)
        }
        log_step("corrections", results["steps"]["corrections"])
    except Exception as e:
        results["steps"]["corrections"] = {"error": str(e)[:100]}

    # Step 11: Cognitive Loop Tick (the brain reflects)
    if COGNITIVE_AVAILABLE and CognitiveLoop:
        try:
            loop = CognitiveLoop(
                wal_path=str(RUNTIME_DIR / ".wal" / "cognitive" / "cognitive_wal.jsonl"),
                safety_mode=True
            )
            loop.run(max_ticks=1)
            results["steps"]["cognitive_tick"] = {"status": "completed"}
            log_step("cognitive_tick", results["steps"]["cognitive_tick"])
        except Exception as e:
            results["steps"]["cognitive_tick"] = {"error": str(e)[:100]}

    # Summary
    cycle_end = datetime.now()
    duration = (cycle_end - cycle_start).total_seconds()
    results["cycle_end"] = cycle_end.isoformat()
    results["duration_seconds"] = round(duration, 2)
    results["status"] = "completed"

    total_actions = (
        results["steps"].get("opportunities", {}).get("found", 0) +
        results["steps"].get("goals", {}).get("generated", 0) +
        len(executed) +
        len(blocked) +
        results["steps"].get("corrections", {}).get("applied", 0)
    )
    results["total_actions"] = total_actions

    return results


def run_loop(interval=300, cycles=0, dry_run=False):
    """Run the unified loop continuously."""
    cycle = 0
    print(f"[unified-loop] Starting (interval={interval}s, dry_run={dry_run})")

    try:
        while True:
            cycle += 1
            print(f"\n[unified-loop] Cycle {cycle} starting...")
            result = run_cycle(dry_run=dry_run)

            # Summary
            steps = result.get("steps", {})
            print(f"[unified-loop] Cycle {cycle} done in {result['duration_seconds']}s:")
            print(f"  Environment: CPU={steps.get('environment', {}).get('cpu', 'N/A')}%")
            print(f"  Opportunities: {steps.get('opportunities', {}).get('found', 0)}")
            print(f"  Goals: {steps.get('goals', {}).get('generated', 0)} generated, {len(result.get('executed', []))} executed")
            print(f"  Failures: {steps.get('failures', {}).get('total', 0)}")
            print(f"  Corrections: {steps.get('corrections', {}).get('applied', 0)}")
            print(f"  Provenance: {steps.get('provenance', {}).get('chain_hash', 'N/A')}")

            if cycles > 0 and cycle >= cycles:
                print(f"\n[unified-loop] Completed {cycles} cycles")
                break

            print(f"[unified-loop] Sleeping {interval}s...")
            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n[unified-loop] Stopped after {cycle} cycles")


# ===== CLI Entry Point =====

def main():
    parser = argparse.ArgumentParser(description="MCR Unified Cognitive Loop")
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="Run one cycle")
    p_run.add_argument("--dry-run", action="store_true")

    p_loop = sub.add_parser("loop", help="Run continuously")
    p_loop.add_argument("--interval", type=int, default=300)
    p_loop.add_argument("--cycles", type=int, default=0)
    p_loop.add_argument("--dry-run", action="store_true")

    sub.add_parser("history", help="Show cycle history")

    args = parser.parse_args()

    if args.command == "run":
        result = run_cycle(dry_run=args.dry_run)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.command == "loop":
        run_loop(interval=args.interval, cycles=args.cycles, dry_run=args.dry_run)
    elif args.command == "history":
        if LOOP_LOG.exists():
            entries = []
            with open(LOOP_LOG, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
            print(json.dumps({
                "total_entries": len(entries),
                "recent": entries[-20:]
            }, indent=2, ensure_ascii=False))
        else:
            print(json.dumps({"total_entries": 0, "recent": []}, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
