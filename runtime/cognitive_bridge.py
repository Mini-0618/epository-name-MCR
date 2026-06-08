"""
Cognitive Bridge — connects mcr-runtime cognitive kernel to ECOSYSTEM.

Imports memory, prediction, world model, and cognitive loop from mcr-runtime
and exposes them through simple functions callable by mcr-os.ps1.

Bridge strategy: sys.path import, no code duplication.
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime

# --- Path setup ---
ECOSYSTEM_ROOT = Path(__file__).parent.parent
MCR_RUNTIME_ROOT = ECOSYSTEM_ROOT / "core" / "mcr-runtime"
WAL_DIR = ECOSYSTEM_ROOT / "runtime" / ".wal"
COGNITIVE_DIR = WAL_DIR / "cognitive"

# Ensure mcr-runtime is importable
if str(MCR_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(MCR_RUNTIME_ROOT))

# Ensure directories exist
COGNITIVE_DIR.mkdir(parents=True, exist_ok=True)

# --- Module availability check ---
_MODULES = {}

def _try_import(name, import_fn):
    try:
        mod = import_fn()
        _MODULES[name] = {"status": "ok", "module": mod}
        return mod
    except Exception as e:
        _MODULES[name] = {"status": "error", "error": str(e)[:120]}
        return None

# Import all cognitive modules
MemoryRetriever = _try_import("memory_retriever", lambda: __import__("runtime.memory_retriever", fromlist=["MemoryRetriever"]).MemoryRetriever)
PredictionTracker = _try_import("prediction_tracker", lambda: __import__("runtime.prediction_tracker", fromlist=["PredictionTracker"]).PredictionTracker)
WorldModel = _try_import("world_model", lambda: __import__("runtime.world_model", fromlist=["WorldModel"]).WorldModel)
CognitiveLoop = _try_import("cognitive_loop", lambda: __import__("runtime.cognitive_loop", fromlist=["CognitiveLoop"]).CognitiveLoop)
SelfImprove = _try_import("self_improve", lambda: __import__("runtime.self_improve", fromlist=["SelfImprove"]).SelfImprove)
TierManager = _try_import("tier_manager", lambda: __import__("runtime.tier_manager", fromlist=["TierManager"]).TierManager)
MCRRuntimeEngine = _try_import("engine", lambda: __import__("runtime.engine", fromlist=["MCRRuntimeEngine"]).MCRRuntimeEngine)
SystemState = _try_import("state", lambda: __import__("runtime.state", fromlist=["SystemState"]).SystemState)


COGNITIVE_WAL = str(COGNITIVE_DIR / "cognitive_wal.jsonl")

def _get_engine():
    """Create a fresh MCRRuntimeEngine with cognitive-specific WAL."""
    if MCRRuntimeEngine is None:
        return None
    return MCRRuntimeEngine(wal_path=COGNITIVE_WAL)


def _get_cognitive_loop(safety_mode=True):
    """Create a CognitiveLoop with cognitive WAL."""
    if CognitiveLoop is None:
        return None
    return CognitiveLoop(wal_path=COGNITIVE_WAL, safety_mode=safety_mode)


# ===== CLI Commands =====

def cmd_status():
    """Show cognitive module readiness."""
    result = {"timestamp": datetime.now().isoformat(), "modules": {}}
    for name, info in _MODULES.items():
        result["modules"][name] = info["status"]

    ok_count = sum(1 for v in _MODULES.values() if v["status"] == "ok")
    total = len(_MODULES)
    result["summary"] = f"{ok_count}/{total} modules ready"

    # Check WAL existence
    wal_path = ECOSYSTEM_ROOT / "runtime" / "events.jsonl"
    result["wal_exists"] = wal_path.exists()
    result["wal_path"] = str(wal_path)
    if wal_path.exists():
        result["wal_size_kb"] = round(wal_path.stat().st_size / 1024, 1)

    # Check cognitive data dir
    result["cognitive_dir"] = str(COGNITIVE_DIR)
    result["cognitive_dir_exists"] = COGNITIVE_DIR.exists()

    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_store(text, namespace="default"):
    """Store a memory entry via engine.emit."""
    engine = _get_engine()
    if engine is None:
        print(json.dumps({"error": "Engine not available"}))
        return

    import uuid
    memory_id = str(uuid.uuid4())[:8]
    event = engine.emit(
        event_type="memory_store",
        memory_id=memory_id,
        coaccess_group_id=namespace,
        payload={"text": text, "namespace": namespace, "timestamp": datetime.now().isoformat()}
    )
    result = {
        "action": "store",
        "text": text,
        "namespace": namespace,
        "memory_id": memory_id,
        "status": "stored",
        "event_type": event.event_type if event else "unknown"
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_query(text, limit=5):
    """Query memory via engine.recall."""
    engine = _get_engine()
    if engine is None:
        print(json.dumps({"error": "Engine not available"}))
        return

    results = engine.recall(query=text)

    output = {
        "action": "query",
        "query": text,
        "results": results,
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


def cmd_predict(claim):
    """Make a prediction using WorldModel and record it."""
    if WorldModel is None:
        print(json.dumps({"error": "WorldModel not available"}))
        return

    wm = WorldModel(
        action_log_path=str(COGNITIVE_DIR / "action_log.jsonl"),
        world_state_path=str(COGNITIVE_DIR / "world_state.json")
    )
    task = {"command": claim, "action_type": "prediction"}
    prediction = wm.predict(task)

    # Also record to prediction tracker for later verification
    tracker_log = str(COGNITIVE_DIR / "predictions.jsonl")
    import pathlib
    pathlib.Path(tracker_log).parent.mkdir(parents=True, exist_ok=True)
    with open(tracker_log, "a", encoding="utf-8") as f:
        entry = {
            "claim": claim,
            "predicted_prob": prediction.success_probability,
            "risk_level": prediction.risk_level,
            "confidence": prediction.confidence,
            "timestamp": datetime.now().isoformat(),
            "verified": False
        }
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    result = {
        "action": "predict",
        "claim": claim,
        "prediction": {
            "success_probability": prediction.success_probability,
            "risk_level": prediction.risk_level,
            "confidence": prediction.confidence,
            "warning": prediction.warning
        },
        "status": "recorded",
        "log": tracker_log
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_gate(action):
    """Gate an action through WorldModel."""
    if WorldModel is None:
        print(json.dumps({"error": "WorldModel not available"}))
        return

    wm = WorldModel(
        action_log_path=str(COGNITIVE_DIR / "action_log.jsonl"),
        world_state_path=str(COGNITIVE_DIR / "world_state.json")
    )
    # WorldModel.predict expects a dict with "command" key
    task = {"command": action, "action_type": "cli"}
    prediction = wm.predict(task)
    decision = wm.gate(prediction)

    result = {
        "action": "gate",
        "target_action": action,
        "prediction": {
            "success_probability": prediction.success_probability,
            "risk_level": prediction.risk_level,
            "confidence": prediction.confidence,
            "warning": prediction.warning
        },
        "decision": {
            "verdict": decision.decision,
            "reason": decision.reason,
            "adjusted_risk_max": decision.adjusted_risk_max
        }
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_tick(max_ticks=1):
    """Run cognitive loop ticks."""
    loop = _get_cognitive_loop(safety_mode=True)
    if loop is None:
        print(json.dumps({"error": "CognitiveLoop not available"}))
        return

    loop.run(max_ticks=max_ticks)
    result = {
        "action": "tick",
        "ticks_run": max_ticks,
        "status": "completed"
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_improve():
    """Run self-improvement cycle."""
    if SelfImprove is None:
        print(json.dumps({"error": "SelfImprove not available"}))
        return

    wm = WorldModel(
        action_log_path=str(COGNITIVE_DIR / "action_log.jsonl"),
        world_state_path=str(COGNITIVE_DIR / "world_state.json")
    )
    improver = SelfImprove(
        wal_path=COGNITIVE_WAL,
        world_model=wm
    )
    result_data = improver.calibrate()

    result = {
        "action": "improve",
        "status": "completed",
        "calibration": result_data
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_reflect():
    """Run full reflection cycle: analyze failures + detect patterns + correct."""
    # Import reflection modules
    failure_analyzer_path = ECOSYSTEM_ROOT / "runtime" / "failure_analyzer.py"
    pattern_detector_path = ECOSYSTEM_ROOT / "runtime" / "pattern_detector.py"
    self_correction_path = ECOSYSTEM_ROOT / "runtime" / "self_correction.py"

    result = {
        "action": "reflect",
        "timestamp": datetime.now().isoformat(),
        "steps": {}
    }

    # Step 1: Analyze failures
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("failure_analyzer", failure_analyzer_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        failure_report = mod.analyze(200)
        result["steps"]["failure_analysis"] = {
            "total_failures": failure_report.get("total_failures", 0),
            "failure_rate": failure_report.get("failure_rate", 0),
            "types": failure_report.get("failure_types", {})
        }
    except Exception as e:
        result["steps"]["failure_analysis"] = {"error": str(e)[:100]}

    # Step 2: Detect patterns
    try:
        spec = importlib.util.spec_from_file_location("pattern_detector", pattern_detector_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        pattern_report = mod.analyze(500)
        result["steps"]["pattern_detection"] = {
            "high_frequency": pattern_report.get("high_frequency_events", {}),
            "idle_periods": len(pattern_report.get("idle_periods", [])),
            "error_clusters": len(pattern_report.get("error_clusters", []))
        }
    except Exception as e:
        result["steps"]["pattern_detection"] = {"error": str(e)[:100]}

    # Step 3: Self-correction
    try:
        spec = importlib.util.spec_from_file_location("self_correction", self_correction_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        correction_report = mod.run_corrections()
        result["steps"]["self_correction"] = {
            "fixes_applied": correction_report.get("fixes_applied", 0),
            "fixes": correction_report.get("fixes", [])
        }
    except Exception as e:
        result["steps"]["self_correction"] = {"error": str(e)[:100]}

    # Summary
    total_issues = (
        result["steps"]["failure_analysis"].get("total_failures", 0) +
        result["steps"]["pattern_detection"].get("error_clusters", 0) +
        result["steps"]["self_correction"].get("fixes_applied", 0)
    )
    result["summary"] = f"Reflection complete. {total_issues} issues found and addressed."
    result["status"] = "completed"

    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_report():
    """Generate cognitive status report."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "modules": {},
        "data_files": {}
    }

    # Module status
    for name, info in _MODULES.items():
        report["modules"][name] = info["status"]

    # Data files
    for f in COGNITIVE_DIR.glob("*.jsonl"):
        report["data_files"][f.name] = {
            "size_kb": round(f.stat().st_size / 1024, 1),
            "lines": sum(1 for _ in f.open(encoding="utf-8")) if f.exists() else 0
        }
    for f in COGNITIVE_DIR.glob("*.json"):
        report["data_files"][f.name] = {
            "size_kb": round(f.stat().st_size / 1024, 1)
        }

    # WAL info
    wal_path = ECOSYSTEM_ROOT / "runtime" / "events.jsonl"
    if wal_path.exists():
        report["wal"] = {
            "path": str(wal_path),
            "size_kb": round(wal_path.stat().st_size / 1024, 1)
        }

    print(json.dumps(report, indent=2, ensure_ascii=False))


# ===== CLI Entry Point =====

def main():
    parser = argparse.ArgumentParser(description="MCR Cognitive Bridge")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Show cognitive module readiness")

    p_store = sub.add_parser("store", help="Store a memory entry")
    p_store.add_argument("text", help="Text to store")
    p_store.add_argument("--namespace", default="default")

    p_query = sub.add_parser("query", help="Query memory")
    p_query.add_argument("text", help="Search query")
    p_query.add_argument("--limit", type=int, default=5)

    p_predict = sub.add_parser("predict", help="Record a prediction")
    p_predict.add_argument("claim", help="Prediction claim")

    p_gate = sub.add_parser("gate", help="Gate an action through WorldModel")
    p_gate.add_argument("action", help="Action to evaluate")

    p_tick = sub.add_parser("tick", help="Run cognitive loop")
    p_tick.add_argument("--max-ticks", type=int, default=1)

    sub.add_parser("improve", help="Run self-improvement cycle")
    sub.add_parser("reflect", help="Run full reflection cycle")
    sub.add_parser("report", help="Generate cognitive report")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status()
    elif args.command == "store":
        cmd_store(args.text, args.namespace)
    elif args.command == "query":
        cmd_query(args.text, args.limit)
    elif args.command == "predict":
        cmd_predict(args.claim)
    elif args.command == "gate":
        cmd_gate(args.action)
    elif args.command == "tick":
        cmd_tick(args.max_ticks)
    elif args.command == "improve":
        cmd_improve()
    elif args.command == "reflect":
        cmd_reflect()
    elif args.command == "report":
        cmd_report()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
