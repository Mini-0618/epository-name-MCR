"""
Global Workspace — MCR 的内分泌系统。

生物学原理：
- 全局工作空间理论 (GWT)：意识 = 关键信息从局部模块广播到全局
- 内分泌系统：激素（肾上腺素/多巴胺/皮质醇）广播到全身
- 不是所有事件都广播，只有显著性超过阈值的才进入全局意识

功能：
1. 接收 EventBus 事件，评估显著性
2. 高显著性信号广播到全局
3. 维护当前焦点、活跃目标、紧急队列
4. 任何模块都可以读取全局上下文
"""

import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

ECOSYSTEM_ROOT = Path(__file__).parent.parent
RUNTIME_DIR = ECOSYSTEM_ROOT / "runtime"
WORKSPACE_STATE = RUNTIME_DIR / ".wal" / "cognitive" / "global_workspace.json"
SIGNAL_LOG = RUNTIME_DIR / ".wal" / "cognitive" / "signals.jsonl"


# ═══ 信号类型定义 ═══

SIGNAL_TYPES = {
    "emergency":   {"color": "red",    "ttl": 60,    "priority": 4, "desc": "紧急：需要立即响应"},
    "opportunity": {"color": "yellow", "ttl": 300,   "priority": 3, "desc": "机会：值得探索"},
    "status":      {"color": "green",  "ttl": 600,   "priority": 2, "desc": "状态：正常更新"},
    "reflection":  {"color": "blue",   "ttl": 1800,  "priority": 1, "desc": "反思：低优先级"},
}

# 事件类型 → 默认信号映射
EVENT_SIGNAL_MAP = {
    "error":             "emergency",
    "security_event":    "emergency",
    "task_failed":       "emergency",
    "opportunity_found": "opportunity",
    "new_goal":          "opportunity",
    "task_completed":    "status",
    "cycle_complete":    "status",
    "memory_decayed":    "reflection",
    "pattern_detected":  "reflection",
}


class GlobalWorkspace:
    """
    MCR 的"内分泌系统"。

    接收所有事件，评估显著性，广播重要信号。
    任何模块都可以读取当前全局状态。
    """

    def __init__(self, state_path=None, signal_log_path=None):
        self.state_path = Path(state_path) if state_path else WORKSPACE_STATE
        self.signal_log_path = Path(signal_log_path) if signal_log_path else SIGNAL_LOG
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.signal_log_path.parent.mkdir(parents=True, exist_ok=True)

        # 加载状态
        self.state = self._load_state()

    def _load_state(self) -> dict:
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "focus": None,
            "active_goals": [],
            "signal_history": [],
            "emergency_queue": [],
            "last_broadcast": None,
            "stats": {"total_evaluated": 0, "total_broadcast": 0},
        }

    def _save_state(self):
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def _log_signal(self, signal: dict):
        with open(self.signal_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(signal, ensure_ascii=False) + "\n")

    # ═══ 核心：显著性评估 ═══

    def evaluate(self, event: dict) -> Optional[dict]:
        """
        评估事件的显著性，决定是否广播。

        返回 signal dict 如果广播，否则 None。
        """
        self.state["stats"]["total_evaluated"] += 1

        saliency = self._compute_saliency(event)
        event_type = event.get("type", event.get("event_type", "unknown"))
        signal_type = EVENT_SIGNAL_MAP.get(event_type, "status")

        # 显著性阈值：emergency 总是广播，其他需要 > 0.3
        threshold = 0.0 if signal_type == "emergency" else 0.3

        if saliency >= threshold:
            signal = {
                "signal_type": signal_type,
                "saliency": round(saliency, 3),
                "event_type": event_type,
                "event_data": {k: v for k, v in event.items() if k not in ("type", "event_type")},
                "timestamp": datetime.now().isoformat(),
                "ttl": SIGNAL_TYPES[signal_type]["ttl"],
                "priority": SIGNAL_TYPES[signal_type]["priority"],
            }

            # 更新状态
            self.state["signal_history"].append(signal)
            # 只保留最近 50 条
            self.state["signal_history"] = self.state["signal_history"][-50:]

            if signal_type == "emergency":
                self.state["emergency_queue"].append(signal)

            # 更新焦点
            if signal["priority"] >= 3:
                self.state["focus"] = {
                    "signal_type": signal_type,
                    "event_type": event_type,
                    "since": signal["timestamp"],
                }

            self.state["stats"]["total_broadcast"] += 1
            self.state["last_broadcast"] = signal["timestamp"]

            # 记录日志
            self._log_signal(signal)
            self._save_state()

            return signal

        return None

    def _compute_saliency(self, event: dict) -> float:
        """
        计算事件显著性（0-1）。

        4 个因素：
        - novelty: 新颖性（最近没出现过的事件类型 → 高）
        - relevance: 与当前目标的相关性
        - urgency: 紧迫性（错误/安全 → 高）
        - valence: 正负面（负面事件更显著）
        """
        factors = []

        # novelty: 最近 20 条信号中有多少同类型
        recent_types = [s.get("event_type") for s in self.state["signal_history"][-20:]]
        event_type = event.get("type", event.get("event_type", "unknown"))
        same_count = recent_types.count(event_type)
        novelty = max(0, 1.0 - same_count * 0.2)  # 出现越多越不新颖
        factors.append(("novelty", novelty, 0.25))

        # relevance: 与当前焦点相关
        relevance = 0.5  # 默认中等
        if self.state.get("focus") and self.state["focus"].get("event_type") == event_type:
            relevance = 0.9  # 与当前焦点相同
        factors.append(("relevance", relevance, 0.2))

        # urgency: 错误/安全事件高紧迫
        urgency_map = {
            "error": 1.0, "security_event": 1.0, "task_failed": 0.8,
            "opportunity_found": 0.6, "new_goal": 0.5,
            "task_completed": 0.3, "cycle_complete": 0.2,
        }
        urgency = urgency_map.get(event_type, 0.3)
        factors.append(("urgency", urgency, 0.35))

        # valence: 负面事件更显著
        negative_types = {"error", "security_event", "task_failed"}
        positive_types = {"task_completed", "opportunity_found"}
        if event_type in negative_types:
            valence = 0.9
        elif event_type in positive_types:
            valence = 0.6
        else:
            valence = 0.4
        factors.append(("valence", valence, 0.2))

        # 加权平均
        total_weight = sum(w for _, _, w in factors)
        saliency = sum(v * w for _, v, w in factors) / total_weight

        return saliency

    # ═══ 查询接口（任何模块可调用）═══

    def get_context(self) -> dict:
        """获取当前全局上下文。"""
        # 清理过期信号
        now = time.time()
        self.state["emergency_queue"] = [
            s for s in self.state["emergency_queue"]
            if (now - datetime.fromisoformat(s["timestamp"]).timestamp()) < s.get("ttl", 60)
        ]

        return {
            "focus": self.state.get("focus"),
            "active_goals": self.state.get("active_goals", []),
            "recent_signals": self.state["signal_history"][-10:],
            "emergency_pending": len(self.state.get("emergency_queue", [])) > 0,
            "emergency_count": len(self.state.get("emergency_queue", [])),
            "stats": self.state.get("stats", {}),
        }

    def get_focus(self) -> Optional[dict]:
        """获取当前焦点。"""
        return self.state.get("focus")

    def has_emergency(self) -> bool:
        """是否有紧急信号。"""
        return len(self.state.get("emergency_queue", [])) > 0

    def pop_emergency(self) -> Optional[dict]:
        """取出最旧的紧急信号。"""
        queue = self.state.get("emergency_queue", [])
        if queue:
            signal = queue.pop(0)
            self._save_state()
            return signal
        return None

    def set_focus(self, focus: dict):
        """手动设置焦点。"""
        self.state["focus"] = focus
        self._save_state()

    def clear_focus(self):
        """清除焦点。"""
        self.state["focus"] = None
        self._save_state()

    def add_active_goal(self, goal: dict):
        """添加活跃目标。"""
        self.state.setdefault("active_goals", []).append(goal)
        self._save_state()

    def remove_active_goal(self, goal_id: str):
        """移除活跃目标。"""
        self.state["active_goals"] = [
            g for g in self.state.get("active_goals", [])
            if g.get("id") != goal_id
        ]
        self._save_state()


# ═══ 便捷函数 ═══

def evaluate_event(event: dict, state_path=None) -> Optional[dict]:
    """便捷函数：评估单个事件。"""
    ws = GlobalWorkspace(state_path=state_path)
    return ws.evaluate(event)


def get_context(state_path=None) -> dict:
    """便捷函数：获取全局上下文。"""
    ws = GlobalWorkspace(state_path=state_path)
    return ws.get_context()


# ═══ CLI ═══

def main():
    parser = argparse.ArgumentParser(description="MCR Global Workspace (内分泌系统)")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("context", help="Show current global context")
    sub.add_parser("signals", help="Show recent signals")
    sub.add_parser("stats", help="Show stats")

    p_eval = sub.add_parser("evaluate", help="Evaluate an event")
    p_eval.add_argument("--type", default="task_completed", help="Event type")
    p_eval.add_argument("--data", default="{}", help="Event data JSON")

    args = parser.parse_args()
    ws = GlobalWorkspace()

    if args.command == "context":
        ctx = ws.get_context()
        print(json.dumps(ctx, indent=2, ensure_ascii=False))
    elif args.command == "signals":
        print(json.dumps(ws.state.get("signal_history", [])[-20:], indent=2, ensure_ascii=False))
    elif args.command == "stats":
        print(json.dumps(ws.state.get("stats", {}), indent=2))
    elif args.command == "evaluate":
        event = json.loads(args.data)
        event["type"] = args.type
        signal = ws.evaluate(event)
        if signal:
            print(f"[broadcast] {signal['signal_type']} (saliency={signal['saliency']})")
            print(json.dumps(signal, indent=2, ensure_ascii=False))
        else:
            print("[filtered] Event saliency below threshold")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
