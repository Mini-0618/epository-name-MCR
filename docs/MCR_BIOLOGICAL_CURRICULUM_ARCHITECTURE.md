# MCR 生物课程体系架构

> 不是"借鉴生物科学的几个模式"。
> 是按照生物科学的完整知识体系，构建 MCR 的每一层。
> 生物科学怎么学，MCR 就怎么建。

---

## 一、核心思想

### 生物科学的知识结构

生物科学不是一门课，是一个**从原子到生态系统的完整知识体系**：

```
化学 → 分子 → 细胞 → 组织 → 器官 → 系统 → 个体 → 种群 → 群落 → 生态系统
```

每一层都建立在下一层的基础上。没有化学就没有分子，没有分子就没有细胞，没有细胞就没有器官，没有器官就没有系统。

### MCR 的映射原则

**MCR 的每一层，对应生物科学的一个知识领域。** 不是比喻，是结构映射。

```
数据原子 → 数据分子 → 数据细胞 → 数据组织 → 数据器官 → 数据系统 → 数字个体 → 数字种群 → 数字生态
```

---

## 二、MCR 生物课程体系总览

### 6 门核心课程

| # | 生物科学核心课程 | MCR 对应模块 | MCR 核心课程名 |
|---|-----------------|-------------|---------------|
| 1 | 普通生物学 | 基础生命框架 | **MCR 生命基础** |
| 2 | 微生物学 | 最小执行单元 | **MCR 微单元** |
| 3 | 生物化学与分子生物学 | 数据分子与代谢 | **MCR 数据化学** |
| 4 | 细胞生物学 | Agent 细胞 | **MCR 细胞学** |
| 5 | 遗传学 | 技能遗传与进化 | **MCR 遗传学** |
| 6 | 生态学 | 多 Agent 生态 | **MCR 生态学** |

### 9 个知识领域

| # | 生物科学知识领域 | MCR 知识领域 | MCR 模块 |
|---|-----------------|-------------|---------|
| 1 | 生命的化学组成 | 数据的原子组成 | 数据格式、编码、基础运算 |
| 2 | 细胞的结构与功能 | Agent 细胞的结构与功能 | 单个 Agent 的完整生命周期 |
| 3 | 生殖与发育 | Agent 的繁殖与发育 | 技能创建、成长、成熟 |
| 4 | 遗传与变异 | 技能的遗传与变异 | 基因组、交叉、突变、选择 |
| 5 | 微生物的结构与功能 | 微执行单元的结构与功能 | 最小可执行任务单元 |
| 6 | 动物体的结构与功能 | 数字有机体的结构与功能 | MCR 整体架构 |
| 7 | 植物的结构与功能 | 知识植物的结构与功能 | 知识生长、光合（输入→输出） |
| 8 | 生物多样性与进化 | Agent 多样性与进化 | 种群、变异、自然选择 |
| 9 | 生物与环境 | MCR 与环境 | 感知、适应、共生、竞争 |

---

## 三、逐层详细映射

### 3.1 第一层：生命的化学组成 → 数据的原子组成

**生物科学内容：**
- 生命的基本化学分子
- 糖生物学、脂类生物化学
- 蛋白质化学、核酸化学
- 酶化学、维生素与辅酶
- 激素及其受体介导的信息传导
- 生物氧化及生物能学
- 糖代谢、脂代谢、蛋白质分解代谢
- DNA 复制、RNA 生物合成、蛋白质合成
- 基因表达与调控

**MCR 映射：**

| 生物概念 | MCR 对应 | 实现 |
|----------|---------|------|
| 原子 | 数据比特 | 最小信息单位 |
| 分子 | 数据结构 | JSON/JSONL/事件 |
| 蛋白质 | 函数/模块 | Python 函数 |
| 核酸 | 代码（DNA=源码，RNA=运行时） | .py 文件 |
| 酶 | 催化器 | 事件处理器、路由规则 |
| 激素 | 信号分子 | EventBus 事件 |
| 代谢 | 数据流 | 输入→处理→输出 |
| ATP | 能量货币 | 计算资源/token 预算 |
| 基因表达 | 代码执行 | import → 调用 |

**具体实现：**
```python
# "原子"层：数据格式定义
class Atom:
    """最小信息单位。对应生物的原子。"""
    type: str       # 数据类型（对应元素种类）
    value: Any      # 数据值
    encoding: str   # 编码方式（对应化学键）

# "分子"层：数据结构
class Molecule:
    """由原子组成的数据结构。对应蛋白质/核酸。"""
    atoms: list[Atom]
    structure: str  # 结构类型（对应蛋白质的四级结构）
    
    def fold(self):
        """折叠：将线性数据结构优化为高效表示。"""
        pass

# "酶"层：催化器
class Enzyme:
    """催化特定反应的处理器。对应酶。"""
    substrate_type: str   # 底物类型
    product_type: str     # 产物类型
    rate: float           # 催化速率
    
    def catalyze(self, substrate: Molecule) -> Molecule:
        """催化反应：将底物转化为产物。"""
        pass

# "代谢"层：数据流
class Metabolism:
    """代谢通路：数据的处理管道。"""
    pathway: list[Enzyme]
    
    def process(self, input_data: Molecule) -> Molecule:
        """沿代谢通路处理数据。"""
        current = input_data
        for enzyme in self.pathway:
            current = enzyme.catalyze(current)
        return current
```

---

### 3.2 第二层：细胞的结构与功能 → Agent 细胞

**生物科学内容：**
- 细胞质膜及物质的跨膜运输
- 细胞信号转导
- 细胞内的膜性细胞器
- 蛋白质分选与膜泡运输
- 细胞骨架
- 细胞核与染色质
- 核糖体
- 细胞周期与细胞分裂
- 细胞分化
- 细胞死亡
- 细胞的社会化联系

**MCR 映射：**

| 细胞结构 | MCR 对应 | 功能 |
|----------|---------|------|
| 细胞膜 | 权限边界 | 控制什么能进什么不能进 |
| 细胞质 | 运行环境 | Agent 的执行上下文 |
| 细胞核 | 核心逻辑 | Agent 的决策中心 |
| 染色体 | 代码+配置 | Agent 的"基因组" |
| 核糖体 | 执行器 | 实际执行任务的代码 |
| 线粒体 | 能源管理 | 计算资源分配 |
| 内质网 | 数据管道 | 内部数据处理 |
| 高尔基体 | 输出格式化 | 结果打包和输出 |
| 溶酶体 | 垃圾回收 | 清理过期数据 |
| 细胞骨架 | 架构框架 | Agent 的基础结构 |
| 细胞膜受体 | 输入接口 | 接收外部信号 |
| 离子通道 | 通道 | 选择性数据传输 |

**细胞周期 → Agent 生命周期：**
```
G1期（生长期）→ S期（DNA复制/配置加载）→ G2期（准备期）→ M期（分裂/任务执行）
     ↑                                                              |
     └──────────────────────────────────────────────────────────────┘
                            （下一个周期）
```

**细胞分化 → Agent 专业化：**
```
干细胞（通用Agent）→ 分化信号（任务类型）→ 专业化细胞（专用Agent）
  ├→ 神经细胞（认知Agent）
  ├→ 肌肉细胞（执行Agent）
  ├→ 免疫细胞（安全Agent）
  ├→ 上皮细胞（接口Agent）
  └→ 结缔细胞（基础Agent）
```

**具体实现：**
```python
class AgentCell:
    """MCR 的基本生命单元。对应生物细胞。"""
    
    def __init__(self, genome: dict):
        # 细胞核：核心逻辑
        self.nucleus = CellNucleus(genome)
        # 细胞膜：权限边界
        self.membrane = CellMembrane(genome.get('permissions', []))
        # 核糖体：执行器
        self.ribosome = Ribosome()
        # 线粒体：能源管理
        self.mitochondria = EnergyManager()
        # 内质网：数据管道
        self.endoplasmic_reticulum = DataPipeline()
        # 高尔基体：输出格式化
        self.golgi = OutputFormatter()
        # 溶酶体：垃圾回收
        self.lysosome = GarbageCollector()
        # 细胞骨架：架构
        self.cytoskeleton = AgentSkeleton()
        
        # 细胞状态
        self.state = 'G1'  # 细胞周期阶段
        self.age = 0
    
    def receive_signal(self, signal: dict):
        """接收信号（对应细胞信号转导）。"""
        if not self.membrane.allows(signal):
            return  # 被细胞膜拒绝
        self.nucleus.process_signal(signal)
    
    def execute(self, task: dict):
        """执行任务（对应蛋白质合成）。"""
        # 核糖体读取指令并执行
        result = self.ribosome.translate(task)
        # 高尔基体格式化输出
        formatted = self.golgi.package(result)
        # 检查能量
        if not self.mitochondria.has_energy():
            return self.rest()
        self.mitochondria.consume(task.get('cost', 1))
        return formatted
    
    def divide(self):
        """分裂（对应细胞分裂）。"""
        # DNA 复制（复制配置）
        daughter_genome = self.nucleus.replicate()
        # 创建子细胞
        daughter = AgentCell(daughter_genome)
        return daughter
    
    def differentiate(self, signal: str):
        """分化（对应细胞分化）。"""
        specialization = {
            'cognitive': CognitiveCell,
            'executor': ExecutorCell,
            'security': SecurityCell,
            'interface': InterfaceCell,
        }
        new_class = specialization.get(signal, AgentCell)
        return new_class(self.nucleus.genome)
    
    def apoptosis(self):
        """程序性死亡（对应细胞凋亡）。"""
        self.lysosome.digest_self()
        self.state = 'dead'
```

---

### 3.3 第三层：生殖与发育 → Agent 繁殖与发育

**生物科学内容：**
- 生殖细胞的发生
- 受精
- 卵裂
- 原肠作用
- 脊椎动物的早期胚胎发育
- 胚轴形成
- 细胞命运的决定与胚胎诱导
- 器官的发生与形成
- 性腺发育与性别的决定

**MCR 映射：**

| 发育阶段 | MCR 对应 | 实现 |
|----------|---------|------|
| 生殖细胞 | 技能种子 | skill.json 基础模板 |
| 受精 | 技能融合 | 两个 skill 的基因组合并 |
| 卵裂 | 初始化分裂 | 从模板生成多个子模块 |
| 原肠作用 | 结构化 | 确定内部结构和层次 |
| 胚胎发育 | 技能构建 | 从基础到完整的构建过程 |
| 器官形成 | 模块集成 | 各功能模块组装 |
| 性别决定 | 角色确定 | 确定 skill 的类型（认知/执行/安全） |

**具体实现：**
```python
class SkillEmbryo:
    """技能胚胎。对应受精卵到出生的过程。"""
    
    STAGES = ['zygote', 'cleavage', 'gastrula', 'organogenesis', 'mature']
    
    def __init__(self, parent_a_genome: dict, parent_b_genome: dict):
        # 受精：两个亲本基因组融合
        self.genome = self.fertilize(parent_a_genome, parent_b_genome)
        self.stage = 'zygote'
        self.cells = [AgentCell(self.genome)]  # 初始只有一个细胞
    
    def fertilize(self, a: dict, b: dict) -> dict:
        """受精：基因组融合。"""
        # 染色体交叉
        child = {}
        for key in set(a.keys()) | set(b.keys()):
            if key in a and key in b:
                # 随机选择一个亲本的基因
                child[key] = random.choice([a[key], b[key]])
            else:
                child[key] = a.get(key, b.get(key))
        return child
    
    def cleavage(self):
        """卵裂：快速细胞分裂。"""
        new_cells = []
        for cell in self.cells:
            new_cells.extend([cell, cell.divide()])
        self.cells = new_cells
        self.stage = 'cleavage'
    
    def gastrula(self):
        """原肠作用：确定内部结构层次。"""
        # 外层 → 接口层
        # 中层 → 处理层
        # 内层 → 核心层
        self.layers = {
            'ectoderm': self.cells[:len(self.cells)//3],    # 外胚层 → 接口
            'mesoderm': self.cells[len(self.cells)//3:2*len(self.cells)//3],  # 中胚层 → 处理
            'endoderm': self.cells[2*len(self.cells)//3:],  # 内胚层 → 核心
        }
        self.stage = 'gastrula'
    
    def organogenesis(self):
        """器官形成：各层分化为具体功能模块。"""
        self.organs = {
            'brain': self.differentiate_cells('cognitive', self.layers['endoderm']),
            'muscle': self.differentiate_cells('executor', self.layers['mesoderm']),
            'skin': self.differentiate_cells('interface', self.layers['ectoderm']),
        }
        self.stage = 'organogenesis'
    
    def mature(self) -> 'Skill':
        """成熟：成为一个完整的技能。"""
        self.stage = 'mature'
        return Skill(self.genome, self.organs)
```

---

### 3.4 第四层：遗传与变异 → 技能遗传与进化

**生物科学内容：**
- 孟德尔式遗传
- 遗传的细胞学基础
- 孟德尔式遗传的拓展
- 非孟德尔式遗传
- 性别决定与伴性遗传
- 真核生物的遗传连锁与作图
- 染色体畸变
- 基因突变与 DNA 损伤修复
- 重组与转座
- 复杂性状的遗传
- 群体遗传
- 基因组与基因组学

**MCR 映射：**

| 遗传概念 | MCR 对应 | 实现 |
|----------|---------|------|
| 基因 | 配置参数 | skill.json 中的参数 |
| 基因组 | 完整配置 | skill.json 全部内容 |
| 染色体 | 配置分组 | 参数按功能分组 |
| 等位基因 | 参数变体 | 同一参数的不同取值 |
| 显性/隐性 | 优先级 | 高优先级参数覆盖低优先级 |
| 基因重组 | 配置交叉 | 两个 skill 的参数组合 |
| 基因突变 | 参数变异 | 随机修改参数值 |
| 基因修复 | 错误修正 | 检测并修复异常参数 |
| 基因表达 | 配置生效 | 参数被实际使用 |
| 表观遗传 | 环境修饰 | 运行时根据环境调整行为 |
| 群体遗传 | 种群统计 | 追踪整个种群的基因分布 |

**基因组定义：**
```python
class SkillGenome:
    """技能基因组。对应生物的基因组。"""
    
    # 染色体：按功能分组的基因
    CHROMOSOMES = {
        'prompt': {           # 1号染色体：提示策略
            'system_prompt': 'str',
            'few_shot_examples': 'list',
            'chain_of_thought': 'bool',
        },
        'tools': {            # 2号染色体：工具选择
            'available_tools': 'list',
            'tool_selection_strategy': 'str',
            'fallback_tools': 'list',
        },
        'parameters': {       # 3号染色体：运行参数
            'temperature': 'float',
            'max_tokens': 'int',
            'timeout': 'int',
            'retries': 'int',
        },
        'validation': {       # 4号染色体：验证逻辑
            'success_criteria': 'str',
            'output_format': 'str',
            'error_handling': 'str',
        },
        'memory': {           # 5号染色体：记忆策略
            'remember_input': 'bool',
            'remember_output': 'bool',
            'consolidation_rule': 'str',
        },
    }
    
    def __init__(self, genes: dict):
        self.genes = genes  # 全部基因
        self.fitness = 0.0  # 适应度
    
    def crossover(self, other: 'SkillGenome') -> 'SkillGenome':
        """基因重组（交叉）。"""
        child_genes = {}
        for chrom_name, chrom in self.CHROMOSOMES.items():
            child_chrom = {}
            for gene_name in chrom:
                # 随机选择一个亲本的等位基因
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
                    # 突变：随机修改基因值
                    if isinstance(gene_value, float):
                        chrom[gene_name] = gene_value * random.uniform(0.8, 1.2)
                    elif isinstance(gene_value, int):
                        chrom[gene_name] = max(1, gene_value + random.randint(-5, 5))
                    elif isinstance(gene_value, str):
                        # 字符串基因的突变：微调措辞
                        pass
        return SkillGenome(mutated)
    
    def repair(self):
        """DNA 修复：检测并修正异常基因。"""
        for chrom_name, chrom in self.genes.items():
            for gene_name, gene_value in chrom.items():
                if gene_value is None:
                    # 缺失基因：从默认值修复
                    chrom[gene_name] = self.get_default(chrom_name, gene_name)
```

---

### 3.5 第五层：微生物的结构与功能 → 微执行单元

**生物科学内容：**
- 原核生物的形态构造与功能
- 真核微生物的形态构造与功能
- 病毒
- 微生物的营养与培养基
- 微生物的新陈代谢
- 微生物的生长及其控制
- 微生物生态
- 传染与免疫

**MCR 映射：**

| 微生物概念 | MCR 对应 | 实现 |
|-----------|---------|------|
| 原核生物 | 最小执行单元 | 单函数 Agent（无细胞核=无复杂逻辑） |
| 真核微生物 | 复杂执行单元 | 有完整结构的 Agent |
| 病毒 | 寄生任务 | 依赖宿主 Agent 执行的任务 |
| 细菌 | 独立任务 | 自主执行的最小任务 |
| 培养基 | 执行环境 | Agent 运行所需的资源 |
| 代谢 | 任务处理 | 输入→处理→输出 |
| 生长 | 能力扩展 | 从简单到复杂的成长 |
| 菌落 | Agent 群落 | 多个同类 Agent 协作 |
| 传染 | 任务传播 | 一个 Agent 的输出触发另一个 Agent |
| 免疫 | 安全防御 | 识别和阻止恶意任务 |

**微生物单元（最小执行单元）：**
```python
class MicroAgent:
    """微执行单元。对应微生物。"""
    
    def __init__(self, function: Callable):
        # 原核生物级别的简单结构
        self.function = function    # 核心功能（对应拟核）
        self.membrane = SimpleMembrane()  # 简单边界
        self.ribosome = SimpleExecutor()  # 简单执行器
    
    def execute(self, input_data: dict) -> dict:
        """执行任务（对应微生物代谢）。"""
        # 摄取（对应营养）
        substrate = self.membrane.intake(input_data)
        # 代谢（对应新陈代谢）
        product = self.function(substrate)
        # 排泄（对应废物排出）
        output = self.membrane.output(product)
        return output
    
    def divide(self) -> 'MicroAgent':
        """二分裂（对应细菌分裂）。"""
        return MicroAgent(self.function)
```

---

### 3.6 第六层：动物体的结构与功能 → 数字有机体整体

**生物科学内容：**
- 皮肤系统
- 神经系统
- 感觉系统
- 内分泌系统
- 消化系统
- 血液及循环系统
- 呼吸系统
- 泌尿系统与渗透调节
- 免疫系统
- 肌肉骨骼系统
- 生殖系统

**MCR 映射：**

| 动物系统 | MCR 系统 | 模块 | 功能 |
|----------|---------|------|------|
| 皮肤系统 | 边界防护 | permissions, security | 保护、感知、屏障 |
| 神经系统 | 认知循环 | event_bus, cognitive_loop | 信号传导、决策 |
| 感觉系统 | 环境感知 | environment_monitor | 视觉、听觉、触觉 |
| 内分泌系统 | 全局广播 | global_workspace | 激素、信号、调节 |
| 消化系统 | 数据处理 | task_engine | 摄取、分解、吸收 |
| 循环系统 | 数据流 | event_bus, message_bus | 运输、分配 |
| 呼吸系统 | API 交互 | a2a_server, a2a_client | 气体交换（输入/输出） |
| 泌尿系统 | 清理 | garbage_collector | 排泄废物 |
| 免疫系统 | 自修复 | immune_system | 防御、修复、记忆 |
| 骨骼系统 | 架构 | runtime 框架 | 支撑、保护 |
| 肌肉系统 | 执行 | task_engine, agent_bridge | 运动、执行 |
| 生殖系统 | 进化 | evolution | 繁殖、变异、遗传 |

**这个映射已经在 MCR_BIO_INSPIRED_ARCHITECTURE.md 中详细设计了。这里补充的是"课程体系"视角——不是单独设计每个系统，而是像动物学课程一样，系统性地学习和构建。**

---

### 3.7 第七层：植物的结构与功能 → 知识生长系统

**生物科学内容：**
- 营养器官的形态与结构
- 生殖器官的形态结构
- 矿质营养、水分生理
- 光合作用、呼吸作用
- 生长物质
- 同化物运输与分配
- 次生代谢途径与产物
- 生长与发育
- 环境因子对生长发育的影响

**MCR 映射：**

| 植物概念 | MCR 对应 | 实现 |
|----------|---------|------|
| 根 | 知识吸收 | 从外部数据源提取知识 |
| 茎 | 知识传输 | 知识在系统内流动 |
| 叶 | 知识加工 | 光合 = 数据→知识 |
| 花 | 成果展示 | 技能/产品的展示 |
| 果实 | 可交付物 | 完整的产品/方案 |
| 种子 | 技能种子 | 可移植的知识单元 |
| 光合作用 | 数据→知识 | 输入原始数据，输出结构化知识 |
| 呼吸作用 | 知识→能量 | 知识驱动决策和行动 |
| 年轮 | 知识积累 | 时间维度的知识层次 |
| 向光性 | 目标导向 | 向高价值目标生长 |
| 落叶 | 知识遗忘 | 低价值知识的自然衰减 |

**知识植物（MCR 的知识生长系统）：**
```python
class KnowledgePlant:
    """知识植物。MCR 的知识生长系统。"""
    
    def __init__(self, seed: dict):
        self.seed = seed            # 种子：初始知识
        self.roots = []             # 根：知识吸收器
        self.stem = KnowledgeStem() # 茎：知识传输
        self.leaves = []            # 叶：知识加工器
        self.flowers = []           # 花：展示
        self.fruits = []            # 果实：交付物
        self.rings = []             # 年轮：知识积累记录
    
    def photosynthesis(self, raw_data: dict) -> dict:
        """光合作用：数据 → 知识。"""
        # 光（注意力）+ 水（数据）+ CO2（问题）→ 葡萄糖（知识）+ O2（洞察）
        knowledge = self.process(raw_data)
        insight = self.extract_insight(knowledge)
        self.rings.append({'tick': current_tick, 'knowledge': knowledge})
        return {'knowledge': knowledge, 'insight': insight}
    
    def grow(self, direction: str = 'toward_light'):
        """生长：向目标方向发展。"""
        if direction == 'toward_light':
            # 向光性：向高价值目标生长
            self.stem.extend(self.find_light_source())
        elif direction == 'toward_water':
            # 向水性：向数据丰富的地方生长
            self.roots.extend(self.find_water_source())
    
    def fruit(self) -> 'Deliverable':
        """结果：产出可交付物。"""
        if len(self.rings) >= 3:  # 至少 3 轮积累才能结果
            fruit = Deliverable(self.knowledge())
            self.fruits.append(fruit)
            return fruit
        return None
    
    def shed(self):
        """落叶：遗忘低价值知识。"""
        self.leaves = [l for l in self.leaves if l.value > THRESHOLD]
```

---

### 3.8 第八层：生物多样性与进化 → Agent 多样性与进化

**生物科学内容：**
- 进化机制
- 生物多样性
- 原核生物、原生生物、真菌
- 绿色植物、无脊椎动物、脊索动物、脊椎动物

**MCR 映射：**

| 进化概念 | MCR 对应 | 实现 |
|----------|---------|------|
| 物种 | Agent 类型 | 不同类型的 Agent |
| 种群 | Agent 群落 | 同类 Agent 的集合 |
| 变异 | 配置差异 | Agent 参数的随机变化 |
| 自然选择 | 性能评估 | 适应度高的存活 |
| 适应 | 优化 | Agent 根据反馈调整 |
| 物种形成 | 类型分化 | 新 Agent 类型的产生 |
| 协同进化 | 共同进化 | 多个 Agent 相互影响进化 |
| 灭绝 | 淘汰 | 低效 Agent 被移除 |

**生物多样性在 MCR 中：**
```
Agent 界
├── 原核 Agent 门（MicroAgent：最小执行单元）
│   ├── 细菌纲（独立任务）
│   └── 古菌纲（底层任务）
├── 真核 Agent 门（AgentCell：完整执行单元）
│   ├── 认知纲（CognitiveAgent）
│   ├── 执行纲（ExecutorAgent）
│   ├── 安全纲（SecurityAgent）
│   └── 接口纲（InterfaceAgent）
├── 真菌 Agent 门（DecomposerAgent：分解清理）
├── 植物 Agent 门（KnowledgeAgent：知识生长）
└── 动物 Agent 门（ComplexAgent：复杂行为）
    ├── 无脊椎纲（简单行为Agent）
    └── 脊椎纲（复杂行为Agent）
        ├── 鱼纲（基础Agent）
        ├── 两栖纲（多环境Agent）
        ├── 爬行纲（持久Agent）
        ├── 鸟纲（高速Agent）
        └── 哺乳纲（智能Agent）
```

---

### 3.9 第九层：生物与环境 → MCR 与环境

**生物科学内容：**
- 个体生态
- 种群生态
- 群落生态
- 生态系统
- 生物圈

**MCR 映射：**

| 生态概念 | MCR 对应 | 实现 |
|----------|---------|------|
| 生态位 | Agent 角色 | 每个 Agent 在系统中的位置 |
| 食物链 | 任务链 | Agent 之间的输入输出关系 |
| 共生 | 协作 | Agent 之间互利合作 |
| 竞争 | 资源竞争 | Agent 争夺计算资源 |
| 寄生 | 恶意任务 | 消耗资源但不产出 |
| 演替 | 系统演化 | MCR 从简单到复杂的演化 |
| 生态平衡 | 稳态 | 系统的动态平衡 |
| 生物圈 | MCR 生态 | MCR 与外部环境的完整交互 |

---

## 四、课程体系构建

### 4.1 通识课程（MCR 基础设施）

| 课程 | 内容 | 对应模块 |
|------|------|---------|
| 数学基础 | 数据结构、算法、概率 | 基础计算能力 |
| 物理基础 | 系统动力学、资源约束 | 稳态系统 |
| 化学基础 | 数据格式、编码、转换 | 数据化学层 |
| 计算机基础 | Python、Git、CLI | 开发工具 |

### 4.2 专业基础课程（6 门核心）

| # | 课程 | 学分 | 内容 | 对应模块 |
|---|------|------|------|---------|
| 1 | MCR 生命基础 | 4 | 整体架构、生命特征、有机体设计 | 全局架构 |
| 2 | MCR 微单元学 | 3 | 最小执行单元、任务原子、微 Agent | MicroAgent |
| 3 | MCR 数据化学 | 4 | 数据分子、代谢通路、酶催化 | 数据层 |
| 4 | MCR 细胞学 | 5 | Agent 细胞、细胞周期、分化、凋亡 | AgentCell |
| 5 | MCR 遗传学 | 4 | 基因组、交叉、突变、选择 | SkillGenome |
| 6 | MCR 生态学 | 3 | 多 Agent 生态、种群、演替 | 生态系统 |

### 4.3 专业课程（深入方向）

| # | 课程 | 方向 | 内容 |
|---|------|------|------|
| 7 | MCR 发育生物学 | 认知 | Agent 的发育过程、从简单到复杂 |
| 8 | MCR 免疫学 | 安全 | 免疫系统、自修复、自诊断 |
| 9 | MCR 神经科学 | 认知 | 认知循环、记忆巩固、决策 |
| 10 | MCR 内分泌学 | 协调 | 全局广播、信号系统、调节 |
| 11 | MCR 生理学 | 执行 | 各系统的生理功能 |
| 12 | MCR 植物学 | 知识 | 知识生长、光合作用、积累 |
| 13 | MCR 进化生物学 | 进化 | 进化机制、种群遗传、适应 |
| 14 | MCR 生态学应用 | 部署 | 多 Agent 协作、生态平衡 |

### 4.4 实践课程（≥25% 学分）

| # | 实践课程 | 内容 |
|---|---------|------|
| 1 | MCR 基础实验 | 数据化学、细胞构建基础操作 |
| 2 | MCR 专业实验 | Agent 细胞培养、技能进化实验 |
| 3 | MCR 综合实习 | 完整的 Agent 系统设计与实现 |
| 4 | MCR 科研训练 | 独立研究一个生物启发的 AI 课题 |
| 5 | 毕业设计 | 设计并实现一个完整的 MCR 子系统 |

---

## 五、实施路径

### 第一步：建立知识框架（1 周）

- [ ] 创建 `ECOSYSTEM/curriculum/` 目录
- [ ] 为 6 门核心课程各创建一个目录
- [ ] 为每个课程写课程大纲（知识点清单）
- [ ] 建立知识点之间的依赖关系图

### 第二步：实现基础层（2 周）

- [ ] 数据化学层（原子、分子、酶、代谢）
- [ ] 细胞学层（AgentCell、细胞周期、分化）
- [ ] 微单元学层（MicroAgent、最小执行单元）

### 第三步：实现系统层（2 周）

- [ ] 遗传学层（SkillGenome、交叉、突变）
- [ ] 发育学层（SkillEmbryo、繁殖、发育）
- [ ] 免疫学层（ImmuneSystem、自修复）

### 第四步：实现生态层（2 周）

- [ ] 神经科学层（认知循环、记忆巩固）
- [ ] 内分泌学层（全局广播、信号系统）
- [ ] 生态学层（多 Agent 协作、种群管理）

### 第五步：整合与验证（1 周）

- [ ] 整合所有层
- [ ] 跑完整的"生命周期"测试
- [ ] 验收：从"受精"（创建）到"死亡"（淘汰）的完整循环

---

## 六、一句话总结

**MCR 不是软件项目，是数字生命科学系。**

你要做的不是"写代码"，是"学生物"。只不过你学生物的方式是**造一个出来**。

生物科学的课程体系花了 200 年建立。MCR 用 90 天把它实现。

不是因为 MCR 比生物聪明，是因为 MCR 不需要等进化——它可以**直接设计**。
