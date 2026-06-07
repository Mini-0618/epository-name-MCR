"""
tool-router.py -- Dynamic Tool Router

Routes tasks to appropriate tools based on task type and context.
Replaces static hardcoded routing with capability-based matching.

Usage:
    python tool-router.py route "scan local ports"
    python tool-router.py route "analyze security of http://localhost"
    python tool-router.py list
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ECOSYSTEM_ROOT = Path(__file__).resolve().parent.parent.parent
AGI_DIR = ECOSYSTEM_ROOT / "runtime" / "agi"
REGISTRY_PATH = ECOSYSTEM_ROOT / "registry" / "apps.json"
ROUTER_LOG = AGI_DIR / "tool-router-log.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, entry: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ============================================================
# Tool Capabilities Registry
# ============================================================

TOOL_CAPABILITIES = {
    "fastport": {
        "app_id": "cyberforge",
        "capabilities": ["port_scan", "service_detection", "banner_grab"],
        "keywords": ["port", "scan", "service", "open", "closed", "tcp", "udp"],
        "risk_level": "low",
    },
    "dirscan": {
        "app_id": "cyberforge",
        "capabilities": ["directory_scan", "file_discovery", "sensitive_file"],
        "keywords": ["directory", "dir", "path", "file", "git", "env", "admin", "login"],
        "risk_level": "low",
    },
    "nuclei": {
        "app_id": "cyberforge",
        "capabilities": ["vulnerability_scan", "cve_check", "template_scan"],
        "keywords": ["vulnerability", "vuln", "cve", "exploit", "poc", "template"],
        "risk_level": "medium",
    },
    "knowledge_search": {
        "app_id": "cyberforge",
        "capabilities": ["knowledge_search", "keyword_search", "graph_query"],
        "keywords": ["knowledge", "search", "find", "info", "about", "what is"],
        "risk_level": "none",
    },
    "self_diagnosis": {
        "app_id": "mcr.runtime",
        "capabilities": ["health_check", "score", "issues"],
        "keywords": ["health", "diagnose", "score", "status", "issues", "check"],
        "risk_level": "none",
    },
    "memory_search": {
        "app_id": "mcr.runtime",
        "capabilities": ["memory_search", "recall", "remember"],
        "keywords": ["remember", "recall", "memory", "past", "history", "before"],
        "risk_level": "none",
    },
    "concept_infer": {
        "app_id": "mcr.runtime",
        "capabilities": ["concept_resolution", "risk_inference", "cross_domain"],
        "keywords": ["concept", "risk", "infer", "similar", "like", "category"],
        "risk_level": "none",
    },
    "feedback_quarantine": {
        "app_id": "mcr.runtime",
        "capabilities": ["quarantine_scan", "injection_detect"],
        "keywords": ["quarantine", "injection", "feedback", "polluted", "fake"],
        "risk_level": "none",
    },
}

# Task type → tool priority mapping
TASK_TYPE_PRIORITY = {
    "port_scan": ["fastport", "knowledge_search"],
    "directory_scan": ["dirscan", "knowledge_search"],
    "vulnerability_scan": ["nuclei", "fastport", "dirscan"],
    "full_scan": ["fastport", "dirscan", "nuclei"],
    "knowledge_search": ["knowledge_search", "memory_search"],
    "health_check": ["self_diagnosis", "feedback_quarantine"],
    "concept_inference": ["concept_infer", "knowledge_search"],
    "memory_recall": ["memory_search", "knowledge_search"],
}


class ToolRouter:
    """Dynamic tool router based on task capabilities."""

    def __init__(self, ecosystem_root: str | Path | None = None):
        self._root = Path(ecosystem_root) if ecosystem_root else ECOSYSTEM_ROOT
        self._log_path = self._root / "runtime" / "agi" / "tool-router-log.jsonl"
        self._tools = TOOL_CAPABILITIES.copy()

    def classify_task(self, task_description: str) -> Tuple[str, float, List[str]]:
        """
        Classify a task description into a task type.

        Returns: (task_type, confidence, matched_keywords)
        """
        desc_lower = task_description.lower()
        scores: Dict[str, List[str]] = {}

        for tool_name, tool_info in self._tools.items():
            matched = []
            for kw in tool_info["keywords"]:
                if kw in desc_lower:
                    matched.append(kw)
            if matched:
                scores[tool_name] = matched

        if not scores:
            return "unknown", 0.0, []

        # Find best match by keyword count
        best_tool = max(scores.keys(), key=lambda t: len(scores[t]))
        matched_keywords = scores[best_tool]
        confidence = min(len(matched_keywords) / 3.0, 1.0)  # 3+ keywords = 1.0

        # Map tool to task type
        tool_to_task = {
            "fastport": "port_scan",
            "dirscan": "directory_scan",
            "nuclei": "vulnerability_scan",
            "knowledge_search": "knowledge_search",
            "self_diagnosis": "health_check",
            "memory_search": "memory_recall",
            "concept_infer": "concept_inference",
            "feedback_quarantine": "health_check",
        }

        task_type = tool_to_task.get(best_tool, "unknown")
        return task_type, confidence, matched_keywords

    def route(self, task_description: str,
              context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Route a task to the best tool(s).

        Returns: routing decision with tool, confidence, and reasoning.
        """
        if context is None:
            context = {}

        task_type, confidence, keywords = self.classify_task(task_description)

        # Get tool priority for this task type
        priority_list = TASK_TYPE_PRIORITY.get(task_type, [])

        # Filter by available tools
        available_tools = []
        for tool_name in priority_list:
            if tool_name in self._tools:
                tool_info = self._tools[tool_name]
                available_tools.append({
                    "tool": tool_name,
                    "app_id": tool_info["app_id"],
                    "capabilities": tool_info["capabilities"],
                    "risk_level": tool_info["risk_level"],
                })

        # Build routing decision
        decision = {
            "task_description": task_description,
            "task_type": task_type,
            "confidence": round(confidence, 3),
            "matched_keywords": keywords,
            "primary_tool": available_tools[0] if available_tools else None,
            "fallback_tools": available_tools[1:] if len(available_tools) > 1 else [],
            "reasoning": self._build_reasoning(task_type, keywords, available_tools),
            "routed_at": _now_iso(),
        }

        # Log
        _append_jsonl(self._log_path, {
            "type": "route",
            "task_type": task_type,
            "confidence": confidence,
            "primary_tool": decision["primary_tool"]["tool"] if decision["primary_tool"] else None,
        })

        return decision

    def _build_reasoning(self, task_type: str, keywords: List[str],
                         tools: List[Dict]) -> str:
        """Build human-readable reasoning for the routing decision."""
        if not tools:
            return f"No tool found for task type '{task_type}'"

        primary = tools[0]["tool"]
        if len(tools) == 1:
            return f"Task matches '{task_type}' (keywords: {keywords}), routed to {primary}"
        else:
            fallbacks = ", ".join(t["tool"] for t in tools[1:])
            return f"Task matches '{task_type}' (keywords: {keywords}), primary: {primary}, fallbacks: {fallbacks}"

    def list_tools(self) -> List[Dict[str, Any]]:
        """List all registered tools and their capabilities."""
        return [
            {
                "tool": name,
                "app_id": info["app_id"],
                "capabilities": info["capabilities"],
                "keywords": info["keywords"],
                "risk_level": info["risk_level"],
            }
            for name, info in self._tools.items()
        ]

    def add_tool(self, name: str, app_id: str, capabilities: List[str],
                 keywords: List[str], risk_level: str = "low") -> None:
        """Register a new tool."""
        self._tools[name] = {
            "app_id": app_id,
            "capabilities": capabilities,
            "keywords": keywords,
            "risk_level": risk_level,
        }


# ============================================================
# CLI
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python tool-router.py <route|list> [args]")
        sys.exit(1)

    action = sys.argv[1]
    router = ToolRouter()

    if action == "route":
        if len(sys.argv) < 3:
            print("Usage: python tool-router.py route '<task description>'")
            sys.exit(1)
        task = " ".join(sys.argv[2:])
        decision = router.route(task)
        print(json.dumps(decision, indent=2, ensure_ascii=False))

    elif action == "list":
        tools = router.list_tools()
        print(json.dumps(tools, indent=2, ensure_ascii=False))

    else:
        print(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
