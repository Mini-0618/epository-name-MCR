"""
Sleep Consolidator — MCR 的记忆巩固系统。

生物学原理：
- 海马体快速编码 → 新皮层慢速巩固
- 睡眠期间记忆被重组和压缩
- 突触缩放：常用的记忆增强，不用的衰减
- REM 睡眠：情感记忆巩固
- 慢波睡眠：陈述性记忆巩固

功能：
1. 回放：从 working memory 中选择高价值事件回放
2. 整合：将相关记忆合并为更紧凑的表示
3. 清理：删除低价值的 working memory 条目
4. 索引：更新语义索引
"""

import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from collections import Counter

ECOSYSTEM_ROOT = Path(__file__).parent.parent
RUNTIME_DIR = ECOSYSTEM_ROOT / "runtime"
MEMORY_DIR = RUNTIME_DIR / "memory"
WAL_COGNITIVE = RUNTIME_DIR / ".wal" / "cognitive"
CONSOLIDATION_LOG = WAL_COGNITIVE / "consolidation_log.jsonl"
CONSOLIDATION_STATE = WAL_COGNITIVE / "consolidation_state.json"


class SleepConsolidator:
    """
    MCR 的"记忆巩固系统"。

    模拟海马-新皮层记忆巩固：
    - 在"空闲"时段（无活跃任务时）自动运行
    - 选择高价值事件回放
    - 整合相关记忆
    - 清理低价值条目
    - 更新语义索引
    """

    def __init__(self, state_path=None):
        self.state_path = Path(state_path) if state_path else CONSOLIDATION_STATE
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
            "last_consolidation": None,
            "total_runs": 0,
            "total_replayed": 0,
            "total_integrated": 0,
            "total_cleaned": 0,
            "memory_stats": {},
        }

    def _save_state(self):
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def _log(self, entry: dict):
        CONSOLIDATION_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(CONSOLIDATION_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ═══ Step 1: 选择候选记忆 ═══

    def select_candidates(self, max_candidates: int = 50) -> list:
        """
        从 working memory 中选择高价值事件。

        选择标准：
        - 最近 24h 内的事件
        - 错误/安全事件优先
        - 重复出现的事件类型优先
        """
        candidates = []

        # 读取 events.jsonl
        events_file = RUNTIME_DIR / "events.jsonl"
        if not events_file.exists():
            return candidates

        now = datetime.now()
        cutoff = now - timedelta(hours=24)

        try:
            with open(events_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for line in lines[-500:]:  # 只看最近 500 条
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts = entry.get("timestamp", entry.get("ts", ""))
                    if not ts:
                        continue

                    event_time = datetime.fromisoformat(ts.replace("Z", "+00:00").split("+")[0])
                    if event_time < cutoff:
                        continue

                    # 计算价值分
                    value = self._compute_memory_value(entry)
                    entry["_memory_value"] = value
                    entry["_event_time"] = ts
                    candidates.append(entry)
                except Exception:
                    continue
        except Exception:
            pass

        # 按价值排序，取 top N
        candidates.sort(key=lambda x: x.get("_memory_value", 0), reverse=True)
        return candidates[:max_candidates]

    def _compute_memory_value(self, entry: dict) -> float:
        """
        计算记忆价值（0-1）。

        高价值：错误、安全事件、新模式
        低价值：重复的 routine 事件
        """
        event_type = entry.get("type", entry.get("event_type", "unknown"))
        value = 0.3  # 基础分

        # 事件类型加分
        high_value_types = {"error", "security_event", "task_failed", "opportunity_found"}
        medium_value_types = {"task_completed", "new_goal", "pattern_detected"}
        if event_type in high_value_types:
            value += 0.4
        elif event_type in medium_value_types:
            value += 0.2

        # 有详细数据加分
        if entry.get("data") or entry.get("details"):
            value += 0.1

        # 有错误信息加分
        if entry.get("error") or entry.get("stderr"):
            value += 0.2

        return min(1.0, value)

    # ═══ Step 2: 回放与整合 ═══

    def replay_and_integrate(self, candidates: list) -> dict:
        """
        回放候选记忆并整合。

        整合策略：
        - 相同事件类型的记忆合并为摘要
        - 高价值记忆保留原文
        - 低价值记忆只保留统计
        """
        if not candidates:
            return {"replayed": 0, "integrated": 0, "groups": {}}

        # 按事件类型分组
        groups = {}
        for entry in candidates:
            event_type = entry.get("type", entry.get("event_type", "unknown"))
            if event_type not in groups:
                groups[event_type] = []
            groups[event_type].append(entry)

        integrated = {}
        replayed_count = 0

        for event_type, entries in groups.items():
            if len(entries) == 1:
                # 单条记忆：保留原文
                integrated[event_type] = {
                    "count": 1,
                    "mode": "full",
                    "entries": entries,
                }
                replayed_count += 1
            elif len(entries) <= 5:
                # 少量记忆：全部保留
                integrated[event_type] = {
                    "count": len(entries),
                    "mode": "group",
                    "entries": entries,
                    "summary": f"{len(entries)} occurrences of {event_type}",
                }
                replayed_count += len(entries)
            else:
                # 大量记忆：压缩为统计
                avg_value = sum(e.get("_memory_value", 0) for e in entries) / len(entries)
                top_entries = sorted(entries, key=lambda x: x.get("_memory_value", 0), reverse=True)[:3]
                integrated[event_type] = {
                    "count": len(entries),
                    "mode": "compressed",
                    "top_entries": top_entries,
                    "summary": f"{len(entries)} occurrences, avg_value={avg_value:.2f}",
                }
                replayed_count += len(entries)

        return {
            "replayed": replayed_count,
            "integrated": len(groups),
            "groups": integrated,
        }

    # ═══ Step 3: 清理低价值记忆 ═══

    def cleanup_old_memories(self, max_age_hours: int = 168) -> dict:
        """
        清理旧记忆。

        保留：
        - 高价值记忆（>0.7）永久保留
        - 中价值记忆（0.3-0.7）保留 7 天
        - 低价值记忆（<0.3）保留 24h
        """
        cleaned = 0
        kept = 0

        # 清理 WAL 中的旧认知日志
        wal_files = list(WAL_COGNITIVE.glob("*.jsonl"))
        for wal_file in wal_files:
            if wal_file.name in ("consolidation_log.jsonl",):
                continue  # 不清理巩固日志

            try:
                with open(wal_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                new_lines = []
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        ts = entry.get("timestamp", entry.get("ts", ""))
                        if ts:
                            event_time = datetime.fromisoformat(ts.replace("Z", "+00:00").split("+")[0])
                            age_hours = (datetime.now() - event_time).total_seconds() / 3600

                            # 高价值保留
                            value = entry.get("_memory_value", 0.5)
                            if value > 0.7:
                                new_lines.append(line)
                                kept += 1
                            elif value > 0.3 and age_hours < max_age_hours:
                                new_lines.append(line)
                                kept += 1
                            elif age_hours < 24:
                                new_lines.append(line)
                                kept += 1
                            else:
                                cleaned += 1
                        else:
                            new_lines.append(line)
                            kept += 1
                    except Exception:
                        new_lines.append(line)
                        kept += 1

                # 回写
                if cleaned > 0:
                    with open(wal_file, "w", encoding="utf-8") as f:
                        for line in new_lines:
                            f.write(line + "\n")

            except Exception:
                continue

        return {"cleaned": cleaned, "kept": kept}

    # ═══ Step 4: 更新索引 ═══

    def update_index(self, integrated: dict) -> dict:
        """更新语义索引。"""
        index_path = WAL_COGNITIVE / "memory_index.json"

        # 加载现有索引
        index = {}
        if index_path.exists():
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    index = json.load(f)
            except Exception:
                pass

        # 更新索引
        for event_type, data in integrated.items():
            if event_type not in index:
                index[event_type] = {"count": 0, "last_seen": None, "summary": ""}

            index[event_type]["count"] += data.get("count", 0)
            index[event_type]["last_seen"] = datetime.now().isoformat()
            index[event_type]["summary"] = data.get("summary", "")

        # 保存
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

        return {"indexed_types": len(integrated), "total_types": len(index)}

    # ═══ 主流程：一次完整巩固 ═══

    def consolidate(self) -> dict:
        """
        执行一次完整的记忆巩固。

        流程：
        1. 选择候选记忆
        2. 回放与整合
        3. 清理低价值记忆
        4. 更新索引
        """
        self.state["total_runs"] += 1
        start_time = datetime.now()

        # Step 1: 选择
        candidates = self.select_candidates()

        # Step 2: 回放与整合
        integration_result = self.replay_and_integrate(candidates)
        self.state["total_replayed"] += integration_result["replayed"]
        self.state["total_integrated"] += integration_result["integrated"]

        # Step 3: 清理
        cleanup_result = self.cleanup_old_memories()
        self.state["total_cleaned"] += cleanup_result["cleaned"]

        # Step 4: 更新索引
        index_result = self.update_index(integration_result.get("groups", {}))

        duration = (datetime.now() - start_time).total_seconds()

        result = {
            "timestamp": start_time.isoformat(),
            "duration_seconds": round(duration, 2),
            "candidates_selected": len(candidates),
            "replayed": integration_result["replayed"],
            "integrated": integration_result["integrated"],
            "cleaned": cleanup_result["cleaned"],
            "kept": cleanup_result["kept"],
            "indexed": index_result["indexed_types"],
        }

        self.state["last_consolidation"] = start_time.isoformat()
        self._save_state()
        self._log(result)

        return result

    # ═══ 查询接口 ═══

    def get_status(self) -> dict:
        """获取巩固系统状态。"""
        return {
            "last_consolidation": self.state.get("last_consolidation"),
            "total_runs": self.state.get("total_runs", 0),
            "total_replayed": self.state.get("total_replayed", 0),
            "total_integrated": self.state.get("total_integrated", 0),
            "total_cleaned": self.state.get("total_cleaned", 0),
        }


# ═══ 便捷函数 ═══

def consolidate(state_path=None) -> dict:
    """便捷函数：执行一次巩固。"""
    sc = SleepConsolidator(state_path=state_path)
    return sc.consolidate()


def get_status(state_path=None) -> dict:
    """便捷函数：获取巩固状态。"""
    sc = SleepConsolidator(state_path=state_path)
    return sc.get_status()


# ═══ CLI ═══

def main():
    parser = argparse.ArgumentParser(description="MCR Sleep Consolidator (记忆巩固)")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("consolidate", help="Run one consolidation cycle")
    sub.add_parser("status", help="Show status")
    sub.add_parser("candidates", help="Show consolidation candidates")

    args = parser.parse_args()
    sc = SleepConsolidator()

    if args.command == "consolidate":
        result = sc.consolidate()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.command == "status":
        print(json.dumps(sc.get_status(), indent=2, ensure_ascii=False))
    elif args.command == "candidates":
        candidates = sc.select_candidates()
        print(f"Found {len(candidates)} candidates:")
        for c in candidates[:10]:
            event_type = c.get("type", c.get("event_type", "?"))
            value = c.get("_memory_value", 0)
            print(f"  [{value:.2f}] {event_type}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
