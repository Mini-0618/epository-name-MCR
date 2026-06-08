"""
Evolution — MCR 的进化系统。

生物学原理：
- 繁殖：两个个体的基因组合产生后代
- 变异：随机修改基因
- 自然选择：适应度高的个体存活
- Sakana AI：通过"繁殖"现有模型创建新模型

功能：
1. SkillGenome：技能的基因组表示
2. EvolutionEngine：繁殖+变异+选择循环
3. 适应度评估：基于成功率、速度、用户反馈
"""

import json
import copy
import random
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

ECOSYSTEM_ROOT = Path(__file__).parent.parent
RUNTIME_DIR = ECOSYSTEM_ROOT / "runtime"
EVOLUTION_STATE = RUNTIME_DIR / ".wal" / "cognitive" / "evolution_state.json"
EVOLUTION_LOG = RUNTIME_DIR / ".wal" / "cognitive" / "evolution_log.jsonl"
SKILLS_DIR = RUNTIME_DIR / "skills"


class SkillGenome:
    """
    技能基因组。

    每个技能由 5 条"染色体"组成：
    - prompt: 系统提示词、few-shot、CoT
    - tools: 可用工具、策略、回退
    - parameters: 温度、超时、重试
    - validation: 验证标准、格式、错误处理
    - memory: 记忆策略
    """

    CHROMOSOMES = {
        "prompt": {
            "system_prompt": "str",
            "few_shot_count": "int",    # 0-5
            "use_cot": "bool",          # 是否用 Chain-of-Thought
            "temperature": "float",     # 0.0-2.0
        },
        "tools": {
            "max_tools": "int",         # 1-20
            "strategy": "str",          # "sequential" / "parallel" / "adaptive"
            "retry_on_fail": "bool",
        },
        "parameters": {
            "timeout_seconds": "int",   # 10-300
            "max_retries": "int",       # 0-5
            "batch_size": "int",        # 1-10
        },
        "validation": {
            "strict_mode": "bool",
            "output_format": "str",     # "json" / "text" / "structured"
            "error_handling": "str",    # "retry" / "fallback" / "abort"
        },
        "memory": {
            "remember_inputs": "bool",
            "remember_outputs": "bool",
            "consolidation": "str",     # "immediate" / "delayed" / "never"
        },
    }

    def __init__(self, genes: dict = None):
        self.genes = genes or self._random_genome()
        self.fitness = 0.0
        self.generation = 0
        self.id = f"genome-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(1000, 9999)}"

    def _random_genome(self) -> dict:
        """生成随机基因组。"""
        return {
            "prompt": {
                "system_prompt": "",
                "few_shot_count": random.randint(0, 3),
                "use_cot": random.random() > 0.5,
                "temperature": round(random.uniform(0.1, 1.5), 2),
            },
            "tools": {
                "max_tools": random.randint(3, 15),
                "strategy": random.choice(["sequential", "parallel", "adaptive"]),
                "retry_on_fail": random.random() > 0.3,
            },
            "parameters": {
                "timeout_seconds": random.choice([30, 60, 120, 180]),
                "max_retries": random.randint(0, 3),
                "batch_size": random.randint(1, 5),
            },
            "validation": {
                "strict_mode": random.random() > 0.5,
                "output_format": random.choice(["json", "text", "structured"]),
                "error_handling": random.choice(["retry", "fallback", "abort"]),
            },
            "memory": {
                "remember_inputs": random.random() > 0.3,
                "remember_outputs": random.random() > 0.5,
                "consolidation": random.choice(["immediate", "delayed", "never"]),
            },
        }

    def crossover(self, other: "SkillGenome") -> "SkillGenome":
        """基因重组：两个亲本产生后代。"""
        child_genes = {}
        for chrom_name in self.CHROMOSOMES:
            child_chrom = {}
            for gene_name in self.CHROMOSOMES[chrom_name]:
                # 50/50 从任一亲本继承
                if random.random() < 0.5:
                    child_chrom[gene_name] = self.genes.get(chrom_name, {}).get(gene_name)
                else:
                    child_chrom[gene_name] = other.genes.get(chrom_name, {}).get(gene_name)
            child_genes[chrom_name] = child_chrom

        child = SkillGenome(child_genes)
        child.generation = max(self.generation, other.generation) + 1
        return child

    def mutate(self, rate: float = 0.1) -> "SkillGenome":
        """基因突变。"""
        mutated = copy.deepcopy(self.genes)
        mutations = []

        for chrom_name, chrom in mutated.items():
            for gene_name, gene_value in chrom.items():
                if random.random() < rate:
                    old_value = gene_value
                    if isinstance(gene_value, float):
                        chrom[gene_name] = round(gene_value * random.uniform(0.7, 1.3), 2)
                        chrom[gene_name] = max(0.0, min(2.0, chrom[gene_name]))
                    elif isinstance(gene_value, int):
                        delta = random.randint(-3, 3)
                        chrom[gene_name] = max(1, gene_value + delta)
                    elif isinstance(gene_value, bool):
                        chrom[gene_name] = not gene_value
                    elif isinstance(gene_value, str) and gene_name in ("strategy", "output_format", "error_handling", "consolidation"):
                        options = {
                            "strategy": ["sequential", "parallel", "adaptive"],
                            "output_format": ["json", "text", "structured"],
                            "error_handling": ["retry", "fallback", "abort"],
                            "consolidation": ["immediate", "delayed", "never"],
                        }
                        chrom[gene_name] = random.choice(options.get(gene_name, [gene_value]))
                    mutations.append(f"{chrom_name}.{gene_name}: {old_value} → {chrom[gene_name]}")

        child = SkillGenome(mutated)
        child.generation = self.generation
        return child

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "genes": self.genes,
            "fitness": self.fitness,
            "generation": self.generation,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SkillGenome":
        g = cls(d.get("genes", {}))
        g.id = d.get("id", g.id)
        g.fitness = d.get("fitness", 0.0)
        g.generation = d.get("generation", 0)
        return g


class EvolutionEngine:
    """
    进化引擎。

    管理技能种群的进化循环：
    1. 评估适应度
    2. 选择亲本
    3. 繁殖后代
    4. 变异
    5. 自然选择（保留最优）
    """

    def __init__(self, state_path=None, population_size: int = 10):
        self.state_path = Path(state_path) if state_path else EVOLUTION_STATE
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.population_size = population_size
        self.state = self._load_state()

    def _load_state(self) -> dict:
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "population": [],
            "generation": 0,
            "best_fitness": 0.0,
            "best_genome_id": None,
            "history": [],
            "stats": {
                "total_generations": 0,
                "total_mutations": 0,
                "total_crossovers": 0,
                "extinctions": 0,
            },
        }

    def _save_state(self):
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def _log(self, entry: dict):
        log_path = EVOLUTION_LOG
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def initialize_population(self):
        """初始化种群。"""
        population = []
        for _ in range(self.population_size):
            genome = SkillGenome()
            population.append(genome.to_dict())
        self.state["population"] = population
        self.state["generation"] = 0
        self._save_state()
        return population

    def evaluate_fitness(self, genome_dict: dict) -> float:
        """
        评估适应度。

        适应度 = 0.4 * 成功率 + 0.3 * 速度分 + 0.2 * 简洁性 + 0.1 * 记忆效率
        """
        genes = genome_dict.get("genes", {})

        # 成功率（基于参数合理性）
        timeout = genes.get("parameters", {}).get("timeout_seconds", 60)
        retries = genes.get("parameters", {}).get("max_retries", 1)
        success_score = min(1.0, (timeout / 120) * 0.5 + (retries / 3) * 0.5)

        # 速度分（超时越短越好，但不能太短）
        speed_score = 1.0 - abs(timeout - 60) / 300
        speed_score = max(0, min(1, speed_score))

        # 简洁性（few-shot 越少越简洁）
        few_shot = genes.get("prompt", {}).get("few_shot_count", 2)
        simplicity = 1.0 - few_shot / 5

        # 记忆效率
        consolidation = genes.get("memory", {}).get("consolidation", "delayed")
        memory_score = {"immediate": 0.9, "delayed": 0.7, "never": 0.3}.get(consolidation, 0.5)

        fitness = (
            0.4 * success_score +
            0.3 * speed_score +
            0.2 * simplicity +
            0.1 * memory_score
        )

        return round(fitness, 4)

    def select_parents(self, population: list) -> tuple:
        """锦标赛选择：随机选 3 个，取最优 2 个。"""
        tournament = random.sample(population, min(3, len(population)))
        tournament.sort(key=lambda g: g.get("fitness", 0), reverse=True)
        return tournament[0], tournament[1] if len(tournament) > 1 else tournament[0]

    def evolve_generation(self) -> dict:
        """执行一代进化。"""
        population = self.state.get("population", [])
        if len(population) < 2:
            self.initialize_population()
            population = self.state["population"]

        # 评估适应度
        for genome_dict in population:
            genome_dict["fitness"] = self.evaluate_fitness(genome_dict)

        # 排序
        population.sort(key=lambda g: g.get("fitness", 0), reverse=True)

        # 记录最优
        best = population[0]
        self.state["best_fitness"] = best["fitness"]
        self.state["best_genome_id"] = best["id"]

        # 繁殖
        new_population = [copy.deepcopy(best)]  # 精英保留

        while len(new_population) < self.population_size:
            p1_dict, p2_dict = self.select_parents(population)
            p1 = SkillGenome.from_dict(p1_dict)
            p2 = SkillGenome.from_dict(p2_dict)

            # 70% 交叉，30% 变异
            if random.random() < 0.7:
                child = p1.crossover(p2)
                self.state["stats"]["total_crossovers"] += 1
            else:
                child = p1.mutate(rate=0.15)
                self.state["stats"]["total_mutations"] += 1

            new_population.append(child.to_dict())

        self.state["population"] = new_population
        self.state["generation"] += 1
        self.state["stats"]["total_generations"] += 1

        # 记录历史
        self.state["history"].append({
            "generation": self.state["generation"],
            "best_fitness": best["fitness"],
            "avg_fitness": round(sum(g["fitness"] for g in population) / len(population), 4),
            "timestamp": datetime.now().isoformat(),
        })
        self.state["history"] = self.state["history"][-50:]

        self._save_state()

        result = {
            "generation": self.state["generation"],
            "best_fitness": best["fitness"],
            "best_id": best["id"],
            "population_size": len(new_population),
            "stats": self.state["stats"],
        }

        self._log(result)
        return result

    def get_status(self) -> dict:
        """获取进化系统状态。"""
        return {
            "generation": self.state.get("generation", 0),
            "population_size": len(self.state.get("population", [])),
            "best_fitness": self.state.get("best_fitness", 0),
            "best_genome_id": self.state.get("best_genome_id"),
            "stats": self.state.get("stats", {}),
            "recent_history": self.state.get("history", [])[-5:],
        }

    def get_best_genome(self) -> Optional[dict]:
        """获取当前最优基因组。"""
        population = self.state.get("population", [])
        if not population:
            return None
        return max(population, key=lambda g: g.get("fitness", 0))


# ═══ 便捷函数 ═══

def evolve(state_path=None, population_size=10) -> dict:
    """便捷函数：进化一代。"""
    engine = EvolutionEngine(state_path=state_path, population_size=population_size)
    return engine.evolve_generation()


def get_status(state_path=None) -> dict:
    """便捷函数：获取进化状态。"""
    engine = EvolutionEngine(state_path=state_path)
    return engine.get_status()


# ═══ CLI ═══

def main():
    parser = argparse.ArgumentParser(description="MCR Evolution Engine (进化系统)")
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="Initialize population")
    p_init.add_argument("--size", type=int, default=10)

    p_evolve = sub.add_parser("evolve", help="Evolve one generation")
    p_evolve.add_argument("--generations", type=int, default=1)

    sub.add_parser("status", help="Show status")
    sub.add_parser("best", help="Show best genome")

    args = parser.parse_args()
    engine = EvolutionEngine()

    if args.command == "init":
        engine.initialize_population()
        print(f"Population initialized: {engine.population_size} genomes")
    elif args.command == "evolve":
        for i in range(args.generations):
            result = engine.evolve_generation()
            print(f"Gen {result['generation']}: best={result['best_fitness']:.4f}")
    elif args.command == "status":
        print(json.dumps(engine.get_status(), indent=2, ensure_ascii=False))
    elif args.command == "best":
        best = engine.get_best_genome()
        if best:
            print(json.dumps(best, indent=2, ensure_ascii=False))
        else:
            print("No population. Run 'init' first.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
