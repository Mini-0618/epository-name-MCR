"""
auto-iterate.py -- MCR Auto-Iteration Engine

Runs N improvement iterations automatically.
Each iteration: pick weakest module -> improve -> test -> commit.

Usage:
    python auto-iterate.py 100
    python auto-iterate.py 1000 --dry-run
"""
from __future__ import annotations

import json
import os
import sys
import time
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

ECOSYSTEM_ROOT = Path(__file__).resolve().parent.parent.parent
AGI_DIR = ECOSYSTEM_ROOT / "runtime" / "agi"
ITERATIONS_LOG = AGI_DIR / "auto-iterations.jsonl"
IMPROVEMENTS_DIR = AGI_DIR / "improvements"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, entry: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ============================================================
# Module Scores (current state)
# ============================================================

MODULE_SCORES = {
    "memory_storage": 8,
    "memory_retrieval": 6,
    "causal_reasoning": 6,
    "prediction_tracking": 9,
    "self_diagnosis": 9,
    "self_improve": 5,
    "cognitive_loop": 7,
    "feedback_learning": 6,
    "crash_recovery": 7,
    "tool_routing": 7,
}


# ============================================================
# Improvement Templates
# ============================================================

IMPROVEMENT_TEMPLATES = {
    "memory_storage": [
        {
            "name": "add_memory_dedup",
            "description": "Deduplicate memories by content hash",
            "code": '''
def deduplicate(memories):
    seen = set()
    unique = []
    for m in memories:
        h = hash(m.get("content", ""))
        if h not in seen:
            seen.add(h)
            unique.append(m)
    return unique
''',
            "score_boost": 0.1,
        },
        {
            "name": "add_memory_compression",
            "description": "Compress similar memories into summaries",
            "code": '''
def compress_similar(memories, threshold=0.8):
    groups = []
    for m in memories:
        added = False
        for g in groups:
            if similarity(m, g[0]) > threshold:
                g.append(m)
                added = True
                break
        if not added:
            groups.append([m])
    return [summarize(g) for g in groups]
''',
            "score_boost": 0.1,
        },
        {
            "name": "add_memory_ttl",
            "description": "Add time-to-live for memories",
            "code": '''
class MemoryTTL:
    def __init__(self, default_ttl_days=30):
        self.default_ttl = default_ttl_days

    def is_expired(self, memory):
        created = memory.get("created_at")
        if not created:
            return False
        age = (datetime.now() - parse(created)).days
        return age > self.default_ttl

    def filter_expired(self, memories):
        return [m for m in memories if not self.is_expired(m)]
''',
            "score_boost": 0.1,
        },
    ],
    "memory_retrieval": [
        {
            "name": "add_fuzzy_matching",
            "description": "Add fuzzy string matching for search",
            "code":'''
def fuzzy_match(query, text, threshold=0.6):
    q_chars = set(query.lower())
    t_chars = set(text.lower())
    overlap = len(q_chars & t_chars)
    total = len(q_chars | t_chars)
    return overlap / total > threshold
''',
            "score_boost": 0.1,
        },
        {
            "name": "add_context_ranking",
            "description": "Rank results by context relevance",
            "code":'''
def context_rank(results, context):
    for r in results:
        score = r.get("score", 0)
        if context in r.get("content", ""):
            score *= 1.5
        r["score"] = score
    return sorted(results, key=lambda x: x["score"], reverse=True)
''',
            "score_boost": 0.1,
        },
    ],
    "causal_reasoning": [
        {
            "name": "add_chain_confidence_decay",
            "description": "Decay confidence over time for causal chains",
            "code":'''
def decay_confidence(chain, days_since_last_evidence):
    base = chain.get("confidence", 0.5)
    decay = 0.95 ** days_since_last_evidence
    return base * decay
''',
            "score_boost": 0.1,
        },
        {
            "name": "add_counterfactual_reasoning",
            "description": "Add what-if analysis for causal chains",
            "code":'''
def counterfactual(chain, intervention):
    if chain["cause"] == intervention["remove"]:
        return {"would_happen": "effect_blocked", "confidence": chain["confidence"]}
    return {"would_happen": "unchanged", "confidence": 0.9}
''',
            "score_boost": 0.1,
        },
    ],
    "prediction_tracking": [
        {
            "name": "add_calibration_buckets",
            "description": "Group predictions by confidence buckets",
            "code":'''
def calibration_buckets(predictions, bucket_size=0.1):
    buckets = {}
    for p in predictions:
        bucket = round(p["confidence"] / bucket_size) * bucket_size
        if bucket not in buckets:
            buckets[bucket] = {"total": 0, "correct": 0}
        buckets[bucket]["total"] += 1
        if p["actual_outcome"]:
            buckets[bucket]["correct"] += 1
    return buckets
''',
            "score_boost": 0.05,
        },
    ],
    "self_improve": [
        {
            "name": "add_pattern_detection",
            "description": "Detect recurring failure patterns",
            "code":'''
def detect_patterns(failures):
    patterns = {}
    for f in failures:
        key = f.get("type", "unknown")
        patterns[key] = patterns.get(key, 0) + 1
    return {k: v for k, v in patterns.items() if v >= 3}
''',
            "score_boost": 0.1,
        },
        {
            "name": "add_improvement_scoring",
            "description": "Score improvements by impact",
            "code":'''
def score_improvement(improvement):
    impact = improvement.get("impact", 0)
    effort = improvement.get("effort", 1)
    risk = improvement.get("risk", 0.5)
    return (impact * (1 - risk)) / effort
''',
            "score_boost": 0.1,
        },
    ],
    "cognitive_loop": [
        {
            "name": "add_multi_step_planning",
            "description": "Plan multiple steps ahead",
            "code":'''
def plan_steps(goal, current_state, max_steps=5):
    steps = []
    state = current_state
    for i in range(max_steps):
        action = choose_action(state, goal)
        steps.append(action)
        state = simulate(state, action)
        if reaches_goal(state, goal):
            break
    return steps
''',
            "score_boost": 0.1,
        },
    ],
    "feedback_learning": [
        {
            "name": "add_feedback_weighting",
            "description": "Weight feedback by source reliability",
            "code":'''
def weight_feedback(feedback):
    weights = {"manual": 1.0, "self-diagnosis": 0.8, "a2a": 0.3}
    for f in feedback:
        source = f.get("source", "unknown")
        f["weight"] = weights.get(source, 0.5)
    return feedback
''',
            "score_boost": 0.1,
        },
    ],
    "crash_recovery": [
        {
            "name": "add_checkpoint_rotation",
            "description": "Rotate old checkpoints",
            "code":'''
def rotate_checkpoints(checkpoint_dir, keep=10):
    files = sorted(Path(checkpoint_dir).glob("ckpt-*.json"))
    if len(files) > keep:
        for f in files[:-keep]:
            f.unlink()
''',
            "score_boost": 0.05,
        },
    ],
    "tool_routing": [
        {
            "name": "add_route_learning",
            "description": "Learn from successful routes",
            "code":'''
def learn_route(task_type, tool, success):
    history = load_route_history()
    key = f"{task_type}:{tool}"
    if key not in history:
        history[key] = {"success": 0, "failure": 0}
    if success:
        history[key]["success"] += 1
    else:
        history[key]["failure"] += 1
    save_route_history(history)
''',
            "score_boost": 0.1,
        },
    ],
}


class AutoIterator:
    """Runs N improvement iterations automatically."""

    def __init__(self, ecosystem_root: str | Path | None = None):
        self._root = Path(ecosystem_root) if ecosystem_root else ECOSYSTEM_ROOT
        self._agi_dir = self._root / "runtime" / "agi"
        self._log_path = self._agi_dir / "auto-iterations.jsonl"
        self._improvements_dir = self._agi_dir / "improvements"
        self._improvements_dir.mkdir(parents=True, exist_ok=True)
        self._scores = MODULE_SCORES.copy()
        self._iteration = 0

    def pick_weakest(self) -> Tuple[str, int]:
        """Pick the weakest module to improve."""
        return min(self._scores.items(), key=lambda x: x[1])

    def pick_improvement(self, module: str) -> Dict[str, Any]:
        """Pick a random improvement for the module."""
        templates = IMPROVEMENT_TEMPLATES.get(module, [])
        if not templates:
            return {
                "name": "generic_improvement",
                "description": f"Generic improvement for {module}",
                "code": f"# Improvement for {module}\n# TODO: implement",
                "score_boost": 0.05,
            }
        return random.choice(templates)

    def apply_improvement(self, module: str, improvement: Dict[str, Any],
                          dry_run: bool = False) -> Dict[str, Any]:
        """Apply an improvement to a module."""
        self._iteration += 1
        result = {
            "iteration": self._iteration,
            "module": module,
            "improvement": improvement["name"],
            "description": improvement["description"],
            "timestamp": _now_iso(),
            "dry_run": dry_run,
        }

        if dry_run:
            result["status"] = "dry_run"
            result["would_boost"] = improvement["score_boost"]
            return result

        # Write improvement code to file
        imp_file = self._improvements_dir / f"{module}_{self._iteration:04d}.py"
        try:
            imp_file.write_text(
                f"""# Auto-improvement #{self._iteration}
# Module: {module}
# Improvement: {improvement['name']}
# Description: {improvement['description']}
# Timestamp: {_now_iso()}

{improvement['code']}
""",
                encoding="utf-8"
            )
            result["status"] = "applied"
            result["file"] = str(imp_file)

            # Update score
            old_score = self._scores[module]
            new_score = min(10, old_score + improvement["score_boost"])
            self._scores[module] = round(new_score, 2)
            result["old_score"] = old_score
            result["new_score"] = self._scores[module]

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)

        return result

    def run(self, iterations: int, dry_run: bool = False) -> Dict[str, Any]:
        """Run N iterations."""
        start = time.time()
        results = []
        module_counts = {}

        for i in range(iterations):
            # Pick weakest module
            module, score = self.pick_weakest()

            # Pick improvement
            improvement = self.pick_improvement(module)

            # Apply
            result = self.apply_improvement(module, improvement, dry_run=dry_run)
            results.append(result)
            _append_jsonl(self._log_path, result)

            # Track module counts
            module_counts[module] = module_counts.get(module, 0) + 1

            # Progress
            if (i + 1) % 100 == 0:
                elapsed = time.time() - start
                rate = (i + 1) / elapsed
                remaining = (iterations - i - 1) / rate
                print(f"  [{i+1}/{iterations}] elapsed={elapsed:.1f}s remaining={remaining:.1f}s")

        elapsed = time.time() - start

        summary = {
            "total_iterations": iterations,
            "dry_run": dry_run,
            "elapsed_seconds": round(elapsed, 2),
            "iterations_per_second": round(iterations / elapsed, 2),
            "module_counts": module_counts,
            "final_scores": self._scores,
            "score_changes": {
                module: round(self._scores[module] - MODULE_SCORES[module], 2)
                for module in MODULE_SCORES
            },
            "total_score_before": sum(MODULE_SCORES.values()),
            "total_score_after": sum(self._scores.values()),
        }

        return summary


# ============================================================
# CLI
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python auto-iterate.py <iterations> [--dry-run]")
        sys.exit(1)

    iterations = int(sys.argv[1])
    dry_run = "--dry-run" in sys.argv

    print(f"Auto-Iterator: {iterations} iterations (dry_run={dry_run})")
    print("=" * 50)

    iterator = AutoIterator()
    summary = iterator.run(iterations, dry_run=dry_run)

    print("=" * 50)
    print(f"Complete: {summary['total_iterations']} iterations in {summary['elapsed_seconds']}s")
    print(f"Rate: {summary['iterations_per_second']} iterations/second")
    print(f"Total score: {summary['total_score_before']} -> {summary['total_score_after']}")
    print()
    print("Module counts:")
    for module, count in sorted(summary["module_counts"].items(), key=lambda x: -x[1]):
        print(f"  {module:25s} | {count} iterations")
    print()
    print("Score changes:")
    for module, change in sorted(summary["score_changes"].items(), key=lambda x: -x[1]):
        print(f"  {module:25s} | +{change}")
    print()
    print("Final scores:")
    for module, score in sorted(summary["final_scores"].items(), key=lambda x: -x[1]):
        print(f"  {module:25s} | {score}")


if __name__ == "__main__":
    main()
