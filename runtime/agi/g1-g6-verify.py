"""
g1-g6-verify.py -- G1-G6 Adaptive Memory Verification

Runs 6 gates against AdaptiveMemory to verify adaptive behavior:
  G1: System adapts - weights differ from baseline (1.0)
  G2: Routine forms - any habit pattern detected
  G3: Weights drift - max weight > 1.2 or min weight < 0.8
  G4: Bounded overhead - retrieval time < 100ms
  G5: Topology divergence - at least 2 tiers have different weights
  G6: No collapse - all weights > 0.1

Output: G1=PASS/FAIL, G2=PASS/FAIL, ... G6=PASS/FAIL
"""

import json
import os
import sys
import time
from pathlib import Path

# Add parent dir to path for import
_script_dir = str(Path(__file__).resolve().parent)
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from importlib import import_module as _imp

# Import adaptive-memory module
_am_mod = __import__("adaptive-memory")
AdaptiveMemory = _am_mod.AdaptiveMemory


def find_memory_files(ecosystem_root):
    """Find available memory JSONL files."""
    candidates = [
        os.path.join(ecosystem_root, "runtime", "memory", "life-memory.jsonl"),
        os.path.join(ecosystem_root, "runtime", "swarm", "memory.jsonl"),
    ]
    found = []
    for p in candidates:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                lines = [l for l in f if l.strip()]
            if lines:
                found.append((p, len(lines)))
    return found


def run_exercise(am, rounds=12):
    """
    Run retrieval + feedback cycles to exercise the adaptive system.
    Uses queries that target different tiers.
    """
    queries = [
        ("security lab check", True),
        ("mcr runtime status", True),
        ("multimodal creative tools", False),
        ("knowledge memory workbench", True),
        ("security lab check", True),
        ("security lab check", True),
        ("security lab check", True),
        ("security lab check", True),
        ("security lab check", True),
        ("security lab check", True),
        ("goals and planning", False),
        ("registry validate", True),
    ]

    for query, success in queries[:rounds]:
        results = am.retrieve(query)
        if results:
            feedback = {
                "result": "success" if success else "failure",
                "tier": results[0]["tier"],
            }
        else:
            feedback = {"result": "failure", "tier": "working"}
        am.adapt(feedback)


def verify_g1(weights):
    """G1: System adapts -- at least one weight differs from 1.0."""
    for t, w in weights.items():
        if abs(w - 1.0) > 0.001:
            return "PASS"
    return "FAIL"


def verify_g2(habits):
    """G2: Routine forms -- habit pattern detected."""
    if habits.get("pattern_detected"):
        return "PASS"
    if habits.get("streak_count", 0) >= 3:
        return "PASS"
    if habits.get("bonuses_applied", 0) > 0:
        return "PASS"
    return "FAIL"


def verify_g3(weights):
    """G3: Weights drift -- max > 1.2 or min < 0.8."""
    vals = list(weights.values())
    if max(vals) > 1.2 or min(vals) < 0.8:
        return "PASS"
    return "FAIL"


def verify_g4(retrieval_time_ms):
    """G4: Bounded overhead -- retrieval time < 100ms."""
    if retrieval_time_ms < 100:
        return "PASS"
    return "FAIL"


def verify_g5(weights):
    """G5: Topology divergence -- at least 2 tiers have different weights."""
    unique = set()
    for w in weights.values():
        unique.add(round(w, 3))
    if len(unique) >= 2:
        return "PASS"
    return "FAIL"


def verify_g6(weights):
    """G6: No collapse -- all weights > 0.1."""
    for t, w in weights.items():
        if w <= 0.1:
            return "FAIL"
    return "PASS"


def run_verification(ecosystem_root=None, output_json=True):
    """Run full G1-G6 verification and return results."""
    if ecosystem_root is None:
        ecosystem_root = str(Path(__file__).resolve().parents[2])

    memory_files = find_memory_files(ecosystem_root)
    if not memory_files:
        return {
            "G1": "FAIL", "G2": "FAIL", "G3": "FAIL",
            "G4": "FAIL", "G5": "FAIL", "G6": "FAIL",
            "error": "No memory files found",
        }

    # Use the file with most entries
    memory_path = max(memory_files, key=lambda x: x[1])[0]
    state_path = os.path.join(ecosystem_root, "runtime", "agi", "adaptive-memory-state.json")

    am = AdaptiveMemory(memory_path, state_path)

    # Exercise the system
    run_exercise(am, rounds=12)

    # Get final state
    weights = am.get_weights()
    habits = am.get_habits()

    # Measure retrieval time
    t0 = time.perf_counter()
    am.retrieve("security lab check")
    t1 = time.perf_counter()
    retrieval_time_ms = (t1 - t0) * 1000

    # Run gates
    results = {
        "G1": verify_g1(weights),
        "G2": verify_g2(habits),
        "G3": verify_g3(weights),
        "G4": verify_g4(retrieval_time_ms),
        "G5": verify_g5(weights),
        "G6": verify_g6(weights),
    }

    # Add details
    results["weights"] = {k: round(v, 4) for k, v in weights.items()}
    results["habits"] = habits
    results["retrieval_time_ms"] = round(retrieval_time_ms, 2)
    results["memory_file"] = memory_path
    results["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    pass_count = sum(1 for k, v in results.items() if k.startswith("G") and v == "PASS")
    results["summary"] = f"{pass_count}/6 gates passed"

    # Write status file
    status_path = os.path.join(ecosystem_root, "runtime", "agi", "g1-g6-status.json")
    os.makedirs(os.path.dirname(status_path), exist_ok=True)
    with open(status_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return results


def main():
    """CLI entry point."""
    ecosystem_root = str(Path(__file__).resolve().parents[2])

    results = run_verification(ecosystem_root)

    # Print summary
    gates = ["G1", "G2", "G3", "G4", "G5", "G6"]
    for g in gates:
        status = results.get(g, "FAIL")
        print(f"{g}={status}", end="  ")
    print()
    print(f"\nSummary: {results['summary']}")
    print(f"Weights: {json.dumps(results.get('weights', {}))}")
    print(f"Retrieval time: {results.get('retrieval_time_ms', 0)}ms")
    print(f"Status saved to: runtime/agi/g1-g6-status.json")

    # Exit code: 0 if all pass, 1 otherwise
    all_pass = all(results.get(g) == "PASS" for g in gates)
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
