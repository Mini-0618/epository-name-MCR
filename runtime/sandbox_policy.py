"""
Sandbox Policy — 预执行静态分析。

在代码运行前扫描危险模式：
- AST 分析（Python）：检测危险 import、exec/eval、dunder 访问
- 正则扫描（所有语言）：检测危险函数调用、网络请求、文件操作

agenticSeek 没有这层，直接 exec()。
"""

import ast
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ViolationSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class PolicyViolation:
    rule: str
    severity: ViolationSeverity
    message: str
    line: Optional[int] = None

    def to_dict(self):
        return {
            "rule": self.rule,
            "severity": self.severity.value,
            "message": self.message,
            "line": self.line,
        }


class StaticAnalyzer:
    """预执行代码分析。AST + 正则双引擎。"""

    # Python 危险模块
    BLOCKED_MODULES = {
        "subprocess", "os", "shutil", "ctypes", "importlib",
        "signal", "multiprocessing", "socket", "http", "urllib",
        "ftplib", "smtplib", "telnetlib", "xmlrpc",
    }

    # Python 危险 dunder 属性
    BLOCKED_DUNDERS = {
        "__import__", "__subclasses__", "__builtins__", "__globals__",
        "__code__", "__bases__", "__class__", "__mro__", "__loader__",
    }

    # 正则模式（所有语言通用）
    DANGEROUS_PATTERNS = [
        # 代码执行
        (r'\bexec\s*\(', "exec() call", ViolationSeverity.CRITICAL),
        (r'\beval\s*\(', "eval() call", ViolationSeverity.CRITICAL),
        (r'__import__', "dynamic __import__", ViolationSeverity.CRITICAL),
        (r'compile\s*\(.+["\']exec', "compile+exec", ViolationSeverity.CRITICAL),

        # 系统命令
        (r'os\.system\s*\(', "os.system()", ViolationSeverity.CRITICAL),
        (r'os\.popen\s*\(', "os.popen()", ViolationSeverity.CRITICAL),
        (r'os\.exec', "os.exec*()", ViolationSeverity.CRITICAL),
        (r'subprocess\.(run|call|Popen|check_output|check_call)\s*\(',
         "subprocess call", ViolationSeverity.CRITICAL),

        # 文件破坏
        (r'shutil\.rmtree\s*\(', "recursive delete", ViolationSeverity.CRITICAL),
        (r'os\.remove\s*\(', "file delete", ViolationSeverity.WARNING),
        (r'os\.unlink\s*\(', "file unlink", ViolationSeverity.WARNING),
        (r'os\.rename\s*\(', "file rename", ViolationSeverity.WARNING),

        # 网络外联
        (r'socket\.', "socket usage", ViolationSeverity.CRITICAL),
        (r'urllib\.request', "HTTP request (urllib)", ViolationSeverity.WARNING),
        (r'requests\.(get|post|put|delete|patch)\s*\(',
         "HTTP request (requests)", ViolationSeverity.WARNING),
        (r'httpx\.(get|post|put|delete|patch)\s*\(',
         "HTTP request (httpx)", ViolationSeverity.WARNING),

        # Dunder 访问
        (r'getattr\s*\(.+,\s*["\']__', "dunder getattr", ViolationSeverity.CRITICAL),
        (r'hasattr\s*\(.+,\s*["\']__', "dunder hasattr", ViolationSeverity.WARNING),

        # Shell 注入
        (r'`[^`]+`', "backtick command", ViolationSeverity.CRITICAL),
        (r'\$\(.*\)', "shell substitution", ViolationSeverity.WARNING),
    ]

    # Shell 危险命令
    SHELL_DANGEROUS = [
        (r'\brm\s+-rf?\b', "rm -rf", ViolationSeverity.CRITICAL),
        (r'\bmkfs\b', "format filesystem", ViolationSeverity.CRITICAL),
        (r'\bdd\s+.*of=', "dd write", ViolationSeverity.CRITICAL),
        (r'\bchmod\s+777\b', "chmod 777", ViolationSeverity.WARNING),
        (r'\bwget\s+.*\|\s*(ba)?sh', "wget pipe to shell", ViolationSeverity.CRITICAL),
        (r'\bcurl\s+.*\|\s*(ba)?sh', "curl pipe to shell", ViolationSeverity.CRITICAL),
        (r'>\s*/dev/', "write to /dev/", ViolationSeverity.CRITICAL),
        (r'\bshutdown\b', "shutdown command", ViolationSeverity.CRITICAL),
        (r'\breboot\b', "reboot command", ViolationSeverity.CRITICAL),
    ]

    def scan(self, code: str, language: str = "python") -> list[PolicyViolation]:
        """扫描代码，返回违规列表。"""
        violations = []

        # Layer 1: 正则扫描（所有语言）
        violations.extend(self._scan_patterns(code))

        # Layer 2: AST 扫描（仅 Python）
        if language == "python":
            violations.extend(self._scan_python_ast(code))

        # Layer 3: Shell 命令扫描
        if language in ("shell", "bash", "sh"):
            violations.extend(self._scan_shell(code))

        return violations

    def _scan_patterns(self, code: str) -> list[PolicyViolation]:
        """正则模式扫描。"""
        violations = []
        for pattern, desc, severity in self.DANGEROUS_PATTERNS:
            for match in re.finditer(pattern, code):
                line = code[:match.start()].count('\n') + 1
                violations.append(PolicyViolation(
                    rule=f"pattern:{desc}",
                    severity=severity,
                    message=f"{desc} at line {line}",
                    line=line,
                ))
        return violations

    def _scan_python_ast(self, code: str) -> list[PolicyViolation]:
        """AST 深度扫描（Python）。"""
        violations = []
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            violations.append(PolicyViolation(
                rule="ast:syntax_error",
                severity=ViolationSeverity.WARNING,
                message=f"Syntax error: {e.msg}",
                line=e.lineno,
            ))
            return violations

        for node in ast.walk(tree):
            # 检查 import
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_module = alias.name.split('.')[0]
                    if root_module in self.BLOCKED_MODULES:
                        violations.append(PolicyViolation(
                            rule=f"ast:import:{alias.name}",
                            severity=ViolationSeverity.CRITICAL,
                            message=f"Blocked import: {alias.name}",
                            line=getattr(node, 'lineno', None),
                        ))

            # 检查 from X import Y
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_module = node.module.split('.')[0]
                    if root_module in self.BLOCKED_MODULES:
                        violations.append(PolicyViolation(
                            rule=f"ast:import_from:{node.module}",
                            severity=ViolationSeverity.CRITICAL,
                            message=f"Blocked import from: {node.module}",
                            line=getattr(node, 'lineno', None),
                        ))

            # 检查 dunder 访问
            elif isinstance(node, ast.Attribute):
                if node.attr in self.BLOCKED_DUNDERS:
                    violations.append(PolicyViolation(
                        rule=f"ast:dunder:{node.attr}",
                        severity=ViolationSeverity.CRITICAL,
                        message=f"Blocked dunder access: {node.attr}",
                        line=getattr(node, 'lineno', None),
                    ))

            # 检查 exec/eval/breakpoint 调用
            elif isinstance(node, ast.Call):
                func_name = self._get_call_name(node)
                if func_name in ("exec", "eval", "breakpoint", "exit", "quit"):
                    violations.append(PolicyViolation(
                        rule=f"ast:call:{func_name}",
                        severity=ViolationSeverity.CRITICAL,
                        message=f"Blocked function call: {func_name}()",
                        line=getattr(node, 'lineno', None),
                    ))

        return violations

    def _scan_shell(self, code: str) -> list[PolicyViolation]:
        """Shell 命令扫描。"""
        violations = []
        for pattern, desc, severity in self.SHELL_DANGEROUS:
            for match in re.finditer(pattern, code):
                line = code[:match.start()].count('\n') + 1
                violations.append(PolicyViolation(
                    rule=f"shell:{desc}",
                    severity=severity,
                    message=f"Dangerous shell command: {desc} at line {line}",
                    line=line,
                ))
        return violations

    @staticmethod
    def _get_call_name(node: ast.Call) -> Optional[str]:
        """提取函数调用名称。"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None

    def has_critical(self, violations: list[PolicyViolation]) -> bool:
        """是否有严重违规。"""
        return any(v.severity == ViolationSeverity.CRITICAL for v in violations)
