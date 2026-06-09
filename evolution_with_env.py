"""
Evolution with Dynamic Environment — 真正的进化。

环境会变化，策略必须适应。
"""

from __future__ import annotations

import json
import random
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ECOSYSTEM_ROOT = Path(__file__).parent


class DynamicEnvironment:
    """动态环境：端口会随机开关。"""

    def __init__(self, base_ports: list[int] = None):
        self.base_ports = base_ports or [21, 22, 80, 443, 445, 3306, 3389, 6379, 8080, 27017]
        self.open_ports: set[int] = set()
        self.generation = 0

    def evolve(self):
        """环境每代变化：随机开关 1-3 个端口。"""
        self.generation += 1
        changes = random.randint(1, 3)
        for _ in range(changes):
            port = random.choice(self.base_ports)
            if port in self.open_ports:
                self.open_ports.discard(port)
            else:
                self.open_ports.add(port)
        # 确保至少有 1 个端口开放
        if not self.open_ports:
            self.open_ports.add(random.choice(self.base_ports))

    def scan(self, timeout: float = 0.3) -> list[int]:
        """扫描当前环境。"""
        found = []
        for port in self.base_ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                # 用 connect_ex 检测，但基于环境状态决定是否真正开放
                # 模拟：只有环境中的开放端口才响应
                if port in self.open_ports:
                    # 真实端口检测
                    result = sock.connect_ex(('127.0.0.1', port))
                    if result == 0:
                        found.append(port)
                sock.close()
            except Exception:
                try:
                    sock.close()
                except Exception:
                    pass
        return found


class EvolvingStrategy:
    """进化中的审计策略。"""

    def __init__(self, genes: dict = None):
        self.genes = genes or {
            "port_weights": {p: random.uniform(0.1, 1.0) for p in [21, 22, 80, 443, 445, 3306, 3389, 6379, 8080, 27017]},
            "timeout": random.choice([0.2, 0.3, 0.5, 1.0]),
            "threshold": random.uniform(0.3, 0.8),  # 权重超过阈值才扫描
        }
        self.fitness = 0.0
        self.discoveries: list[int] = []
        self.scanned_ports: list[int] = []

    def decide_ports(self) -> list[int]:
        """根据基因权重决定扫哪些端口。"""
        threshold = self.genes["threshold"]
        return [port for port, weight in self.genes["port_weights"].items() if weight > threshold]

    def crossover(self, other: "EvolvingStrategy") -> "EvolvingStrategy":
        child_weights = {}
        for port in self.genes["port_weights"]:
            if random.random() < 0.5:
                child_weights[port] = self.genes["port_weights"][port]
            else:
                child_weights[port] = other.genes["port_weights"][port]
        return EvolvingStrategy({
            "port_weights": child_weights,
            "timeout": random.choice([self.genes["timeout"], other.genes["timeout"]]),
            "threshold": (self.genes["threshold"] + other.genes["threshold"]) / 2,
        })

    def mutate(self, rate: float = 0.3) -> "EvolvingStrategy":
        new_weights = dict(self.genes["port_weights"])
        for port in new_weights:
            if random.random() < rate:
                new_weights[port] = max(0.0, min(1.0, new_weights[port] + random.uniform(-0.3, 0.3)))
        return EvolvingStrategy({
            "port_weights": new_weights,
            "timeout": self.genes["timeout"] if random.random() > rate else random.choice([0.2, 0.3, 0.5, 1.0]),
            "threshold": max(0.1, min(0.9, self.genes["threshold"] + random.uniform(-0.2, 0.2) if random.random() < rate else self.genes["threshold"])),
        })


def evaluate_strategy(strategy: EvolvingStrategy, env: DynamicEnvironment) -> float:
    """评估策略在当前环境中的表现。"""
    target_ports = strategy.decide_ports()
    strategy.scanned_ports = target_ports

    # 模拟扫描：只发现环境中真正开放的端口
    strategy.discoveries = [p for p in target_ports if p in env.open_ports]

    # 适应度
    if not env.open_ports:
        return 0.0

    recall = len(strategy.discoveries) / len(env.open_ports)  # 发现率
    precision = len(strategy.discoveries) / max(1, len(target_ports))  # 准确率
    efficiency = 1.0 - len(target_ports) / 10  # 效率（扫的越少越好）

    fitness = 0.5 * recall + 0.3 * precision + 0.2 * max(0, efficiency)
    return round(fitness, 4)


def run_evolution(generations: int = 30, population_size: int = 10):
    """运行进化。"""
    env = DynamicEnvironment()
    population = [EvolvingStrategy() for _ in range(population_size)]

    print(f"=== Evolution with Dynamic Environment ===")
    print(f"Generations: {generations}, Population: {population_size}")
    print()

    history = []

    for gen in range(1, generations + 1):
        # 环境变化
        env.evolve()

        # 评估
        for strategy in population:
            strategy.fitness = evaluate_strategy(strategy, env)

        # 排序
        population.sort(key=lambda s: s.fitness, reverse=True)
        best = population[0]
        avg = sum(s.fitness for s in population) / len(population)

        # 记录
        record = {
            "gen": gen,
            "best_fitness": best.fitness,
            "avg_fitness": round(avg, 4),
            "env_ports": sorted(env.open_ports),
            "best_scanned": sorted(best.scanned_ports),
            "best_discovered": sorted(best.discoveries),
            "best_threshold": round(best.genes["threshold"], 2),
        }
        history.append(record)

        # 输出
        env_str = ",".join(str(p) for p in sorted(env.open_ports))
        scan_str = ",".join(str(p) for p in sorted(best.scanned_ports))
        disc_str = ",".join(str(p) for p in sorted(best.discoveries))
        print(f"Gen {gen:2d} | fitness={best.fitness:.4f} avg={avg:.4f} | "
              f"env=[{env_str}] scan=[{scan_str}] found=[{disc_str}] | "
              f"threshold={best.genes['threshold']:.2f}")

        # 繁殖
        new_population = [EvolvingStrategy(dict(best.genes))]  # 精英
        while len(new_population) < population_size:
            p1 = max(random.sample(population, min(3, len(population))), key=lambda s: s.fitness)
            p2 = max(random.sample(population, min(3, len(population))), key=lambda s: s.fitness)
            if random.random() < 0.7:
                child = p1.crossover(p2)
            else:
                child = p1.mutate()
            new_population.append(child)
        population = new_population

    # 保存
    out_path = ECOSYSTEM_ROOT / "runtime" / ".wal" / "cognitive" / "real_evolution.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"history": history}, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print(f"=== Results ===")
    fitnesses = [h["best_fitness"] for h in history]
    print(f"First gen: {fitnesses[0]:.4f}")
    print(f"Last gen:  {fitnesses[-1]:.4f}")
    print(f"Max:       {max(fitnesses):.4f}")
    print(f"Trend:     {'improving' if fitnesses[-1] > fitnesses[0] else 'stable'}")

    # 分析进化
    early_avg = sum(fitnesses[:5]) / 5
    late_avg = sum(fitnesses[-5:]) / 5
    print(f"Early avg: {early_avg:.4f}")
    print(f"Late avg:  {late_avg:.4f}")
    print(f"Improvement: {((late_avg - early_avg) / early_avg * 100):.1f}%")


if __name__ == "__main__":
    run_evolution()
