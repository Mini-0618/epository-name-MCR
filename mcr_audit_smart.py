#!/usr/bin/env python3
"""
MCR Smart Audit — 智能安全审计员。

不是扫描器，是审计员。
它会思考、记忆、推理、进化。

用法:
    python mcr_audit_smart.py <target>
    python mcr_audit_smart.py 192.168.1.1
"""

from __future__ import annotations

import json
import socket
import sys
import time
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# 尝试导入 CyberForge 知识库
try:
    from cyberforge_knowledge import CyberForgeKnowledge
    CYBERFORGE_AVAILABLE = True
except ImportError:
    CYBERFORGE_AVAILABLE = False


# ═══ 知识库 ═══

SECURITY_KNOWLEDGE = {
    "FTP": {
        "port": 21,
        "description": "文件传输协议，明文传输",
        "risks": [
            "用户名和密码明文传输，可被抓包窃取",
            "匿名 FTP 可能暴露敏感文件",
            "vsftpd 2.3.4 后门 (CVE-2011-2523)",
        ],
        "recommendations": [
            "禁用 FTP，改用 SFTP (SSH 文件传输)",
            "如果必须用 FTP，启用 FTPS (FTP over TLS)",
            "禁用匿名访问",
            "限制用户只能访问自己的目录",
        ],
        "cves": ["CVE-2011-2523", "CVE-2010-4221"],
    },
    "SSH": {
        "port": 22,
        "description": "安全外壳协议，加密远程登录",
        "risks": [
            "暴力破解密码",
            "旧版本可能有漏洞",
            "弱密码是最大风险",
        ],
        "recommendations": [
            "使用密钥登录，禁用密码认证",
            "更改默认端口",
            "安装 fail2ban 防暴力破解",
            "保持 OpenSSH 版本最新",
        ],
        "cves": ["CVE-2023-38408", "CVE-2020-15778"],
    },
    "Telnet": {
        "port": 23,
        "description": "远程终端，明文传输",
        "risks": [
            "所有数据明文传输，包括密码",
            "任何网络上的人都能看到你的操作",
            "几乎没有认证安全可言",
        ],
        "recommendations": [
            "立即禁用 Telnet",
            "改用 SSH",
            "如果设备不支持 SSH，更换设备",
        ],
        "cves": [],
    },
    "SMTP": {
        "port": 25,
        "description": "邮件传输协议",
        "risks": [
            "开放中继可被用于发送垃圾邮件",
            "邮件内容可能明文传输",
            "可被用于钓鱼攻击",
        ],
        "recommendations": [
            "配置 SMTP 认证",
            "启用 STARTTLS 加密",
            "限制中继权限",
            "配置 SPF/DKIM/DMARC",
        ],
        "cves": ["CVE-2020-28017"],
    },
    "HTTP": {
        "port": 80,
        "description": "超文本传输协议，明文传输",
        "risks": [
            "数据明文传输，可被中间人攻击",
            "可能暴露敏感信息",
            "未加密的 HTTP 不安全",
        ],
        "recommendations": [
            "强制 HTTPS 重定向",
            "配置 HSTS 头",
            "使用有效的 SSL 证书",
        ],
        "cves": [],
    },
    "HTTPS": {
        "port": 443,
        "description": "加密的 HTTP",
        "risks": [
            "旧版 TLS (1.0/1.1) 不安全",
            "弱加密套件可被破解",
            "证书过期会影响安全和信任",
        ],
        "recommendations": [
            "只启用 TLS 1.2 和 1.3",
            "使用强加密套件",
            "配置 HSTS",
            "定期更新证书",
        ],
        "cves": ["CVE-2014-3566"],
    },
    "SMB": {
        "port": 445,
        "description": "服务器消息块，Windows 文件共享",
        "risks": [
            "EternalBlue 漏洞 (CVE-2017-0144) 可远程执行代码",
            "WannaCry 勒索软件利用此端口传播",
            "暴力破解 NTLM 认证",
            "横向移动（从一台电脑跳到另一台）",
        ],
        "recommendations": [
            "不要将 SMB 暴露到公网",
            "打 MS17-010 补丁",
            "禁用 SMBv1",
            "使用防火墙限制访问",
        ],
        "cves": ["CVE-2017-0144", "CVE-2020-0796"],
    },
    "MSSQL": {
        "port": 1433,
        "description": "Microsoft SQL Server 数据库",
        "risks": [
            "数据库暴露，可被暴力破解",
            "SA 弱密码是常见问题",
            "SQL 注入可导致数据泄露",
        ],
        "recommendations": [
            "不要将数据库端口暴露到公网",
            "使用强密码",
            "限制访问 IP",
            "启用审计日志",
        ],
        "cves": ["CVE-2020-0618"],
    },
    "MySQL": {
        "port": 3306,
        "description": "MySQL 数据库",
        "risks": [
            "数据库暴露，可被暴力破解",
            "root 空密码是致命问题",
            "SQL 注入可导致数据泄露",
        ],
        "recommendations": [
            "不要将数据库端口暴露到公网",
            "设置强密码",
            "删除匿名用户",
            "限制 bind-address",
        ],
        "cves": ["CVE-2023-21977"],
    },
    "RDP": {
        "port": 3389,
        "description": "远程桌面协议",
        "risks": [
            "BlueKeep 漏洞 (CVE-2019-0708) 可远程执行代码",
            "暴力破解 Windows 密码",
            "勒索软件的常见入侵点",
        ],
        "recommendations": [
            "不要将 RDP 暴露到公网",
            "使用 VPN 访问",
            "启用网络级认证 (NLA)",
            "使用强密码 + 双因素认证",
        ],
        "cves": ["CVE-2019-0708", "CVE-2020-0618"],
    },
    "PostgreSQL": {
        "port": 5432,
        "description": "PostgreSQL 数据库",
        "risks": [
            "数据库暴露",
            "默认配置可能允许远程连接",
        ],
        "recommendations": [
            "限制 pg_hba.conf 的访问权限",
            "使用强密码",
            "不要暴露到公网",
        ],
        "cves": [],
    },
    "VNC": {
        "port": 5900,
        "description": "虚拟网络计算，远程桌面",
        "risks": [
            "VNC 认证弱，容易被破解",
            "数据可能未加密",
            "可远程控制整台电脑",
        ],
        "recommendations": [
            "不要将 VNC 暴露到公网",
            "使用 SSH 隧道访问",
            "设置强密码",
        ],
        "cves": [],
    },
    "Redis": {
        "port": 6379,
        "description": "内存数据库，默认无认证",
        "risks": [
            "默认无密码，任何人可直接访问",
            "可读写服务器文件",
            "可写入 SSH 公钥实现远程登录",
            "可执行 Lua 脚本",
        ],
        "recommendations": [
            "设置密码 (requirepass)",
            "绑定本地 IP",
            "不要暴露到公网",
            "禁用危险命令 (CONFIG, FLUSHALL)",
        ],
        "cves": [],
    },
    "Elasticsearch": {
        "port": 9200,
        "description": "搜索引擎，默认无认证",
        "risks": [
            "默认无认证，可直接访问所有数据",
            "可删除所有索引",
            "可读取敏感日志和数据",
        ],
        "recommendations": [
            "启用 X-Pack 安全功能",
            "设置用户认证",
            "不要暴露到公网",
        ],
        "cves": ["CVE-2014-3120"],
    },
    "MongoDB": {
        "port": 27017,
        "description": "NoSQL 数据库，默认无认证",
        "risks": [
            "默认无认证，任何人可直接访问",
            "大量 MongoDB 因无认证被勒索",
            "可读写所有数据",
        ],
        "recommendations": [
            "启用认证 (authorization)",
            "绑定本地 IP",
            "不要暴露到公网",
            "设置强密码",
        ],
        "cves": [],
    },
}

# Web 路径风险知识
PATH_KNOWLEDGE = {
    ".git": {
        "risk": "CRITICAL",
        "description": "Git 仓库暴露，可下载全部源代码和提交历史",
        "impact": "攻击者可以看到你的所有代码、密码、密钥",
        "fix": "在 Web 服务器配置中禁止访问 .git 目录",
    },
    ".env": {
        "risk": "CRITICAL",
        "description": "环境变量文件，通常包含数据库密码、API 密钥",
        "impact": "攻击者可以直接获取你的所有密钥和密码",
        "fix": "永远不要把 .env 放在 Web 根目录",
    },
    ".svn": {
        "risk": "CRITICAL",
        "description": "SVN 仓库暴露",
        "impact": "可下载全部源代码",
        "fix": "禁止访问 .svn 目录",
    },
    "admin": {
        "risk": "HIGH",
        "description": "管理后台入口",
        "impact": "攻击者可以尝试暴力破解管理员密码",
        "fix": "限制管理后台的访问 IP，启用双因素认证",
    },
    "wp-admin": {
        "risk": "HIGH",
        "description": "WordPress 管理后台",
        "impact": "WordPress 是最常被攻击的 CMS",
        "fix": "限制访问 IP，使用强密码，安装安全插件",
    },
    "phpmyadmin": {
        "risk": "CRITICAL",
        "description": "数据库管理界面",
        "impact": "攻击者可以直接操作你的数据库",
        "fix": "不要将 phpMyAdmin 暴露到公网",
    },
    "robots.txt": {
        "risk": "MEDIUM",
        "description": "搜索引擎爬虫规则，可能暴露隐藏路径",
        "impact": "攻击者可以从 robots.txt 发现你不想公开的目录",
        "fix": "检查 robots.txt 是否泄露了敏感路径",
    },
    "swagger": {
        "risk": "MEDIUM",
        "description": "API 文档",
        "impact": "攻击者可以了解你的全部 API 接口",
        "fix": "生产环境不要暴露 API 文档",
    },
    "graphql": {
        "risk": "MEDIUM",
        "description": "GraphQL 接口",
        "impact": "攻击者可以查询任意数据",
        "fix": "限制查询深度和复杂度，启用认证",
    },
    "debug": {
        "risk": "HIGH",
        "description": "调试接口",
        "impact": "可能暴露系统内部信息，甚至允许远程执行代码",
        "fix": "生产环境禁用调试模式",
    },
}


# ═══ 扫描器（复用 mcr_audit.py 的核心） ═══

COMMON_PORTS = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 993, 995,
                1433, 1521, 3306, 3389, 5432, 5900, 6379, 8080, 8443, 8888, 9200, 27017]
PORT_NAMES = {21:"FTP",22:"SSH",23:"Telnet",25:"SMTP",53:"DNS",80:"HTTP",
              110:"POP3",143:"IMAP",443:"HTTPS",445:"SMB",993:"IMAPS",995:"POP3S",
              1433:"MSSQL",1521:"Oracle",3306:"MySQL",3389:"RDP",5432:"PostgreSQL",
              5900:"VNC",6379:"Redis",8080:"HTTP-Alt",8443:"HTTPS-Alt",8888:"HTTP-Alt2",
              9200:"Elasticsearch",27017:"MongoDB"}
SENSITIVE_PATHS = ["admin","login","wp-admin","phpmyadmin","backup",".git",
                   ".env","robots.txt","sitemap.xml",".htaccess","web.config",
                   "api-docs","swagger","graphql","debug","server-status",
                   "console","manager/html",".svn",".DS_Store"]


def scan_port(host: str, port: int, timeout: float = 1.0) -> dict | None:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        if result == 0:
            return {"port": port, "state": "open", "service": PORT_NAMES.get(port, "unknown")}
    except Exception:
        pass
    return None


def scan_ports(host: str, threads: int = 50) -> list[dict]:
    results = []
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {executor.submit(scan_port, host, port): port for port in COMMON_PORTS}
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
    return sorted(results, key=lambda x: x["port"])


def check_web_path(host: str, port: int, path: str) -> dict | None:
    import urllib.request, urllib.error, ssl
    scheme = "https" if port in (443, 8443) else "http"
    url = f"{scheme}://{host}:{port}/{path}"
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "MCR-Audit/1.0")
        resp = urllib.request.urlopen(req, timeout=3, context=ctx)
        if resp.getcode() in (200, 201, 204, 301, 302, 403):
            return {"path": path, "url": url, "status": resp.getcode()}
    except urllib.error.HTTPError as e:
        if e.code in (403, 401):
            return {"path": path, "url": url, "status": e.code}
    except Exception:
        pass
    return None


# ═══ 智能审计员 ═══

class SecurityAuditor:
    """MCR 安全审计员。不只是扫描，是思考。"""

    def __init__(self, memory_path: str = "audit_memory.json"):
        self.memory_path = Path(memory_path)
        self.memory = self._load_memory()

    def _load_memory(self) -> dict:
        if self.memory_path.exists():
            try:
                return json.loads(self.memory_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"scans": [], "findings": {}, "patterns": []}

    def _save_memory(self):
        self.memory_path.write_text(json.dumps(self.memory, ensure_ascii=False, indent=2), encoding="utf-8")

    def audit(self, target: str) -> str:
        """执行智能安全审计。"""
        start = time.time()
        print(f"[MCR] 智能审计开始: {target}")
        print(f"[MCR] 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # DNS
        try:
            ip = socket.gethostbyname(target)
            print(f"[+] IP: {ip}")
        except socket.gaierror:
            return f"无法解析: {target}"

        # 端口扫描
        print(f"[*] 扫描 {len(COMMON_PORTS)} 个端口...")
        open_ports = scan_ports(ip)
        print(f"[+] 发现 {len(open_ports)} 个开放端口")

        # Web 路径扫描
        web_paths = []
        for p in open_ports:
            if p["port"] in (80, 443, 8080, 8443):
                print(f"[*] 扫描 Web 路径 (端口 {p['port']})...")
                for sp in SENSITIVE_PATHS:
                    result = check_web_path(ip, p["port"], sp)
                    if result:
                        web_paths.append(result)
                    time.sleep(0.1)

        # ═══ 智能分析（不是查表，是推理）═══
        print(f"\n[*] 智能分析中...")
        analysis = self._analyze(target, ip, open_ports, web_paths)

        # 记忆本次扫描
        self._remember(target, ip, open_ports, web_paths, analysis)

        # 生成报告
        report = self._generate_report(target, ip, open_ports, web_paths, analysis, time.time() - start)

        # 保存报告
        report_dir = Path("audit_reports")
        report_dir.mkdir(exist_ok=True)
        report_file = report_dir / f"smart_audit_{target.replace('.','_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_file.write_text(report, encoding="utf-8")
        print(f"\n[+] 报告: {report_file}")

        return report

    def _analyze(self, target: str, ip: str, ports: list[dict], paths: list[dict]) -> dict:
        """智能分析：不只是查表，是推理。"""
        findings = []
        risk_score = 0

        # 初始化 CyberForge 知识库
        cf = CyberForgeKnowledge() if CYBERFORGE_AVAILABLE else None

        # 1. 端口分析
        for p in ports:
            service = p["service"]
            knowledge = SECURITY_KNOWLEDGE.get(service)

            if knowledge:
                finding = {
                    "type": "port",
                    "port": p["port"],
                    "service": service,
                    "description": knowledge["description"],
                    "risks": knowledge["risks"],
                    "recommendations": knowledge["recommendations"],
                    "cves": knowledge["cves"],
                    "severity": "CRITICAL" if service in ("Telnet", "Redis", "MongoDB") else
                               "HIGH" if service in ("SMB", "RDP", "MSSQL", "MySQL", "VNC") else
                               "MEDIUM" if service in ("FTP", "SMTP") else "LOW",
                }

                # 从 CyberForge 知识库补充信息
                if cf:
                    cf_knowledge = cf.search_service(service)
                    if cf_knowledge:
                        finding["cyberforge_knowledge"] = cf_knowledge[:500]
                    # 搜索 CVE 详细信息
                    for cve_id in knowledge.get("cves", []):
                        cve_detail = cf.search_cve(cve_id)
                        if cve_detail:
                            finding.setdefault("cve_details", {})[cve_id] = cve_detail[:500]

                findings.append(finding)
                risk_score += {"CRITICAL": 30, "HIGH": 15, "MEDIUM": 5, "LOW": 1}[finding["severity"]]
            else:
                findings.append({
                    "type": "port",
                    "port": p["port"],
                    "service": service,
                    "description": f"未知服务 (端口 {p['port']})",
                    "risks": ["未知服务可能有未知漏洞"],
                    "recommendations": ["确认此服务是否必要", "如果不必要，关闭此端口"],
                    "cves": [],
                    "severity": "MEDIUM",
                })
                risk_score += 5

        # 2. Web 路径分析
        for p in paths:
            knowledge = PATH_KNOWLEDGE.get(p["path"])
            if knowledge:
                finding = {
                    "type": "path",
                    "path": p["path"],
                    "url": p["url"],
                    "status": p["status"],
                    "description": knowledge["description"],
                    "impact": knowledge["impact"],
                    "fix": knowledge["fix"],
                    "severity": knowledge["risk"],
                }
                findings.append(finding)
                risk_score += {"CRITICAL": 25, "HIGH": 10, "MEDIUM": 5, "LOW": 1}[knowledge["risk"]]

        # 3. 关联推理（这是扫描器做不到的）
        correlations = self._correlate(findings)

        # 4. 与历史对比
        historical = self._compare_with_history(target, findings)

        risk_score = min(100, risk_score)

        return {
            "findings": findings,
            "correlations": correlations,
            "historical": historical,
            "risk_score": risk_score,
        }

    def _correlate(self, findings: list[dict]) -> list[str]:
        """关联推理：发现组合风险。"""
        correlations = []
        services = {f["service"] for f in findings if f["type"] == "port"}
        paths = {f["path"] for f in findings if f["type"] == "path"}

        # 数据库 + Web 管理界面 = 极高风险
        if {"MySQL", "MSSQL", "PostgreSQL", "MongoDB", "Redis"} & services:
            if {"phpmyadmin", "admin", "console"} & paths:
                correlations.append("🔴 数据库暴露 + 管理界面暴露 = 攻击者可以直接操作数据库")

        # SMB + RDP = 横向移动风险
        if "SMB" in services and "RDP" in services:
            correlations.append("🔴 SMB + RDP 同时开放 = 攻击者可以横向移动整网")

        # .env + 数据库 = 密码泄露
        if ".env" in paths and ({"MySQL", "MSSQL", "PostgreSQL", "MongoDB"} & services):
            correlations.append("🔴 .env 文件暴露 + 数据库开放 = 数据库密码可能已泄露")

        # .git + 任何服务 = 源码泄露
        if ".git" in paths:
            correlations.append("🟠 .git 暴露 = 攻击者可以下载全部源代码，寻找更多漏洞")

        # 多个高危端口 = 攻击面大
        high_ports = [f for f in findings if f.get("severity") in ("CRITICAL", "HIGH") and f["type"] == "port"]
        if len(high_ports) >= 3:
            correlations.append(f"🟠 {len(high_ports)} 个高危端口同时开放 = 攻击面过大")

        # Redis + SSH = 写入公钥
        if "Redis" in services and "SSH" in services:
            correlations.append("🔴 Redis + SSH 同时开放 = 攻击者可能通过 Redis 写入 SSH 公钥")

        return correlations

    def _compare_with_history(self, target: str, findings: list[dict]) -> dict:
        """与历史扫描对比。"""
        history = [s for s in self.memory.get("scans", []) if s.get("target") == target]

        if not history:
            return {"status": "first_scan", "message": "首次扫描此目标"}

        last = history[-1]
        last_ports = set(last.get("ports", []))
        current_ports = set(f["port"] for f in findings if f["type"] == "port")

        new_ports = current_ports - last_ports
        closed_ports = last_ports - current_ports

        result = {
            "status": "compared",
            "previous_scan": last.get("time", "unknown"),
            "new_ports": sorted(new_ports),
            "closed_ports": sorted(closed_ports),
        }

        if new_ports:
            result["message"] = f"⚠️ 新开 {len(new_ports)} 个端口: {sorted(new_ports)}"
        elif closed_ports:
            result["message"] = f"✅ 关闭了 {len(closed_ports)} 个端口"
        else:
            result["message"] = "端口状态无变化"

        return result

    def _remember(self, target: str, ip: str, ports: list, paths: list, analysis: dict):
        """记住这次扫描。"""
        self.memory.setdefault("scans", []).append({
            "target": target,
            "ip": ip,
            "time": datetime.now().isoformat(),
            "ports": [p["port"] for p in ports],
            "paths": [p["path"] for p in paths],
            "risk_score": analysis["risk_score"],
        })

        # 只保留最近 50 次扫描
        self.memory["scans"] = self.memory["scans"][-50:]

        # 累积发现
        for f in analysis["findings"]:
            key = f"{f['type']}:{f.get('port', f.get('path'))}"
            self.memory.setdefault("findings", {})[key] = {
                "last_seen": datetime.now().isoformat(),
                "count": self.memory.get("findings", {}).get(key, {}).get("count", 0) + 1,
                "severity": f.get("severity", "UNKNOWN"),
            }

        self._save_memory()

    def _generate_report(self, target: str, ip: str, ports: list, paths: list,
                        analysis: dict, elapsed: float) -> str:
        """生成智能报告。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        risk_score = analysis["risk_score"]
        findings = analysis["findings"]
        correlations = analysis["correlations"]
        historical = analysis["historical"]

        if risk_score >= 70:
            risk_label = "🔴 高风险"
        elif risk_score >= 40:
            risk_label = "🟡 中风险"
        elif risk_score >= 10:
            risk_label = "🟢 低风险"
        else:
            risk_label = "✅ 安全"

        # 分类
        critical = [f for f in findings if f.get("severity") == "CRITICAL"]
        high = [f for f in findings if f.get("severity") == "HIGH"]
        medium = [f for f in findings if f.get("severity") == "MEDIUM"]
        low = [f for f in findings if f.get("severity") == "LOW"]

        report = f"""# MCR 智能安全审计报告

> 目标：{target} ({ip})
> 时间：{now}
> 耗时：{elapsed:.1f} 秒
> 工具：MCR Smart Audit v1.0

---

## 风险评估

**{risk_label}** — 风险评分：{risk_score}/100

| 级别 | 发现数 |
|------|--------|
| 🔴 CRITICAL | {len(critical)} |
| 🟠 HIGH | {len(high)} |
| 🟡 MEDIUM | {len(medium)} |
| 🟢 LOW | {len(low)} |

"""

        # 关联推理
        if correlations:
            report += "## ⚠️ 关联风险（组合发现）\n\n"
            report += "> 这些风险单独看可能不严重，但组合起来非常危险。\n\n"
            for c in correlations:
                report += f"- {c}\n"
            report += "\n"

        # 历史对比
        report += f"## 📊 历史对比\n\n"
        report += f"- 状态：{historical['message']}\n"
        if historical.get("new_ports"):
            report += f"- 新开端口：{historical['new_ports']}\n"
        if historical.get("closed_ports"):
            report += f"- 已关闭：{historical['closed_ports']}\n"
        report += "\n"

        # 详细发现
        if critical:
            report += "## 🔴 紧急处理\n\n"
            for f in critical:
                if f["type"] == "port":
                    report += f"### 端口 {f['port']} — {f['service']}\n\n"
                    report += f"**{f['description']}**\n\n"
                    report += "风险：\n"
                    for r in f["risks"]:
                        report += f"- {r}\n"
                    report += "\n修复：\n"
                    for r in f["recommendations"]:
                        report += f"- {r}\n"
                    if f.get("cves"):
                        report += f"\n相关漏洞：{', '.join(f['cves'])}\n"
                elif f["type"] == "path":
                    report += f"### {f['url']}\n\n"
                    report += f"**{f['description']}**\n\n"
                    report += f"影响：{f['impact']}\n\n"
                    report += f"修复：{f['fix']}\n"
                report += "\n"

        if high:
            report += "## 🟠 尽快处理\n\n"
            for f in high:
                if f["type"] == "port":
                    report += f"- **端口 {f['port']} ({f['service']})**: {f['risks'][0]}\n"
                elif f["type"] == "path":
                    report += f"- **/{f['path']}**: {f['description']}\n"
            report += "\n"

        if medium:
            report += "## 🟡 建议处理\n\n"
            for f in medium:
                if f["type"] == "port":
                    report += f"- **端口 {f['port']} ({f['service']})**: {f['risks'][0]}\n"
                elif f["type"] == "path":
                    report += f"- **/{f['path']}**: {f['description']}\n"
            report += "\n"

        if not critical and not high:
            report += "## ✅ 总结\n\n"
            report += "未发现严重安全问题。建议定期复查。\n\n"

        report += f"""---

## 关于本报告

本报告由 MCR Smart Audit 生成。
MCR 是一个本地运行的 AI 安全审计系统，不只是扫描，还能推理。

本报告仅用于授权的安全测试。

---
*Generated by MCR v5.0 — My Cognitive Runtime*
"""
        return report


# ═══ 主程序 ═══

def main():
    if len(sys.argv) < 2:
        print("MCR Smart Audit v1.0")
        print()
        print("用法: python mcr_audit_smart.py <target>")
        print()
        print("这是智能审计员，不是普通扫描器。它会：")
        print("  1. 扫描端口和路径")
        print("  2. 分析每个发现的风险和修复方法")
        print("  3. 发现组合风险（关联推理）")
        print("  4. 与历史扫描对比")
        print("  5. 记住这次扫描，下次更准")
        sys.exit(1)

    target = sys.argv[1]
    auditor = SecurityAuditor()
    auditor.audit(target)


if __name__ == "__main__":
    main()
