#!/usr/bin/env python3
"""
MCR Security Audit — 第一个可用产品。

给一个目标，出一份安全报告。

用法:
    python mcr_audit.py <target>
    python mcr_audit.py 192.168.1.1
    python mcr_audit.py example.com

不需要装任何额外依赖（只用 socket + 标准库）。
"""

from __future__ import annotations

import socket
import sys
import time
import json
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


# ═══ 配置 ═══

COMMON_PORTS = [
    21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 993, 995,
    1433, 1521, 3306, 3389, 5432, 5900, 6379, 8080, 8443, 8888, 9200, 27017,
]

PORT_NAMES = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
    80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS", 445: "SMB",
    993: "IMAPS", 995: "POP3S", 1433: "MSSQL", 1521: "Oracle",
    3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL", 5900: "VNC",
    6379: "Redis", 8080: "HTTP-Alt", 8443: "HTTPS-Alt", 8888: "HTTP-Alt2",
    9200: "Elasticsearch", 27017: "MongoDB",
}

RISK_PORTS = {
    21: ("HIGH", "FTP 明文传输，建议用 SFTP"),
    23: ("CRITICAL", "Telnet 明文传输，强烈建议禁用"),
    25: ("MEDIUM", "SMTP 可能被用于垃圾邮件"),
    445: ("HIGH", "SMB 常被勒索软件利用"),
    1433: ("HIGH", "MSSQL 数据库暴露，检查认证"),
    1521: ("HIGH", "Oracle 数据库暴露，检查认证"),
    3306: ("HIGH", "MySQL 数据库暴露，检查认证"),
    3389: ("CRITICAL", "RDP 暴露，常被暴力破解"),
    5432: ("HIGH", "PostgreSQL 数据库暴露，检查认证"),
    5900: ("HIGH", "VNC 远程桌面暴露"),
    6379: ("CRITICAL", "Redis 默认无认证，可直接访问"),
    9200: ("HIGH", "Elasticsearch 暴露，检查认证"),
    27017: ("CRITICAL", "MongoDB 默认无认证，可直接访问"),
}

SENSITIVE_PATHS = [
    "admin", "login", "wp-admin", "phpmyadmin", "backup", ".git",
    ".env", "robots.txt", "sitemap.xml", ".htaccess", "web.config",
    "api-docs", "swagger", "graphql", "debug", "server-status",
    "console", "manager/html", ".svn", ".DS_Store",
]


# ═══ 端口扫描 ═══

def scan_port(host: str, port: int, timeout: float = 1.0) -> dict | None:
    """扫描单个端口。"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()

        if result == 0:
            service = PORT_NAMES.get(port, "unknown")
            risk_level, risk_msg = RISK_PORTS.get(port, ("LOW", ""))
            return {
                "port": port,
                "state": "open",
                "service": service,
                "risk_level": risk_level,
                "risk_message": risk_msg,
            }
    except Exception:
        pass
    return None


def scan_ports(host: str, ports: list[int] = None, threads: int = 50) -> list[dict]:
    """并发扫描多个端口。"""
    if ports is None:
        ports = COMMON_PORTS

    results = []
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {executor.submit(scan_port, host, port): port for port in ports}
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    return sorted(results, key=lambda x: x["port"])


# ═══ Web 路径扫描 ═══

def check_web_path(host: str, port: int, path: str, timeout: float = 3.0) -> dict | None:
    """检测单个 Web 路径。"""
    import urllib.request
    import urllib.error
    import ssl

    scheme = "https" if port in (443, 8443) else "http"
    url = f"{scheme}://{host}:{port}/{path}"

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "MCR-Audit/1.0")

        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        status = resp.getcode()

        if status in (200, 201, 204, 301, 302, 403):
            risk = "LOW"
            if path in (".git", ".env", ".svn", "backup", ".htaccess"):
                risk = "CRITICAL"
            elif path in ("admin", "wp-admin", "phpmyadmin", "console", "debug"):
                risk = "HIGH"
            elif path in ("robots.txt", "sitemap.xml", "api-docs", "swagger"):
                risk = "MEDIUM"

            return {
                "path": path,
                "url": url,
                "status": status,
                "risk_level": risk,
            }
    except urllib.error.HTTPError as e:
        if e.code in (403, 401):
            return {"path": path, "url": url, "status": e.code, "risk_level": "MEDIUM"}
    except Exception:
        pass
    return None


def scan_web_paths(host: str, port: int = 80, paths: list[str] = None) -> list[dict]:
    """扫描 Web 敏感路径。"""
    if paths is None:
        paths = SENSITIVE_PATHS

    results = []
    for path in paths:
        result = check_web_path(host, port, path)
        if result:
            results.append(result)
        time.sleep(0.1)  # 不要太快

    return results


# ═══ 报告生成 ═══

def generate_report(target: str, open_ports: list[dict], web_paths: list[dict]) -> str:
    """生成人类可读的安全报告。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 统计
    total_ports = len(open_ports)
    critical_ports = [p for p in open_ports if p["risk_level"] == "CRITICAL"]
    high_ports = [p for p in open_ports if p["risk_level"] == "HIGH"]
    medium_ports = [p for p in open_ports if p["risk_level"] == "MEDIUM"]
    low_ports = [p for p in open_ports if p["risk_level"] == "LOW"]

    critical_paths = [p for p in web_paths if p["risk_level"] == "CRITICAL"]
    high_paths = [p for p in web_paths if p["risk_level"] == "HIGH"]

    # 风险评分
    risk_score = 0
    risk_score += len(critical_ports) * 30
    risk_score += len(high_ports) * 15
    risk_score += len(medium_ports) * 5
    risk_score += len(critical_paths) * 25
    risk_score += len(high_paths) * 10
    risk_score = min(100, risk_score)

    if risk_score >= 70:
        risk_label = "🔴 高风险"
    elif risk_score >= 40:
        risk_label = "🟡 中风险"
    elif risk_score >= 10:
        risk_label = "🟢 低风险"
    else:
        risk_label = "✅ 安全"

    report = f"""# MCR 安全审计报告

> 目标：{target}
> 时间：{now}
> 工具：MCR Security Audit v1.0

---

## 风险评估

**{risk_label}** — 风险评分：{risk_score}/100

| 级别 | 端口 | 路径 |
|------|------|------|
| 🔴 CRITICAL | {len(critical_ports)} | {len(critical_paths)} |
| 🟠 HIGH | {len(high_ports)} | {len(high_paths)} |
| 🟡 MEDIUM | {len(medium_ports)} | {len([p for p in web_paths if p['risk_level'] == 'MEDIUM'])} |
| 🟢 LOW | {len(low_ports)} | {len([p for p in web_paths if p['risk_level'] == 'LOW'])} |

---

## 开放端口 ({total_ports} 个)

"""

    if open_ports:
        report += "| 端口 | 服务 | 风险 | 说明 |\n"
        report += "|------|------|------|------|\n"
        for p in open_ports:
            icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(p["risk_level"], "⚪")
            report += f"| {p['port']} | {p['service']} | {icon} {p['risk_level']} | {p.get('risk_message', '')} |\n"
    else:
        report += "未发现开放端口。\n"

    report += f"""
---

## Web 路径发现 ({len(web_paths)} 个)

"""

    if web_paths:
        report += "| 路径 | 状态 | 风险 |\n"
        report += "|------|------|------|\n"
        for p in web_paths:
            icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(p["risk_level"], "⚪")
            report += f"| /{p['path']} | {p['status']} | {icon} {p['risk_level']} |\n"
    else:
        report += "未发现敏感路径。\n"

    report += f"""
---

## 建议

"""

    if critical_ports:
        report += "### 🔴 紧急处理\n\n"
        for p in critical_ports:
            report += f"- **端口 {p['port']} ({p['service']})**: {p['risk_message']}\n"
        report += "\n"

    if high_ports:
        report += "### 🟠 尽快处理\n\n"
        for p in high_ports:
            report += f"- **端口 {p['port']} ({p['service']})**: {p['risk_message']}\n"
        report += "\n"

    if critical_paths:
        report += "### 🔴 敏感路径暴露\n\n"
        for p in critical_paths:
            report += f"- **{p['url']}**: 状态 {p['status']}，可能泄露敏感信息\n"
        report += "\n"

    if not critical_ports and not high_ports and not critical_paths:
        report += "未发现严重问题。建议定期复查。\n\n"

    report += f"""---

## 关于本报告

本报告由 MCR Security Audit 生成。
MCR 是一个本地运行的 AI 安全审计系统，基于 CyberForge 安全知识库。

本报告仅用于授权的安全测试。未经授权扫描他人系统是违法的。

---
*Generated by MCR v5.0 — My Cognitive Runtime*
"""

    return report, risk_score


# ═══ 主程序 ═══

def audit(target: str, web_port: int = None) -> tuple[str, int]:
    """执行完整安全审计。"""
    print(f"[MCR] 开始审计: {target}")
    print(f"[MCR] 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # DNS 解析
    print("[*] DNS 解析...")
    try:
        ip = socket.gethostbyname(target)
        print(f"[+] IP: {ip}")
    except socket.gaierror:
        print(f"[-] 无法解析: {target}")
        return "", 0

    # 端口扫描
    print(f"[*] 端口扫描 ({len(COMMON_PORTS)} 个常见端口)...")
    open_ports = scan_ports(ip)
    print(f"[+] 发现 {len(open_ports)} 个开放端口")

    for p in open_ports:
        icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(p["risk_level"], "⚪")
        print(f"    {icon} {p['port']}/{p['service']} — {p['risk_level']}")

    # Web 路径扫描
    web_paths = []
    web_port_candidates = []
    if web_port:
        web_port_candidates = [web_port]
    else:
        for p in open_ports:
            if p["port"] in (80, 443, 8080, 8443, 8888):
                web_port_candidates.append(p["port"])

    if web_port_candidates:
        for wp in web_port_candidates:
            print(f"[*] Web 路径扫描 (端口 {wp})...")
            paths = scan_web_paths(ip, wp)
            web_paths.extend(paths)
            print(f"[+] 发现 {len(paths)} 个可访问路径")
    else:
        print("[*] 未发现 Web 服务，跳过路径扫描")

    # 生成报告
    print()
    print("[*] 生成报告...")
    report, risk_score = generate_report(target, open_ports, web_paths)

    # 保存报告
    report_dir = Path("audit_reports")
    report_dir.mkdir(exist_ok=True)
    report_file = report_dir / f"audit_{target.replace('.', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_file.write_text(report, encoding="utf-8")

    # 保存原始数据
    data_file = report_dir / f"audit_{target.replace('.', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    data_file.write_text(json.dumps({
        "target": target,
        "ip": ip,
        "timestamp": datetime.now().isoformat(),
        "open_ports": open_ports,
        "web_paths": web_paths,
        "risk_score": risk_score,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[+] 报告已保存: {report_file}")
    print()
    print(f"{'='*50}")
    print(f"  风险评分: {risk_score}/100")
    print(f"  开放端口: {len(open_ports)}")
    print(f"  Web路径: {len(web_paths)}")
    print(f"{'='*50}")

    return report, risk_score


def main():
    if len(sys.argv) < 2:
        print("MCR Security Audit v1.0")
        print()
        print("用法: python mcr_audit.py <target>")
        print()
        print("示例:")
        print("  python mcr_audit.py 192.168.1.1")
        print("  python mcr_audit.py example.com")
        print("  python mcr_audit.py localhost --web-port 8080")
        sys.exit(1)

    target = sys.argv[1]
    web_port = None

    if "--web-port" in sys.argv:
        idx = sys.argv.index("--web-port")
        if idx + 1 < len(sys.argv):
            web_port = int(sys.argv[idx + 1])

    audit(target, web_port)


if __name__ == "__main__":
    main()
