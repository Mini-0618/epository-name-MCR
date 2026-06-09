#!/usr/bin/env python3
"""
MCR — My Cognitive Runtime
统一入口。给它任何任务，它自己决定怎么做。

用法:
    python mcr.py "扫描这个网站的安全漏洞"
    python mcr.py "帮我写一个 Python 脚本"
    python mcr.py "整理我的知识库"
    python mcr.py "分析这段代码"
    python mcr.py status
    python mcr.py loop
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ECOSYSTEM_ROOT = Path(__file__).parent
RUNTIME_DIR = ECOSYSTEM_ROOT / "runtime"
sys.path.insert(0, str(RUNTIME_DIR))


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


class MCR:
    """MCR 统一入口。"""

    def __init__(self):
        self.runtime_dir = RUNTIME_DIR
        self._modules = {}

    def _load(self, name: str):
        """懒加载模块。"""
        if name not in self._modules:
            try:
                import importlib.util
                path = self.runtime_dir / f"{name}.py"
                spec = importlib.util.spec_from_file_location(name, str(path))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                self._modules[name] = mod
            except Exception as e:
                self._modules[name] = None
                log(f"Warning: {name} not available: {e}")
        return self._modules.get(name)

    def run(self, task: str) -> str:
        """执行任何任务。自动判断用哪个系统。"""
        task_lower = task.lower()

        # 安全审计
        if any(kw in task_lower for kw in ["扫描", "安全", "审计", "漏洞", "scan", "security", "audit", "vulnerability"]):
            return self._audit(task)

        # 代码分析
        if any(kw in task_lower for kw in ["分析", "检查", "代码", "analyze", "check", "code", "review"]):
            return self._analyze(task)

        # 代码执行
        if any(kw in task_lower for kw in ["运行", "执行", "跑", "run", "execute"]):
            return self._execute(task)

        # 知识查询
        if any(kw in task_lower for kw in ["知识", "搜索", "查询", "knowledge", "search", "query"]):
            return self._knowledge(task)

        # 系统状态
        if any(kw in task_lower for kw in ["状态", "健康", "status", "health"]):
            return self._status()

        # 默认：用 LLM 处理
        return self._think(task)

    def _audit(self, task: str) -> str:
        """安全审计。"""
        log("启动安全审计...")

        # 提取目标
        import re
        targets = re.findall(r'(?:扫描|审计|检查)\s*(\S+)', task)
        if not targets:
            targets = re.findall(r'(\d+\.\d+\.\d+\.\d+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', task)

        if not targets:
            return "请指定审计目标，例如：python mcr.py '扫描 example.com'"

        target = targets[0]
        log(f"目标: {target}")

        # 调用智能审计
        try:
            from mcr_audit_smart import SecurityAuditor
            auditor = SecurityAuditor()
            report = auditor.audit(target)
            return report
        except Exception as e:
            return f"审计失败: {e}"

    def _execute(self, task: str) -> str:
        """代码执行。"""
        log("启动代码执行...")

        # 提取代码
        import re
        code_match = re.search(r'```python\n(.*?)```', task, re.DOTALL)
        if code_match:
            code = code_match.group(1)
        elif "python" in task.lower():
            # 尝试从任务描述生成代码
            code = task.split("python")[-1].strip()
            if not code:
                return "请提供要执行的 Python 代码"
        else:
            return "请提供要执行的代码，用 ```python ``` 包裹"

        # 用沙箱执行
        try:
            from sandbox import CodeSandbox, SandboxPolicy
            sandbox = CodeSandbox(SandboxPolicy(security_level="standard"))
            result = sandbox.execute(code=code, language="python")
            return f"状态: {result.status}\n输出: {result.stdout}\n错误: {result.stderr}\n耗时: {result.duration_seconds:.2f}s"
        except Exception as e:
            return f"执行失败: {e}"

    def _analyze(self, task: str) -> str:
        """代码分析。"""
        log("启动代码分析...")

        # 提取文件路径
        import re
        files = re.findall(r'(?:分析|检查|review)\s*(\S+\.py)', task)
        if not files:
            files = re.findall(r'(\S+\.py)', task)

        if not files:
            return "请指定要分析的 Python 文件"

        results = []
        for f in files:
            path = Path(f)
            if not path.exists():
                results.append(f"文件不存在: {f}")
                continue

            content = path.read_text(encoding="utf-8", errors="replace")
            lines = content.split("\n")

            analysis = {
                "文件": str(path),
                "行数": len(lines),
                "函数": len([l for l in lines if l.strip().startswith("def ")]),
                "类": len([l for l in lines if l.strip().startswith("class ")]),
                "导入": len([l for l in lines if l.strip().startswith(("import ", "from "))]),
                "注释": len([l for l in lines if l.strip().startswith("#")]),
            }

            # 风险扫描
            try:
                from sandbox_policy import PolicyEngine
                engine = PolicyEngine()
                violations = engine.scan(content)
                analysis["风险"] = len(violations)
                if violations:
                    analysis["风险详情"] = [f"{v.severity.value}: {v.message}" for v in violations[:5]]
            except Exception:
                pass

            results.append(json.dumps(analysis, ensure_ascii=False, indent=2))

        return "\n".join(results)

    def _knowledge(self, task: str) -> str:
        """知识查询。"""
        log("启动知识查询...")

        # 尝试 CyberForge 知识库
        try:
            from cyberforge_knowledge import CyberForgeKnowledge
            kf = CyberForgeKnowledge()

            # 提取查询关键词
            import re
            keywords = re.findall(r'(?:搜索|查询|查找)\s*(\S+)', task)
            if not keywords:
                keywords = re.findall(r'[a-zA-Z]+', task)

            results = []
            for kw in keywords[:3]:
                # 搜索 CVE
                cve_result = kf.search_cve(kw)
                if cve_result:
                    results.append(f"=== CVE: {kw} ===\n{cve_result[:500]}")

                # 搜索服务
                svc_result = kf.search_service(kw)
                if svc_result:
                    results.append(f"=== 服务: {kw} ===\n{svc_result[:500]}")

            if results:
                return "\n\n".join(results)
            else:
                return f"未找到关于 {keywords} 的知识"
        except Exception as e:
            return f"知识查询失败: {e}"

    def _status(self) -> str:
        """系统状态。"""
        log("检查系统状态...")

        lines = ["MCR v5.0 系统状态", "=" * 40]

        # 稳态
        try:
            from homeostasis import Homeostasis
            hs = Homeostasis()
            status = hs.get_status()
            lines.append("\n稳态系统:")
            for name, m in status.get("measurements", {}).items():
                s = "OK" if m.get("status") == "normal" else "WARN"
                lines.append(f"  {name}: {m.get('current', '?')} [{s}]")
        except Exception:
            lines.append("\n稳态系统: 不可用")

        # 免疫
        try:
            from immune_system import patrol
            immune = patrol()
            lines.append(f"\n免疫系统: {immune['summary']['detected']} 威胁")
        except Exception:
            lines.append("\n免疫系统: 不可用")

        # 进化
        try:
            evo_path = RUNTIME_DIR / ".wal" / "cognitive" / "real_evolution.json"
            if evo_path.exists():
                evo = json.loads(evo_path.read_text(encoding="utf-8"))
                lines.append(f"\n进化系统: gen={evo.get('generation', 0)} fitness={evo.get('best_fitness', 0):.4f}")
        except Exception:
            pass

        # LLM
        try:
            from llm_provider import LLMProvider
            provider = LLMProvider()
            health = provider.health_check()
            ok = sum(1 for v in health.values() if v.get("status") == "ok")
            lines.append(f"\nLLM Provider: {ok}/{len(health)} 可用")
        except Exception:
            lines.append("\nLLM Provider: 不可用")

        return "\n".join(lines)

    def _think(self, task: str) -> str:
        """用 LLM 思考。"""
        log("启动认知循环...")

        try:
            from llm_provider import LLMProvider
            provider = LLMProvider()
            result = provider.call(
                messages=[
                    {"role": "system", "content": "你是 MCR，一个本地 AI 系统。用中文回答，简洁直接。"},
                    {"role": "user", "content": task},
                ],
                max_tokens=1000,
            )
            if result and result.get("content"):
                return result["content"]
            else:
                return "LLM 无响应。检查 API key 配置。"
        except Exception as e:
            return f"思考失败: {e}"

    def loop(self, interval: int = 60):
        """持续运行模式。"""
        log("MCR 持续运行模式启动")
        log(f"间隔: {interval}秒")

        from global_workspace import GlobalWorkspace
        from homeostasis import Homeostasis
        from sleep_consolidator import SleepConsolidator
        from immune_system import patrol
        from evolution_with_env import EvolvingStrategy, DynamicEnvironment, evaluate_strategy

        ws = GlobalWorkspace()
        hs = Homeostasis()
        sc = SleepConsolidator()
        env = DynamicEnvironment()
        population = [EvolvingStrategy() for _ in range(10)]
        import random

        cycle = 0
        try:
            while True:
                cycle += 1

                # 认知循环
                for i in range(10):
                    ws.evaluate({"type": "cycle_complete", "cycle": cycle * 10 + i})

                # 稳态
                hs_result = hs.regulate()
                abnormal = [k for k, v in hs_result.items() if v.get("status") not in ("normal", "unavailable")]

                # 巩固
                if cycle % 5 == 0:
                    sc.consolidate()

                # 进化
                env.evolve()
                for s in population:
                    s.fitness = evaluate_strategy(s, env)
                population.sort(key=lambda s: s.fitness, reverse=True)
                best = population[0]
                avg = sum(s.fitness for s in population) / len(population)
                new_pop = [type(best)(dict(best.genes))]
                while len(new_pop) < 10:
                    p1 = max(random.sample(population, min(3, len(population))), key=lambda s: s.fitness)
                    p2 = max(random.sample(population, min(3, len(population))), key=lambda s: s.fitness)
                    if random.random() < 0.7:
                        child = p1.crossover(p2)
                    else:
                        child = p1.mutate()
                    new_pop.append(child)
                population = new_pop

                # 免疫
                immune = {"summary": {"detected": 0, "fixed": 0}}
                if cycle % 10 == 0:
                    immune = patrol()

                log(f"#{cycle} | fitness={best.fitness:.4f} avg={avg:.4f} | 稳态:{'无' if not abnormal else abnormal} | 免疫:{immune['summary']['detected']}威胁")

                time.sleep(interval)

        except KeyboardInterrupt:
            log(f"MCR 停止。共 {cycle} 轮。")


def main():
    if len(sys.argv) < 2:
        print("MCR — My Cognitive Runtime")
        print()
        print("用法:")
        print('  python mcr.py "扫描 example.com 的安全漏洞"')
        print('  python mcr.py "分析 runtime/unified_loop.py"')
        print('  python mcr.py "搜索 Redis 相关知识"')
        print('  python mcr.py "帮我写一个排序算法"')
        print("  python mcr.py status")
        print("  python mcr.py loop")
        return

    mcr = MCR()

    if sys.argv[1] == "status":
        print(mcr._status())
    elif sys.argv[1] == "loop":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 60
        mcr.loop(interval)
    else:
        task = " ".join(sys.argv[1:])
        result = mcr.run(task)
        print(result)


if __name__ == "__main__":
    main()
