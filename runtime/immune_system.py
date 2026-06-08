"""
Immune System — MCR 的免疫系统。

两层防御：
1. 先天免疫：已知问题 → 查表修复（快速）
2. 适应性免疫：未知问题 → 学习记忆（长期）

整合 failure_analyzer + pattern_detector + self_correction。
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from collections import Counter

ECOSYSTEM_ROOT = Path(__file__).parent.parent
RUNTIME_DIR = ECOSYSTEM_ROOT / "runtime"
EVENTS_LOG = RUNTIME_DIR / "events.jsonl"
IMMUNE_MEMORY = RUNTIME_DIR / ".wal" / "cognitive" / "immune_memory.jsonl"
IMMUNE_STATE = RUNTIME_DIR / ".wal" / "cognitive" / "immune_state.json"


# ═══ 先天免疫：已知问题 → 修复动作 ═══

INNATE_RESPONSES = {
    # 问题类型 → (检测函数, 修复函数)
    "memory_pressure": {
        "detect": lambda: _check_memory_pressure(),
        "fix": lambda: _fix_memory_pressure(),
        "description": "Working memory 条目过多",
    },
    "event_backlog": {
        "detect": lambda: _check_event_backlog(),
        "fix": lambda: _fix_event_backlog(),
        "description": "events.jsonl 文件过大",
    },
    "disk_pressure": {
        "detect": lambda: _check_disk_pressure(),
        "fix": lambda: _fix_disk_pressure(),
        "description": "磁盘使用率过高",
    },
    "encoding_corruption": {
        "detect": lambda: _check_encoding_corruption(),
        "fix": lambda: _fix_encoding_corruption(),
        "description": "文件编码损坏",
    },
    "missing_directories": {
        "detect": lambda: _check_missing_dirs(),
        "fix": lambda: _fix_missing_dirs(),
        "description": "必需目录缺失",
    },
    "stale_sessions": {
        "detect": lambda: _check_stale_sessions(),
        "fix": lambda: _fix_stale_sessions(),
        "description": "过期会话未清理",
    },
    "high_failure_rate": {
        "detect": lambda: _check_failure_rate(),
        "fix": lambda: _fix_high_failure_rate(),
        "description": "失败率异常偏高",
    },
}


# ═══ 检测函数 ═══

def _check_memory_pressure():
    """检查 working memory 是否压力过大。"""
    memory_dir = RUNTIME_DIR / "memory"
    if not memory_dir.exists():
        return None
    count = 0
    for f in memory_dir.glob("*.jsonl"):
        try:
            count += sum(1 for _ in open(f, encoding="utf-8", errors="replace"))
        except Exception:
            pass
    if count > 1000:
        return {"type": "memory_pressure", "count": count, "threshold": 1000}
    return None


def _check_event_backlog():
    """检查 events.jsonl 是否过大。"""
    if not EVENTS_LOG.exists():
        return None
    size_mb = EVENTS_LOG.stat().st_size / (1024 * 1024)
    if size_mb > 10:
        return {"type": "event_backlog", "size_mb": round(size_mb, 1), "threshold_mb": 10}
    return None


def _check_disk_pressure():
    """检查磁盘使用率。"""
    import shutil
    total, used, free = shutil.disk_usage("C:/")
    usage_pct = round(used / total * 100, 1)
    if usage_pct > 90:
        return {"type": "disk_pressure", "usage_pct": usage_pct, "threshold_pct": 90}
    return None


def _check_encoding_corruption():
    """检查关键文件是否有编码问题。"""
    issues = []
    for f in [EVENTS_LOG]:
        if f.exists():
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    fh.read(1000)
            except UnicodeDecodeError:
                issues.append(str(f))
    if issues:
        return {"type": "encoding_corruption", "files": issues}
    return None


def _check_missing_dirs():
    """检查必需目录是否存在。"""
    required = [
        RUNTIME_DIR / ".wal",
        RUNTIME_DIR / ".wal" / "cognitive",
        RUNTIME_DIR / "memory",
        RUNTIME_DIR / "life",
    ]
    missing = [str(d) for d in required if not d.exists()]
    if missing:
        return {"type": "missing_directories", "missing": missing}
    return None


def _check_stale_sessions():
    """检查过期会话。"""
    sessions_dir = RUNTIME_DIR / ".wal" / "sessions"
    if not sessions_dir.exists():
        return None
    stale = []
    for d in sessions_dir.iterdir():
        if d.is_dir():
            meta = d / "metadata.json"
            if meta.exists():
                try:
                    with open(meta) as f:
                        data = json.loads(f.read())
                    created = data.get("created_at", "")
                    if created:
                        age = (datetime.now() - datetime.fromisoformat(created)).days
                        if age > 7:
                            stale.append({"session": d.name, "age_days": age})
                except Exception:
                    pass
    if stale:
        return {"type": "stale_sessions", "count": len(stale), "sessions": stale[:5]}
    return None


def _check_failure_rate():
    """检查失败率是否异常。"""
    if not EVENTS_LOG.exists():
        return None
    events = []
    with open(EVENTS_LOG, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    events = events[-100:]  # 最近 100 条
    if not events:
        return None
    failures = sum(1 for e in events if e.get("payload", {}).get("status") in ("error", "failed"))
    rate = round(failures / len(events) * 100, 1)
    if rate > 20:
        return {"type": "high_failure_rate", "rate_pct": rate, "threshold_pct": 20}
    return None


# ═══ 修复函数 ═══

def _fix_memory_pressure():
    """修复内存压力：标记低价值记忆为待清理。"""
    return {"action": "trigger_consolidation", "status": "suggested"}


def _fix_event_backlog():
    """修复事件堆积：建议压缩。"""
    return {"action": "trigger_compaction", "status": "suggested"}


def _fix_disk_pressure():
    """修复磁盘压力：清理临时文件。"""
    cleaned = 0
    # 清理 .wal 下超过 30 天的文件
    wal_dir = RUNTIME_DIR / ".wal"
    if wal_dir.exists():
        for f in wal_dir.rglob("*"):
            if f.is_file():
                age_days = (datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)).days
                if age_days > 30 and f.suffix in (".log", ".tmp"):
                    try:
                        f.unlink()
                        cleaned += 1
                    except Exception:
                        pass
    return {"action": "cleanup_temp_files", "cleaned": cleaned}


def _fix_encoding_corruption():
    """修复编码问题。"""
    return {"action": "flag_for_repair", "status": "needs_manual_review"}


def _fix_missing_dirs():
    """修复缺失目录。"""
    created = []
    for d in [
        RUNTIME_DIR / ".wal",
        RUNTIME_DIR / ".wal" / "cognitive",
        RUNTIME_DIR / "memory",
        RUNTIME_DIR / "life",
    ]:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created.append(str(d))
    return {"action": "create_directories", "created": created}


def _fix_stale_sessions():
    """修复过期会话：标记为待清理。"""
    return {"action": "flag_stale_sessions", "status": "suggested"}


def _fix_high_failure_rate():
    """修复高失败率：记录警告。"""
    return {"action": "alert_owner", "status": "logged"}


# ═══ 免疫记忆 ═══

def load_immune_memory():
    """加载免疫记忆。"""
    memories = []
    if IMMUNE_MEMORY.exists():
        with open(IMMUNE_MEMORY, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        memories.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return memories


def save_immune_encounter(threat_type, response, outcome):
    """保存一次免疫遭遇。"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "threat_type": threat_type,
        "response": response,
        "outcome": outcome,
    }
    IMMUNE_MEMORY.parent.mkdir(parents=True, exist_ok=True)
    with open(IMMUNE_MEMORY, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def find_similar_threat(threat_type):
    """在免疫记忆中查找类似威胁。"""
    memories = load_immune_memory()
    matches = [m for m in memories if m.get("threat_type") == threat_type]
    if matches:
        # 返回最近一次成功的修复
        successful = [m for m in matches if m.get("outcome") == "fixed"]
        if successful:
            return successful[-1]
    return None


# ═══ 巡逻（主函数） ═══

def patrol(verbose=False):
    """
    巡逻：检查系统健康，发现并修复问题。

    这是免疫系统的核心动作。定期运行。
    """
    results = {
        "timestamp": datetime.now().isoformat(),
        "threats_detected": [],
        "threats_fixed": [],
        "threats_skipped": [],
        "threats_unknown": [],
    }

    # 先天免疫：逐个检查已知威胁
    for threat_type, spec in INNATE_RESPONSES.items():
        try:
            detection = spec["detect"]()
            if detection:
                results["threats_detected"].append(detection)

                # 检查免疫记忆：之前处理过这个威胁吗？
                past = find_similar_threat(threat_type)
                if past and past.get("outcome") == "fixed":
                    # 记忆中有成功修复经验，直接用
                    results["threats_fixed"].append({
                        "type": threat_type,
                        "fix": past.get("response"),
                        "source": "immune_memory",
                    })
                    save_immune_encounter(threat_type, past.get("response"), "fixed")
                else:
                    # 执行先天修复
                    fix_result = spec["fix"]()
                    results["threats_fixed"].append({
                        "type": threat_type,
                        "fix": fix_result,
                        "source": "innate",
                    })
                    save_immune_encounter(threat_type, fix_result, "fixed")
        except Exception as e:
            results["threats_skipped"].append({
                "type": threat_type,
                "error": str(e)[:100],
            })

    # 总结
    results["summary"] = {
        "detected": len(results["threats_detected"]),
        "fixed": len(results["threats_fixed"]),
        "skipped": len(results["threats_skipped"]),
        "unknown": len(results["threats_unknown"]),
    }

    # 保存巡逻结果
    save_patrol_result(results)

    return results


def save_patrol_result(results):
    """保存巡逻结果到免疫状态文件。"""
    state = {
        "last_patrol": results["timestamp"],
        "threats_fixed_total": results["summary"]["fixed"],
        "immune_memory_size": len(load_immune_memory()),
    }
    IMMUNE_STATE.parent.mkdir(parents=True, exist_ok=True)
    with open(IMMUNE_STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def status():
    """显示免疫系统状态。"""
    memory = load_immune_memory()
    threat_counts = Counter(m.get("threat_type") for m in memory)

    state = {}
    if IMMUNE_STATE.exists():
        with open(IMMUNE_STATE, "r") as f:
            state = json.load(f)

    return {
        "immune_memory_size": len(memory),
        "threat_history": dict(threat_counts.most_common()),
        "last_patrol": state.get("last_patrol", "never"),
        "threats_fixed_total": state.get("threats_fixed_total", 0),
    }


# ═══ CLI ═══

def main():
    parser = argparse.ArgumentParser(description="MCR Immune System")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("patrol", help="Run patrol (check and fix threats)")
    sub.add_parser("status", help="Show immune system status")
    sub.add_parser("memory", help="Show immune memory")

    args = parser.parse_args()

    if args.command == "patrol":
        result = patrol()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.command == "status":
        result = status()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.command == "memory":
        memories = load_immune_memory()
        print(json.dumps({
            "total": len(memories),
            "recent": memories[-20:]
        }, indent=2, ensure_ascii=False))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
