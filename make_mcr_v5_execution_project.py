"""
MCR v5.0 Execution Project Generator

生成 MCR v5.0 生物启发有机体架构的可执行骨架。
包含：15步认知循环、10大生命系统、执行清单。

用法：
    python make_mcr_v5_execution_project.py
    cd mcr_v5_execution_project
    python run.py
"""

from __future__ import annotations

import textwrap
from pathlib import Path


PROJECT = "mcr_v5_execution_project"


FILES: dict[str, str] = {
    "README.md": """
# MCR v5.0 Execution Project

这是根据 MCR v5.0 生物启发有机体架构生成的可执行骨架。

核心：
- 15步认知循环
- 10大生命系统
- runtime 模块化
- 执行记录
- 失败分析
- 模式检测
- 自修复
- 技能进化
- Sleep 巩固

运行：
```bash
python run.py
```

健康检查：
```bash
python -m mcr_v5.health_check
```

执行清单：
```text
docs/EXECUTION_CHECKLIST.md
```
""",

    "pyproject.toml": """
[project]
name = "mcr-v5-execution-project"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = []

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
""",

    "run.py": """
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mcr_v5.unified_loop import UnifiedLoopV5


def main() -> None:
    loop = UnifiedLoopV5()
    report = loop.run_once()

    print("MCR v5.0 unified loop finished")
    print(f"steps: {len(report['steps'])}")
    print(f"events: {len(report['events'])}")
    print(f"status: {report['status']}")


if __name__ == "__main__":
    main()
""",

    "config/mcr_v5.json": """
{
    "version": "5.0",
    "mode": "safe_local",
    "allow_network": false,
    "allow_shell": false,
    "max_tasks_per_cycle": 3,
    "homeostasis": {
        "cpu_limit": 0.85,
        "memory_limit": 0.85,
        "failure_limit": 3,
        "energy_limit": 0.7,
        "confidence_limit": 0.6
    },
    "checkpoint_every_cycles": 1
}
""",

    "src/mcr_v5/__init__.py": """
from mcr_v5.unified_loop import UnifiedLoopV5

__all__ = ["UnifiedLoopV5"]
""",

    "src/mcr_v5/core.py": """
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Event:
    type: str
    source: str
    payload: dict[str, Any]
    created_at: float = field(default_factory=time.time)


@dataclass
class LoopContext:
    cycle_id: str
    state: dict[str, Any] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)
    skills: list[dict[str, Any]] = field(default_factory=list)

    def emit(self, event_type: str, source: str, payload: dict[str, Any]) -> None:
        self.events.append(Event(type=event_type, source=source, payload=payload))

    def step(self, name: str, system: str, ok: bool, detail: dict[str, Any]) -> None:
        self.steps.append(
            {
                "name": name,
                "system": system,
                "ok": ok,
                "detail": detail,
                "time": time.time(),
            }
        )
""",

    "src/mcr_v5/event_bus.py": """
from __future__ import annotations

from mcr_v5.core import Event


class EventBus:
    def __init__(self) -> None:
        self.queue: list[Event] = []

    def publish(self, event: Event) -> None:
        self.queue.append(event)

    def drain(self) -> list[Event]:
        events = list(self.queue)
        self.queue.clear()
        return events
""",

    "src/mcr_v5/environment_monitor.py": """
from __future__ import annotations

from pathlib import Path

from mcr_v5.core import LoopContext


class EnvironmentMonitor:
    def scan(self, ctx: LoopContext) -> dict:
        root = Path.cwd()
        files = list(root.glob("*.py"))

        result = {
            "cwd": str(root),
            "python_files": [p.name for p in files],
            "file_count": len(files),
        }

        ctx.emit("environment.scanned", "environment_monitor", result)
        return result
""",

    "src/mcr_v5/cognitive_bridge.py": """
from __future__ import annotations

from mcr_v5.core import LoopContext


class CognitiveBridge:
    def build_world_model(self, ctx: LoopContext, environment: dict) -> dict:
        model = {
            "project_type": "local_runtime",
            "visible_files": environment.get("python_files", []),
            "confidence": 0.75,
        }

        ctx.emit("world_model.updated", "cognitive_bridge", model)
        return model
""",

    "src/mcr_v5/opportunity_detector.py": """
from __future__ import annotations

from mcr_v5.core import LoopContext


class OpportunityDetector:
    def detect(self, ctx: LoopContext, world_model: dict) -> list[dict]:
        opportunities = []

        if world_model.get("visible_files"):
            opportunities.append(
                {
                    "id": "audit_visible_python_files",
                    "priority": 5,
                    "reason": "python files detected",
                }
            )

        if not opportunities:
            opportunities.append(
                {
                    "id": "create_project_baseline",
                    "priority": 3,
                    "reason": "no obvious files detected",
                }
            )

        ctx.emit("opportunity.detected", "opportunity_detector", {"count": len(opportunities)})
        return opportunities
""",

    "src/mcr_v5/goal_generator.py": """
from __future__ import annotations

from mcr_v5.core import LoopContext


class GoalGenerator:
    def generate(self, ctx: LoopContext, opportunities: list[dict]) -> list[dict]:
        goals = []

        for item in opportunities:
            goals.append(
                {
                    "goal_id": f"goal_{item['id']}",
                    "source": item["id"],
                    "priority": item["priority"],
                    "description": f"Handle opportunity: {item['reason']}",
                }
            )

        ctx.emit("goal.generated", "goal_generator", {"count": len(goals)})
        return goals
""",

    "src/mcr_v5/task_engine.py": """
from __future__ import annotations

from mcr_v5.core import LoopContext


class TaskEngine:
    def execute(self, ctx: LoopContext, goals: list[dict], max_tasks: int = 3) -> list[dict]:
        results = []

        for goal in sorted(goals, key=lambda x: x["priority"], reverse=True)[:max_tasks]:
            results.append(
                {
                    "goal_id": goal["goal_id"],
                    "status": "done",
                    "output": f"executed {goal['goal_id']}",
                }
            )

        ctx.emit("task.executed", "task_engine", {"count": len(results)})
        return results
""",

    "src/mcr_v5/provenance.py": """
from __future__ import annotations

import json
from pathlib import Path

from mcr_v5.core import LoopContext


class ProvenanceRecorder:
    def __init__(self, path: str = "runtime_logs/provenance.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, ctx: LoopContext, data: dict) -> None:
        row = {
            "cycle_id": ctx.cycle_id,
            "data": data,
        }

        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\\n")

        ctx.emit("provenance.recorded", "provenance", {"path": str(self.path)})
""",

    "src/mcr_v5/failure_analyzer.py": """
from __future__ import annotations

from mcr_v5.core import LoopContext


class FailureAnalyzer:
    def analyze(self, ctx: LoopContext, task_results: list[dict]) -> list[dict]:
        failures = []

        for item in task_results:
            if item.get("status") != "done":
                failures.append(
                    {
                        "goal_id": item.get("goal_id"),
                        "reason": item.get("error", "unknown"),
                    }
                )

        ctx.failures.extend(failures)
        ctx.emit("failure.analyzed", "failure_analyzer", {"count": len(failures)})
        return failures
""",

    "src/mcr_v5/pattern_detector.py": """
from __future__ import annotations

from mcr_v5.core import LoopContext


class PatternDetector:
    def detect(self, ctx: LoopContext) -> list[dict]:
        patterns = []

        if len(ctx.failures) >= 2:
            patterns.append(
                {
                    "type": "repeated_failure",
                    "count": len(ctx.failures),
                }
            )

        ctx.emit("pattern.detected", "pattern_detector", {"count": len(patterns)})
        return patterns
""",

    "src/mcr_v5/immune_system.py": """
from __future__ import annotations

from mcr_v5.core import LoopContext


class ImmuneSystem:
    def patrol(self, ctx: LoopContext) -> dict:
        risk_level = "low"

        if len(ctx.failures) >= 3:
            risk_level = "high"
        elif len(ctx.failures) > 0:
            risk_level = "medium"

        result = {
            "risk_level": risk_level,
            "failure_count": len(ctx.failures),
        }

        ctx.emit("immune.patrol", "immune_system", result)
        return result
""",

    "src/mcr_v5/self_correction.py": """
from __future__ import annotations

from mcr_v5.core import LoopContext


class SelfCorrection:
    def repair(self, ctx: LoopContext, immune_report: dict) -> list[dict]:
        patches = []

        if immune_report["risk_level"] in ("medium", "high"):
            patches.append(
                {
                    "type": "prompt_guard",
                    "message": "reduce risk and add verification before next task",
                }
            )

        ctx.emit("self_correction.done", "self_correction", {"patches": len(patches)})
        return patches
""",

    "src/mcr_v5/cognitive_loop.py": """
from __future__ import annotations

from mcr_v5.core import LoopContext


class CognitiveLoop:
    def reflect(self, ctx: LoopContext) -> dict:
        reflection = {
            "events": len(ctx.events),
            "failures": len(ctx.failures),
            "steps": len(ctx.steps),
            "summary": "cycle reflected",
        }

        ctx.emit("cognitive.reflected", "cognitive_loop", reflection)
        return reflection
""",

    "src/mcr_v5/global_workspace.py": """
from __future__ import annotations

from mcr_v5.core import LoopContext


class GlobalWorkspace:
    def broadcast(self, ctx: LoopContext, reflection: dict) -> dict:
        salience = 0.5

        if reflection.get("failures", 0) > 0:
            salience += 0.2

        signal = {
            "salience": salience,
            "message": reflection.get("summary", ""),
        }

        ctx.emit("workspace.broadcast", "global_workspace", signal)
        return signal
""",

    "src/mcr_v5/homeostasis.py": """
from __future__ import annotations

from mcr_v5.core import LoopContext


class Homeostasis:
    def regulate(self, ctx: LoopContext, signal: dict) -> dict:
        salience = signal.get("salience", 0.5)

        policy = {
            "max_tasks_next_cycle": 1 if salience > 0.7 else 3,
            "energy_mode": "conserve" if salience > 0.7 else "normal",
        }

        ctx.emit("homeostasis.regulated", "homeostasis", policy)
        return policy
""",

    "src/mcr_v5/evolution.py": """
from __future__ import annotations

import json
from pathlib import Path

from mcr_v5.core import LoopContext


class EvolutionEngine:
    def __init__(self, path: str = "runtime_logs/skills.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def evolve(self, ctx: LoopContext, failures: list[dict], patterns: list[dict]) -> list[dict]:
        skills = []

        if not failures:
            skills.append(
                {
                    "skill": "stable_cycle",
                    "reason": "cycle completed without failures",
                }
            )
        else:
            skills.append(
                {
                    "skill": "failure_avoidance",
                    "reason": f"{len(failures)} failures observed",
                }
            )

        for skill in skills:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(skill, ensure_ascii=False) + "\\n")

        ctx.skills.extend(skills)
        ctx.emit("evolution.skills_updated", "evolution", {"count": len(skills)})
        return skills
""",

    "src/mcr_v5/sleep_consolidator.py": """
from __future__ import annotations

import json
from pathlib import Path

from mcr_v5.core import LoopContext


class SleepConsolidator:
    def __init__(self, path: str = "runtime_logs/sleep_memory.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def consolidate(self, ctx: LoopContext) -> dict:
        memory = {
            "cycle_id": ctx.cycle_id,
            "events": len(ctx.events),
            "steps": len(ctx.steps),
            "failures": len(ctx.failures),
            "skills": len(ctx.skills),
        }

        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(memory, ensure_ascii=False) + "\\n")

        ctx.emit("sleep.consolidated", "sleep_consolidator", memory)
        return memory
""",

    "src/mcr_v5/data_structures.py": """
from __future__ import annotations

import time
from typing import Any


class SimpleRateLimiter:
    def __init__(self, rate: float, capacity: int) -> None:
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last = time.monotonic()

    def allow(self) -> bool:
        now = time.monotonic()
        elapsed = now - self.last
        self.last = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

        if self.tokens >= 1:
            self.tokens -= 1
            return True

        return False


class RingBuffer:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.data: list[Any] = []

    def put(self, item: Any) -> None:
        self.data.append(item)
        if len(self.data) > self.capacity:
            self.data.pop(0)

    def to_list(self) -> list[Any]:
        return list(self.data)
""",

    "src/mcr_v5/unified_loop.py": """
from __future__ import annotations

import uuid

from mcr_v5.cognitive_bridge import CognitiveBridge
from mcr_v5.cognitive_loop import CognitiveLoop
from mcr_v5.core import LoopContext
from mcr_v5.environment_monitor import EnvironmentMonitor
from mcr_v5.evolution import EvolutionEngine
from mcr_v5.failure_analyzer import FailureAnalyzer
from mcr_v5.global_workspace import GlobalWorkspace
from mcr_v5.goal_generator import GoalGenerator
from mcr_v5.homeostasis import Homeostasis
from mcr_v5.immune_system import ImmuneSystem
from mcr_v5.opportunity_detector import OpportunityDetector
from mcr_v5.pattern_detector import PatternDetector
from mcr_v5.provenance import ProvenanceRecorder
from mcr_v5.self_correction import SelfCorrection
from mcr_v5.sleep_consolidator import SleepConsolidator
from mcr_v5.task_engine import TaskEngine


class UnifiedLoopV5:
    def __init__(self) -> None:
        self.environment_monitor = EnvironmentMonitor()
        self.cognitive_bridge = CognitiveBridge()
        self.opportunity_detector = OpportunityDetector()
        self.goal_generator = GoalGenerator()
        self.task_engine = TaskEngine()
        self.provenance = ProvenanceRecorder()
        self.failure_analyzer = FailureAnalyzer()
        self.pattern_detector = PatternDetector()
        self.immune_system = ImmuneSystem()
        self.self_correction = SelfCorrection()
        self.cognitive_loop = CognitiveLoop()
        self.global_workspace = GlobalWorkspace()
        self.homeostasis = Homeostasis()
        self.evolution = EvolutionEngine()
        self.sleep = SleepConsolidator()

    def run_once(self) -> dict:
        ctx = LoopContext(cycle_id=f"cycle_{uuid.uuid4().hex[:8]}")

        # Step 1: 感觉系统 — 环境扫描
        environment = self.environment_monitor.scan(ctx)
        ctx.step("step_01_environment_scan", "感觉系统", True, environment)

        # Step 2: 神经系统 — 世界模型
        world_model = self.cognitive_bridge.build_world_model(ctx, environment)
        ctx.step("step_02_world_model", "神经系统", True, world_model)

        # Step 3: 感觉系统 — 机会检测
        opportunities = self.opportunity_detector.detect(ctx, world_model)
        ctx.step("step_03_opportunity_detection", "感觉系统", True, {"count": len(opportunities)})

        # Step 4: 自主神经系统 — 目标生成
        goals = self.goal_generator.generate(ctx, opportunities)
        ctx.step("step_04_goal_generation", "自主神经系统", True, {"count": len(goals)})

        # Step 5: 执行系统 — 任务执行
        task_results = self.task_engine.execute(ctx, goals)
        ctx.step("step_05_task_execution", "执行系统", True, {"count": len(task_results)})

        # Step 6: 循环系统 — 溯源记录
        self.provenance.record(ctx, {"task_results": task_results})
        ctx.step("step_06_provenance", "循环系统", True, {"recorded": True})

        # Step 7: 免疫系统 — 失败分析
        failures = self.failure_analyzer.analyze(ctx, task_results)
        ctx.step("step_07_failure_analysis", "免疫系统", True, {"count": len(failures)})

        # Step 8: 免疫系统 — 模式检测
        patterns = self.pattern_detector.detect(ctx)
        ctx.step("step_08_pattern_detection", "免疫系统", True, {"count": len(patterns)})

        # Step 9: 免疫系统 — 巡逻
        immune_report = self.immune_system.patrol(ctx)
        ctx.step("step_09_immune_patrol", "免疫系统", True, immune_report)

        # Step 10: 免疫系统 — 自修复
        patches = self.self_correction.repair(ctx, immune_report)
        ctx.step("step_10_self_repair", "免疫系统", True, {"patches": len(patches)})

        # Step 11: 神经系统 — 认知反思
        reflection = self.cognitive_loop.reflect(ctx)
        ctx.step("step_11_cognitive_reflection", "神经系统", True, reflection)

        # Step 12: 内分泌系统 — 全局广播
        signal = self.global_workspace.broadcast(ctx, reflection)
        ctx.step("step_12_global_broadcast", "内分泌系统", True, signal)

        # Step 13: 稳态系统 — 资源调节
        policy = self.homeostasis.regulate(ctx, signal)
        ctx.step("step_13_homeostasis", "稳态系统", True, policy)

        # Step 14: 进化系统 — 技能进化
        skills = self.evolution.evolve(ctx, failures, patterns)
        ctx.step("step_14_skill_evolution", "进化系统", True, {"skills": len(skills)})

        # Step 15: 记忆系统 — Sleep 巩固
        memory = self.sleep.consolidate(ctx)
        ctx.step("step_15_sleep_consolidation", "记忆系统", True, memory)

        return {
            "cycle_id": ctx.cycle_id,
            "status": "ok",
            "events": [event.__dict__ for event in ctx.events],
            "steps": ctx.steps,
            "failures": ctx.failures,
            "skills": ctx.skills,
        }
""",

    "src/mcr_v5/health_check.py": """
from __future__ import annotations

from mcr_v5.unified_loop import UnifiedLoopV5


def main() -> None:
    loop = UnifiedLoopV5()
    report = loop.run_once()

    assert report["status"] == "ok"
    assert len(report["steps"]) == 15

    print("health_check: PASS")
    print(f"cycle_id: {report['cycle_id']}")
    print(f"steps: {len(report['steps'])}")
    print(f"events: {len(report['events'])}")


if __name__ == "__main__":
    main()
""",

    "tests/test_unified_loop.py": """
from mcr_v5.unified_loop import UnifiedLoopV5


def test_unified_loop_runs_15_steps() -> None:
    loop = UnifiedLoopV5()
    report = loop.run_once()

    assert report["status"] == "ok"
    assert len(report["steps"]) == 15
    assert len(report["events"]) >= 15
""",

    "docs/EXECUTION_CHECKLIST.md": """
# MCR v5.0 执行清单

## Phase 0：安全边界
- [ ] 确认当前是本地测试工程
- [ ] 不访问外部网络
- [ ] 不执行危险 shell 命令
- [ ] 不删除用户文件
- [ ] 所有运行日志写入 `runtime_logs/`

## Phase 1：生成工程
- [ ] 运行 `python make_mcr_v5_execution_project.py`
- [ ] 进入 `mcr_v5_execution_project/`
- [ ] 确认存在 `src/mcr_v5/unified_loop.py`
- [ ] 确认存在 `config/mcr_v5.json`
- [ ] 确认存在 `docs/EXECUTION_CHECKLIST.md`

## Phase 2：最小运行
- [ ] 执行 `python run.py`
- [ ] 看到 `status: ok`
- [ ] 看到 `steps: 15`
- [ ] 看到 `events` 大于等于 15

## Phase 3：健康检查
- [ ] 执行 `python -m mcr_v5.health_check`
- [ ] 输出 `health_check: PASS`
- [ ] 无异常堆栈

## Phase 4：测试
- [ ] 执行 `python -m pytest`
- [ ] `test_unified_loop_runs_15_steps` 通过
- [ ] 如果 pytest 不存在，先只运行 health_check，不要重装环境

## Phase 5：15步循环验收
- [ ] Step 1  环境扫描
- [ ] Step 2  世界模型
- [ ] Step 3  机会检测
- [ ] Step 4  目标生成
- [ ] Step 5  任务执行
- [ ] Step 6  溯源记录
- [ ] Step 7  失败分析
- [ ] Step 8  模式检测
- [ ] Step 9  免疫巡逻
- [ ] Step 10 自修复
- [ ] Step 11 认知反思
- [ ] Step 12 全局广播
- [ ] Step 13 稳态调节
- [ ] Step 14 技能进化
- [ ] Step 15 Sleep 巩固

## Phase 6：产物检查
- [ ] `runtime_logs/provenance.jsonl` 已生成
- [ ] `runtime_logs/skills.jsonl` 已生成
- [ ] `runtime_logs/sleep_memory.jsonl` 已生成

## Phase 7：下一步扩展
- [ ] 把 `TaskEngine.execute()` 接入真实任务系统
- [ ] 把 `FailureAnalyzer` 接入真实 eval 结果
- [ ] 把 `EvolutionEngine` 接入 prompt 进化系统
- [ ] 把 `Homeostasis` 接入 token / CPU / memory 监控
- [ ] 把 `SleepConsolidator` 接入长期记忆库

## 当前结论

这是 MCR v5.0 的可执行骨架，不是最终完整系统。

验收标准：
- python run.py 能跑
- health_check PASS
- 15 个 step 全部出现
- runtime_logs 有记录
""",
}


def write_project() -> None:
    root = Path(PROJECT)

    for relative, content in FILES.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")

    print(f"已生成：{root.resolve()}")
    print()
    print("执行：")
    print(f"cd {PROJECT}")
    print("python run.py")
    print("python -m mcr_v5.health_check")
    print("python -m pytest")


if __name__ == "__main__":
    write_project()
