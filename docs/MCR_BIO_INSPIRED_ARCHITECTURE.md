# MCR 生物启发有机体架构 v4.0

> MCR = 活的有机体。不是模块堆叠，是有生命特征的数字系统。
> v4.0 更新：补全孤儿模块映射 + 课程体系底层 + 完整的系统间交互设计。

---

## 一、设计哲学

### 1.1 从工程架构到生命架构

MCR 的前身是"工程架构"——模块之间靠函数调用和 JSONL 文件连接，像搭积木。
现在要重构成"生命架构"——子系统之间靠信号传递和反馈回路连接，像活的有机体。

**核心区别：**

| 工程架构 | 生命架构 |
|---------|---------|
| 模块调用 | 信号传递 |
| 硬编码流程 | 涌现行为 |
| 集中控制 | 分布式自组织 |
| 手动维护 | 自修复 |
| 静态配置 | 进化适应 |

### 1.2 生物启发的 6 条原则

| # | 原则 | 来源 | MCR 含义 |
|---|------|------|---------|
| 1 | **异构专业化** | 连接组学（果蝇14万神经元搞定复杂行为） | Agent 不要均匀网络，要任务特化模块 |
| 2 | **稀疏事件驱动** | SNN（0.3 spikes/neuron 够用） | 事件触发而非轮询，低功耗高效率 |
| 3 | **记忆巩固** | 海马→新皮层→睡眠整理 | 工作记忆+长期知识库+离线压缩 |
| 4 | **稳态自调节** | 负反馈维持平衡 | Agent 自调节资源管理 |
| 5 | **自创生** | 生命自我修复 | 自修复/自诊断 |
| 6 | **开放进化** | 繁殖+变异+选择 | Agent/技能交叉组合进化 |

### 1.3 不是什么

- ❌ 不是 AGI（不声称意识或通用智能）
- ❌ 不是神经网络模拟（不模拟生物神经元）
- ❌ 不是仿生学照搬（取原理，不抄实现）
- ✅ 是用生物系统的组织原则来设计软件架构

---

## 二、有机体架构总览

### 2.1 十大生命系统（v4.0 扩展）

v3.0 有 7 大系统。v4.0 扩展到 10 大系统，补全了循环系统、呼吸系统、自主神经系统。

```
┌──────────────────────────────────────────────────────────────┐
│                       MCR 有机体 v4.0                         │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │ 1.神经系统 │  │ 2.记忆系统 │  │ 3.内分泌  │  │ 4.循环系统 │     │
│  │ 事件驱动  │  │ 4层巩固   │  │ 全局广播  │  │ 消息运输  │     │
│  │ 认知循环  │  │ Sleep整理  │  │ 信号分级  │  │ Agent通信 │     │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘     │
│       │              │              │              │          │
│  ┌────┴──────────────┴──────────────┴──────────────┴────┐     │
│  │               共享事件总线 (EventBus)                   │     │
│  └────┬──────────────┬──────────────┬──────────────┬────┘     │
│       │              │              │              │          │
│  ┌────┴─────┐  ┌────┴─────┐  ┌────┴─────┐  ┌────┴─────┐     │
│  │ 5.免疫系统 │  │ 6.进化系统 │  │ 7.感觉系统 │  │ 8.呼吸系统 │     │
│  │ 自修复    │  │ 繁殖变异  │  │ 环境感知  │  │ 外部交互  │     │
│  │ 自诊断    │  │ 自然选择  │  │ 机会检测  │  │ A2A/MCP  │     │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘     │
│                                                              │
│  ┌──────────────────────┐  ┌──────────────────────┐          │
│  │ 9. 稳态系统            │  │ 10. 自主神经系统       │          │
│  │ 资源监控 / 负反馈调节  │  │ 目标生成 / 动机驱动   │          │
│  └──────────────────────┘  └──────────────────────┘          │
│                                                              │
│  ┌──────────────────────────────────────────────┐            │
│  │ 不变层：WAL / 事件溯源 / 密码学证明链           │            │
│  └──────────────────────────────────────────────┘            │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 生物 → MCR 完整映射表（v4.0 完整版）

| 生物系统 | 功能 | MCR 子系统 | 当前模块 | 状态 |
|----------|------|-----------|---------|------|
| **神经系统** | 信号传导、认知处理 | 事件驱动认知循环 | event_bus, cognitive_loop, unified_loop, world_model, prediction_tracker | ⚠️ 需激活 |
| **记忆系统** | 海马→新皮层巩固 | 4层记忆 + Sleep | layered_memory, memory_retriever, memory_index, temporal_memory, tier_manager, memory_adapter | ⚠️ 需加巩固 |
| **内分泌系统** | 全局激素广播 | 全局工作空间 | global_workspace | ❌ 新建 |
| **循环系统** | 血液运输、物质分配 | 消息总线 | message_bus, agent_bridge | ✅ 已有 |
| **免疫系统** | 识别+消灭威胁 | 自修复/自诊断 | failure_analyzer, pattern_detector, self_correction, security_scanner | ⚠️ 需升级 |
| **进化系统** | 繁殖+变异+选择 | Agent/技能进化 | evolution, self_improve, agi/ 下 60+ 文件 | ⚠️ 需结构化 |
| **感觉系统** | 感知环境变化 | 环境监控 | environment_monitor, opportunity_detector, monitor | ⚠️ 需强化 |
| **呼吸系统** | 与外部环境交换 | 外部交互 | a2a_server, a2a_client, hermes_bridge, claude_bridge, mcp_server | ✅ 已有 |
| **稳态系统** | 维持内部平衡 | 资源自调节 | homeostasis | ❌ 新建 |
| **自主神经系统** | 目标生成、动机驱动 | 自主目标 | goal_generator, autonomous_agent, autonomous_scheduler | ⚠️ 需整合 |
| **骨骼/肌肉** | 执行动作 | Task Engine | task_engine | ✅ 已有 |
| **皮肤** | 边界防护 | 安全模型 | permissions, deny/approve/allow | ✅ 已有 |
| **DNA** | 遗传信息 | 事件溯源 | wal, state, reducer, event_gate, events, provenance, replay_verifier | ✅ 已有 |

### 2.3 数据流

```
外部输入 ──→ 感觉系统 ──→ 神经系统 ──→ 记忆系统
                │              │              │
                ▼              ▼              ▼
           环境监控       认知循环       4层记忆
           机会检测       决策生成       Sleep巩固
                │              │              │
                └──────┬───────┼──────────────┘
                       │       │
              ┌────────┴───────┴────────┐
              │    内分泌系统（全局广播）   │
              └──┬────────┬────────┬────┘
                 │        │        │
            ┌────┴───┐ ┌──┴───┐ ┌──┴────┐
            │免疫系统 │ │进化  │ │自主神经│
            │自修复   │ │系统  │ │目标生成│
            └────┬───┘ └──┬───┘ └──┬────┘
                 │        │        │
                 └────────┼────────┘
                          │
                    ┌─────┼─────┐
                    ▼           ▼
              稳态系统      循环系统
              资源调节      消息运输
                    │           │
                    └─────┬─────┘
                          │
                    ┌─────┼─────┐
                    ▼           ▼
               执行系统     呼吸系统
              Task Engine   A2A/MCP
```

---

## 三、十大生命系统详细设计

### 3.1 神经系统 — 事件驱动认知循环

**生物学原理：**
- 大脑不轮询，而是事件驱动——刺激来了才响应
- 0.3 spikes/neuron 就够（Nature Communications 2024）
- 果蝇 14 万神经元靠异构回路协调复杂行为

**当前模块：**
- `event_bus.py` — 基础 pub/sub + WAL（良好，需加脉冲分级）
- `cognitive_loop.py` — observe→predict→gate→execute→record（良好，但未接入 ECOSYSTEM）
- `unified_loop.py` — 串行 8 步管道（需改为异构多回路）
- `world_model.py` — 预测系统（优秀，但未被调用）
- `prediction_tracker.py` — Brier 校准（优秀，但未被调用）

**改造目标：**

#### 3.1.1 稀疏脉冲事件总线

```
当前：所有事件都广播，订阅者自己过滤
目标：事件有"脉冲强度"，低强度事件不广播，只记录到 WAL
```

**脉冲强度分级：**
| 强度 | 行为 | 示例 |
|------|------|------|
| 0 (静默) | 只写 WAL | routine heartbeat |
| 1 (低) | 写 WAL + 日志 | memory decay |
| 2 (中) | 写 WAL + 通知订阅者 | task completed |
| 3 (高) | 写 WAL + 全局广播 | error, opportunity |
| 4 (紧急) | 写 WAL + 全局广播 + 中断当前任务 | security event |

#### 3.1.2 异构认知回路

```
当前：Scan → Detect → Goal → Execute → Record → Analyze → Pattern → Correct
     （一个循环做所有事）

目标：多个专业化回路并行运行
     ├── 感知回路（高频，10s）：环境扫描 + 异常检测
     ├── 决策回路（中频，60s）：目标生成 + 策略选择
     ├── 学习回路（低频，300s）：模式识别 + 知识巩固
     └── 维护回路（极低频，3600s）：自诊断 + 进化
```

#### 3.1.3 认知循环

保持 mcr-runtime 的 observe→predict→gate→execute→record→learn，但：
- observe 从感觉系统读取（不只是文件）
- predict 调用 world_model（不只是模板）
- gate 参考全局工作空间的信号
- execute 通过 task_engine（已有）
- record 写入事件溯源 WAL（已有）
- learn 触发记忆巩固（新增）

---

### 3.2 记忆系统 — 4 层记忆 + Sleep 巩固

**生物学原理：**
- 海马体快速编码 → 新皮层慢速巩固
- 睡眠期间记忆被重组和压缩
- 突触缩放：常用的记忆增强，不用的衰减

**当前模块：**
- `layered_memory.py` — 5785 行，4 层生命周期完整（**最成熟模块**）
- `memory_retriever.py` — 语义检索（良好）
- `memory_index.py` — 记忆索引（良好）
- `temporal_memory.py` — 时序记忆（良好）
- `tier_manager.py` — 层级管理（良好）
- `memory_adapter.py` — 统一接口（良好）

**改造目标：**

#### 3.2.1 4 层记忆（已有，保持）

```
working → episodic → semantic → archive → DELETED
```

#### 3.2.2 Sleep 巩固（新增）

新增 `runtime/sleep_consolidator.py`：

```python
class SleepConsolidator:
    """
    模拟海马-新皮层记忆巩固。

    在"空闲"时段（无活跃任务时）自动运行：
    1. 回放：从 working memory 中选择高价值事件回放
    2. 整合：将相关记忆合并为更紧凑的表示
    3. 清理：删除低价值的 working memory 条目
    4. 索引：更新语义索引
    """
    def consolidate(self, tick: int): ...
    def select_candidates(self): ...
    def replay_and_integrate(self, memory): ...
```

**触发条件：** Daemon 空闲时 / 手动 `mcr-os memory sleep` / 每 24h 至少一次

---

### 3.3 内分泌系统 — 全局工作空间（新建）

**生物学原理：**
- 全局工作空间理论 (GWT)：意识 = 关键信息从局部模块广播到全局
- 内分泌系统：激素（肾上腺素/多巴胺/皮质醇）广播到全身

**新建模块：** `runtime/global_workspace.py`

```python
class GlobalWorkspace:
    """
    MCR 的"内分泌系统"。

    接收所有 EventBus 事件，评估显著性，广播重要信号。
    任何模块都可以读取当前全局状态。
    """
    SIGNALS = {
        'emergency':  {'color': '🔴', 'ttl': 60,   'priority': 4},
        'opportunity': {'color': '🟡', 'ttl': 300,  'priority': 3},
        'status':     {'color': '🟢', 'ttl': 600,  'priority': 2},
        'reflection': {'color': '🔵', 'ttl': 1800, 'priority': 1},
    }

    def evaluate(self, event) -> Optional[dict]:
        """评估事件的显著性，决定是否广播。"""
        saliency = self.compute_saliency(event)
        if saliency >= THRESHOLD:
            signal = self.create_signal(event, saliency)
            self.broadcast(signal)
            return signal
        return None

    def compute_saliency(self, event) -> float:
        """计算事件显著性（0-1）。"""
        factors = [
            self.novelty(event),      # 新颖性
            self.relevance(event),    # 与当前目标的相关性
            self.urgency(event),      # 紧迫性
            self.valence(event),      # 正/负面
        ]
        return weighted_average(factors)

    def get_context(self) -> dict:
        """获取当前全局上下文（任何模块可调用）。"""
        return {
            'focus': self.focus,
            'active_goals': self.active_goals,
            'recent_signals': self.signal_history[-10:],
            'emergency_pending': len(self.emergency_queue) > 0,
        }
```

**系统间交互：**
- 神经系统 → 内分泌系统：所有事件都经过显著性评估
- 内分泌系统 → 认知循环：提供当前焦点和紧急信号
- 内分泌系统 → 免疫系统：emergency 信号触发免疫响应
- 内分泌系统 → 稳态系统：status 信号反映系统状态
- 内分泌系统 → 自主神经系统：opportunity 信号触发目标生成

---

### 3.4 循环系统 — 消息运输（已有，需整合）

**生物学原理：**
- 血液循环运输氧气、营养、激素到全身
- 心脏是泵，血管是通道
- 血液还携带免疫细胞

**当前模块：**
- `message_bus.py` — Agent 间消息传递
- `agent_bridge.py` — 调用外部 Agent

**映射：**
| 生物概念 | MCR 对应 | 说明 |
|----------|---------|------|
| 心脏 | message_bus 的核心路由 | 消息的泵送中心 |
| 血管 | Agent 间通信通道 | 消息传输管道 |
| 血液 | 消息/事件载体 | 携带数据和信号 |
| 血小板 | 消息优先级 | 紧急消息优先传输 |

**改造目标：**
- 整合到 EventBus 的脉冲分级系统
- 高优先级消息（相当于肾上腺素）加速传输
- 低优先级消息（相当于代谢废物）延迟或丢弃

---

### 3.5 免疫系统 — 自修复/自诊断（升级现有）

**生物学原理：**
- 先天免疫：快速、通用响应（巨噬细胞、炎症反应）
- 适应性免疫：学习特定威胁（T 细胞、B 细胞、记忆细胞）

**当前模块：**
- `failure_analyzer.py` — 分类失败原因（超时/权限/缺失/网络/编码/依赖/解析）
- `pattern_detector.py` — 检测重复序列、高频事件
- `self_correction.py` — 修复编码问题和缺失目录
- `security_scanner.py` — 安全扫描

**差距：** 当前只有"先天免疫"的一小部分（静态分类+简单修复），没有"适应性免疫"（学习能力）和"免疫记忆"。

**改造目标：**

新建 `runtime/immune_system.py`，整合现有三件套：

```python
class ImmuneSystem:
    """
    MCR 的"免疫系统"。

    两层防御：
    1. 先天免疫：快速检测已知问题模式，自动修复
    2. 适应性免疫：学习新的问题模式，建立记忆
    """
    INNATE_RESPONSES = {
        'memory_pressure': 'compact_working_memory',
        'event_backlog': 'trigger_compaction',
        'module_crash': 'restart_module',
        'permission_spike': 'alert_owner',
        'disk_full': 'cleanup_logs',
        'wakeup_timeout': 'restart_daemon',
    }

    def patrol(self, tick: int):
        """巡逻：检查系统健康状态。"""
        anomalies = self.scan_for_anomalies()
        for anomaly in anomalies:
            response = self.respond(anomaly)
            self.record_encounter(anomaly, response)

    def respond(self, anomaly: dict) -> dict:
        """对异常做出响应。"""
        # 先天免疫：查表
        if anomaly['type'] in self.INNATE_RESPONSES:
            return self.execute_innate(self.INNATE_RESPONSES[anomaly['type']], anomaly)
        # 适应性免疫：查记忆
        similar = self.find_similar_past(anomaly)
        if similar and similar['resolution']:
            return self.execute_learned(similar['resolution'], anomaly)
        # 未知威胁：报告给 owner
        return self.report_unknown(anomaly)

    def record_encounter(self, anomaly, response):
        """记录遭遇（免疫记忆）。"""
        self.memory.append({
            'anomaly': anomaly, 'response': response, 'outcome': None, 'tick': current_tick,
        })
```

**与现有模块的关系：**
- failure_analyzer → 免疫系统的"抗原识别"
- pattern_detector → 免疫系统的"异常检测"
- self_correction → 免疫系统的"先天免疫响应"
- security_scanner → 免疫系统的"巡逻"

---

### 3.6 进化系统 — Agent/技能进化（结构化现有）

**生物学原理：**
- 繁殖：两个个体的基因组合产生后代
- 变异：随机修改基因
- 自然选择：适应度高的个体存活
- Sakana AI：通过"繁殖"现有模型创建新模型

**当前模块：**
- `self_improve.py` (mcr-runtime) — 自我改进校准周期
- `agi/` 目录下 60+ 个文件 — 自动迭代改进的工程实现（self_improve_*.py, feedback_learning_*.py 等）

**差距：** 当前的"进化"是散落在 agi/ 目录下的工程实现，没有结构化的基因组概念。需要统一为进化框架。

**改造目标：**

新建 `runtime/evolution.py`，统一现有 agi/ 文件：

```python
class SkillGenome:
    """技能基因组。"""
    CHROMOSOMES = {
        'prompt': {'system_prompt': 'str', 'few_shot': 'list', 'cot': 'bool'},
        'tools': {'available': 'list', 'strategy': 'str', 'fallback': 'list'},
        'parameters': {'temperature': 'float', 'timeout': 'int', 'retries': 'int'},
        'validation': {'criteria': 'str', 'format': 'str', 'error_handling': 'str'},
        'memory': {'remember_input': 'bool', 'remember_output': 'bool', 'consolidation': 'str'},
    }

    def crossover(self, other: 'SkillGenome') -> 'SkillGenome': ...
    def mutate(self, rate: float = 0.01) -> 'SkillGenome': ...
    def repair(self): ...

class EvolutionEngine:
    """进化引擎。"""
    def evolve(self, population_size: int = 10): ...
    def evaluate_population(self): ...
    def select_parents(self, fitness): ...
```

**与现有模块的关系：**
- self_improve.py → 进化系统的"适应度评估"
- agi/ 下 60+ 文件 → 进化系统的"变异实验记录"
- skill promotion → 进化系统的"自然选择"

---

### 3.7 感觉系统 — 环境感知（已有，需强化）

**生物学原理：**
- 感觉器官持续感知环境
- 感觉信号传到大脑前先经过"门控"——不重要的信号被过滤

**当前模块：**
- `environment_monitor.py` — 文件扫描、端口检测、系统资源
- `opportunity_detector.py` — 从环境事件中检测机会
- `monitor.py` (mcr-runtime) — 运行监控

**改造目标：**

增强为三模式感知：

| 模式 | 频率 | 说明 |
|------|------|------|
| 被动扫描 | 固定周期 | 文件、端口、资源 |
| 主动探测 | 事件触发 | 某个事件引起时主动扫描 |
| 预测性扫描 | 基于世界模型 | 预测可能的变化 |

**新增感知维度：**
| 感知 | 来源 | 频率 |
|------|------|------|
| 文件系统 | 目录监控 | 实时 |
| 网络 | 端口扫描 | 60s |
| 进程 | psutil | 30s |
| 市场 | A2A market-list | 3600s |
| 用户 | ChatOps 输入 | 事件驱动 |
| LLM | 模型可用性 | 300s |

---

### 3.8 呼吸系统 — 外部交互（已有，需整合）

**生物学原理：**
- 呼吸系统与外部环境交换气体（吸入 O₂，呼出 CO₂）
- 肺泡是交换界面，血液是运输介质

**当前模块：**
- `a2a_server.py` — A2A 服务端（接收外部请求）
- `a2a_client.py` — A2A 客户端（发起外部请求）
- `hermes_bridge.py` — Hermes LLM 适配
- `claude_bridge.py` — Claude 适配
- `mcp_server.py` — MCP 工具暴露

**映射：**
| 生物概念 | MCR 对应 | 说明 |
|----------|---------|------|
| 肺 | A2A 服务端/客户端 | 与外部环境的交换界面 |
| 肺泡 | API 端点 | 数据交换的微观界面 |
| 氧气 | 外部能力/模型 | 从外部获取的能力 |
| 二氧化碳 | 请求/任务 | 向外部发送的需求 |
| 呼吸频率 | API 调用频率 | 受稳态系统调节 |

**改造目标：**
- 整合到脉冲分级系统（高优先级请求优先处理）
- 呼吸频率受稳态系统调节（CPU 高时降低 API 调用频率）
- 呼吸失败（外部服务不可用）触发免疫响应

---

### 3.9 稳态系统 — 资源自调节（新建）

**生物学原理：**
- 负反馈：血糖高 → 胰岛素分泌 → 血糖降低
- 预测性稳态：预期运动 → 提前分泌肾上腺素

**新建模块：** `runtime/homeostasis.py`

```python
class Homeostasis:
    """
    MCR 的"稳态系统"。
    持续监控关键指标，通过负反馈维持平衡。
    """
    VARIABLES = {
        'working_memory_size': {'min': 10, 'max': 100, 'target': 50},
        'event_rate':         {'min': 0,  'max': 100, 'target': 20},
        'cpu_usage':          {'min': 0,  'max': 80,  'target': 30},
        'disk_usage':         {'min': 0,  'max': 90,  'target': 50},
        'task_queue_depth':   {'min': 0,  'max': 50,  'target': 10},
    }

    def regulate(self):
        """执行一轮稳态调节。"""
        for var_name, spec in self.VARIABLES.items():
            current = self.measure(var_name)
            if current > spec['max']:
                self.correct_high(var_name, current, spec)
            elif current < spec['min']:
                self.correct_low(var_name, current, spec)
```

**稳态变量：**
| 变量 | 目标范围 | 过高时 | 过低时 |
|------|---------|--------|--------|
| working_memory 条目 | 10-100 | 触发巩固 | 增加感知频率 |
| 事件速率 | 0-100/s | 提高显著性阈值 | 降低阈值 |
| CPU 使用率 | 0-80% | 降低扫描频率 | 增加扫描 |
| 磁盘使用率 | 0-90% | 清理日志 | — |
| 任务队列深度 | 0-50 | 节流新任务 | — |

**与其他系统的交互：**
- 稳态系统 → 感觉系统：CPU 高时降低扫描频率
- 稳态系统 → 呼吸系统：CPU 高时降低 API 调用频率
- 稳态系统 → 神经系统：事件速率高时提高显著性阈值
- 稳态系统 → 记忆系统：working memory 满时触发巩固
- 稳态系统 → 免疫系统：异常指标触发巡逻

---

### 3.10 自主神经系统 — 目标生成（已有，需整合）

**生物学原理：**
- 自主神经系统控制无意识的生理功能（心跳、呼吸、消化）
- 交感神经（兴奋）和副交感神经（抑制）平衡
- 不需要意识参与就能维持基本功能

**当前模块：**
- `goal_generator.py` — 自主目标生成
- `autonomous_agent.py` (mcr-runtime) — 自主 Agent
- `autonomous_scheduler.py` (mcr-runtime) — 自主调度

**映射：**
| 生物概念 | MCR 对应 | 说明 |
|----------|---------|------|
| 交感神经 | 兴奋信号 | 检测到机会时生成目标 |
| 副交感神经 | 抑制信号 | 资源不足时暂停目标 |
| 心跳 | daemon loop | 持续运行的基本节律 |
| 呼吸 | 事件循环 | 持续的输入输出 |
| 消化 | 任务执行 | 持续处理任务 |

**改造目标：**
- 目标生成参考全局工作空间的 opportunity 信号
- 目标优先级受稳态系统调节
- 目标执行受免疫系统监控（异常目标被阻止）

---

## 四、课程体系底层 — 数据化学与细胞学

### 4.1 数据化学层（v4.0 新增）

**生物科学对应：** 生命的化学组成

**核心概念：**

```python
class Atom:
    """数据原子。最小信息单位。"""
    type: str       # 数据类型（对应元素种类）
    value: Any      # 数据值
    encoding: str   # 编码方式

class Molecule:
    """数据分子。由原子组成的数据结构。"""
    atoms: list[Atom]
    structure: str  # 结构类型
    
    def fold(self):
        """折叠：优化数据表示。"""
        pass

class Enzyme:
    """数据酶。催化特定反应的处理器。"""
    substrate_type: str
    product_type: str
    rate: float
    
    def catalyze(self, substrate: Molecule) -> Molecule:
        """催化反应。"""
        pass

class Metabolism:
    """代谢通路。数据处理管道。"""
    pathway: list[Enzyme]
    
    def process(self, input_data: Molecule) -> Molecule:
        """沿代谢通路处理数据。"""
        current = input_data
        for enzyme in self.pathway:
            current = enzyme.catalyze(current)
        return current
```

**与现有模块的关系：**
- 当前 MCR 的数据流是原始 JSON/JSONL
- 数据化学层是底层抽象，不改变现有逻辑，只是给数据加上结构
- task_engine 的输入输出可以是 Molecule 类型
- event_bus 的事件可以是 Atom 类型

### 4.2 Agent 细胞学（v4.0 新增）

**生物科学对应：** 细胞的结构与功能

**核心概念：**

```python
class AgentCell:
    """MCR 的基本生命单元。"""
    
    def __init__(self, genome: dict):
        self.nucleus = CellNucleus(genome)          # 核心逻辑
        self.membrane = CellMembrane(genome.get('permissions', []))  # 权限边界
        self.ribosome = Ribosome()                  # 执行器
        self.mitochondria = EnergyManager()         # 能源管理
        self.endoplasmic_reticulum = DataPipeline() # 数据管道
        self.golgi = OutputFormatter()              # 输出格式化
        self.lysosome = GarbageCollector()          # 垃圾回收
        self.cytoskeleton = AgentSkeleton()         # 架构框架
        self.state = 'G1'                           # 细胞周期阶段
    
    def receive_signal(self, signal: dict):
        """接收信号（细胞信号转导）。"""
        if not self.membrane.allows(signal):
            return
        self.nucleus.process_signal(signal)
    
    def execute(self, task: dict):
        """执行任务（蛋白质合成）。"""
        result = self.ribosome.translate(task)
        return self.golgi.package(result)
    
    def divide(self) -> 'AgentCell':
        """分裂。"""
        daughter_genome = self.nucleus.replicate()
        return AgentCell(daughter_genome)
    
    def differentiate(self, signal: str):
        """分化。"""
        specialization = {
            'cognitive': CognitiveCell,
            'executor': ExecutorCell,
            'security': SecurityCell,
            'interface': InterfaceCell,
        }
        return specialization.get(signal, AgentCell)(self.nucleus.genome)
    
    def apoptosis(self):
        """程序性死亡。"""
        self.lysosome.digest_self()
        self.state = 'dead'
```

**与现有模块的关系：**
- task_engine 的任务执行 → ribosome（核糖体）
- permissions → membrane（细胞膜）
- garbage collector → lysosome（溶酶体）
- AgentCell 是对现有 Agent 概念的结构化抽象

### 4.3 技能遗传学（v4.0 新增）

**生物科学对应：** 遗传与变异

**核心概念：**

```python
class SkillGenome:
    """技能基因组。"""
    CHROMOSOMES = {
        'prompt': {'system_prompt': 'str', 'few_shot': 'list', 'cot': 'bool'},
        'tools': {'available': 'list', 'strategy': 'str', 'fallback': 'list'},
        'parameters': {'temperature': 'float', 'timeout': 'int', 'retries': 'int'},
        'validation': {'criteria': 'str', 'format': 'str', 'error_handling': 'str'},
        'memory': {'remember_input': 'bool', 'remember_output': 'bool', 'consolidation': 'str'},
    }
    
    def crossover(self, other: 'SkillGenome') -> 'SkillGenome':
        """基因重组。"""
        child_genes = {}
        for chrom_name, chrom in self.CHROMOSOMES.items():
            child_chrom = {}
            for gene_name in chrom:
                if random.random() < 0.5:
                    child_chrom[gene_name] = self.genes.get(chrom_name, {}).get(gene_name)
                else:
                    child_chrom[gene_name] = other.genes.get(chrom_name, {}).get(gene_name)
            child_genes[chrom_name] = child_chrom
        return SkillGenome(child_genes)
    
    def mutate(self, rate: float = 0.01) -> 'SkillGenome':
        """基因突变。"""
        mutated = copy.deepcopy(self.genes)
        for chrom_name, chrom in mutated.items():
            for gene_name, gene_value in chrom.items():
                if random.random() < rate:
                    if isinstance(gene_value, float):
                        chrom[gene_name] = gene_value * random.uniform(0.8, 1.2)
                    elif isinstance(gene_value, int):
                        chrom[gene_name] = max(1, gene_value + random.randint(-5, 5))
        return SkillGenome(mutated)
```

### 4.4 知识植物学（v4.0 新增）

**生物科学对应：** 植物的结构与功能

**核心概念：**

```python
class KnowledgePlant:
    """知识植物。MCR 的知识生长系统。"""
    
    def __init__(self, seed: dict):
        self.seed = seed
        self.roots = []             # 根：知识吸收器
        self.stem = KnowledgeStem() # 茎：知识传输
        self.leaves = []            # 叶：知识加工器
        self.fruits = []            # 果实：交付物
        self.rings = []             # 年轮：知识积累记录
    
    def photosynthesis(self, raw_data: dict) -> dict:
        """光合作用：数据 → 知识。"""
        knowledge = self.process(raw_data)
        insight = self.extract_insight(knowledge)
        self.rings.append({'tick': current_tick, 'knowledge': knowledge})
        return {'knowledge': knowledge, 'insight': insight}
    
    def grow(self, direction: str = 'toward_light'):
        """生长：向目标方向发展。"""
        if direction == 'toward_light':
            self.stem.extend(self.find_light_source())
        elif direction == 'toward_water':
            self.roots.extend(self.find_water_source())
    
    def fruit(self) -> 'Deliverable':
        """结果：产出可交付物。"""
        if len(self.rings) >= 3:
            return Deliverable(self.knowledge())
        return None
```

---

## 五、系统间交互矩阵

| 发送方 ↓ / 接收方 → | 神经 | 记忆 | 内分泌 | 循环 | 免疫 | 进化 | 感觉 | 呼吸 | 稳态 | 自主神经 |
|---------------------|------|------|--------|------|------|------|------|------|------|---------|
| **神经系统** | — | 写入记忆 | 发送事件 | — | 报告异常 | — | 读取感知 | — | 报告状态 | — |
| **记忆系统** | 提供上下文 | — | — | — | — | 提供历史 | — | — | 报告容量 | — |
| **内分泌系统** | 提供焦点 | — | — | 广播信号 | 触发免疫 | 触发进化 | — | — | 报告状态 | 触发目标 |
| **循环系统** | 传递信号 | 传递数据 | 传递信号 | — | 传递免疫细胞 | — | 传递感知 | 传递外部数据 | — | — |
| **免疫系统** | 报告修复 | 记录遭遇 | — | — | — | — | — | — | 触发巡逻 | — |
| **进化系统** | — | 记录进化 | — | — | — | — | — | — | — | — |
| **感觉系统** | 传递感知 | — | 传递事件 | — | 传递异常 | — | — | — | 报告环境 | — |
| **呼吸系统** | 传递外部数据 | — | — | 传递外部数据 | — | — | — | — | 报告可用性 | — |
| **稳态系统** | 调节频率 | 触发巩固 | 调节阈值 | — | 触发巡逻 | — | 调节扫描 | 调节API频率 | — | 调节目标 |
| **自主神经系统** | 生成目标 | — | — | — | — | — | — | — | — | — |

---

## 六、内核合并方案

### 6.1 迁移清单

#### Phase 1: 核心引擎
| 源文件 | 目标 | 说明 |
|--------|------|------|
| `runtime/engine.py` | `ECOSYSTEM/runtime/engine.py` | MCRRuntimeEngine |
| `runtime/wal.py` | `ECOSYSTEM/runtime/wal.py` | WAL |
| `runtime/state.py` | `ECOSYSTEM/runtime/state.py` | 状态管理 |
| `runtime/reducer.py` | `ECOSYSTEM/runtime/reducer.py` | 纯函数状态转换 |
| `runtime/event_gate.py` | `ECOSYSTEM/runtime/event_gate.py` | 事件验证 |
| `runtime/events.py` | `ECOSYSTEM/runtime/events.py` | 30+ 事件类型 |

#### Phase 2: 认知层
| 源文件 | 目标 | 说明 |
|--------|------|------|
| `runtime/cognitive_loop.py` | `ECOSYSTEM/runtime/cognitive_loop.py` | 认知循环 |
| `runtime/world_model.py` | `ECOSYSTEM/runtime/world_model.py` | 世界模型 |
| `runtime/prediction_tracker.py` | `ECOSYSTEM/runtime/prediction_tracker.py` | 预测追踪 |
| `runtime/self_improve.py` | `ECOSYSTEM/runtime/self_improve.py` | 自我改进 |
| `runtime/autonomous_agent.py` | `ECOSYSTEM/runtime/autonomous_agent.py` | 自主 Agent |

#### Phase 3: 记忆层
| 源文件 | 目标 | 说明 |
|--------|------|------|
| `stable/layered_memory.py` | `ECOSYSTEM/runtime/layered_memory.py` | 4 层记忆 |
| `runtime/memory_adapter.py` | `ECOSYSTEM/runtime/memory_adapter.py` | 记忆接口 |
| `runtime/memory_retriever.py` | `ECOSYSTEM/runtime/memory_retriever.py` | 语义检索 |
| `runtime/memory_index.py` | `ECOSYSTEM/runtime/memory_index.py` | 记忆索引 |
| `runtime/temporal_memory.py` | `ECOSYSTEM/runtime/temporal_memory.py` | 时序记忆 |
| `runtime/tier_manager.py` | `ECOSYSTEM/runtime/tier_manager.py` | 层级管理 |

#### Phase 4: 桥接层
| 源文件 | 动作 | 说明 |
|--------|------|------|
| `runtime/hermes_bridge.py` | 迁入 | Hermes LLM 适配 |
| `runtime/claude_bridge.py` | 迁入 | Claude 适配 |
| `runtime/mcp_server.py` | 迁入 | MCP 工具暴露 |

### 6.2 合并后的目录结构

```
ECOSYSTEM/runtime/
  # ═══ 不变层（DNA）═══
  engine.py             — G2 引擎
  wal.py                — WAL
  state.py              — 状态管理
  reducer.py            — 状态转换
  event_gate.py         — 事件验证
  events.py             — 事件类型
  provenance.py         — 密码学证明链
  replay_verifier.py    — 重放验证

  # ═══ 神经系统 ═══
  event_bus.py          — 事件总线（加脉冲分级）
  cognitive_loop.py     — 认知循环
  world_model.py        — 世界模型
  prediction_tracker.py — 预测追踪
  unified_loop.py       — 认知主循环（重写为异构多回路）

  # ═══ 记忆系统 ═══
  layered_memory.py     — 4 层记忆
  memory_adapter.py     — 记忆接口
  memory_retriever.py   — 语义检索
  memory_index.py       — 记忆索引
  temporal_memory.py    — 时序记忆
  tier_manager.py       — 层级管理
  sleep_consolidator.py — Sleep 巩固（新建）

  # ═══ 内分泌系统 ═══
  global_workspace.py   — 全局工作空间（新建）

  # ═══ 循环系统 ═══
  message_bus.py        — 消息总线
  agent_bridge.py       — Agent 桥接

  # ═══ 免疫系统 ═══
  immune_system.py      — 免疫系统（新建，整合 failure_analyzer/pattern_detector/self_correction）
  failure_analyzer.py   — 抗原识别
  pattern_detector.py   — 异常检测
  self_correction.py    — 先天免疫响应
  security_scanner.py   — 安全巡逻

  # ═══ 进化系统 ═══
  evolution.py          — 进化引擎（新建）
  self_improve.py       — 适应度评估
  skill_genome.py       — 技能基因组（新建）

  # ═══ 感觉系统 ═══
  environment_monitor.py — 环境监控（增强）
  opportunity_detector.py — 机会检测
  monitor.py            — 运行监控

  # ═══ 呼吸系统 ═══
  a2a_server.py         — A2A 服务端
  a2a_client.py         — A2A 客户端
  hermes_bridge.py      — Hermes 适配
  claude_bridge.py      — Claude 适配
  mcp_server.py         — MCP 工具

  # ═══ 稳态系统 ═══
  homeostasis.py        — 稳态调节（新建）

  # ═══ 自主神经系统 ═══
  goal_generator.py     — 目标生成
  autonomous_agent.py   — 自主 Agent
  autonomous_scheduler.py — 自主调度

  # ═══ 执行系统 ═══
  task_engine.py        — 任务管道

  # ═══ 课程体系底层 ═══
  data_chemistry.py     — 数据化学（Atom/Molecule/Enzyme/Metabolism）（新建）
  agent_cell.py         — Agent 细胞学（新建）
  knowledge_plant.py    — 知识植物学（新建）
```

---

## 七、实施路线图

### Phase 0: 架构文档（✅ 完成）
- ✅ v3.0 文档
- ✅ v4.0 文档（本次更新）

### Phase 1: 合并内核 + 接通认知
**目标：** Cognitive Core 3/10 → 6/10
1. 迁移 mcr-runtime 核心模块到 ECOSYSTEM/runtime/
2. 重写 cognitive_bridge.py
3. 重写 unified_loop.py 为异构多回路
4. 验收：`mcr-os cognitive status` 返回真实世界模型状态

### Phase 2: 全局工作空间 + 循环系统
**目标：** 新增全局广播能力
1. 新建 global_workspace.py
2. 修改 event_bus.py 加入脉冲分级
3. 整合 message_bus 到脉冲系统
4. 验收：紧急事件自动广播

### Phase 3: 免疫系统 + 稳态系统
**目标：** 系统能自我维持
1. 新建 immune_system.py（整合现有三件套）
2. 新建 homeostasis.py
3. 验收：异常自动修复，资源自动调节

### Phase 4: 进化系统 + Sleep 巩固
**目标：** 系统能自我进化
1. 新建 evolution.py + skill_genome.py
2. 新建 sleep_consolidator.py
3. 整合 agi/ 下 60+ 文件到进化框架
4. 验收：技能自动优化，记忆定期巩固

### Phase 5: 课程体系底层
**目标：** 从工程架构彻底转变为生命架构
1. 新建 data_chemistry.py（Atom/Molecule/Enzyme/Metabolism）
2. 新建 agent_cell.py（AgentCell + 细胞周期 + 分化）
3. 新建 knowledge_plant.py（知识生长系统）
4. 验收：数据流使用结构化抽象

---

## 八、评分预测

| 维度 | 当前 | P1 后 | P2 后 | P3 后 | P4 后 | P5 后 |
|------|------|-------|-------|-------|-------|-------|
| Agentic OS | 9.7 | 9.7 | 9.8 | 9.8 | 9.9 | **10** |
| Cognitive Core | 3 | **6** | 7 | 7 | **8** | **9** |
| Digital Coworker | 6.7 | 7.0 | 7.5 | **8.0** | **8.5** | **9.0** |
| AGI-Readiness | 5.6 | 6.0 | 6.5 | 7.0 | **7.5** | **8.0** |

---

## 九、关键参考

| 生物学来源 | 架构应用 |
|-----------|---------|
| 连接组学 (FlyWire 2024) | 异构专业化回路 |
| SNN (Nature Communications 2024) | 稀疏脉冲事件驱动 |
| 记忆巩固 (Brodt 2023) | Sleep 巩固机制 |
| GWT (Dehaene-Changeux) | 全局工作空间 |
| 自创生 (Maturana-Varela) | 免疫系统 |
| Sakana AI (2024) | 进化系统 |
| 自由能原理 (Friston) | 稳态系统 |
| IIT (Tononi) | 信息整合度 |
| 生物科学课程体系 | 数据化学/细胞学/遗传学/植物学 |

---

**一句话：** MCR 不是软件，是数字有机体。十大系统协同，从原子到生态，从数据到生命。
