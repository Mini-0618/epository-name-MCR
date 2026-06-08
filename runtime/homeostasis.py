"""
Homeostasis — MCR 的稳态系统。

生物学原理：
- 负反馈：血糖高 → 胰岛素分泌 → 血糖降低
- 预测性稳态：预期运动 → 提前分泌肾上腺素
- 内环境稳态：pH、体温、血糖等关键指标维持在狭窄范围

功能：
1. 持续监控 5 个关键指标
2. 指标超出范围时自动触发修复
3. 与其他系统交互：调节扫描频率、触发巩固、触发免疫巡逻
"""

import json
import os
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

ECOSYSTEM_ROOT = Path(__file__).parent.parent
RUNTIME_DIR = ECOSYSTEM_ROOT / "runtime"
HOMEOSTASIS_STATE = RUNTIME_DIR / ".wal" / "cognitive" / "homeostasis.json"
HOMEOSTASIS_LOG = RUNTIME_DIR / ".wal" / "cognitive" / "homeostasis_log.jsonl"

# 需要 psutil，没装就降级
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# ═══ 稳态变量定义 ═══

VARIABLES = {
    "working_memory_size": {
        "min": 10, "max": 100, "target": 50,
        "unit": "entries",
        "measure": "memory",
        "desc": "工作记忆条目数",
    },
    "event_rate": {
        "min": 0, "max": 100, "target": 20,
        "unit": "events/min",
        "measure": "event_bus",
        "desc": "事件速率",
    },
    "cpu_usage": {
        "min": 0, "max": 80, "target": 30,
        "unit": "%",
        "measure": "system",
        "desc": "CPU 使用率",
    },
    "disk_usage": {
        "min": 0, "max": 90, "target": 50,
        "unit": "%",
        "measure": "system",
        "desc": "磁盘使用率",
    },
    "task_queue_depth": {
        "min": 0, "max": 50, "target": 10,
        "unit": "tasks",
        "measure": "task_engine",
        "desc": "任务队列深度",
    },
}


class Homeostasis:
    """
    MCR 的"稳态系统"。
    持续监控关键指标，通过负反馈维持平衡。
    """

    def __init__(self, state_path=None):
        self.state_path = Path(state_path) if state_path else HOMEOSTASIS_STATE
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()

    def _load_state(self) -> dict:
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "measurements": {},
            "corrections": [],
            "last_regulate": None,
            "stats": {
                "total_regulations": 0,
                "total_corrections": 0,
                "high_triggers": {},
                "low_triggers": {},
            },
        }

    def _save_state(self):
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def _log(self, entry: dict):
        log_path = HOMEOSTASIS_LOG
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ═══ 测量 ═══

    def measure(self, var_name: str) -> Optional[float]:
        """测量一个稳态变量的当前值。"""
        spec = VARIABLES.get(var_name)
        if not spec:
            return None

        if spec["measure"] == "system":
            return self._measure_system(var_name)
        elif spec["measure"] == "memory":
            return self._measure_memory(var_name)
        elif spec["measure"] == "event_bus":
            return self._measure_event_rate(var_name)
        elif spec["measure"] == "task_engine":
            return self._measure_task_queue(var_name)
        return None

    def _measure_system(self, var_name: str) -> Optional[float]:
        if not HAS_PSUTIL:
            return None
        if var_name == "cpu_usage":
            return psutil.cpu_percent(interval=0.1)
        elif var_name == "disk_usage":
            return psutil.disk_usage("/").percent if os.name != "nt" else psutil.disk_usage("C:\\").percent
        return None

    def _measure_memory(self, var_name: str) -> float:
        """统计工作记忆条目数。

        只统计真正的记忆文件，不统计日志。
        Working memory = memory/*.jsonl（life-memory, temporal-memory）
        """
        memory_dir = RUNTIME_DIR / "memory"
        count = 0
        if memory_dir.exists():
            for f in memory_dir.glob("*.jsonl"):
                try:
                    with open(f, "r", encoding="utf-8") as fh:
                        count += sum(1 for line in fh if line.strip())
                except Exception:
                    pass
        return float(count)

    def _measure_event_rate(self, var_name: str) -> float:
        """统计最近 1 分钟的事件数。"""
        events_file = RUNTIME_DIR / "events.jsonl"
        if not events_file.exists():
            return 0.0

        now = datetime.now()
        count = 0
        try:
            with open(events_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            # 只看最后 200 行
            for line in lines[-200:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts = entry.get("timestamp", entry.get("ts", ""))
                    if ts:
                        event_time = datetime.fromisoformat(ts.replace("Z", "+00:00").split("+")[0])
                        if (now - event_time).total_seconds() < 60:
                            count += 1
                except Exception:
                    pass
        except Exception:
            pass
        return float(count)

    def _measure_task_queue(self, var_name: str) -> float:
        """统计待处理任务数。"""
        # 检查 queue 目录下的待处理任务
        queue_dir = RUNTIME_DIR / "queue"
        count = 0
        if queue_dir.exists():
            count += len(list(queue_dir.glob("*.json")))
        # 也检查 tasks.jsonl
        tasks_file = RUNTIME_DIR / ".wal" / "cognitive" / "tasks.jsonl"
        if tasks_file.exists():
            try:
                with open(tasks_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            entry = json.loads(line)
                            if entry.get("status") in ("pending", "proposed"):
                                count += 1
            except Exception:
                pass
        return float(count)

    # ═══ 调节 ═══

    def regulate(self) -> dict:
        """执行一轮稳态调节。"""
        self.state["stats"]["total_regulations"] += 1
        results = {}

        for var_name, spec in VARIABLES.items():
            current = self.measure(var_name)
            if current is None:
                results[var_name] = {"status": "unavailable"}
                continue

            self.state["measurements"][var_name] = {
                "value": current,
                "timestamp": datetime.now().isoformat(),
            }

            result = {"current": current, "target": spec["target"]}

            if current > spec["max"]:
                result["status"] = "high"
                result["action"] = self._correct_high(var_name, current, spec)
                self.state["stats"]["high_triggers"][var_name] = \
                    self.state["stats"].get("high_triggers", {}).get(var_name, 0) + 1
                self.state["stats"]["total_corrections"] += 1
            elif current < spec["min"]:
                result["status"] = "low"
                result["action"] = self._correct_low(var_name, current, spec)
                self.state["stats"]["low_triggers"][var_name] = \
                    self.state["stats"].get("low_triggers", {}).get(var_name, 0) + 1
                self.state["stats"]["total_corrections"] += 1
            else:
                result["status"] = "normal"

            results[var_name] = result

        self.state["last_regulate"] = datetime.now().isoformat()
        self._save_state()

        # 记录日志
        self._log({
            "timestamp": datetime.now().isoformat(),
            "results": results,
        })

        return results

    def _correct_high(self, var_name: str, current: float, spec: dict) -> str:
        """指标过高时的修复动作。"""
        actions = {
            "working_memory_size": "trigger_consolidation",
            "event_rate": "raise_saliency_threshold",
            "cpu_usage": "reduce_scan_frequency",
            "disk_usage": "cleanup_logs",
            "task_queue_depth": "throttle_new_tasks",
        }
        action = actions.get(var_name, "monitor")

        self.state["corrections"].append({
            "var": var_name, "direction": "high", "value": current,
            "action": action, "timestamp": datetime.now().isoformat(),
        })
        # 只保留最近 50 条
        self.state["corrections"] = self.state["corrections"][-50:]

        return action

    def _correct_low(self, var_name: str, current: float, spec: dict) -> str:
        """指标过低时的修复动作。"""
        actions = {
            "working_memory_size": "increase_perception_frequency",
            "event_rate": "lower_saliency_threshold",
            "cpu_usage": "increase_scan_frequency",
            "disk_usage": "no_action",
            "task_queue_depth": "no_action",
        }
        action = actions.get(var_name, "monitor")

        self.state["corrections"].append({
            "var": var_name, "direction": "low", "value": current,
            "action": action, "timestamp": datetime.now().isoformat(),
        })
        self.state["corrections"] = self.state["corrections"][-50:]

        return action

    # ═══ 查询接口 ═══

    def get_status(self) -> dict:
        """获取稳态系统状态。"""
        measurements = {}
        for var_name, spec in VARIABLES.items():
            current = self.measure(var_name)
            measurements[var_name] = {
                "current": current,
                "target": spec["target"],
                "range": f"{spec['min']}-{spec['max']}",
                "unit": spec["unit"],
                "status": "normal" if current is not None and spec["min"] <= current <= spec["max"] else "abnormal",
            }

        return {
            "measurements": measurements,
            "corrections": self.state.get("corrections", [])[-5:],
            "stats": self.state.get("stats", {}),
            "last_regulate": self.state.get("last_regulate"),
        }


# ═══ 便捷函数 ═══

def regulate(state_path=None) -> dict:
    """便捷函数：执行一轮稳态调节。"""
    hs = Homeostasis(state_path=state_path)
    return hs.regulate()


def get_status(state_path=None) -> dict:
    """便捷函数：获取稳态状态。"""
    hs = Homeostasis(state_path=state_path)
    return hs.get_status()


# ═══ CLI ═══

def main():
    parser = argparse.ArgumentParser(description="MCR Homeostasis (稳态系统)")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("regulate", help="Run one regulation cycle")
    sub.add_parser("status", help="Show current status")
    sub.add_parser("measurements", help="Show all measurements")

    args = parser.parse_args()
    hs = Homeostasis()

    if args.command == "regulate":
        results = hs.regulate()
        print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    elif args.command == "status":
        print(json.dumps(hs.get_status(), indent=2, ensure_ascii=False, default=str))
    elif args.command == "measurements":
        for name, spec in VARIABLES.items():
            val = hs.measure(name)
            status = "OK" if val is not None and spec["min"] <= val <= spec["max"] else "ABNORMAL"
            print(f"  {name}: {val} {spec['unit']} (target: {spec['min']}-{spec['max']}) [{status}]")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
