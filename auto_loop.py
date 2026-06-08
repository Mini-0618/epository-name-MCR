"""
MCR 自动循环 — 不需要人看着，自己跑。

后台运行：
    python auto_loop.py

每 60 秒做一轮：
1. 认知循环 10 轮
2. 稳态调节
3. 记忆巩固
4. 进化 1 代
5. 免疫巡逻
6. 异常自修复
7. 写日志

跑到你手动停（Ctrl+C）为止。
"""

from __future__ import annotations

import json
import sys
import time
import signal
from datetime import datetime
from pathlib import Path

RUNTIME_DIR = Path(__file__).parent / "runtime"
sys.path.insert(0, str(RUNTIME_DIR))

# 优雅退出
running = True
def handle_signal(sig, frame):
    global running
    running = False
    print("\n[MCR] 收到停止信号，正在优雅退出...")

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def main():
    global running

    log("MCR 自动循环启动")
    log("按 Ctrl+C 停止")

    # 导入模块
    from global_workspace import GlobalWorkspace
    from homeostasis import Homeostasis
    from sleep_consolidator import SleepConsolidator
    from evolution import EvolutionEngine
    from immune_system import patrol

    ws = GlobalWorkspace()
    hs = Homeostasis()
    sc = SleepConsolidator()
    evo = EvolutionEngine(state_path=str(RUNTIME_DIR / ".wal" / "cognitive" / "evolution_state.json"), population_size=10)

    if not evo.state.get("population"):
        evo.initialize_population()
        log("进化种群初始化完成")

    cycle = 0
    errors = 0

    while running:
        cycle += 1
        try:
            # 1. 认知循环 10 轮
            for i in range(10):
                ws.evaluate({"type": "cycle_complete", "cycle": cycle * 10 + i})

            # 2. 稳态调节
            hs_result = hs.regulate()
            abnormal = [k for k, v in hs_result.items() if v.get("status") not in ("normal", "unavailable")]

            # 3. 记忆巩固（每 5 轮）
            sc_result = {"replayed": 0, "cleaned": 0}
            if cycle % 5 == 0:
                sc_result = sc.consolidate()

            # 4. 进化 1 代
            evo_result = evo.evolve_generation()

            # 5. 免疫巡逻（每 10 轮）
            immune = {"summary": {"detected": 0, "fixed": 0}}
            if cycle % 10 == 0:
                immune = patrol()

            # 6. 异常自修复
            fixes = 0
            if abnormal:
                # working_memory_size 异常 → 触发巩固
                if "working_memory_size" in abnormal:
                    sc.consolidate()
                    fixes += 1

            # 7. 写日志
            log_entry = {
                "ts": datetime.now().isoformat(),
                "cycle": cycle,
                "abnormal": abnormal,
                "evo_gen": evo_result["generation"],
                "evo_fitness": evo_result["best_fitness"],
                "immune": immune["summary"],
                "sc": sc_result,
                "fixes": fixes,
            }
            log_path = RUNTIME_DIR / ".wal" / "cognitive" / "auto_loop_log.jsonl"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

            # 输出
            abn = f" abnormal={abnormal}" if abnormal else ""
            fix = f" fixes={fixes}" if fixes else ""
            log(f"#{cycle:4d} | evo={evo_result['generation']} fitness={evo_result['best_fitness']:.4f} | immune={immune['summary']['detected']} | sc={sc_result['replayed']}/{sc_result['cleaned']}{abn}{fix}")

            errors = 0  # 重置错误计数

        except Exception as e:
            errors += 1
            log(f"#{cycle:4d} | ERROR: {e}")
            if errors >= 5:
                log("连续 5 次错误，停止")
                break

        # 等 60 秒
        for _ in range(60):
            if not running:
                break
            time.sleep(1)

    log(f"MCR 自动循环停止。共 {cycle} 轮。")


if __name__ == "__main__":
    main()
