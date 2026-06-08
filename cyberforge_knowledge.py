"""
CyberForge Knowledge Loader — 从 49 万安全知识文件中提取有用信息。

给定一个服务名或 CVE 编号，返回相关的知识。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

CYBERFORGE_ROOT = Path("D:/AIProjects/CyberForge")


class CyberForgeKnowledge:
    """CyberForge 知识库查询器。"""

    def __init__(self, root: Path = CYBERFORGE_ROOT):
        self.root = root
        self._cache: dict[str, str] = {}

    def search_cve(self, cve_id: str) -> Optional[str]:
        """搜索 CVE 知识。"""
        # 搜索 cve-lab 目录
        cve_lab = self.root / "cve-lab"
        if not cve_lab.exists():
            return None

        # 精确匹配
        for f in cve_lab.rglob("*.md"):
            if cve_id.upper() in f.name.upper():
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                    # 只返回前 2000 字符
                    return content[:2000]
                except Exception:
                    pass

        # 模糊搜索：在所有 CVE 文件中搜索
        for f in cve_lab.rglob("*.md"):
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                if cve_id.upper() in content.upper():
                    # 提取包含 CVE 的段落
                    lines = content.split("\n")
                    relevant = []
                    capture = False
                    for line in lines:
                        if cve_id.upper() in line.upper():
                            capture = True
                        if capture:
                            relevant.append(line)
                            if len(relevant) > 30:
                                break
                            if line.startswith("##") and len(relevant) > 5:
                                break
                    if relevant:
                        return "\n".join(relevant)
            except Exception:
                continue

        return None

    def search_service(self, service: str) -> Optional[str]:
        """搜索服务相关知识。"""
        service_lower = service.lower()

        # 搜索 attack-knowledge
        attack_dir = self.root / "attack-knowledge"
        if attack_dir.exists():
            for f in attack_dir.rglob("*.md"):
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                    if service_lower in content.lower():
                        # 提取相关段落
                        lines = content.split("\n")
                        relevant = []
                        for i, line in enumerate(lines):
                            if service_lower in line.lower():
                                start = max(0, i - 2)
                                end = min(len(lines), i + 15)
                                relevant.extend(lines[start:end])
                                relevant.append("---")
                        if relevant:
                            return "\n".join(relevant[:100])
                except Exception:
                    continue

        # 搜索 knowledge
        knowledge_dir = self.root / "knowledge"
        if knowledge_dir.exists():
            for f in knowledge_dir.glob("*.md"):
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                    if service_lower in content.lower():
                        lines = content.split("\n")
                        relevant = []
                        for i, line in enumerate(lines):
                            if service_lower in line.lower():
                                start = max(0, i - 2)
                                end = min(len(lines), i + 15)
                                relevant.extend(lines[start:end])
                                relevant.append("---")
                        if relevant:
                            return "\n".join(relevant[:100])
                except Exception:
                    continue

        return None

    def search_attack(self, attack_type: str) -> Optional[str]:
        """搜索攻击类型知识。"""
        attack_dir = self.root / "attack-knowledge"
        if not attack_dir.exists():
            return None

        for f in attack_dir.rglob("*.md"):
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                if attack_type.lower() in content.lower():
                    lines = content.split("\n")
                    relevant = []
                    for i, line in enumerate(lines):
                        if attack_type.lower() in line.lower():
                            start = max(0, i - 2)
                            end = min(len(lines), i + 20)
                            relevant.extend(lines[start:end])
                            relevant.append("---")
                    if relevant:
                        return "\n".join(relevant[:150])
            except Exception:
                continue

        return None

    def get_defense_advice(self, threat_type: str) -> Optional[str]:
        """获取防御建议。"""
        defense_dir = self.root / "defense-knowledge"
        if not defense_dir.exists():
            return None

        for f in defense_dir.rglob("*.md"):
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                if threat_type.lower() in content.lower():
                    lines = content.split("\n")
                    relevant = []
                    for i, line in enumerate(lines):
                        if threat_type.lower() in line.lower():
                            start = max(0, i - 2)
                            end = min(len(lines), i + 20)
                            relevant.extend(lines[start:end])
                            relevant.append("---")
                    if relevant:
                        return "\n".join(relevant[:150])
            except Exception:
                continue

        return None


# 便捷函数
def search_cve(cve_id: str) -> Optional[str]:
    kf = CyberForgeKnowledge()
    return kf.search_cve(cve_id)


def search_service(service: str) -> Optional[str]:
    kf = CyberForgeKnowledge()
    return kf.search_service(service)


if __name__ == "__main__":
    kf = CyberForgeKnowledge()

    print("=== 测试 CVE 搜索 ===")
    result = kf.search_cve("CVE-2024-1709")
    if result:
        print(result[:500])
    else:
        print("未找到")

    print("\n=== 测试服务搜索 ===")
    result = kf.search_service("Redis")
    if result:
        print(result[:500])
    else:
        print("未找到")
