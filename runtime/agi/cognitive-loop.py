"""
cognitive-loop.py -- ECOSYSTEM Cognitive Loop

Simplified autonomous cognitive cycle adapted from mcr-runtime.
Flow per tick: Observe -> Predict -> Gate -> Execute -> Record

Safety:
  - Only local, read-only operations allowed
  - No external commands, no destructive actions
  - PredictionTracker should_intervene() check after each tick

Reads memory via MemoryIndex, uses PredictionTracker for predictions.
Writes state to runtime/agi/cognitive-state.json.

No external dependencies. Pure Python.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Resolve sibling modules
_SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(_SCRIPT_DIR))

# Import sibling modules with hyphenated filenames
_mi_mod = __import__("memory-index")
MemoryIndex = _mi_mod.MemoryIndex

_pt_mod = __import__("prediction-tracker")
PredictionTracker = _pt_mod.PredictionTracker

# -- Paths --

DEFAULT_STATE_PATH = _SCRIPT_DIR / "cognitive-state.json"
DEFAULT_MEMORY_PATHS = [
    _SCRIPT_DIR.parent.parent / "runtime" / "swarm" / "memory.jsonl",
    _SCRIPT_DIR.parent.parent / "runtime" / "memory" / "life-memory.jsonl",
]

# -- Safety --

BLOCKED_ACTIONS = {
    "external_command", "network_request", "file_delete",
    "system_modify", "install_package", "send_email",
}

SAFE_ACTIONS = {
    "memory_search", "memory_read", "pattern_detect",
    "status_check", "reflection", "goal_propose",
    "report_generate",
}


class CognitiveLoop:
    """
    Simplified autonomous cognitive loop for ECOSYSTEM.

    Per tick:
      1. observe  -- gather context from memory index
      2. predict  -- predict outcome of proposed action
      3. gate     -- safety gate: PASS / CAUTION / BLOCK
      4. execute  -- record approved action
      5. record   -- feed back to prediction tracker

    Usage:
        loop = CognitiveLoop("/path/to/ecosystem")
        loop.run(max_ticks=1)
    """

    def __init__(self, ecosystem_root: str):
        self._root = Path(ecosystem_root)
        self._state_path = DEFAULT_STATE_PATH
        self._tick_count = 0
        self._errors: List[str] = []
        self._safety_mode = False

        # Find the best memory file
        memory_path = self._find_memory_path()
        self._memory_index = MemoryIndex(str(memory_path)) if memory_path else None

        # Prediction tracker
        tracker_path = _SCRIPT_DIR / "predictions.jsonl"
        self._tracker = PredictionTracker(str(tracker_path))

        # Load or init state
        self._state = self._load_state()

    # -- Memory path resolution --

    def _find_memory_path(self) -> Optional[Path]:
        """Find the most populated memory.jsonl file."""
        candidates = [
            self._root / "runtime" / "swarm" / "memory.jsonl",
            self._root / "runtime" / "memory" / "life-memory.jsonl",
        ]
        best_path = None
        best_count = -1
        for p in candidates:
            if p.exists():
                try:
                    count = sum(1 for line in open(p, encoding="utf-8") if line.strip())
                    if count > best_count:
                        best_count = count
                        best_path = p
                except OSError:
                    pass
        return best_path

    # -- State persistence --

    def _load_state(self) -> dict:
        if self._state_path.exists():
            try:
                with open(self._state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {
            "schema_version": "0.1",
            "total_ticks": 0,
            "last_tick_at": None,
            "safety_mode": False,
            "last_observe_query": "",
            "last_gate_decision": None,
            "actions_executed": 0,
            "actions_blocked": 0,
            "errors": [],
        }

    def _save_state(self):
        self._state["total_ticks"] = self._tick_count
        self._state["last_tick_at"] = datetime.now(timezone.utc).isoformat()
        self._state["safety_mode"] = self._safety_mode
        self._state["errors"] = self._errors[-20:]  # keep last 20
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._state_path, "w", encoding="utf-8") as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
        except OSError as e:
            self._errors.append(f"save_state error: {e}")

    # -- Cognitive steps --

    def observe(self, query: str = "") -> List[Dict[str, Any]]:
        """
        Step 1: Gather context from memory.

        Args:
            query: search query. If empty, returns recent memories.

        Returns:
            List of memory entries with content, tier, score.
        """
        if not self._memory_index:
            return []
        if not query:
            # Auto-generate query from recent activity patterns
            query = self._auto_query()
        self._state["last_observe_query"] = query
        results = self._memory_index.search(query, limit=5)
        return results

    def _auto_query(self) -> str:
        """Generate a query from recent state patterns."""
        last_q = self._state.get("last_observe_query", "")
        if last_q:
            return last_q
        return "ecosystem status"

    def predict(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 2: Predict outcome of an action.

        Uses PredictionTracker calibration to estimate success probability.

        Args:
            action: dict with action_type, description, etc.

        Returns:
            Prediction dict with success_probability, risk_level, confidence.
        """
        action_type = action.get("action_type", "unknown")

        # Block dangerous actions outright
        if action_type in BLOCKED_ACTIONS:
            return {
                "success_probability": 0.0,
                "risk_level": "critical",
                "confidence": 0.95,
                "warning": f"action type '{action_type}' is blocked by safety policy",
            }

        # Use tracker stats to estimate baseline
        stats = self._tracker.get_stats()
        brier = stats.get("brier_score", 0.25)
        accuracy = stats.get("accuracy", 0.5)

        # Safe actions get high probability
        if action_type in SAFE_ACTIONS:
            base_prob = 0.85
        else:
            base_prob = max(0.3, accuracy)

        # Adjust by brier: worse calibration = lower confidence
        confidence = max(0.3, 1.0 - brier)

        return {
            "success_probability": round(base_prob, 3),
            "risk_level": "low" if base_prob > 0.7 else "medium" if base_prob > 0.4 else "high",
            "confidence": round(confidence, 3),
            "warning": None,
        }

    def gate(self, prediction: Dict[str, Any], confidence: float = 0.5) -> Dict[str, Any]:
        """
        Step 3: Safety gate.

        Returns:
            {"decision": "PASS"|"CAUTION"|"BLOCK", "reason": str}
        """
        prob = prediction.get("success_probability", 0.5)
        risk = prediction.get("risk_level", "medium")
        warning = prediction.get("warning")

        if risk == "critical" or prob < 0.1:
            decision = "BLOCK"
            reason = warning or f"critical risk (prob={prob:.2f})"
        elif risk == "high" or prob < 0.4 or confidence < 0.3:
            decision = "CAUTION"
            reason = warning or f"high risk or low confidence (prob={prob:.2f}, conf={confidence:.2f})"
        elif self._safety_mode and prob < 0.7:
            decision = "CAUTION"
            reason = f"safety_mode active, elevated threshold (prob={prob:.2f})"
        else:
            decision = "PASS"
            reason = f"acceptable risk (prob={prob:.2f}, risk={risk})"

        result = {"decision": decision, "reason": reason}
        self._state["last_gate_decision"] = result
        return result

    def decide(self, observations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Make a real decision based on observations.

        Analyzes patterns in observations and decides what to do next.
        Returns a decision with action, reasoning, and confidence.
        """
        if not observations:
            return {
                "action": "wait",
                "reasoning": "No observations to analyze",
                "confidence": 0.0,
            }

        # Analyze observation patterns
        patterns = {
            "success_count": 0,
            "failure_count": 0,
            "stale_count": 0,
            "risk_mentions": 0,
        }

        for obs in observations:
            content = obs.get("content", "").lower()
            if "pass" in content or "success" in content:
                patterns["success_count"] += 1
            elif "fail" in content or "error" in content:
                patterns["failure_count"] += 1
            if "stale" in content or "old" in content:
                patterns["stale_count"] += 1
            if "risk" in content or "vuln" in content:
                patterns["risk_mentions"] += 1

        # Decision logic
        if patterns["failure_count"] > 2:
            return {
                "action": "investigate_failures",
                "reasoning": f"Found {patterns['failure_count']} failures in observations",
                "confidence": 0.8,
                "patterns": patterns,
            }
        elif patterns["risk_mentions"] > 0:
            return {
                "action": "assess_risk",
                "reasoning": f"Found {patterns['risk_mentions']} risk mentions",
                "confidence": 0.7,
                "patterns": patterns,
            }
        elif patterns["stale_count"] > 2:
            return {
                "action": "refresh_memory",
                "reasoning": f"Found {patterns['stale_count']} stale entries",
                "confidence": 0.6,
                "patterns": patterns,
            }
        else:
            return {
                "action": "continue",
                "reasoning": "No significant patterns detected",
                "confidence": 0.5,
                "patterns": patterns,
            }

    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 4: Execute an approved action.

        For ECOSYSTEM, "execution" means recording the action and its
        predicted outcome. Actual side-effects happen elsewhere.

        Returns:
            {"executed": bool, "action_type": str, "result": str}
        """
        action_type = action.get("action_type", "unknown")

        if action_type in BLOCKED_ACTIONS:
            self._state["actions_blocked"] = self._state.get("actions_blocked", 0) + 1
            return {
                "executed": False,
                "action_type": action_type,
                "result": "blocked by safety policy",
            }

        self._state["actions_executed"] = self._state.get("actions_executed", 0) + 1
        return {
            "executed": True,
            "action_type": action_type,
            "result": "recorded",
        }

    def record(self, action: Dict[str, Any], prediction: Dict[str, Any],
               outcome: bool, description: str = "") -> Dict[str, Any]:
        """
        Step 5: Record prediction vs outcome to tracker.

        Args:
            action: the action dict
            prediction: the prediction dict
            outcome: True if action succeeded, False otherwise
            description: human-readable description

        Returns:
            The recorded entry.
        """
        desc = description or action.get("description", action.get("action_type", "unknown"))
        prob = prediction.get("success_probability", 0.5)
        entry = self._tracker.record(desc, prob, outcome, metadata={
            "action_type": action.get("action_type"),
            "tick": self._tick_count,
        })
        return entry

    # -- Full tick --

    def tick(self) -> Dict[str, Any]:
        """
        Run one cognitive cycle.

        Returns:
            Tick summary with observe results, prediction, gate decision.
        """
        self._tick_count += 1

        # 1. Observe
        observations = self.observe()
        obs_summary = f"{len(observations)} memories retrieved"

        # 2. Decide what to do based on observations
        decision = self.decide(observations)

        # 3. Propose action based on observations and decision
        action = self._propose_action(observations)
        action["decision"] = decision

        # 4. Predict
        prediction = self.predict(action)

        # 4. Gate
        gate_result = self.gate(prediction, prediction.get("confidence", 0.5))

        # 5. Execute (if not blocked)
        execution = None
        if gate_result["decision"] != "BLOCK":
            execution = self.execute(action)
        else:
            self._state["actions_blocked"] = self._state.get("actions_blocked", 0) + 1

        # 6. Safety check via tracker
        if not self._safety_mode and self._tracker.should_intervene():
            self._safety_mode = True
            self._errors.append("safety_mode activated: prediction error too high")

        # Save state
        self._save_state()

        return {
            "tick": self._tick_count,
            "observations": obs_summary,
            "observation_count": len(observations),
            "decision": decision,
            "action": action,
            "prediction": prediction,
            "gate": gate_result,
            "execution": execution,
            "safety_mode": self._safety_mode,
        }

    def _propose_action(self, observations: List[Dict]) -> Dict[str, Any]:
        """Propose an action based on current observations and tool router."""
        if not observations:
            return {
                "action_type": "memory_search",
                "description": "search for recent ecosystem activity",
            }

        # Analyze memory patterns
        tier_counts: Dict[str, int] = {}
        for obs in observations:
            tier = obs.get("tier", "episodic")
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

        # If mostly semantic, propose a reflection
        if tier_counts.get("semantic", 0) > len(observations) * 0.6:
            return {
                "action_type": "reflection",
                "description": "reflect on semantic memory patterns",
            }

        # If low-access memories, propose a pattern detection
        avg_access = sum(o.get("access_count", 0) for o in observations) / max(len(observations), 1)
        if avg_access < 2:
            return {
                "action_type": "pattern_detect",
                "description": "detect patterns in under-explored memories",
            }

        # Default: status check
        return {
            "action_type": "status_check",
            "description": "check ecosystem health from recent observations",
        }

    # -- Run loop --

    def run(self, max_ticks: int = 1) -> Dict[str, Any]:
        """
        Run N cognitive cycles.

        Args:
            max_ticks: number of ticks to run (default 1)

        Returns:
            Summary dict with tick results.
        """
        start = time.time()
        results = []

        for _ in range(max_ticks):
            try:
                result = self.tick()
                results.append(result)
            except Exception as e:
                self._errors.append(f"tick error: {e}")
                results.append({"error": str(e)})

        elapsed = round(time.time() - start, 3)

        summary = {
            "ticks_run": len(results),
            "elapsed_seconds": elapsed,
            "total_ticks": self._tick_count,
            "safety_mode": self._safety_mode,
            "actions_executed": self._state.get("actions_executed", 0),
            "actions_blocked": self._state.get("actions_blocked", 0),
            "prediction_stats": self._tracker.get_stats(),
            "errors": self._errors[-5:],
            "last_tick": results[-1] if results else None,
        }
        return summary

    def get_status(self) -> Dict[str, Any]:
        """Return current cognitive loop status."""
        return {
            "tick_count": self._tick_count,
            "safety_mode": self._safety_mode,
            "state": self._state,
            "tracker_stats": self._tracker.get_stats() if self._tracker else None,
            "memory_index_stats": self._memory_index.get_stats() if self._memory_index else None,
            "errors": self._errors[-10:],
        }


# =============================================================================
# CLI
# =============================================================================

def main():
    """CLI entry point."""
    args = sys.argv[1:]
    ecosystem_root = str(_SCRIPT_DIR.parent.parent)

    if not args:
        print("Usage: cognitive-loop.py <status|tick|run [n]>")
        sys.exit(1)

    cmd = args[0]

    if cmd == "status":
        loop = CognitiveLoop(ecosystem_root)
        status = loop.get_status()
        print(json.dumps(status, ensure_ascii=False, indent=2))

    elif cmd == "tick":
        loop = CognitiveLoop(ecosystem_root)
        result = loop.tick()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "run":
        n = int(args[1]) if len(args) > 1 else 1
        loop = CognitiveLoop(ecosystem_root)
        summary = loop.run(max_ticks=n)
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        print("Commands: status, tick, run [n]")
        sys.exit(1)


if __name__ == "__main__":
    main()
