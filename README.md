# Prompt Engineering Agent（PEA）

把自然语言需求或原始 Prompt 变成经过诊断、策略选择、生成、评估和有界迭代的可执行 Prompt，并保存每次修改的证据与版本。

当前版本 **0.2.0 Beta**：201 项自动化测试、四个产品工作区、100 条中文 Benchmark 草稿和 80 条公共数据审计。默认提供商为 OpenAI；未配置凭证时可在界面选择 Mock 离线运行。

![Python](https://img.shields.io/badge/Python-3.12%2B-blue) ![LangGraph](https://img.shields.io/badge/LangGraph-1.2.24-green) ![FastAPI](https://img.shields.io/badge/FastAPI-0.165.0-teal) ![License](https://img.shields.io/badge/Code-MIT-lightgrey)

**入口**：[本地跑起来](#s10) · [Agent harness](#s13) · [产品需求](docs/PRD.md) · [评测证据](docs/HARNESS_EVALUATION.md)

PEA 的目标不是“把 Prompt 写得更长”，而是回答三个问题：原始意图有没有被保留、每个修改为什么存在、优化是否真的有效。结构检查、真实模型输出、模拟结果和人工判断在项目中分开记录，不混成一个好看的分数。

## 目录

1. [项目背景](#s1)
2. [技术栈选型](#s2)
3. [核心功能](#s3)
4. [结果与验证](#s4)
5. [实现思路](#s5)
6. [踩坑与优化](#s6)
7. [和外部方案的对照](#s7)
8. [更新](#s8)
9. [安装](#s9)
10. [快速开始](#s10)
11. [数据与 Benchmark](#s11)
12. [生成偏好与复杂任务](#s12)
13. [Agent harness](#s13)
14. [前端设计](#s14)
15. [目录结构](#s15)
16. [文档](#s16)
17. [Roadmap](#s17)
18. [许可](#s18)

<a id="s1"></a>

## 项目背景

Prompt 优化有个常见误区：加上角色、步骤、示例和一大段“请认真思考”，看起来更像专业 Prompt，但实际结果可能只是更长、更贵，甚至把用户最重要的细节挤掉。

这个项目验证一个更具体的问题：**能不能做一个可运行的 harness，让每次修改都有理由、每次执行都有记录、效果不理想时能够停止并回到最佳版本。**

当前答案是：工程链路可以完整跑通，语义质量仍需要按任务持续验证。项目不把模拟结果写成真实模型提升，也不把 Promptfoo 的结构断言当作开放任务质量排名。

<a id="s2"></a>

## 技术栈选型

每个环节选用能独立验证的最简方案，右边是被否掉或暂缓的备选。

| 环节 | 选择 | 备选 | 为什么不选备选 |
|---|---|---|---|
| Agent 编排 | LangGraph | 手写循环 / 多 Agent 自由对话 | 需要显式状态、条件路由、人工中断和最佳版本，不为“看起来智能”增加 Agent 数量 |
| 模型接入 | LiteLLM SDK + 内部 Gateway | 各业务节点直接调 SDK / 独立 Proxy | 统一异常、Token 和成本；本地产品暂不增加 Proxy 运维 |
| 数据契约 | Pydantic v2 | 无约束 dict | 节点、API、评估和存储共用可序列化契约 |
| 后端 | FastAPI | 只写 Streamlit 内部逻辑 | UI 与业务解耦，外部评测可以复用 HTTP/Python API |
| 前端 | Streamlit | 本阶段改 React 全家桶 | 先完成本地产品闭环，不为了界面重写核心栈；生产协作限制单独列出 |
| 数据库 | SQLite + SQLAlchemy | PostgreSQL | 本地单实例够用，历史、版本和导出仍可完整实现 |
| 测试 | Pytest + Promptfoo 桥接 | 只用 LLM 自评 | 程序化断言、异常路径和独立执行器比单一模型评分更可复核 |
| 部署 | Docker 多目标配置 | 默认公网 SaaS | 当前是本地产品；公网认证、授权和数据隔离不能靠容器自动获得 |

<a id="s3"></a>

## 核心功能

四个工作区共用同一套 FastAPI 应用服务，不是四套互相独立的演示逻辑。

- **优化工作台**：原始需求/原始 Prompt、详略与探索偏好、目标模型适配、诊断、策略和版本对比
- **历史与版本**：SQLite 历史、统一 diff、分数变化、策略变化、JSON/Markdown 下载
- **评测中心**：100 条 Benchmark 审核状态、80 条公共 Prompt 结构审计和已知缺陷检测
- **系统状态**：本地服务、运行边界、OpenAPI 入口和未验证事项

同时提供 `/v1/chat/completions`，标准 OpenAI 客户端可以直接获取 PEA 生成的优化 Prompt；该接口与“使用 OpenAI 作为下游模型提供商”是两条独立链路。

模型之外还有一层可追溯设计：每次修改有理由，每轮生成有评估，最终版本不一定是最新版本，而是评估得分更高的版本。

<a id="s4"></a>

## 结果与验证

| 范围 | 实际结果 | 能说明什么 |
|---|---|---|
| 自动化测试 | **201 passed，1 warning** | 单元、集成、异常、工作流、API、数据和部署配置回归 |
| 包构建 | 0.2.0 wheel 与源码包构建通过 | 项目可以作为 Python 包安装与分发 |
| 真实浏览器 | 偏好提交、探索模块、历史、评测与系统状态通过 | 前端不是静态截图，能实际调用 API |
| 公共结构审计 | 80 条样例目标/上下文保留与输出结构检查 | 结构行为可复现，不等于开放任务语义质量 |
| 已知缺陷变异 | 英文歧义、长度冲突、模糊需求和输出缺失回归 | 修复有测试，不靠单次演示 |
| 本地 OpenAI 格式联调 | 实际 LiteLLM 调本机 `/v1/chat/completions` | 请求/响应格式可验证，不访问外部模型 |
| 真实模型对照 | **未形成正式结论** | 不能宣称真实正确率提升或优于其他产品 |

**当前没有 CI 通过声明。** GitHub Actions 激活仍需维护者补充 `workflow` 权限。

<a id="s5"></a>

## 实现思路

```text
Streamlit / CLI / FastAPI
          ↓
     WorkflowRunner
          ↓
意图 → 诊断 → 策略 → 生成 → 评估
          ↑              ↓
          └──── Refiner ←┘
          ↓
模型适配 / SQLite / 评测报告 / 导出
          ↓
Mock · OpenAI-compatible · Anthropic
```

分七层，每层都能单独测试：

- **接口层**：CLI、FastAPI 和 Streamlit 复用应用服务
- **工作流层**：显式状态、条件路由、澄清中断、取消和三次生成上限
- **专业节点**：意图、诊断、策略、生成、Evaluator、Refiner、Model Adapter
- **生成层**：按任务动态组织输入材料、执行步骤、输出要求与验收标准
- **模型层**：统一 Gateway 处理异常、重试、Token、成本、延迟和 OpenAI-compatible Base URL
- **证据层**：静态/动态指标、参考评分、成对统计、公共审计和模拟边界
- **存储层**：运行、逐轮版本、最佳标记、统一 diff 和导出

两个“重试”严格分开：Gateway 重试处理网络与限流；工作流迭代处理 Prompt 不合格。这样不会把两类调用次数叠成不可控循环。

<a id="s6"></a>

## 踩坑与优化

### 生成与诊断

| 现象 | 根因 | 处理 |
|---|---|---|
| 优化邮件反而没原版详细 | 通用行动请求和礼貌语挤占补救细节 | 具体内容优先，保留事实、日期、原因和补救行动；不把字数减少当质量 |
| 简单抽取被加成研究角色与复杂拆解 | 长参考上下文里的关键词和长度参与分类 | 指令与 Context 分开分析，原始上下文仍完整保留 |
| 优化 Prompt 混入“请优化这个 Prompt” | 元指令被当成目标约束 | 清除纯元指令，同时保留“保持专业语气”等新增要求 |
| 背景段落只是重复任务目标 | 固定模板无条件输出背景 | 背景去重；嵌入式 Context 独立为输入材料 |
| 复杂 Prompt 只有标题，没有验收口径 | 输出模块缺少任务差异 | 研究、数据、总结和写作分别生成步骤与验收标准 |
| 已明确“输出一句话”仍选结构化策略 | 只要提取到输出要求就选策略 | 原始规范已清楚时保持轻量，不重复优化 |

### 性能与成本

| 改动 | 效果 |
|---|---|
| LiteLLM 本地价格表 + 延迟导入 | 避免导入时远程价格表超时，普通诊断与 Mock 不加载 SDK |
| 动态评估复用原始基线 | 三轮动态迭代调用由 6 次降为 4 次 |
| 候选策略共享原始基线 | 8 条 train、2 候选模拟调用由 32 降为 24，评分保持一致 |
| 约束去重 | 修复中间版本的 Prompt 膨胀回归，不靠复制约束提高检测率 |
| 默认最多三次生成 | 不达标也停止并返回真实评分下的最佳版本 |

### 数据与评测

| 改动 | 效果 |
|---|---|
| Dolly 15,011 条去重切分 | train 10,306 / dev 2,208 / test 2,214，哈希锁定 |
| 旧开发样例隔离 | 排除旧 80 条及近重复，不把调参样例当最终测试 |
| Promptfoo 独立执行 | 通过 Python Provider 调 PEA，外部断言与内部 Evaluator 分离 |
| 模拟人工明确标识 | 子 Agent 评审不写成真实人工，失败和负面结果也保留 |
| 最终 test 访问审计 | 哈希、dev 报告、提供商、样本与 seed 均记录 |

<a id="s7"></a>

## 和外部方案的对照

选择 Promptfoo 作为评测参照，不是把它当成 Prompt 优化产品来“击败”。

| 维度 | PEA | Promptfoo 参照 |
|---|---|---|
| 主要定位 | Prompt 诊断、生成、评估、迭代和版本 | 评测、模型比较、红队和 CI |
| 人工澄清 | 内置 interrupt/resume | 不是核心工作流 |
| 自动修订 | Refiner + 有界迭代 + 最佳版本 | 由外部优化逻辑实现 |
| 断言生态 | 结构、长度、参考指标与统计 | 更广泛的确定性、模型和自定义断言 |
| 红队 | 尚未实现 | 核心能力 |
| Provider | OpenAI-compatible、Anthropic、Mock | 更广泛的模型与应用生态 |
| 产品历史 | SQLite、版本 diff 和导出 | Eval 结果与分享工作流 |

公共样例和变异场景曾由 Promptfoo 从 80/82 提升到 82/82。这些断言针对 PEA 已定义缺陷，**不是产品排行榜，也不证明 PEA 优于 Promptfoo**。

<a id="s8"></a>

## 更新

- **2026-11-27**：发布 0.2.0 Beta；新增四工作区前端、详略/探索偏好、复杂任务验收标准、PRD 和完整产品规范；仓库公开。
- **2026-11-27**：根据人工邮件评审修复“更短但更不详细”和元指令泄漏；根据复杂 Prompt 评审去除固定三节模板。
- **2026-11-26**：完成 LangGraph、SQLite、FastAPI、评估实验、公共 Dolly 审计、策略搜索与最终测试访问控制。
- **2026-11-26**：支持 OpenAI-compatible Base URL，并通过本机 OpenAI 格式服务验证实际 LiteLLM 请求。

<a id="s9"></a>

## 安装

要求 Python 3.12+ 和 uv 0.11.19。

```bash
uv sync --extra dev
```

运行回归和构建：

```bash
uv run pytest
uv build
```

Docker 配置也已提供：

```bash
docker compose up --build
```

容器运行需要在目标 Docker 环境独立验证；配置文件存在不等于镜像已经验收。

<a id="s10"></a>

## 快速开始

终端一启动 API：

```bash
uv run uvicorn pea.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

终端二启动产品界面：

```bash
uv run streamlit run src/pea/ui/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
```

浏览器打开：

- 产品：http://127.0.0.1:8501
- OpenAPI：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

也可以只用 CLI：

```bash
uv run pea --optimize "写一份新员工入职指南，输出 Markdown。"
uv run pea --optimize "写一条生日祝福，输出一句话。" --workflow
uv run pea --validate-benchmark
```

默认 `PEA_DEFAULT_PROVIDER=openai`。未配置真实凭证时，可在界面选择 `mock` 离线运行。真实 OpenAI-compatible 调用需要配置：

```bash
OPENAI_API_BASE=https://your-endpoint/v1
OPENAI_API_KEY=your-key
OPENAI_MODEL=your-model
PEA_ENABLE_REAL_PROVIDERS=True
PEA_COST_BUDGET_USD=your-approved-budget
```

<a id="s11"></a>

## 数据与 Benchmark

项目维护两类数据，不把它们混为一个“金标”。

### 中文 Benchmark 草稿

100 条，分布为商务 20、创作 20、数据 15、总结 15、邮件 15、研究 15。每条包含需求、原始 Prompt、输出、约束、评价标准和机器检查。

当前全部为 `pending_human_review`，不能作为已审核标准答案。

### Dolly 公共数据

从 15,011 条 Dolly 记录建立可复现切分，保留原始 SHA256、固定种子、许可和本地审核状态。包内包含 80 条公共结构审计样例；完整切分文件是本地生成资产，不随 Git 仓库重复打包。

此前 test 已用于明确标识的最终模拟。后续正式模型评估应使用新的未见 holdout，避免开发与模拟访问造成选择偏差。

数据来源与限制见 [外部数据说明](benchmarks/EXTERNAL_DATASETS.md)，人工盲评规范见 [HUMAN_REVIEW_RUBRIC](benchmarks/HUMAN_REVIEW_RUBRIC.md)。

<a id="s12"></a>

## 生成偏好与复杂任务

详略是一等输入，不靠事后裁剪：

| 偏好 | 行为 |
|---|---|
| 详细 | 信息完整、论据和具体细节优先，不因形式简洁删关键内容 |
| 均衡 | 保留默认任务策略和验收标准 |
| 简洁 | 删除重复背景和无关解释，但仍保留交付物与约束 |

探索模式不是多加一个“认真思考”标题，而是要求：替代假设或路径、支持与反对证据、推翻主结论的新证据，以及何时切换方案。

简单任务不强行添加探索模块；复杂研究生成可以动态包含专业视角、任务目标、输入材料、执行步骤、工具与证据、输出要求、约束和验收标准。

可查看[复杂 Prompt 重构实例](benchmarks/results/complex_prompt_optimization_example.json)，其中只包含 Prompt，不附执行结果。

<a id="s13"></a>

## Agent harness

```text
用户输入
  → 意图分析
  → 信息不足：interrupt / resume
  → 八维诊断
  → 动态策略
  → Prompt 生成
  → 静态评估 / 可选动态执行
  → 达标或最多三次：最佳版本
  → 目标模型适配
  → SQLite 与导出
```

关键设计：

- 每个专业节点可独立测试，不是多个自治 Agent 互相聊天
- 修改理由与 Prompt 一起保存，能解释为什么添加或删除模块
- 失败或取消后不再继续新的模型调用
- 成本未知时保留 `null`，不伪报为 0
- 结构评估、参考 F1、人工偏好和真实 API 质量分开解释
- Mock、LLM 子 Agent 和模拟人工都有明确标记

产品短板与下一步语义能力见 [PRODUCT_CRITIQUE](docs/PRODUCT_CRITIQUE.md)。

<a id="s14"></a>

## 前端设计

| 设计 | 为什么这么做 |
|---|---|
| 四个工作区，而不是一个长页面 | 优化、版本、证据和系统状态是不同任务，减少相互干扰 |
| 原始与最佳 Prompt 并排 | 用户可以直接判断结构变化，不必在两个页面来回跳 |
| 详略与探索直接入表单 | 偏好进入真实 API 契约，不是仅在前端显示的摆设 |
| 诊断、策略、评估、适配分 Tab | 需要证据时能展开，不需要时不干扰主流程 |
| 版本显示统一 diff 与分数变化 | 不只保存历史，还能看每轮为什么更好或更差 |
| 评测中心显示“未验证” | 防止结构 100% 被误读为语义质量 100% |
| 默认 OpenAI、可切换 Mock、页面不接收密钥 | 默认使用真实产品接入方式，离线体验与凭证输入分离 |

真实浏览器已验证详细+探索偏好进入 API，并实际生成“备选路径与反证”模块。

<a id="s15"></a>

## 目录结构

```text
.
├── src/pea/
│   ├── agents/           # 意图、诊断、策略、生成与 Refiner
│   ├── workflow/         # LangGraph 状态、路由、中断与取消
│   ├── gateway/          # Mock、LiteLLM 与统一模型调用
│   ├── evaluation/       # 指标、公共数据、实验、统计与策略搜索
│   ├── models/           # Pydantic 核心契约
│   ├── storage/          # SQLite、版本比较与导出
│   ├── api/              # FastAPI 应用服务
│   └── ui/               # Streamlit 四工作区
├── tests/                # 201 项自动化测试
├── benchmarks/           # 审核规范、Promptfoo 与模拟证据
├── docs/                 # PRD、架构、部署与评测报告
├── pyproject.toml        # 包元数据与直接依赖
├── uv.lock               # 完整依赖锁
├── Dockerfile / compose.yaml
└── README.md
```

<a id="s16"></a>

## 文档

- [产品需求](docs/PRD.md)：用户、功能、非功能需求与验收边界
- [架构](ARCHITECTURE.md)：状态、节点、评估、存储和外部审计
- [API](API.md)：HTTP、CLI 与 Python 接口
- [部署](docs/DEPLOYMENT.md)：本地、配置与 Docker
- [产品短板](docs/PRODUCT_CRITIQUE.md)：语义、反事实、策略记忆与协作方向
- [Harness 对照评测](docs/HARNESS_EVALUATION.md)：公共数据与 Promptfoo 结果
- [真实质量协议](docs/REAL_QUALITY_EVALUATION.md)：train/dev/test、指标和统计
- [最终模拟报告](docs/SIMULATION_FINAL_REPORT.md)：模拟流程终点与限制
- [贡献指南](CONTRIBUTING.md) / [安全说明](SECURITY.md)

<a id="s17"></a>

## Roadmap

- [x] LangGraph 完整优化工作流与澄清恢复
- [x] 详略偏好、探索式反证和任务特定验收标准
- [x] SQLite 历史、版本 diff、FastAPI 和 Streamlit 产品界面
- [x] 公共数据审计、Promptfoo 桥接和策略搜索
- [x] OpenAI-compatible API 与本地格式验证
- [ ] 模型增强语义规划与可编辑 Prompt Blueprint
- [ ] 策略记忆、失败归因和跨任务经验复用
- [ ] 新 holdout 上的真实模型对照与人工校准
- [ ] 持久化任务队列、团队协作与权限模型
- [ ] GitHub Actions 权限补齐与远端 CI 激活

完整路线见 [ROADMAP.md](ROADMAP.md)。

<a id="s18"></a>

## 许可

代码使用 [MIT License](LICENSE)。

第三方数据和适配样例保留原许可。Dolly 公共样例为 CC BY-SA 3.0，来源、原始哈希与修改方式见 [外部数据说明](benchmarks/EXTERNAL_DATASETS.md) 和资源 provenance 文件。

模型、提供商服务和外部工具分别遵循其自身许可。不要把真实客户数据、个人信息、凭证或商业机密提交到 Issue、Benchmark 或公开 PR。
