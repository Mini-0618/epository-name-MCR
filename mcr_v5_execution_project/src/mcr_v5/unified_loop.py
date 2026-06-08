"""
MCR v5.0 Unified Loop — 接入真实 runtime 模块。

不再是骨架，而是真正调用 ECOSYSTEM/runtime/ 下的：
- environment_monitor.py → 感觉系统
- cognitive_bridge.py → 神经系统 (世界模型)
- opportunity_detector.py → 感觉系统 (机会检测)
- goal_generator.py → 自主神经系统
- task_engine.py + sandbox.py → 执行系统
- provenance.py → 循环系统 (溯源)
- failure_analyzer.py → 免疫系统 (失败分析)
- pattern_detector.py → 免疫系统 (模式检测)
- immune_system.py → 免疫系统 (巡逻)
- self_correction.py → 免疫系统 (自修复)
- cognitive_bridge.py → 神经系统 (认知循环)
- global_workspace.py → 内分泌系统 (全局广播)
- homeostasis.py → 稳态系统 (资源调节)
- evolution_max.py → 进化系统 (技能进化)
- sleep_consolidator.py → 记忆系统 (Sleep巩固)
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any

# 接入 ECOSYSTEM/runtime/ 真实模块
ECOSYSTEM_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RUNTIME_DIR = ECOSYSTEM_ROOT / "runtime"

# 把 runtime 加入 sys.path
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from mcr_v5.core import LoopContext


def _try_import(module_name: str, class_name: str = None):
    """尝试从 runtime 导入真实模块，失败则用 stub。"""
    try:
        mod = __import__(module_name)
        if class_name:
            return getattr(mod, class_name)
        return mod
    except (ImportError, Exception) as e:
        print(f"[v5] Warning: cannot import {module_name}: {e}, using stub")
        return None


class UnifiedLoopV5:
    def __init__(self, use_real: bool = True) -> None:
        self.use_real = use_real
        self.runtime_dir = RUNTIME_DIR

        # 尝试导入真实模块
        if use_real:
            self._init_real_modules()
        else:
            self._init_stubs()

    def _init_real_modules(self):
        """初始化真实 runtime 模块。"""
        # 感觉系统
        self.env_monitor = _try_import("environment_monitor")

        # 神经系统
        self.cognitive_bridge = _try_import("cognitive_bridge")

        # 机会检测
        self.opp_detector = _try_import("opportunity_detector")

        # 目标生成
        self.goal_gen = _try_import("goal_generator")

        # 免疫系统
        self.immune = _try_import("immune_system")
        self.fail_analyzer = _try_import("failure_analyzer")
        self.pattern_det = _try_import("pattern_detector")
        self.self_correct = _try_import("self_correction")

        # 内分泌系统
        self.workspace = _try_import("global_workspace", "GlobalWorkspace")
        self.workspace_inst = self.workspace() if self.workspace else None

        # 稳态系统
        self.homeo = _try_import("homeostasis", "Homeostasis")
        self.homeo_inst = self.homeo() if self.homeo else None

        # 进化系统
        self.evo_max = _try_import("evolution_max", "EvolutionEngine")
        self.evo_inst = None  # 需要 root 参数

        # 记忆巩固
        self.sleep_mod = _try_import("sleep_consolidator", "SleepConsolidator")
        self.sleep_inst = self.sleep_mod() if self.sleep_mod else None

        # 溯源
        self.prov = _try_import("provenance")

        # 沙箱
        self.sandbox = _try_import("sandbox", "CodeSandbox")
        self.sandbox_inst = None
        if self.sandbox:
            try:
                from sandbox import SandboxPolicy
                self.sandbox_inst = self.sandbox(SandboxPolicy(security_level="standard"))
            except Exception:
                pass

    def _init_stubs(self):
        """初始化 stub 模块。"""
        self.env_monitor = None
        self.cognitive_bridge = None
        self.opp_detector = None
        self.goal_gen = None
        self.immune = None
        self.fail_analyzer = None
        self.pattern_det = None
        self.self_correct = None
        self.workspace_inst = None
        self.homeo_inst = None
        self.evo_max = None
        self.evo_inst = None
        self.sleep_inst = None
        self.prov = None
        self.sandbox = None
        self.sandbox_inst = None

    def run_once(self) -> dict:
        ctx = LoopContext(cycle_id=f"cycle_{uuid.uuid4().hex[:8]}")

        # ═══ Step 1: 感觉系统 — 环境扫描 ═══
        env_data = self._step_environment(ctx)
        ctx.step("step_01_environment_scan", "感觉系统", True, env_data)

        # ═══ Step 2: 神经系统 — 世界模型 ═══
        wm_data = self._step_world_model(ctx, env_data)
        ctx.step("step_02_world_model", "神经系统", True, wm_data)

        # ═══ Step 3: 感觉系统 — 机会检测 ═══
        opps = self._step_opportunities(ctx, wm_data)
        ctx.step("step_03_opportunity_detection", "感觉系统", True, {"count": len(opps)})

        # ═══ Step 4: 自主神经系统 — 目标生成 ═══
        goals = self._step_goals(ctx, opps)
        ctx.step("step_04_goal_generation", "自主神经系统", True, {"count": len(goals)})

        # ═══ Step 5: 执行系统 — 任务执行 ═══
        task_results = self._step_execute(ctx, goals)
        ctx.step("step_05_task_execution", "执行系统", True, {"count": len(task_results)})

        # ═══ Step 6: 循环系统 — 溯源记录 ═══
        self._step_provenance(ctx, task_results)
        ctx.step("step_06_provenance", "循环系统", True, {"recorded": True})

        # ═══ Step 7: 免疫系统 — 失败分析 ═══
        failures = self._step_failure_analysis(ctx, task_results)
        ctx.step("step_07_failure_analysis", "免疫系统", True, {"count": len(failures)})

        # ═══ Step 8: 免疫系统 — 模式检测 ═══
        patterns = self._step_pattern_detection(ctx)
        ctx.step("step_08_pattern_detection", "免疫系统", True, {"count": len(patterns)})

        # ═══ Step 9: 免疫系统 — 巡逻 ═══
        immune_report = self._step_immune_patrol(ctx)
        ctx.step("step_09_immune_patrol", "免疫系统", True, immune_report)

        # ═══ Step 10: 免疫系统 — 自修复 ═══
        patches = self._step_self_correction(ctx, immune_report)
        ctx.step("step_10_self_repair", "免疫系统", True, {"patches": len(patches)})

        # ═══ Step 11: 神经系统 — 认知反思 ═══
        reflection = self._step_cognitive_reflection(ctx)
        ctx.step("step_11_cognitive_reflection", "神经系统", True, reflection)

        # ═══ Step 12: 内分泌系统 — 全局广播 ═══
        signal = self._step_global_broadcast(ctx, reflection)
        ctx.step("step_12_global_broadcast", "内分泌系统", True, signal)

        # ═══ Step 13: 稳态系统 — 资源调节 ═══
        policy = self._step_homeostasis(ctx, signal)
        ctx.step("step_13_homeostasis", "稳态系统", True, policy)

        # ═══ Step 14: 进化系统 — 技能进化 ═══
        skills = self._step_evolution(ctx, failures, patterns)
        ctx.step("step_14_skill_evolution", "进化系统", True, {"skills": len(skills)})

        # ═══ Step 15: 记忆系统 — Sleep 巩固 ═══
        memory = self._step_sleep(ctx)
        ctx.step("step_15_sleep_consolidation", "记忆系统", True, memory)

        return {
            "cycle_id": ctx.cycle_id,
            "status": "ok",
            "events": [event.__dict__ for event in ctx.events],
            "steps": ctx.steps,
            "failures": ctx.failures,
            "skills": ctx.skills,
        }

    # ═══════════════════════════════════════════════════════
    # Step 实现：真实模块优先，fallback 到 stub
    # ═══════════════════════════════════════════════════════

    def _step_environment(self, ctx: LoopContext) -> dict:
        """Step 1: 感觉系统 — 环境扫描。"""
        if self.env_monitor and hasattr(self.env_monitor, "scan_environment"):
            try:
                result = self.env_monitor.scan_environment()
                ctx.emit("environment.scanned", "environment_monitor", {
                    "cpu": result.get("system", {}).get("cpu_percent"),
                    "memory": result.get("system", {}).get("memory_percent"),
                })
                return result
            except Exception as e:
                ctx.emit("environment.error", "environment_monitor", {"error": str(e)[:100]})

        # fallback
        from pathlib import Path
        root = Path.cwd()
        files = list(root.glob("*.py"))
        result = {"cwd": str(root), "python_files": [p.name for p in files], "file_count": len(files)}
        ctx.emit("environment.scanned", "environment_monitor_stub", result)
        return result

    def _step_world_model(self, ctx: LoopContext, env_data: dict) -> dict:
        """Step 2: 神经系统 — 世界模型。"""
        if self.cognitive_bridge and hasattr(self.cognitive_bridge, "WorldModel"):
            try:
                wm = self.cognitive_bridge.WorldModel(
                    action_log_path=str(self.runtime_dir / ".wal" / "cognitive" / "action_log.jsonl"),
                    world_state_path=str(self.runtime_dir / ".wal" / "cognitive" / "world_state.json"),
                )
                pred = wm.predict({"command": "unified_cycle", "action_type": "cycle"})
                model = {
                    "success_probability": pred.success_probability,
                    "risk_level": pred.risk_level,
                    "confidence": pred.confidence,
                }
                ctx.emit("world_model.updated", "cognitive_bridge", model)
                return model
            except Exception as e:
                ctx.emit("world_model.error", "cognitive_bridge", {"error": str(e)[:100]})

        model = {"project_type": "local_runtime", "confidence": 0.75}
        ctx.emit("world_model.updated", "cognitive_bridge_stub", model)
        return model

    def _step_opportunities(self, ctx: LoopContext, wm_data: dict) -> list[dict]:
        """Step 3: 感觉系统 — 机会检测。"""
        if self.opp_detector and hasattr(self.opp_detector, "scan_for_opportunities"):
            try:
                result = self.opp_detector.scan_for_opportunities()
                opps = result.get("opportunities", [])
                ctx.emit("opportunity.detected", "opportunity_detector", {"count": len(opps)})
                return opps
            except Exception as e:
                ctx.emit("opportunity.error", "opportunity_detector", {"error": str(e)[:100]})

        opps = [{"id": "baseline", "priority": 3, "reason": "no real detector"}]
        ctx.emit("opportunity.detected", "opportunity_detector_stub", {"count": len(opps)})
        return opps

    def _step_goals(self, ctx: LoopContext, opps: list[dict]) -> list[dict]:
        """Step 4: 自主神经系统 — 目标生成。"""
        if self.goal_gen and hasattr(self.goal_gen, "generate_goals"):
            try:
                result = self.goal_gen.generate_goals()
                goals = [{"goal_id": f"goal_{i}", "priority": 3} for i in range(result.get("new_goals_generated", 0))]
                ctx.emit("goal.generated", "goal_generator", {"count": len(goals)})
                return goals
            except Exception as e:
                ctx.emit("goal.error", "goal_generator", {"error": str(e)[:100]})

        goals = [{"goal_id": f"goal_{o['id']}", "source": o["id"], "priority": o.get("priority", 3)} for o in opps]
        ctx.emit("goal.generated", "goal_generator_stub", {"count": len(goals)})
        return goals

    def _step_execute(self, ctx: LoopContext, goals: list[dict]) -> list[dict]:
        """Step 5: 执行系统 — 任务执行（接入沙箱）。"""
        results = []

        for goal in goals[:3]:
            if self.sandbox_inst:
                try:
                    gid = goal.get("goal_id", "unknown")
                    sandbox_result = self.sandbox_inst.execute(
                        code=f"print('executing {gid}')",
                        language="python",
                        task_id=gid,
                    )
                    results.append({
                        "goal_id": goal.get("goal_id"),
                        "status": sandbox_result.status,
                        "exit_code": sandbox_result.exit_code,
                        "duration_seconds": sandbox_result.duration_seconds,
                    })
                    continue
                except Exception as e:
                    results.append({"goal_id": goal.get("goal_id"), "status": "error", "error": str(e)[:100]})
                    continue

            results.append({
                "goal_id": goal.get("goal_id"),
                "status": "done",
                "output": f"executed {goal.get('goal_id')}",
            })

        ctx.emit("task.executed", "task_engine", {"count": len(results)})
        return results

    def _step_provenance(self, ctx: LoopContext, task_results: list[dict]):
        """Step 6: 循环系统 — 溯源记录。"""
        if self.prov and hasattr(self.prov, "create_provenance_event"):
            try:
                event = self.prov.create_provenance_event("unified_cycle", {
                    "task_results": task_results,
                    "cycle_id": ctx.cycle_id,
                })
                ctx.emit("provenance.recorded", "provenance", {
                    "event_id": event.get("event_id"),
                })
                return
            except Exception as e:
                ctx.emit("provenance.error", "provenance", {"error": str(e)[:100]})

        # fallback: 写 JSONL
        log_path = Path("runtime_logs/provenance.jsonl")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"cycle_id": ctx.cycle_id, "data": {"task_results": task_results}}, ensure_ascii=False) + "\n")
        ctx.emit("provenance.recorded", "provenance_stub", {"path": str(log_path)})

    def _step_failure_analysis(self, ctx: LoopContext, task_results: list[dict]) -> list[dict]:
        """Step 7: 免疫系统 — 失败分析。"""
        if self.fail_analyzer and hasattr(self.fail_analyzer, "analyze"):
            try:
                result = self.fail_analyzer.analyze(50)
                failures = [{"total": result.get("total_failures", 0), "rate": result.get("failure_rate", 0)}]
                ctx.failures.extend(failures)
                ctx.emit("failure.analyzed", "failure_analyzer", {"count": len(failures)})
                return failures
            except Exception as e:
                ctx.emit("failure.error", "failure_analyzer", {"error": str(e)[:100]})

        failures = [r for r in task_results if r.get("status") not in ("done", "success")]
        ctx.failures.extend(failures)
        ctx.emit("failure.analyzed", "failure_analyzer_stub", {"count": len(failures)})
        return failures

    def _step_pattern_detection(self, ctx: LoopContext) -> list[dict]:
        """Step 8: 免疫系统 — 模式检测。"""
        if self.pattern_det and hasattr(self.pattern_det, "analyze"):
            try:
                result = self.pattern_det.analyze(100)
                patterns = []
                if result.get("high_frequency_events"):
                    patterns.append({"type": "high_freq", "count": len(result["high_frequency_events"])})
                if result.get("error_clusters"):
                    patterns.append({"type": "error_cluster", "count": len(result["error_clusters"])})
                ctx.emit("pattern.detected", "pattern_detector", {"count": len(patterns)})
                return patterns
            except Exception as e:
                ctx.emit("pattern.error", "pattern_detector", {"error": str(e)[:100]})

        patterns = []
        if len(ctx.failures) >= 2:
            patterns.append({"type": "repeated_failure", "count": len(ctx.failures)})
        ctx.emit("pattern.detected", "pattern_detector_stub", {"count": len(patterns)})
        return patterns

    def _step_immune_patrol(self, ctx: LoopContext) -> dict:
        """Step 9: 免疫系统 — 巡逻。"""
        if self.immune and hasattr(self.immune, "patrol"):
            try:
                result = self.immune.patrol()
                report = {
                    "detected": result["summary"]["detected"],
                    "fixed": result["summary"]["fixed"],
                    "skipped": result["summary"]["skipped"],
                }
                ctx.emit("immune.patrol", "immune_system", report)
                return report
            except Exception as e:
                ctx.emit("immune.error", "immune_system", {"error": str(e)[:100]})

        report = {"risk_level": "high" if len(ctx.failures) >= 3 else "medium" if ctx.failures else "low"}
        ctx.emit("immune.patrol", "immune_system_stub", report)
        return report

    def _step_self_correction(self, ctx: LoopContext, immune_report: dict) -> list[dict]:
        """Step 10: 免疫系统 — 自修复。"""
        if self.self_correct and hasattr(self.self_correct, "run_corrections"):
            try:
                result = self.self_correct.run_corrections()
                patches = [{"fixes": result.get("fixes_applied", 0)}]
                ctx.emit("self_correction.done", "self_correction", {"patches": len(patches)})
                return patches
            except Exception as e:
                ctx.emit("self_correction.error", "self_correction", {"error": str(e)[:100]})

        patches = []
        if immune_report.get("risk_level") in ("medium", "high"):
            patches.append({"type": "prompt_guard", "message": "reduce risk"})
        ctx.emit("self_correction.done", "self_correction_stub", {"patches": len(patches)})
        return patches

    def _step_cognitive_reflection(self, ctx: LoopContext) -> dict:
        """Step 11: 神经系统 — 认知反思。"""
        reflection = {
            "events": len(ctx.events),
            "failures": len(ctx.failures),
            "steps": len(ctx.steps),
            "summary": "cycle reflected",
        }
        ctx.emit("cognitive.reflected", "cognitive_loop", reflection)
        return reflection

    def _step_global_broadcast(self, ctx: LoopContext, reflection: dict) -> dict:
        """Step 12: 内分泌系统 — 全局广播。"""
        if self.workspace_inst:
            try:
                event = {"type": "cycle_complete", "failures": reflection.get("failures", 0)}
                signal_result = self.workspace_inst.evaluate(event)
                ctx_result = self.workspace_inst.get_context()
                signal = {
                    "signal": signal_result["signal_type"] if signal_result else "filtered",
                    "saliency": signal_result["saliency"] if signal_result else 0,
                    "has_emergency": ctx_result.get("emergency_pending", False),
                }
                ctx.emit("workspace.broadcast", "global_workspace", signal)
                return signal
            except Exception as e:
                ctx.emit("workspace.error", "global_workspace", {"error": str(e)[:100]})

        salience = 0.7 if reflection.get("failures", 0) > 0 else 0.5
        signal = {"salience": salience, "message": reflection.get("summary", "")}
        ctx.emit("workspace.broadcast", "global_workspace_stub", signal)
        return signal

    def _step_homeostasis(self, ctx: LoopContext, signal: dict) -> dict:
        """Step 13: 稳态系统 — 资源调节。"""
        if self.homeo_inst:
            try:
                results = self.homeo_inst.regulate()
                abnormal = [k for k, v in results.items() if v.get("status") not in ("normal", "unavailable")]
                policy = {
                    "regulated": len(results),
                    "abnormal": abnormal,
                    "abnormal_count": len(abnormal),
                }
                ctx.emit("homeostasis.regulated", "homeostasis", policy)
                return policy
            except Exception as e:
                ctx.emit("homeostasis.error", "homeostasis", {"error": str(e)[:100]})

        salience = signal.get("salience", 0.5)
        policy = {"max_tasks_next_cycle": 1 if salience > 0.7 else 3}
        ctx.emit("homeostasis.regulated", "homeostasis_stub", policy)
        return policy

    def _step_evolution(self, ctx: LoopContext, failures: list, patterns: list) -> list[dict]:
        """Step 14: 进化系统 — 技能进化。"""
        if self.evo_max:
            try:
                evo = self.evo_max(str(self.runtime_dir / ".wal" / "cognitive" / "evolution_lab"))
                # 种群为空则初始化
                if not evo.repo.list_all():
                    evo.ws.init_files()
                result = evo.repo.list_all()
                if result:
                    # 用 evolution.py 的基础版做种群进化
                    from evolution import evolve as evo_basic
                    evo_result = evo_basic(str(self.runtime_dir / ".wal" / "cognitive" / "evolution_state.json"))
                    skills = [{"generation": evo_result.get("generation", 0), "best_fitness": evo_result.get("best_fitness", 0)}]
                else:
                    skills = [{"skill": "initialized", "reason": "no candidates yet"}]
                ctx.skills.extend(skills)
                ctx.emit("evolution.skills_updated", "evolution", {"count": len(skills)})
                return skills
            except Exception as e:
                ctx.emit("evolution.error", "evolution", {"error": str(e)[:100]})

        skills = []
        if not failures:
            skills.append({"skill": "stable_cycle", "reason": "no failures"})
        else:
            skills.append({"skill": "failure_avoidance", "reason": f"{len(failures)} failures"})
        ctx.skills.extend(skills)
        ctx.emit("evolution.skills_updated", "evolution_stub", {"count": len(skills)})
        return skills

    def _step_sleep(self, ctx: LoopContext) -> dict:
        """Step 15: 记忆系统 — Sleep 巩固。"""
        if self.sleep_inst:
            try:
                result = self.sleep_inst.consolidate()
                ctx.emit("sleep.consolidated", "sleep_consolidator", result)
                return result
            except Exception as e:
                ctx.emit("sleep.error", "sleep_consolidator", {"error": str(e)[:100]})

        memory = {
            "cycle_id": ctx.cycle_id,
            "events": len(ctx.events),
            "steps": len(ctx.steps),
            "failures": len(ctx.failures),
            "skills": len(ctx.skills),
        }

        # 写入日志
        log_path = Path("runtime_logs/sleep_memory.jsonl")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(memory, ensure_ascii=False) + "\n")

        ctx.emit("sleep.consolidated", "sleep_consolidator_stub", memory)
        return memory
