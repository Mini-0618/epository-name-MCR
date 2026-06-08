<p align="center">
  <strong>MCR — My Cognitive Runtime</strong>
</p>

<p align="center">
  一个会<strong>思考</strong>的本地 AI Agent 运行时。<br/>
  4 层记忆、世界模型预测、生物启发免疫系统、代码安全沙箱——<br/>
  全部跑在你自己的机器上，零云端依赖。
</p>

<p align="center">
  <code>pip install mcr-sdk && mcr-os status</code>
</p>

<p align="center">
  <!-- TODO: 替换为实际截图 -->
  <img src="docs/screenshot_demo.png" alt="MCR Demo" width="680"/>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue?style=flat-square" alt="license"/></a>
  <a href="https://github.com/Mini-0618/epository-name-MCR/stargazers"><img src="https://img.shields.io/github/stars/Mini-0618/epository-name-MCR?style=flat-square" alt="stars"/></a>
  <img src="https://img.shields.io/badge/python-3.10+-green?style=flat-square" alt="python"/>
  <a href="https://x.com/Maomaos8yt"><img src="https://img.shields.io/badge/X-@Maomaos8yt-black?style=flat-square&logo=x" alt="X"/></a>
</p>

---

## 为什么选 MCR？

| | agenticSeek | MCR |
|---|---|---|
| **代码安全** | ❌ `exec()` 直接执行，无沙箱 | ✅ 三层防御（AST 分析 + 受限执行 + 审计链） |
| **记忆** | ❌ 单层对话历史 | ✅ 4 层记忆（工作→情景→语义→归档），自动巩固 |
| **决策** | ❌ 先做再想 | ✅ 世界模型预测 + 风险门控（先想再做） |
| **自愈** | ❌ 崩溃就崩溃 | ✅ 免疫系统（7 种威胁检测 + 自动修复） |
| **审计** | ❌ 无日志 | ✅ 事件溯源 + HMAC 密码学证明链 |
| **LLM** | ✅ 7 个 Provider | ✅ 5 个 Provider（Ollama / OpenAI / Anthropic / DeepSeek / Local） |

**一句话：agenticSeek 做广度（浏览器 + 多语言），MCR 做深度（记忆 + 安全 + 认知）。**

---

## 核心特性

### 🧠 认知内核

MCR 不只是"执行命令的 Agent"，它会**思考**。

```
感知 → 预测 → 门控 → 执行 → 记录 → 学习
```

- **世界模型**：每次执行前预测成功率和风险，高风险自动拦截
- **认知循环**：observe → predict → gate → execute → record → learn
- **不是读写 JSONL 的循环**，是真正的认知参与决策

### 🛡️ 代码安全沙箱

agenticSeek 社区最痛的点（[#483](https://github.com/Fosowl/agenticSeek/issues/483), [#494](https://github.com/Fosowl/agenticSeek/issues/494)），MCR 已经解决了。

```
Layer 1: 静态分析 — AST 扫描 + 正则匹配，拦截 15 种危险模式
Layer 2: 受限执行 — shell=False，网络隔离，超时/内存限制
Layer 3: 审计链 — 每次执行记录到 HMAC 签名的 provenance 链
```

拦截能力：
- `exec()` / `eval()` → 拦截
- `import subprocess` → 审计（standard 模式）或拦截（strict 模式）
- `os.system()` / `rm -rf` / `curl | sh` → 拦截
- 网络外联（socket / requests）→ 拦截

### 🧬 4 层记忆系统

像人脑一样记忆：海马体快速编码 → 新皮层慢速巩固。

```
working（工作记忆）→ episodic（情景记忆）→ semantic（语义记忆）→ archive（归档）
```

- 5785 行代码，完整的生命周期管理
- 自动晋升和衰减
- 语义检索（向量搜索，sentence-transformers）

### 💉 免疫系统

7 种已知威胁检测 + 免疫记忆 + 自动修复。

| 威胁 | 检测 | 修复 |
|------|------|------|
| 内存压力 | working memory 条目 > 阈值 | 触发巩固 |
| 事件堆积 | events.jsonl 过大 | 触发压缩 |
| 编码损坏 | UTF-8 decode error | 自动修复 |
| 缺失目录 | FileNotFoundError | 自动创建 |
| 过期会话 | 超过 24h 无活动 | 自动清理 |
| 高失败率 | 连续失败 > 3 次 | 报告 + 降频 |
| 磁盘压力 | 使用率 > 90% | 清理日志 |

### 🔌 统一 LLM 接口

一个接口调所有模型：

```python
from llm_provider import LLMProvider

provider = LLMProvider()
response = provider.chat("你好", model="ollama:qwen2.5:7b")      # 本地
response = provider.chat("你好", model="deepseek:deepseek-chat")  # 云端
```

支持：Ollama（本地）、OpenAI、Anthropic、DeepSeek、自定义端点

### 📜 事件溯源

所有状态变化通过 WAL（Write-Ahead Log）记录，支持：

- 完整的状态重放：`runtime_state == replay(initial_state, WAL)`
- HMAC-SHA256 密码学证明链
- 跨版本状态恢复

---

## 快速开始

### 前置条件

- Python 3.10+
- Git
- Ollama（可选，本地推理）

### 安装

```bash
git clone https://github.com/Mini-0618/MCR.git
cd MCR
pip install -e sdk/python/
```

### 运行

```bash
# 查看状态
python runtime/unified_loop.py status

# 跑一轮认知循环
python runtime/unified_loop.py run --dry-run

# 沙箱自测
python runtime/sandbox.py test

# 免疫系统巡逻
python runtime/immune_system.py patrol
```

### 配置 LLM

编辑 `config/llm_providers.json`：

```json
{
  "default_model": "ollama:qwen2.5:7b",
  "providers": {
    "ollama": {
      "type": "ollama",
      "base_url": "http://localhost:11434",
      "models": ["qwen2.5:7b", "deepseek-coder:6.7b"]
    }
  }
}
```

---

## 项目结构

```
ECOSYSTEM/
├── runtime/
│   ├── unified_loop.py        # 认知主循环（11 步）
│   ├── cognitive_bridge.py    # 认知内核桥接
│   ├── world_model.py         # 世界模型 + 预测
│   ├── sandbox.py             # 代码安全沙箱
│   ├── sandbox_policy.py      # 静态分析引擎
│   ├── immune_system.py       # 免疫系统
│   ├── llm_provider.py        # 统一 LLM 接口
│   ├── layered_memory.py      # 4 层记忆系统
│   ├── task_engine.py         # 任务执行引擎
│   ├── event_bus.py           # 事件总线
│   ├── provenance.py          # 密码学证明链
│   └── ...
├── sdk/python/                # Python SDK
├── config/                    # 配置文件
├── registry/                  # App 注册表
└── docs/                      # 文档
```

---

## 与 agenticSeek 的对比

| 能力 | agenticSeek | MCR |
|------|------------|-----|
| 浏览器自动化 | ✅ Selenium | 🔜 计划中（Playwright） |
| 代码执行安全 | ❌ 无沙箱 | ✅ 三层防御 |
| 记忆系统 | ❌ 单层 | ✅ 4 层 + 语义检索 |
| 世界模型 | ❌ 无 | ✅ 预测 + 风险门控 |
| 事件溯源 | ❌ 无 | ✅ WAL + HMAC 证明链 |
| 免疫系统 | ❌ 无 | ✅ 7 种威胁 + 自动修复 |
| 多 LLM | ✅ 7 个 | ✅ 5 个 |
| 语音 | ✅ TTS/STT | 🔜 计划中 |
| 社区 | ⭐ 26K | 🌱 刚开始 |

**MCR 的护城河不是代码（代码可以抄），是认知深度。**

---

## 路线图

- [x] 认知内核接通（WorldModel + CognitiveLoop）
- [x] 代码安全沙箱（AST + 受限执行 + 审计）
- [x] 免疫系统（威胁检测 + 自动修复）
- [x] 统一 LLM 接口（Ollama + 云端）
- [ ] 全局工作空间（事件优先级广播）
- [ ] Sleep 巩固（记忆离线整理）
- [ ] 进化系统（技能交叉 + 变异 + 选择）
- [ ] 浏览器自动化
- [ ] 语音交互

---

## 生物启发架构

MCR 不是"模块堆叠"，是按生物系统组织的数字有机体。

| 生物系统 | MCR 子系统 | 功能 |
|----------|-----------|------|
| 🧠 神经系统 | EventBus + CognitiveLoop | 信号传导、认知处理 |
| 🧬 记忆系统 | LayeredMemory | 4 层巩固 |
| 🛡️ 免疫系统 | ImmuneSystem | 自修复、自诊断 |
| 💉 内分泌系统 | GlobalWorkspace（计划中） | 全局广播 |
| ⚖️ 稳态系统 | Homeostasis（计划中） | 资源自调节 |
| 🧪 进化系统 | Evolution（计划中） | 技能进化 |
| 👁️ 感觉系统 | EnvironmentMonitor | 环境感知 |

详见 [生物启发架构文档](docs/MCR_BIO_INSPIRED_ARCHITECTURE.md)。

---

## 贡献

欢迎贡献！查看 [open issues](https://github.com/Mini-0618/MCR/issues) 或提 PR。

## License

Apache-2.0

---

<p align="center">
  <strong>MCR — 不是工具，是数字生命。</strong>
</p>
