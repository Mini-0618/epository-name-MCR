"""
Unified Cognitive Loop — connects all MCR capabilities into one autonomous flow.

v5.0: Bio-inspired organism architecture. 10 life systems all participate.

Flow (10 systems):
  1. 感觉系统 (environment scan)
  2. 神经系统 (world model predict + cognitive loop)
  3. 内分泌系统 (global workspace evaluation)
  4. 记忆系统 (opportunity detection + sleep consolidation)
  5. 自主神经系统 (goal generation)
  6. 执行系统 (goal execution with world model gate)
  7. 免疫系统 (patrol + self-heal)
  8. 稳态系统 (homeostasis regulation)
  9. 进化系统 (skill evolution, periodic)
  10. 循环系统 (provenance recording)
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

# Import new bio-inspired modules
try:
    from global_workspace import GlobalWorkspace
    GLOBAL_WORKSPACE_AVAILABLE = True
except ImportError:
    GLOBAL_WORKSPACE_AVAILABLE = False

try:
    from homeostasis import Homeostasis
    HOMEOSTASIS_AVAILABLE = True
except ImportError:
    HOMEOSTASIS_AVAILABLE = False

try:
    from evolution import EvolutionEngine
    EVOLUTION_AVAILABLE = True
except ImportError:
    EVOLUTION_AVAILABLE = False

try:
    from sleep_consolidator import SleepConsolidator
    SLEEP_AVAILABLE = True
except ImportError:
    SLEEP_AVAILABLE = False


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


def run_cycle(dry_run=False, cycle_number=0):
    """Run one complete cognitive cycle.

    v5.0: 10 life systems all participate.
    """
    cycle_start = datetime.now()
    results = {
        "cycle_start": cycle_start.isoformat(),
        "cycle_number": cycle_number,
        "steps": {},
        "status": "running",
        "cognitive_active": COGNITIVE_AVAILABLE,
        "systems_active": {
            "nervous": COGNITIVE_AVAILABLE,
            "endocrine": GLOBAL_WORKSPACE_AVAILABLE,
            "homeostasis": HOMEOSTASIS_AVAILABLE,
            "evolution": EVOLUTION_AVAILABLE,
            "sleep": SLEEP_AVAILABLE,
        },
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

    # Step 12: Global Workspace (内分泌系统) — evaluate all events this cycle
    if GLOBAL_WORKSPACE_AVAILABLE:
        try:
            ws = GlobalWorkspace()
            # Evaluate the cycle itself as an event
            cycle_event = {
                "type": "cycle_complete",
                "cycle_number": cycle_number,
                "opportunities": results["steps"].get("opportunities", {}).get("found", 0),
                "failures": results["steps"].get("failures", {}).get("total", 0),
                "corrections": results["steps"].get("corrections", {}).get("applied", 0),
            }
            signal = ws.evaluate(cycle_event)
            ctx = ws.get_context()
            results["steps"]["global_workspace"] = {
                "signal": signal["signal_type"] if signal else "filtered",
                "saliency": signal["saliency"] if signal else 0,
                "has_emergency": ctx.get("emergency_pending", False),
                "focus": ctx.get("focus", {}).get("event_type") if ctx.get("focus") else None,
            }
            log_step("global_workspace", results["steps"]["global_workspace"])
        except Exception as e:
            results["steps"]["global_workspace"] = {"error": str(e)[:100]}

    # Step 13: Homeostasis (稳态系统) — regulate resources
    if HOMEOSTASIS_AVAILABLE:
        try:
            hs = Homeostasis()
            hs_results = hs.regulate()
            abnormal = [k for k, v in hs_results.items() if v.get("status") not in ("normal", "unavailable")]
            results["steps"]["homeostasis"] = {
                "regulated": len(hs_results),
                "abnormal": abnormal,
                "abnormal_count": len(abnormal),
            }
            log_step("homeostasis", results["steps"]["homeostasis"])
        except Exception as e:
            results["steps"]["homeostasis"] = {"error": str(e)[:100]}

    # Step 14: Evolution (进化系统) — evolve skills every 10 cycles
    if EVOLUTION_AVAILABLE and cycle_number > 0 and cycle_number % 10 == 0:
        try:
            engine = EvolutionEngine()
            evo_result = engine.evolve_generation()
            results["steps"]["evolution"] = {
                "generation": evo_result["generation"],
                "best_fitness": evo_result["best_fitness"],
            }
            log_step("evolution", results["steps"]["evolution"])
        except Exception as e:
            results["steps"]["evolution"] = {"error": str(e)[:100]}

    # Step 15: Sleep Consolidation (记忆系统) — consolidate every 5 cycles
    if SLEEP_AVAILABLE and cycle_number > 0 and cycle_number % 5 == 0:
        try:
            sc = SleepConsolidator()
            sleep_result = sc.consolidate()
            results["steps"]["sleep_consolidation"] = {
                "replayed": sleep_result["replayed"],
                "integrated": sleep_result["integrated"],
                "cleaned": sleep_result["cleaned"],
            }
            log_step("sleep_consolidation", results["steps"]["sleep_consolidation"])
        except Exception as e:
            results["steps"]["sleep_consolidation"] = {"error": str(e)[:100]}

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
    print(f"[unified-loop] Starting v5.0 (interval={interval}s, dry_run={dry_run})")
    print(f"[unified-loop] Systems: cognitive={COGNITIVE_AVAILABLE} workspace={GLOBAL_WORKSPACE_AVAILABLE} "
          f"homeostasis={HOMEOSTASIS_AVAILABLE} evolution={EVOLUTION_AVAILABLE} sleep={SLEEP_AVAILABLE}")

    try:
        while True:
            cycle += 1
            print(f"\n[unified-loop] Cycle {cycle} starting...")
            result = run_cycle(dry_run=dry_run, cycle_number=cycle)

            # Summary
            steps = result.get("steps", {})
            systems = result.get("systems_active", {})
            print(f"[unified-loop] Cycle {cycle} done in {result['duration_seconds']}s:")
            print(f"  [感觉] Environment: CPU={steps.get('environment', {}).get('cpu', 'N/A')}%")
            print(f"  [神经] Cognitive: {steps.get('cognitive_tick', {}).get('status', 'N/A')}")
            print(f"  [内分泌] Workspace: signal={steps.get('global_workspace', {}).get('signal', 'N/A')}")
            print(f"  [记忆] Opportunities: {steps.get('opportunities', {}).get('found', 0)}")
            print(f"  [自主神经] Goals: {steps.get('goals', {}).get('generated', 0)}")
            print(f"  [免疫] Patrol: detected={steps.get('immune', {}).get('detected', 0)} fixed={steps.get('immune', {}).get('fixed', 0)}")
            print(f"  [稳态] Abnormal: {steps.get('homeostasis', {}).get('abnormal_count', 0)}")
            if "evolution" in steps:
                print(f"  [进化] Gen {steps['evolution'].get('generation', '?')}: fitness={steps['evolution'].get('best_fitness', '?')}")
            if "sleep_consolidation" in steps:
                print(f"  [睡眠] Consolidated: replayed={steps['sleep_consolidation'].get('replayed', 0)} cleaned={steps['sleep_consolidation'].get('cleaned', 0)}")

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
        result = run_cycle(dry_run=args.dry_run, cycle_number=1)
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
