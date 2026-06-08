"""
Evolution System Max v1.0 — MCR 进化引擎增强版。

版本库 + 风控 + 评测 + 打分 + 锦标赛 + 报告 + CLI

功能：
- CandidateRepo: 候选版本管理（创建、查询、谱系追踪）
- RiskAuditor: 代码风险扫描（4级：CRITICAL/HIGH/MEDIUM/LOW）
- SafeCommandRunner: 安全命令执行（拦截危险命令）
- ScoreCalculator: 综合评分（运行结果+测试+风险+性能）
- EvolutionEngine: 完整进化循环（seed→eval→tournament→promote）
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Optional


APP_NAME = "Evolution System Max"
APP_VERSION = "1.0.0"


def now_ts() -> float:
    return time.time()


def now_text() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def ensure_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def short_id(prefix: str = "id") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


# ============================================================
# Data Classes
# ============================================================

@dataclasses.dataclass
class Candidate:
    id: str
    name: str
    generation: int
    path: str
    content_hash: str
    parent_id: Optional[str]
    created_at: float
    note: str = ""
    tags: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class RiskFinding:
    level: str
    pattern: str
    message: str
    line: int
    text: str


@dataclasses.dataclass
class EvaluationResult:
    id: str
    candidate_id: str
    command: list[str]
    cwd: Optional[str]
    returncode: int
    stdout: str
    stderr: str
    runtime_ms: float
    score: float
    passed: bool
    pytest_passed: int
    pytest_failed: int
    risk_count: int
    risks: list[dict[str, Any]]
    created_at: float


@dataclasses.dataclass
class EvolutionDecision:
    id: str
    winner_id: str
    loser_ids: list[str]
    reason: str
    scores: dict[str, float]
    created_at: float


@dataclasses.dataclass
class PromotionRecord:
    id: str
    candidate_id: str
    source_path: str
    target_path: str
    created_at: float
    note: str = ""


# ============================================================
# JSONL Store
# ============================================================

class JsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, obj: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []

        items: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return items


# ============================================================
# Workspace
# ============================================================

class EvolutionWorkspace:
    def __init__(self, root: str | Path = "evolution_lab_max") -> None:
        self.root = Path(root)
        self.candidates_dir = self.root / "candidates"
        self.logs_dir = self.root / "logs"
        self.reports_dir = self.root / "reports"
        self.promoted_dir = self.root / "promoted"
        self.artifacts_dir = self.root / "artifacts"

        for d in (
            self.root,
            self.candidates_dir,
            self.logs_dir,
            self.reports_dir,
            self.promoted_dir,
            self.artifacts_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

        self.candidate_store = JsonlStore(self.logs_dir / "candidates.jsonl")
        self.evaluation_store = JsonlStore(self.logs_dir / "evaluations.jsonl")
        self.decision_store = JsonlStore(self.logs_dir / "decisions.jsonl")
        self.promotion_store = JsonlStore(self.logs_dir / "promotions.jsonl")

    def init_files(self) -> None:
        readme = f"""# {APP_NAME}

Version: {APP_VERSION}

目录说明：
- candidates/ — 候选版本
- logs/ — 评测日志
- reports/ — 进化报告
- promoted/ — 晋升版本
- artifacts/ — 产物

基本命令：
```bash
python evolution_max.py seed --file coding_tools.py --name coding_tools
python evolution_max.py eval --candidate <id> --cmd "python -m py_compile {{file}}"
python evolution_max.py tournament --candidates <id1> <id2>
python evolution_max.py report
```
"""
        write_text(self.root / "README.md", readme)


# ============================================================
# Candidate Repo
# ============================================================

class CandidateRepo:
    def __init__(self, ws: EvolutionWorkspace) -> None:
        self.ws = ws

    def create_from_text(
        self,
        name: str,
        content: str,
        generation: int = 0,
        parent_id: Optional[str] = None,
        note: str = "",
        tags: Optional[list[str]] = None,
        suffix: str = ".py",
    ) -> Candidate:
        content_hash = sha256_text(content)
        cid = f"c_{content_hash[:10]}_{uuid.uuid4().hex[:6]}"
        safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", name).strip("_") or "candidate"

        folder = self.ws.candidates_dir / f"gen_{generation:04d}" / cid
        folder.mkdir(parents=True, exist_ok=True)

        file_path = folder / f"{safe_name}{suffix}"
        file_path.write_text(content, encoding="utf-8")

        candidate = Candidate(
            id=cid,
            name=safe_name,
            generation=generation,
            path=str(file_path),
            content_hash=content_hash,
            parent_id=parent_id,
            created_at=now_ts(),
            note=note,
            tags=tags or [],
        )

        self.ws.candidate_store.append(dataclasses.asdict(candidate))
        return candidate

    def create_from_file(
        self,
        file_path: str | Path,
        name: Optional[str] = None,
        generation: int = 0,
        parent_id: Optional[str] = None,
        note: str = "",
        tags: Optional[list[str]] = None,
    ) -> Candidate:
        p = Path(file_path)
        content = p.read_text(encoding="utf-8")
        suffix = p.suffix or ".py"

        return self.create_from_text(
            name=name or p.stem,
            content=content,
            generation=generation,
            parent_id=parent_id,
            note=note,
            tags=tags,
            suffix=suffix,
        )

    def get(self, candidate_id: str) -> Candidate:
        for item in self.ws.candidate_store.read_all():
            if item.get("id") == candidate_id:
                return Candidate(**item)
        raise KeyError(f"candidate not found: {candidate_id}")

    def list_all(self) -> list[Candidate]:
        return [Candidate(**x) for x in self.ws.candidate_store.read_all()]

    def content(self, candidate_id: str) -> str:
        c = self.get(candidate_id)
        return Path(c.path).read_text(encoding="utf-8")

    def lineage(self, candidate_id: str) -> list[Candidate]:
        result: list[Candidate] = []
        current = self.get(candidate_id)

        while True:
            result.append(current)
            if current.parent_id is None:
                break
            current = self.get(current.parent_id)

        result.reverse()
        return result


# ============================================================
# Risk Auditor
# ============================================================

class RiskAuditor:
    """轻量风险扫描器。"""

    RULES: list[tuple[str, str, str]] = [
        ("CRITICAL", r"rm\s+-rf\s+/", "dangerous recursive delete"),
        ("CRITICAL", r"format\s+c:", "dangerous disk format"),
        ("CRITICAL", r"del\s+/f\s+/s", "dangerous Windows delete"),
        ("HIGH", r"subprocess\.[a-zA-Z_]+\(.*shell\s*=\s*True", "subprocess shell=True"),
        ("HIGH", r"os\.system\(", "os.system command execution"),
        ("HIGH", r"eval\(", "eval usage"),
        ("HIGH", r"exec\(", "exec usage"),
        ("HIGH", r"pickle\.loads", "unsafe pickle loads"),
        ("MEDIUM", r"yaml\.load\(", "unsafe yaml load"),
        ("MEDIUM", r"requests\.", "network request usage"),
        ("MEDIUM", r"urllib\.request", "network request usage"),
        ("MEDIUM", r"socket\.", "socket usage"),
        ("MEDIUM", r"open\(.+['\"]w", "file write usage"),
        ("LOW", r"time\.sleep\(", "sleep usage may slow tests"),
    ]

    PENALTY = {
        "CRITICAL": 40.0,
        "HIGH": 20.0,
        "MEDIUM": 8.0,
        "LOW": 2.0,
    }

    def scan(self, text: str) -> list[RiskFinding]:
        findings: list[RiskFinding] = []
        lines = text.splitlines()

        for line_no, line in enumerate(lines, start=1):
            for level, pattern, message in self.RULES:
                if re.search(pattern, line, flags=re.IGNORECASE):
                    findings.append(
                        RiskFinding(
                            level=level,
                            pattern=pattern,
                            message=message,
                            line=line_no,
                            text=line.strip()[:200],
                        )
                    )

        return findings

    def penalty(self, findings: list[RiskFinding]) -> float:
        total = 0.0
        for finding in findings:
            total += self.PENALTY.get(finding.level, 5.0)
        return min(80.0, total)


# ============================================================
# Safe Command Runner
# ============================================================

class SafeCommandRunner:
    """运行评测命令，默认不允许明显危险命令。"""

    DANGEROUS = [
        r"rm\s+-rf",
        r"format\s+c:",
        r"del\s+/f\s+/s",
        r"shutdown",
        r"reboot",
        r"mkfs",
    ]

    def __init__(self, timeout: float = 60.0) -> None:
        self.timeout = timeout

    def validate_command(self, command: list[str]) -> None:
        joined = " ".join(command)
        for pattern in self.DANGEROUS:
            if re.search(pattern, joined, flags=re.IGNORECASE):
                raise ValueError(f"dangerous command blocked: {pattern}")

    def run(
        self,
        command: list[str],
        cwd: Optional[str | Path] = None,
        timeout: Optional[float] = None,
    ) -> tuple[int, str, str, float]:
        self.validate_command(command)
        start = time.perf_counter()

        try:
            proc = subprocess.run(
                command,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout or self.timeout,
            )
            runtime_ms = (time.perf_counter() - start) * 1000
            return proc.returncode, proc.stdout, proc.stderr, runtime_ms

        except subprocess.TimeoutExpired as exc:
            runtime_ms = (time.perf_counter() - start) * 1000
            return 124, ensure_text(exc.stdout), ensure_text(exc.stderr) or "timeout", runtime_ms


# ============================================================
# Score Calculator
# ============================================================

class ScoreCalculator:
    def parse_pytest(self, text: str) -> tuple[int, int]:
        passed = 0
        failed = 0
        skipped = 0

        m = re.search(r"(\d+)\s+passed", text)
        if m:
            passed = int(m.group(1))

        m = re.search(r"(\d+)\s+failed", text)
        if m:
            failed = int(m.group(1))

        m = re.search(r"(\d+)\s+skipped", text)
        if m:
            skipped = int(m.group(1))

        return passed + skipped, failed

    def calculate(
        self,
        returncode: int,
        stdout: str,
        stderr: str,
        runtime_ms: float,
        risks: list[RiskFinding],
    ) -> tuple[float, int, int]:
        text = stdout + "\n" + stderr
        pytest_passed, pytest_failed = self.parse_pytest(text)

        score = 0.0

        if returncode == 0:
            score += 45.0

        if pytest_passed + pytest_failed > 0:
            total = pytest_passed + pytest_failed
            score += 35.0 * (pytest_passed / total)
            if pytest_failed == 0:
                score += 10.0
        else:
            if "SyntaxError" not in text and returncode == 0:
                score += 20.0

        if runtime_ms < 1000:
            score += 10.0
        elif runtime_ms < 5000:
            score += 6.0
        elif runtime_ms < 15000:
            score += 2.0

        auditor = RiskAuditor()
        score -= auditor.penalty(risks)
        score = max(0.0, min(100.0, score))
        return score, pytest_passed, pytest_failed


# ============================================================
# Evaluator
# ============================================================

class Evaluator:
    def __init__(self, ws: EvolutionWorkspace, timeout: float = 60.0) -> None:
        self.ws = ws
        self.repo = CandidateRepo(ws)
        self.auditor = RiskAuditor()
        self.runner = SafeCommandRunner(timeout=timeout)
        self.scorer = ScoreCalculator()

    def evaluate(
        self,
        candidate_id: str,
        command: list[str],
        cwd: Optional[str | Path] = None,
        timeout: Optional[float] = None,
    ) -> EvaluationResult:
        candidate = self.repo.get(candidate_id)
        content = read_text(candidate.path)
        risks = self.auditor.scan(content)

        file_path = str(Path(candidate.path).resolve())
        expanded = [part.replace("{file}", file_path) for part in command]

        try:
            returncode, stdout, stderr, runtime_ms = self.runner.run(
                expanded, cwd=cwd, timeout=timeout,
            )
        except ValueError as exc:
            returncode, stdout, stderr, runtime_ms = 126, "", str(exc), 0.0

        score, pytest_passed, pytest_failed = self.scorer.calculate(
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            runtime_ms=runtime_ms,
            risks=risks,
        )

        result = EvaluationResult(
            id=short_id("eval"),
            candidate_id=candidate_id,
            command=expanded,
            cwd=str(cwd) if cwd else None,
            returncode=returncode,
            stdout=stdout[-20000:],
            stderr=stderr[-20000:],
            runtime_ms=runtime_ms,
            score=score,
            passed=returncode == 0,
            pytest_passed=pytest_passed,
            pytest_failed=pytest_failed,
            risk_count=len(risks),
            risks=[dataclasses.asdict(x) for x in risks],
            created_at=now_ts(),
        )

        self.ws.evaluation_store.append(dataclasses.asdict(result))
        return result

    def latest_eval(self, candidate_id: str) -> Optional[EvaluationResult]:
        items = [
            x for x in self.ws.evaluation_store.read_all()
            if x.get("candidate_id") == candidate_id
        ]
        if not items:
            return None
        latest = max(items, key=lambda x: x.get("created_at", 0))
        return EvaluationResult(**latest)


# ============================================================
# Evolution Engine
# ============================================================

class EvolutionEngine:
    def __init__(self, root: str | Path = "evolution_lab_max", timeout: float = 60.0) -> None:
        self.ws = EvolutionWorkspace(root)
        self.repo = CandidateRepo(self.ws)
        self.evaluator = Evaluator(self.ws, timeout=timeout)

    def init(self) -> None:
        self.ws.init_files()

    def seed_file(
        self,
        file_path: str | Path,
        name: Optional[str] = None,
        note: str = "seed",
    ) -> Candidate:
        return self.repo.create_from_file(
            file_path=file_path, name=name, generation=0, note=note,
        )

    def mutate_file(
        self,
        parent_id: str,
        file_path: str | Path,
        note: str = "mutation",
    ) -> Candidate:
        parent = self.repo.get(parent_id)
        return self.repo.create_from_file(
            file_path=file_path,
            name=parent.name,
            generation=parent.generation + 1,
            parent_id=parent_id,
            note=note,
        )

    def evaluate(
        self,
        candidate_id: str,
        command: list[str],
        cwd: Optional[str | Path] = None,
    ) -> EvaluationResult:
        return self.evaluator.evaluate(candidate_id, command, cwd=cwd)

    def tournament(self, candidate_ids: list[str]) -> EvolutionDecision:
        if len(candidate_ids) < 1:
            raise ValueError("need at least one candidate")

        scores: dict[str, float] = {}
        missing: list[str] = []

        for cid in candidate_ids:
            result = self.evaluator.latest_eval(cid)
            if result is None:
                missing.append(cid)
            else:
                scores[cid] = result.score

        if missing:
            raise ValueError(f"missing evaluation results: {missing}")

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        winner_id = ranked[0][0]
        loser_ids = [cid for cid, _ in ranked[1:]]

        reason = (
            f"winner={winner_id}, score={scores[winner_id]:.2f}, "
            f"selected by latest eval score"
        )

        decision = EvolutionDecision(
            id=short_id("decision"),
            winner_id=winner_id,
            loser_ids=loser_ids,
            reason=reason,
            scores=scores,
            created_at=now_ts(),
        )

        self.ws.decision_store.append(dataclasses.asdict(decision))
        return decision

    def diff(self, old_id: str, new_id: str) -> str:
        old = self.repo.content(old_id).splitlines()
        new = self.repo.content(new_id).splitlines()
        return "\n".join(
            difflib.unified_diff(old, new, fromfile=old_id, tofile=new_id, lineterm="")
        )

    def promote(
        self,
        candidate_id: str,
        target_name: Optional[str] = None,
        note: str = "",
    ) -> PromotionRecord:
        c = self.repo.get(candidate_id)
        src = Path(c.path)
        target = self.ws.promoted_dir / (target_name or src.name)
        shutil.copy2(src, target)

        record = PromotionRecord(
            id=short_id("promo"),
            candidate_id=candidate_id,
            source_path=str(src),
            target_path=str(target),
            created_at=now_ts(),
            note=note,
        )

        self.ws.promotion_store.append(dataclasses.asdict(record))
        return record

    def generate_next_prompt(
        self,
        candidate_id: str,
        goal: str = "继续提升稳定性、测试覆盖和工程质量",
    ) -> str:
        c = self.repo.get(candidate_id)
        content = self.repo.content(candidate_id)
        latest = self.evaluator.latest_eval(candidate_id)

        latest_text = "无评测记录"
        if latest:
            latest_text = (
                f"score={latest.score:.2f}, passed={latest.passed}, "
                f"pytest_passed={latest.pytest_passed}, "
                f"pytest_failed={latest.pytest_failed}, "
                f"risk_count={latest.risk_count}"
            )

        return f"""你现在基于上一代代码继续进化。

上一代信息：
- candidate_id: {c.id}
- generation: {c.generation}
- path: {c.path}
- note: {c.note}
- latest_eval: {latest_text}

进化目标：
{goal}

硬性规则：
1. 不要删除用户文件。
2. 不要访问网络。
3. 不要重装 Python 或第三方库。
4. 保持公共 API 尽量兼容。
5. 优先修复真实问题，不要为了复杂而复杂。
6. 增加测试，但不要编造测试结果。

上一代代码：
```python
{content}
```"""

    def report(self) -> str:
        candidates = self.repo.list_all()
        evals = [EvaluationResult(**x) for x in self.ws.evaluation_store.read_all()]
        decisions = [EvolutionDecision(**x) for x in self.ws.decision_store.read_all()]
        promotions = [PromotionRecord(**x) for x in self.ws.promotion_store.read_all()]

        lines: list[str] = []
        lines.append(f"# {APP_NAME} Report")
        lines.append("")
        lines.append(f"生成时间：{now_text()}")
        lines.append(f"版本：{APP_VERSION}")
        lines.append("")

        lines.append("## Summary")
        lines.append("")
        lines.append(f"- Candidates: {len(candidates)}")
        lines.append(f"- Evaluations: {len(evals)}")
        lines.append(f"- Decisions: {len(decisions)}")
        lines.append(f"- Promotions: {len(promotions)}")
        lines.append("")

        lines.append("## Candidates")
        lines.append("")
        for c in candidates:
            lines.append(
                f"- `{c.id}` | gen={c.generation} | parent={c.parent_id} | "
                f"name={c.name} | note={c.note}"
            )

        lines.append("")
        lines.append("## Evaluations")
        lines.append("")
        for e in evals:
            lines.append(
                f"- `{e.candidate_id}` | score={e.score:.2f} | passed={e.passed} | "
                f"pytest={e.pytest_passed}/{e.pytest_failed} | risks={e.risk_count} | "
                f"runtime={e.runtime_ms:.1f}ms"
            )

        lines.append("")
        lines.append("## Decisions")
        lines.append("")
        for d in decisions:
            lines.append(
                f"- `{d.id}` | winner=`{d.winner_id}` | losers={d.loser_ids}"
            )

        lines.append("")
        lines.append("## Promotions")
        lines.append("")
        for p in promotions:
            lines.append(
                f"- `{p.id}` | candidate=`{p.candidate_id}` | target={p.target_path}"
            )

        text = "\n".join(lines)
        write_text(self.ws.reports_dir / "report.md", text)
        return text


# ============================================================
# CLI Helpers
# ============================================================

def split_cmd(cmd: str) -> list[str]:
    import shlex
    return shlex.split(cmd)


def print_json(obj: Any) -> None:
    if dataclasses.is_dataclass(obj):
        print(json_dumps(dataclasses.asdict(obj)))
    else:
        print(json_dumps(obj))


# ============================================================
# CLI
# ============================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} v{APP_VERSION}")
    parser.add_argument("--root", default="evolution_lab_max", help="workspace root")
    parser.add_argument("--timeout", type=float, default=60.0, help="command timeout")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init")

    p_seed = sub.add_parser("seed")
    p_seed.add_argument("--file", required=True)
    p_seed.add_argument("--name", default=None)
    p_seed.add_argument("--note", default="seed")

    p_mutate = sub.add_parser("mutate")
    p_mutate.add_argument("--parent", required=True)
    p_mutate.add_argument("--file", required=True)
    p_mutate.add_argument("--note", default="mutation")

    p_eval = sub.add_parser("eval")
    p_eval.add_argument("--candidate", required=True)
    p_eval.add_argument("--cmd", required=True)
    p_eval.add_argument("--cwd", default=None)

    p_tour = sub.add_parser("tournament")
    p_tour.add_argument("--candidates", nargs="+", required=True)

    p_list = sub.add_parser("list")
    p_list.add_argument(
        "--kind",
        choices=["candidates", "evals", "decisions", "promotions"],
        default="candidates",
    )

    p_show = sub.add_parser("show")
    p_show.add_argument("--candidate", required=True)

    p_diff = sub.add_parser("diff")
    p_diff.add_argument("--old", required=True)
    p_diff.add_argument("--new", required=True)

    p_lineage = sub.add_parser("lineage")
    p_lineage.add_argument("--candidate", required=True)

    p_prompt = sub.add_parser("prompt")
    p_prompt.add_argument("--candidate", required=True)
    p_prompt.add_argument("--goal", default="继续提升稳定性、测试覆盖和工程质量")

    p_promote = sub.add_parser("promote")
    p_promote.add_argument("--candidate", required=True)
    p_promote.add_argument("--target-name", default=None)
    p_promote.add_argument("--note", default="")

    sub.add_parser("report")

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    engine = EvolutionEngine(root=args.root, timeout=args.timeout)

    if args.command == "init":
        engine.init()
        print(f"initialized: {args.root}")
        return 0

    if args.command == "seed":
        c = engine.seed_file(args.file, name=args.name, note=args.note)
        print_json(c)
        return 0

    if args.command == "mutate":
        c = engine.mutate_file(args.parent, args.file, note=args.note)
        print_json(c)
        return 0

    if args.command == "eval":
        result = engine.evaluate(args.candidate, split_cmd(args.cmd), cwd=args.cwd)
        print_json(result)
        return 0 if result.passed else 1

    if args.command == "tournament":
        d = engine.tournament(args.candidates)
        print_json(d)
        return 0

    if args.command == "list":
        if args.kind == "candidates":
            print_json([dataclasses.asdict(x) for x in engine.repo.list_all()])
        elif args.kind == "evals":
            print_json(engine.ws.evaluation_store.read_all())
        elif args.kind == "decisions":
            print_json(engine.ws.decision_store.read_all())
        elif args.kind == "promotions":
            print_json(engine.ws.promotion_store.read_all())
        return 0

    if args.command == "show":
        print(engine.repo.content(args.candidate))
        return 0

    if args.command == "diff":
        print(engine.diff(args.old, args.new))
        return 0

    if args.command == "lineage":
        print_json([dataclasses.asdict(x) for x in engine.repo.lineage(args.candidate)])
        return 0

    if args.command == "prompt":
        print(engine.generate_next_prompt(args.candidate, goal=args.goal))
        return 0

    if args.command == "promote":
        record = engine.promote(args.candidate, target_name=args.target_name, note=args.note)
        print_json(record)
        return 0

    if args.command == "report":
        print(engine.report())
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
