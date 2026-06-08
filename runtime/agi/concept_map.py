"""
concept_map.py -- ECOSYSTEM Concept Map v0.1

Adds minimal abstraction to World Model:
  observation → concept → risk_candidate

Enables cross-domain transfer without memorization.

Usage:
    python concept_map.py resolve "jenkins_detected"
    python concept_map.py infer --observation "pacs_detected" --context "exposed_port,credential_surface"
    python concept_map.py test

No external dependencies -- stdlib only.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# -- Paths --
ECOSYSTEM_ROOT = Path(__file__).resolve().parent.parent.parent
AGI_DIR = ECOSYSTEM_ROOT / "runtime" / "agi"
CONFIG_DIR = ECOSYSTEM_ROOT / "config"
CONCEPT_MAP_PATH = CONFIG_DIR / "concept_map.json"
CONCEPT_MAP_LOG = AGI_DIR / "concept-map-log.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _append_jsonl(path: Path, entry: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ============================================================
# Default Concept Map Configuration
# ============================================================

DEFAULT_CONCEPT_MAP = {
    "schema_version": "0.1",
    "description": "Observation → Concept → Risk mapping for cross-domain transfer",

    # Observation → Concept mappings
    "mappings": {
        # Web admin interfaces
        "jenkins_detected": {"concept": "web_admin_interface", "confidence": 0.95},
        "router_admin_detected": {"concept": "web_admin_interface", "confidence": 0.90},
        "pacs_detected": {"concept": "web_admin_interface", "confidence": 0.85},
        "grafana_detected": {"concept": "web_admin_interface", "confidence": 0.90},
        "phpmyadmin_detected": {"concept": "web_admin_interface", "confidence": 0.95},
        "admin_panel_detected": {"concept": "web_admin_interface", "confidence": 0.90},

        # NOT web admin interfaces
        "static_http_site": {"concept": "static_content", "confidence": 0.90},
        "api_endpoint": {"concept": "api_service", "confidence": 0.85},
        "cdn_node": {"concept": "static_content", "confidence": 0.80},
    },

    # Concept → Risk candidates (inference rules)
    "inference_rules": [
        {
            "rule_id": "R001",
            "name": "web_admin_weak_password",
            "conditions": {
                "concept": "web_admin_interface",
                "context_required": ["exposed_port", "credential_surface"],
            },
            "conclusion": "weak_password_risk",
            "confidence_range": [0.3, 0.6],
            "reasoning": "Web admin interfaces with exposed ports and credential surfaces are common weak password targets",
        },
        {
            "rule_id": "R002",
            "name": "web_admin_default_creds",
            "conditions": {
                "concept": "web_admin_interface",
                "context_required": ["exposed_port"],
            },
            "conclusion": "default_credentials_risk",
            "confidence_range": [0.2, 0.5],
            "reasoning": "Web admin interfaces may use default credentials",
        },
    ],

    # Negative rules (explicit exclusions)
    "exclusions": {
        "static_content": ["weak_password_risk", "default_credentials_risk"],
        "api_service": ["default_credentials_risk"],
    },
}


class ConceptMap:
    """Observation → Concept → Risk inference engine."""

    def __init__(self, ecosystem_root: str | Path | None = None,
                 config_path: str | Path | None = None):
        self._root = Path(ecosystem_root) if ecosystem_root else ECOSYSTEM_ROOT
        self._config_path = Path(config_path) if config_path else self._root / "config" / "concept_map.json"
        self._log_path = self._root / "runtime" / "agi" / "concept-map-log.jsonl"
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load concept map config, create default if missing."""
        config = _load_json(self._config_path)
        if not config:
            # Write default config
            _save_json(self._config_path, DEFAULT_CONCEPT_MAP)
            config = DEFAULT_CONCEPT_MAP
        return config

    def reload(self) -> None:
        """Reload config from disk."""
        self._config = self._load_config()

    # ------------------------------------------------------------------
    # Core: Observation → Concept resolution
    # ------------------------------------------------------------------

    def resolve(self, observation: str) -> Optional[Dict[str, Any]]:
        """
        Resolve an observation to a concept.

        Returns: {"concept": str, "confidence": float} or None
        """
        mappings = self._config.get("mappings", {})
        mapping = mappings.get(observation)

        if mapping:
            result = {
                "observation": observation,
                "concept": mapping["concept"],
                "confidence": mapping["confidence"],
                "resolved_at": _now_iso(),
            }
            _append_jsonl(self._log_path, {"type": "resolve", **result})
            return result

        # Try partial match (substring)
        for obs_key, obs_mapping in mappings.items():
            if obs_key in observation or observation in obs_key:
                result = {
                    "observation": observation,
                    "matched_pattern": obs_key,
                    "concept": obs_mapping["concept"],
                    "confidence": obs_mapping["confidence"] * 0.8,  # penalty for partial match
                    "resolved_at": _now_iso(),
                    "partial_match": True,
                }
                _append_jsonl(self._log_path, {"type": "resolve_partial", **result})
                return result

        return None

    # ------------------------------------------------------------------
    # Core: Concept → Risk inference
    # ------------------------------------------------------------------

    def infer(self, observation: str,
              context: Optional[List[str]] = None,
              days_since_last_evidence: int = 0) -> List[Dict[str, Any]]:
        """
        Infer risk candidates from observation + context.

        Args:
            observation: The observation string (e.g., "pacs_detected")
            context: List of context flags (e.g., ["exposed_port", "credential_surface"])
            days_since_last_evidence: Days since last evidence for confidence decay

        Returns: List of risk candidates with confidence scores
        """
        if context is None:
            context = []

        # Step 1: Resolve observation to concept
        resolution = self.resolve(observation)
        if not resolution:
            return []

        concept = resolution["concept"]

        # Step 2: Check exclusions
        exclusions = self._config.get("exclusions", {})
        excluded_risks = set(exclusions.get(concept, []))

        # Step 3: Apply inference rules
        rules = self._config.get("inference_rules", [])
        results = []

        for rule in rules:
            conditions = rule.get("conditions", {})
            required_concept = conditions.get("concept", "")
            required_context = set(conditions.get("context_required", []))

            # Check concept match
            if required_concept != concept:
                continue

            # Check context requirements
            if not required_context.issubset(set(context)):
                continue

            conclusion = rule["conclusion"]

            # Check exclusions
            if conclusion in excluded_risks:
                continue

            # Calculate confidence with decay
            concept_conf = resolution["confidence"]
            conf_range = rule.get("confidence_range", [0.1, 0.5])
            # Scale confidence by concept confidence
            base_conf = (conf_range[0] + conf_range[1]) / 2
            final_conf = base_conf * concept_conf

            # Apply confidence decay based on evidence age
            if days_since_last_evidence > 0:
                decay = 0.95 ** days_since_last_evidence
                final_conf = final_conf * decay

            result = {
                "observation": observation,
                "concept": concept,
                "risk": conclusion,
                "confidence": round(final_conf, 3),
                "rule_id": rule["rule_id"],
                "rule_name": rule["name"],
                "reasoning": rule["reasoning"],
                "context_used": list(required_context),
                "evidence_age_days": days_since_last_evidence,
                "inferred_at": _now_iso(),
            }
            results.append(result)

        # Log inference
        _append_jsonl(self._log_path, {
            "type": "infer",
            "observation": observation,
            "concept": concept,
            "context": context,
            "results_count": len(results),
            "risks": [r["risk"] for r in results],
        })

        return results

    # ------------------------------------------------------------------
    # Query: Get all concepts and mappings
    # ------------------------------------------------------------------

    def list_concepts(self) -> Dict[str, List[str]]:
        """List all concepts and their mapped observations."""
        mappings = self._config.get("mappings", {})
        concepts: Dict[str, List[str]] = {}
        for obs, mapping in mappings.items():
            concept = mapping["concept"]
            if concept not in concepts:
                concepts[concept] = []
            concepts[concept].append(obs)
        return concepts

    def list_rules(self) -> List[Dict[str, Any]]:
        """List all inference rules."""
        return self._config.get("inference_rules", [])

    def get_exclusions(self) -> Dict[str, List[str]]:
        """Get exclusion rules."""
        return self._config.get("exclusions", {})

    # ------------------------------------------------------------------
    # Validation: Check for contradictions
    # ------------------------------------------------------------------

    def validate(self) -> Dict[str, Any]:
        """Validate concept map for consistency."""
        issues = []
        mappings = self._config.get("mappings", {})
        exclusions = self._config.get("exclusions", {})
        rules = self._config.get("inference_rules", [])

        # Check: observation mapped to concept but excluded from all risks
        for obs, mapping in mappings.items():
            concept = mapping["concept"]
            excluded = set(exclusions.get(concept, []))
            # Find rules that apply to this concept
            applicable_risks = set()
            for rule in rules:
                if rule.get("conditions", {}).get("concept") == concept:
                    applicable_risks.add(rule["conclusion"])
            # If all applicable risks are excluded, the mapping is useless
            if applicable_risks and applicable_risks.issubset(excluded):
                issues.append({
                    "type": "dead_mapping",
                    "observation": obs,
                    "concept": concept,
                    "message": f"Observation '{obs}' maps to '{concept}' but all risks are excluded",
                })

        # Check: rule references non-existent concept
        existing_concepts = set(m["concept"] for m in mappings.values())
        for rule in rules:
            required_concept = rule.get("conditions", {}).get("concept", "")
            if required_concept not in existing_concepts:
                issues.append({
                    "type": "orphan_rule",
                    "rule_id": rule["rule_id"],
                    "concept": required_concept,
                    "message": f"Rule {rule['rule_id']} references concept '{required_concept}' with no observations",
                })

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "mappings_count": len(mappings),
            "rules_count": len(rules),
            "exclusions_count": sum(len(v) for v in exclusions.values()),
        }


# ============================================================
# CLI
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python concept_map.py <resolve|infer|concepts|rules|validate|test> [args]")
        sys.exit(1)

    action = sys.argv[1]
    cm = ConceptMap()

    if action == "resolve":
        if len(sys.argv) < 3:
            print("Usage: python concept_map.py resolve <observation>")
            sys.exit(1)
        observation = sys.argv[2]
        result = cm.resolve(observation)
        if result:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(json.dumps({"observation": observation, "concept": None, "message": "No mapping found"}, indent=2))

    elif action == "infer":
        # Parse --observation and --context from args
        observation = ""
        context = []
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--observation" and i + 1 < len(sys.argv):
                observation = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--context" and i + 1 < len(sys.argv):
                context = sys.argv[i + 1].split(",")
                i += 2
            else:
                i += 1

        if not observation:
            print("Usage: python concept_map.py infer --observation <obs> --context <ctx1,ctx2>")
            sys.exit(1)

        results = cm.infer(observation, context)
        print(json.dumps(results, indent=2, ensure_ascii=False))

    elif action == "concepts":
        concepts = cm.list_concepts()
        print(json.dumps(concepts, indent=2, ensure_ascii=False))

    elif action == "rules":
        rules = cm.list_rules()
        print(json.dumps(rules, indent=2, ensure_ascii=False))

    elif action == "validate":
        result = cm.validate()
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif action == "test":
        run_tests(cm)

    else:
        print(f"Unknown action: {action}")
        sys.exit(1)


def run_tests(cm: ConceptMap):
    """Run built-in validation tests."""
    print("Concept Map v0.1 Tests")
    print("=" * 50)

    passed = 0
    failed = 0

    def check(name: str, condition: bool, detail: str = ""):
        nonlocal passed, failed
        if condition:
            print(f"  [PASS] {name}")
            passed += 1
        else:
            print(f"  [FAIL] {name} {detail}")
            failed += 1

    # Test 1: Basic resolution
    r = cm.resolve("jenkins_detected")
    check("jenkins → web_admin_interface",
          r is not None and r["concept"] == "web_admin_interface")

    # Test 2: PACS resolution (cross-domain transfer)
    r = cm.resolve("pacs_detected")
    check("pacs → web_admin_interface (cross-domain)",
          r is not None and r["concept"] == "web_admin_interface")

    # Test 3: Router admin resolution
    r = cm.resolve("router_admin_detected")
    check("router_admin → web_admin_interface",
          r is not None and r["concept"] == "web_admin_interface")

    # Test 4: Static site should NOT map to web_admin_interface
    r = cm.resolve("static_http_site")
    check("static_http_site → static_content (NOT web_admin)",
          r is not None and r["concept"] != "web_admin_interface")

    # Test 5: Inference with context
    results = cm.infer("pacs_detected", ["exposed_port", "credential_surface"])
    check("pacs + exposed_port + credential_surface → weak_password_risk",
          len(results) > 0 and any(r["risk"] == "weak_password_risk" for r in results))

    # Test 6: Inference without sufficient context should fail
    results = cm.infer("pacs_detected", ["exposed_port"])
    check("pacs + exposed_port only → no weak_password_risk (missing credential_surface)",
          not any(r["risk"] == "weak_password_risk" for r in results))

    # Test 7: Static site should NOT infer weak_password_risk
    results = cm.infer("static_http_site", ["exposed_port", "credential_surface"])
    check("static_http_site → NO weak_password_risk (exclusion rule)",
          not any(r["risk"] == "weak_password_risk" for r in results))

    # Test 8: Jenkins should also infer weak_password_risk
    results = cm.infer("jenkins_detected", ["exposed_port", "credential_surface"])
    check("jenkins + context → weak_password_risk",
          len(results) > 0 and any(r["risk"] == "weak_password_risk" for r in results))

    # Test 9: PACS does NOT directly memorize weak_password_risk
    # It goes through web_admin_interface concept
    r = cm.resolve("pacs_detected")
    results = cm.infer("pacs_detected", ["exposed_port", "credential_surface"])
    check("PACS → web_admin_interface → weak_password_risk (via concept, not direct)",
          r["concept"] == "web_admin_interface" and
          len(results) > 0 and
          results[0]["concept"] == "web_admin_interface")

    # Test 10: Validation passes
    validation = cm.validate()
    check("Concept map validation passes",
          validation["valid"],
          str(validation.get("issues", [])))

    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
