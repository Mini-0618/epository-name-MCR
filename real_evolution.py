"""
Real Evolution — 真正能进化的系统。

不是刷数字，是用真实结果驱动进化。

策略:
1. 每个基因组 = 一种审计策略
2. 执行策略 = 扫描真实目标
3. 适应度 = 真实发现数量 + 知识匹配度 + 速度
4. 好的策略繁殖，差的淘汰
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
sys.path.insert(0, str(ECOSYSTEM_ROOT / "runtime"))


# ═══ 审计策略基因组 ═══

class AuditGenome:
    """一种审计策略的基因组。"""

    # 基因空间
    PORT_RANGES = {
        "quick": [21, 22, 23, 25, 80, 443, 445, 3306, 3389, 6379, 8080],
        "standard": [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 993, 995,
                     1433, 1521, 3306, 3389, 5432, 5900, 6379, 8080, 8443, 9200, 27017],
        "deep": list(range(1, 1025)) + [3306, 3389, 5432, 5900, 6379, 8080, 8443, 9200, 27017],
    }
    TIMEOUT_OPTIONS = [0.3, 0.5, 1.0, 2.0]
    THREAD_OPTIONS = [10, 25, 50, 100]
    SCAN_MODES = ["fast", "thorough"]

    def __init__(self, genes: dict = None):
        self.genes = genes or self._random_genes()
        self.fitness = 0.0
        self.results = {}
        self.id = f"g_{random.randint(10000, 99999)}"

    def _random_genes(self) -> dict:
        return {
            "port_range": random.choice(list(self.PORT_RANGES.keys())),
            "timeout": random.choice(self.TIMEOUT_OPTIONS),
            "threads": random.choice(self.THREAD_OPTIONS),
            "scan_mode": random.choice(self.SCAN_MODES),
            "risk_weight_critical": random.uniform(20, 40),
            "risk_weight_high": random.uniform(10, 20),
            "risk_weight_medium": random.uniform(3, 10),
        }

    def crossover(self, other: "AuditGenome") -> "AuditGenome":
        child_genes = {}
        for key in self.genes:
            if random.random() < 0.5:
                child_genes[key] = self.genes[key]
            else:
                child_genes[key] = other.genes[key]
        child = AuditGenome(child_genes)
        return child

    def mutate(self, rate: float = 0.2) -> "AuditGenome":
        mutated = dict(self.genes)
        for key in mutated:
            if random.random() < rate:
                if key == "port_range":
                    mutated[key] = random.choice(list(self.PORT_RANGES.keys()))
                elif key == "timeout":
                    mutated[key] = random.choice(self.TIMEOUT_OPTIONS)
                elif key == "threads":
                    mutated[key] = random.choice(self.THREAD_OPTIONS)
                elif key == "scan_mode":
                    mutated[key] = random.choice(self.SCAN_MODES)
                elif isinstance(mutated[key], float):
                    mutated[key] = mutated[key] * random.uniform(0.7, 1.3)
        return AuditGenome(mutated)

    def get_ports(self) -> list[int]:
        return self.PORT_RANGES.get(self.genes["port_range"], self.PORT_RANGES["standard"])


# ═══ 真实扫描执行器 ═══

def scan_port(host: str, port: int, timeout: float) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        try:
            sock.close()
        except Exception:
            pass
        return False


def execute_audit_strategy(genome: AuditGenome, target: str) -> dict:
    """执行一种审计策略，返回真实结果。"""
    start = time.time()

    try:
        ip = socket.gethostbyname(target)
    except socket.gaierror:
        return {"open_ports": 0, "risk_score": 0, "duration": 0, "error": "dns_failed"}

    ports = genome.get_ports()
    timeout = genome.genes["timeout"]
    threads = genome.genes["threads"]

    # 扫描
    open_ports = []
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {executor.submit(scan_port, ip, port, timeout): port for port in ports}
        for future in as_completed(futures):
            port = futures[future]
            try:
                if future.result():
                    open_ports.append(port)
            except Exception:
                pass

    duration = time.time() - start

    # 计算风险分
    risk_score = 0
    critical_ports = {23, 6379, 27017}  # Telnet, Redis, MongoDB
    high_ports = {21, 445, 1433, 3306, 3389, 5432, 5900}
    medium_ports = {25, 80, 8080, 8443, 9200}

    for port in open_ports:
        if port in critical_ports:
            risk_score += genome.genes["risk_weight_critical"]
        elif port in high_ports:
            risk_score += genome.genes["risk_weight_high"]
        elif port in medium_ports:
            risk_score += genome.genes["risk_weight_medium"]
        else:
            risk_score += 1

    return {
        "open_ports": len(open_ports),
        "ports": sorted(open_ports),
        "risk_score": round(risk_score, 2),
        "duration": round(duration, 3),
        "ports_scanned": len(ports),
        "coverage": round(len(open_ports) / max(1, len(ports)) * 100, 1),
    }


# ═══ 适应度评估 ═══

def evaluate_fitness(genome: AuditGenome, target: str) -> float:
    """用真实扫描结果评估适应度。"""
    result = execute_audit_strategy(genome, target)
    genome.results = result

    if result.get("error"):
        return 0.0

    # 适应度 = 发现能力 + 速度 + 覆盖率
    discovery = min(1.0, result["open_ports"] / 5)  # 发现 5 个端口满分
    speed = max(0, 1.0 - result["duration"] / 30)  # 30 秒内满分
    coverage = result["coverage"] / 100

    fitness = 0.5 * discovery + 0.3 * speed + 0.2 * coverage
    return round(fitness, 4)


# ═══ 进化引擎 ═══

class RealEvolutionEngine:
    """真正能进化的引擎。"""

    def __init__(self, population_size: int = 10):
        self.population_size = population_size
        self.population: list[AuditGenome] = []
        self.generation = 0
        self.history = []
        self.state_path = ECOSYSTEM_ROOT / "runtime" / ".wal" / "cognitive" / "real_evolution.json"

    def initialize(self):
        self.population = [AuditGenome() for _ in range(self.population_size)]
        self.generation = 0

    def evolve_one_generation(self, target: str) -> dict:
        """进化一代。"""
        self.generation += 1

        # 评估适应度
        for genome in self.population:
            genome.fitness = evaluate_fitness(genome, target)

        # 排序
        self.population.sort(key=lambda g: g.fitness, reverse=True)
        best = self.population[0]
        avg_fitness = sum(g.fitness for g in self.population) / len(self.population)

        # 选择 + 繁殖
        new_population = [AuditGenome(dict(best.genes))]  # 精英保留

        while len(new_population) < self.population_size:
            # 锦标赛选择
            p1 = self._tournament_select()
            p2 = self._tournament_select()

            if random.random() < 0.7:
                child = p1.crossover(p2)
            else:
                child = p1.mutate(rate=0.3)

            new_population.append(child)

        self.population = new_population

        # 记录
        record = {
            "gen": self.generation,
            "best_fitness": best.fitness,
            "avg_fitness": round(avg_fitness, 4),
            "best_ports": best.results.get("open_ports", 0),
            "best_duration": best.results.get("duration", 0),
            "best_genes": dict(best.genes),
            "target": target,
            "ts": datetime.now().isoformat(),
        }
        self.history.append(record)
        self._save_state()

        return record

    def _tournament_select(self, k: int = 3) -> AuditGenome:
        tournament = random.sample(self.population, min(k, len(self.population)))
        return max(tournament, key=lambda g: g.fitness)

    def _save_state(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "generation": self.generation,
            "best_fitness": self.history[-1]["best_fitness"] if self.history else 0,
            "history": self.history[-50:],
        }
        self.state_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_status(self) -> dict:
        return {
            "generation": self.generation,
            "population_size": len(self.population),
            "best_fitness": self.history[-1]["best_fitness"] if self.history else 0,
            "history_count": len(self.history),
        }


# ═══ 主程序 ═══

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Real Evolution Engine")
    parser.add_argument("--target", default="localhost", help="Scan target")
    parser.add_argument("--generations", type=int, default=10, help="Generations to evolve")
    parser.add_argument("--population", type=int, default=10, help="Population size")
    args = parser.parse_args()

    engine = RealEvolutionEngine(population_size=args.population)
    engine.initialize()

    print(f"=== Real Evolution: {args.generations} generations on {args.target} ===")
    print()

    for gen in range(args.generations):
        record = engine.evolve_one_generation(args.target)
        print(f"Gen {record['gen']:3d} | fitness={record['best_fitness']:.4f} avg={record['avg_fitness']:.4f} | "
              f"ports={record['best_ports']} duration={record['best_duration']:.2f}s | "
              f"strategy={record['best_genes']['port_range']}/{record['best_genes']['scan_mode']}")

    print()
    print(f"=== Final: {engine.generation} generations, best fitness={engine.history[-1]['best_fitness']:.4f} ===")
    best_genes = engine.history[-1]["best_genes"]
    print(f"Best strategy: ports={best_genes['port_range']}, timeout={best_genes['timeout']}, "
          f"threads={best_genes['threads']}, mode={best_genes['scan_mode']}")


if __name__ == "__main__":
    main()
