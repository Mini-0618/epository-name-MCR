# MCR — My Cognitive Runtime

一个会**思考**的本地 AI 系统。不只扫描，还能推理、记忆、进化。

---

## 3 秒开始

```bash
git clone https://github.com/Mini-0618/MCR.git
cd MCR
python mcr.py status
```

---

## 用法

```bash
# 安全审计
python mcr.py "扫描 127.0.0.1 的安全漏洞"
python mcr.py "扫描 example.com"

# 代码分析
python mcr.py "分析 runtime/unified_loop.py"
python mcr.py "分析 mcr_audit_smart.py"

# 知识查询
python mcr.py "搜索 Redis 安全知识"
python mcr.py "查询 CVE-2017-0144"

# 系统状态
python mcr.py status

# 持续运行（后台进化）
python mcr.py loop
python mcr.py loop 30   # 每 30 秒一轮
```

---

## 它能干什么

| 功能 | 命令 | 说明 |
|------|------|------|
| 安全审计 | `python mcr.py "扫描 X"` | 端口扫描 + 路径扫描 + CVE 知识 + 关联推理 + 历史对比 |
| 代码分析 | `python mcr.py "分析 X.py"` | 行数/函数/类/导入 + 风险扫描 |
| 系统状态 | `python mcr.py status` | 稳态/免疫/进化/LLM 全部状态 |
| 持续运行 | `python mcr.py loop` | 10 大生命系统持续运转 |
| 知识查询 | `python mcr.py "搜索 X"` | 从 49 万安全知识文件中检索 |

---

## 架构

```
python mcr.py "你的任务"
        │
        ▼
   ┌─────────┐
   │  路由器  │ ← 自动判断任务类型
   └────┬────┘
        │
   ┌────┴────────────────────────────┐
   │                                 │
   ▼                                 ▼
安全审计                        认知循环
mcr_audit_smart.py             unified_loop.py
   │                                 │
   ├── 端口扫描                  15 步认知循环
   ├── 路径扫描                  10 大生命系统
   ├── CVE 知识库                真实进化引擎
   ├── 关联推理                  免疫自修复
   └── 历史对比                  稳态自调节
```

---

## 10 大生命系统

| # | 系统 | 功能 | 模块 |
|---|------|------|------|
| 1 | 神经系统 | 信号传导、认知处理 | event_bus, cognitive_bridge |
| 2 | 记忆系统 | 4层巩固、Sleep 整理 | sleep_consolidator, agi/ |
| 3 | 内分泌系统 | 全局广播、信号分级 | global_workspace |
| 4 | 循环系统 | 消息运输、Agent 通信 | message_bus, agent_bridge |
| 5 | 免疫系统 | 自修复、自诊断 | immune_system, failure_analyzer |
| 6 | 进化系统 | 繁殖、变异、选择 | evolution, evolution_with_env |
| 7 | 感觉系统 | 环境感知、机会检测 | environment_monitor |
| 8 | 呼吸系统 | 外部交互、A2A/MCP | a2a_server, llm_provider |
| 9 | 稳态系统 | 资源监控、负反馈调节 | homeostasis |
| 10 | 自主神经系统 | 目标生成、动机驱动 | goal_generator |

---

## 数字

- 25 个核心模块
- 23 个 AGI 模块
- 18 个应用
- 49 万安全知识文件
- codex-local 准确率 96%
- 本地运行，零云端依赖

---

## 依赖

Python 3.10+，无额外依赖。

可选：
- `psutil` — 稳态系统 CPU/内存监控
- `requests` — Web 路径扫描

---

## 许可证

Apache License 2.0

---

*MCR — 不只是工具，是数字有机体。*
