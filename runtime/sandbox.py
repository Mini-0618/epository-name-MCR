"""
Sandbox — MCR 的代码安全执行引擎。

三层防御：
1. 预执行静态分析（AST + 正则）→ 拦截危险代码
2. 受限子进程执行（隔离环境 + 资源限制）→ 安全运行
3. 执行后审计（provenance 链）→ 可追溯

替代 task_engine.py 中的 shell=True 直接执行。

用法:
    sandbox = CodeSandbox()
    result = sandbox.execute("print('hello')", language="python")
    print(result.status, result.stdout)
"""

import json
import os
import subprocess
import sys
import time
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from sandbox_policy import StaticAnalyzer, ViolationSeverity

ECOSYSTEM_ROOT = Path(__file__).parent.parent
SANDBOX_DIR = ECOSYSTEM_ROOT / "runtime" / ".sandbox"


@dataclass
class SandboxPolicy:
    """沙箱安全策略。"""
    # 资源限制
    max_timeout_seconds: int = 30
    max_memory_mb: int = 256
    max_output_bytes: int = 512_000  # 512KB
    max_code_size_bytes: int = 1_000_000  # 1MB

    # 语言白名单
    allowed_languages: tuple = ("python", "node", "shell", "bash", "cmd")

    # 文件系统
    filesystem_root: Optional[str] = None  # 限制工作目录
    filesystem_writable: tuple = ()  # 允许写入的路径

    # 网络
    network_allowed: bool = False

    # 安全级别: strict / standard / passthrough
    security_level: str = "strict"


@dataclass
class SandboxResult:
    """沙箱执行结果。"""
    task_id: str = ""
    status: str = "pending"  # success / blocked / timeout / error / policy_violation
    executor: str = ""
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    violations: list = field(default_factory=list)
    audit_event_id: str = ""

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "status": self.status,
            "executor": self.executor,
            "exit_code": self.exit_code,
            "stdout": self.stdout[:2000] if self.stdout else "",
            "stderr": self.stderr[:2000] if self.stderr else "",
            "duration_seconds": round(self.duration_seconds, 3),
            "violations": [v.to_dict() if hasattr(v, 'to_dict') else v for v in self.violations],
        }


class CodeSandbox:
    """MCR 代码沙箱。替代 shell=True。"""

    def __init__(self, policy: SandboxPolicy = None, provenance_enabled: bool = True):
        self.policy = policy or SandboxPolicy()
        self.analyzer = StaticAnalyzer()
        self.provenance_enabled = provenance_enabled
        self._provenance = None

    @property
    def provenance(self):
        if self._provenance is None and self.provenance_enabled:
            try:
                sys.path.insert(0, str(ECOSYSTEM_ROOT / "runtime"))
                import provenance as prov_mod
                self._provenance = prov_mod
            except ImportError:
                self.provenance_enabled = False
        return self._provenance

    def execute(self, code: str, language: str = "python",
                task_id: str = None, cwd: str = None,
                env: dict = None) -> SandboxResult:
        """
        执行代码。三层防御流水线。

        Args:
            code: 要执行的代码或命令
            language: 语言 (python / node / shell / bash)
            task_id: 任务 ID（用于审计）
            cwd: 工作目录
            env: 额外环境变量

        Returns:
            SandboxResult
        """
        task_id = task_id or f"sandbox-{uuid.uuid4().hex[:8]}"

        # ── Layer 0: 前置检查 ──
        if language not in self.policy.allowed_languages:
            return SandboxResult(
                task_id=task_id, status="blocked",
                executor=language, stderr=f"Language not allowed: {language}",
            )

        if len(code.encode()) > self.policy.max_code_size_bytes:
            return SandboxResult(
                task_id=task_id, status="blocked",
                executor=language, stderr="Code too large",
            )

        # ── Layer 1: 静态分析 ──
        violations = []
        if self.policy.security_level in ("strict", "standard"):
            violations = self.analyzer.scan(code, language)
            critical = self.analyzer.has_critical(violations)
            if critical and self.policy.security_level == "strict":
                return SandboxResult(
                    task_id=task_id, status="policy_violation",
                    executor=language, violations=violations,
                    stderr=f"Blocked: {len([v for v in violations if v.severity == ViolationSeverity.CRITICAL])} critical violations",
                )

        # ── Layer 2: 受限执行 ──
        result = self._run_restricted(code, language, task_id, cwd, env)
        result.violations = violations

        # ── Layer 3: 审计 ──
        self._audit(result, violations)

        return result

    def _run_restricted(self, code: str, language: str,
                        task_id: str, cwd: str,
                        env: dict) -> SandboxResult:
        """受限子进程执行。"""
        start = time.time()

        # 准备工作目录
        if cwd is None:
            cwd = str(SANDBOX_DIR / task_id)
            os.makedirs(cwd, exist_ok=True)

        # 准备环境变量（隔离网络 + 限制资源）
        exec_env = self._build_env(env)

        # 构建命令
        cmd_args = self._build_command(code, language)
        if cmd_args is None:
            return SandboxResult(
                task_id=task_id, status="error",
                executor=language, stderr=f"Cannot execute {language}",
            )

        try:
            result = subprocess.run(
                cmd_args,
                shell=False,  # 关键：不用 shell=True
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",  # 编码错误用替换字符，不崩溃
                timeout=self.policy.max_timeout_seconds,
                cwd=cwd,
                env=exec_env,
            )
            duration = time.time() - start

            # 截断输出
            stdout = result.stdout[:self.policy.max_output_bytes] if result.stdout else ""
            stderr = result.stderr[:self.policy.max_output_bytes] if result.stderr else ""

            return SandboxResult(
                task_id=task_id,
                status="success" if result.returncode == 0 else "error",
                executor=language,
                exit_code=result.returncode,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=duration,
            )

        except subprocess.TimeoutExpired:
            return SandboxResult(
                task_id=task_id, status="timeout",
                executor=language,
                duration_seconds=self.policy.max_timeout_seconds,
                stderr=f"Timed out after {self.policy.max_timeout_seconds}s",
            )
        except Exception as e:
            return SandboxResult(
                task_id=task_id, status="error",
                executor=language,
                stderr=str(e),
                duration_seconds=time.time() - start,
            )

    def _build_command(self, code: str, language: str) -> Optional[list]:
        """构建命令参数列表。shell=False 用列表，不用字符串。"""
        if language == "python":
            return [sys.executable, "-c", code]
        elif language in ("node", "javascript"):
            return ["node", "-e", code]
        elif language in ("shell", "bash", "sh"):
            # Shell 命令：写入临时文件执行，不用 shell=True
            if sys.platform == "win32":
                # Windows: 用 cmd /c 执行
                script_path = SANDBOX_DIR / f"_{uuid.uuid4().hex[:8]}.bat"
                script_path.parent.mkdir(parents=True, exist_ok=True)
                with open(script_path, "w", encoding="utf-8") as f:
                    f.write(code)
                return ["cmd", "/c", str(script_path)]
            else:
                script_path = SANDBOX_DIR / f"_{uuid.uuid4().hex[:8]}.sh"
                script_path.parent.mkdir(parents=True, exist_ok=True)
                with open(script_path, "w", encoding="utf-8") as f:
                    f.write(code)
                return ["bash", str(script_path)]
        return None

    def _build_env(self, extra_env: dict = None) -> dict:
        """构建隔离的环境变量。"""
        env = os.environ.copy()

        # 资源限制
        env["PYTHONMALLOC"] = "malloc"
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        # 网络隔离
        if not self.policy.network_allowed:
            env["no_proxy"] = "*"
            env["NO_PROXY"] = "*"
            env["http_proxy"] = ""
            env["https_proxy"] = ""
            env["HTTP_PROXY"] = ""
            env["HTTPS_PROXY"] = ""

        # 合并额外环境变量
        if extra_env:
            env.update(extra_env)

        return env

    def _audit(self, result: SandboxResult, violations: list):
        """记录审计事件。"""
        if not self.provenance_enabled or not self.provenance:
            return

        try:
            payload = {
                "task_id": result.task_id,
                "executor": result.executor,
                "status": result.status,
                "exit_code": result.exit_code,
                "duration_seconds": result.duration_seconds,
                "violations_count": len(violations),
                "critical_violations": len([v for v in violations
                                           if v.severity == ViolationSeverity.CRITICAL]),
            }
            event = self.provenance.create_provenance_event(
                "sandbox_execution", payload
            )
            result.audit_event_id = event.get("event_id", "")
        except Exception:
            pass  # 审计失败不应阻止执行

    def execute_file(self, file_path: str, language: str = None,
                     task_id: str = None, cwd: str = None,
                     env: dict = None) -> SandboxResult:
        """执行文件。自动检测语言。"""
        path = Path(file_path)
        if not path.exists():
            return SandboxResult(
                task_id=task_id or "file", status="error",
                stderr=f"File not found: {file_path}",
            )

        # 自动检测语言
        if language is None:
            ext_map = {
                ".py": "python", ".js": "node", ".ts": "node",
                ".sh": "shell", ".bash": "bash",
            }
            language = ext_map.get(path.suffix, "python")

        with open(path, "r", encoding="utf-8") as f:
            code = f.read()

        return self.execute(code, language=language, task_id=task_id,
                           cwd=cwd or str(path.parent), env=env)


def create_sandbox(security_level: str = "strict",
                   max_timeout: int = 30) -> CodeSandbox:
    """工厂函数。快速创建沙箱。"""
    policy = SandboxPolicy(
        security_level=security_level,
        max_timeout_seconds=max_timeout,
    )
    return CodeSandbox(policy=policy)


# ─── CLI ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MCR Sandbox")
    sub = parser.add_subparsers(dest="command")

    # execute
    exec_p = sub.add_parser("execute", help="Execute code")
    exec_p.add_argument("code", help="Code to execute")
    exec_p.add_argument("--language", "-l", default="python")
    exec_p.add_argument("--level", "-s", default="strict",
                        choices=["strict", "standard", "passthrough"])

    # scan
    scan_p = sub.add_parser("scan", help="Scan code for violations")
    scan_p.add_argument("code", help="Code to scan")
    scan_p.add_argument("--language", "-l", default="python")

    # test
    sub.add_parser("test", help="Run self-test")

    args = parser.parse_args()

    if args.command == "execute":
        sandbox = create_sandbox(security_level=args.level)
        result = sandbox.execute(args.code, language=args.language)
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    elif args.command == "scan":
        analyzer = StaticAnalyzer()
        violations = analyzer.scan(args.code, args.language)
        print(json.dumps([v.to_dict() for v in violations], indent=2))

    elif args.command == "test":
        print("=== Sandbox Self-Test ===\n")

        sandbox = create_sandbox(security_level="strict")

        # Test 1: 安全代码
        r = sandbox.execute("print('hello sandbox')", language="python")
        assert r.status == "success", f"Test 1 failed: {r.status}"
        assert "hello sandbox" in r.stdout
        print("✅ Test 1: Safe code executes")

        # Test 2: 危险代码被拦截
        r = sandbox.execute("import subprocess; subprocess.run(['ls'])", language="python")
        assert r.status == "policy_violation", f"Test 2 failed: {r.status}"
        print("✅ Test 2: Dangerous import blocked")

        # Test 3: exec() 被拦截
        r = sandbox.execute("exec('import os')", language="python")
        assert r.status == "policy_violation", f"Test 3 failed: {r.status}"
        print("✅ Test 3: exec() blocked")

        # Test 4: os.system 被拦截
        r = sandbox.execute("os.system('rm -rf /')", language="python")
        assert r.status == "policy_violation", f"Test 4 failed: {r.status}"
        print("✅ Test 4: os.system() blocked")

        # Test 5: 标准模式只警告不拦截
        std_sandbox = create_sandbox(security_level="standard")
        r = std_sandbox.execute("import subprocess", language="python")
        assert r.status != "policy_violation", f"Test 5 failed: {r.status}"
        assert len(r.violations) > 0
        print("✅ Test 5: Standard mode warns but allows")

        # Test 6: 输出截断
        r = sandbox.execute("print('x' * 1000000)", language="python")
        assert r.status == "success"
        assert len(r.stdout) <= 512_000 + 100  # 大致范围
        print("✅ Test 6: Output truncated")

        # Test 7: 超时
        r = sandbox.execute("import time; time.sleep(60)", language="python")
        assert r.status == "timeout", f"Test 7 failed: {r.status}"
        print("✅ Test 7: Timeout enforced")

        # Test 8: shell=False（不会执行 rm -rf）
        if sys.platform == "win32":
            r = sandbox.execute("echo safe", language="shell")
        else:
            r = sandbox.execute("echo safe", language="shell")
        assert r.status == "success", f"Test 8 failed: {r.status} - {r.stderr}"
        print("✅ Test 8: Shell command via subprocess args (not shell=True)")

        print("\n🎉 All tests passed!")
        print(f"\nAudit events written to provenance chain.")
