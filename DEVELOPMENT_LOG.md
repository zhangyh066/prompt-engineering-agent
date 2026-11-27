# 开发日志

## OpenAI 默认接入与兼容接口 — 2026-11-27

- OpenAI设为产品默认提供商，Mock改为显式离线/测试选择。
- PEA对外提供 `/v1/chat/completions`，标准OpenAI客户端可获取优化Prompt。
- 完整201项测试通过，文档与产品界面同步。

## 0.2.0 产品前端与发布验收 — 2026-11-27

- 完成四工作区产品前端与真实浏览器端到端验收。
- 完成PRD、路线图、贡献、安全、MIT许可、CHANGELOG和GitHub CI。
- 版本统一为0.2.0 Beta，198项测试与构建通过。
- 私有仓库已创建：https://github.com/zhangyh066/prompt-engineering-agent 。Git HTTPS不可用时通过GitHub官方Git Data API上传源码、测试和文档。
- 当前token缺少workflow scope，远端Actions文件与CI激活仍是明确待办，未声称CI通过。

## 产品短板分析与生成偏好增强 — 2026-11-27

- 完成非防御性产品短板分析，聚焦语义、反事实、经验和协作能力。
- 实现详略偏好、探索式替代方案和API契约。
- 197项测试通过，构建成功；下一阶段前端产品化与GitHub发布准备。

## 动态生成器与复杂 Prompt 重构 — 2026-11-27

- 按用户对三节模板信息增量不足的反馈，重构生成器模块。
- 新增上下文去重、任务特定步骤、验收标准、输出前缀去重和简单任务策略克制。
- 复杂研究生成8个动态模块，不附执行结果，交由用户评审Prompt本身。
- 最终194项测试通过，构建成功。

## 人工邮件评审驱动修复 — 2026-11-27

- 用户确认初版优化结果信息不如原始版详细，据此修复邮件具体内容优先和元指令泄漏。
- 保留额外语气要求，32项相关测试通过。
- 新子Agent生成v2，仍由用户判断是否优于原版；不把字数变化当质量。
- 最终192项测试通过，构建成功。

## 最终端到端模拟联调 — 2026-11-27

- 按用户要求，将 API、人工评审和外部服务全部以明确标识的子Agent模拟替代，执行到流程终点。
- Dev 通用对照后锁定 PEA 模拟组，校验 test 哈希并记录最终访问。
- 完成最终参考指标、配对统计和两名独立模拟盲评，保留指标方向不一致的结果。
- 未证明真实正确率提升或产品优越性；test 模拟后不再调参，正式评估需新 holdout。
- 完整报告 `docs/SIMULATION_FINAL_REPORT.md`；191项测试通过，构建成功。

## LLM 子 Agent 语义联调与上下文修复 — 2026-11-26

- 使用独立子 Agent 生成原始/优化组 dev8 回答，参考答案只在主流程评分时读取。
- 首次模拟发现优化组退化，保留完整负面报告。
- 修复参考上下文对任务分类、约束提取和复杂度的干扰，原始上下文仍完整保留。
- 新子 Agent 复测优化均分由 0.2478 回升至 0.3151，但仍未证明与原始组等效或优越。
- 最终 191 项测试通过，构建成功；真实 API 质量、成本和延迟仍未验证。

## FinalEvaluationRunner — 2026-11-26

- 实现 test 哈希、dev 完成状态、同提供商/模型和显式确认门禁。
- 实现追加式最终访问日志，真实终评不能复用 Mock dev 解锁。
- 临时夹具验证通过，真实锁定 test 未读取。
- 最终 190 项测试通过，构建成功。

## 跨候选基线缓存 — 2026-11-26

- QualityRunner 新增原始执行缓存与缓存命中统计。
- 候选搜索共享基线，缓存不计入新增调用、Token、成本或耗时。
- train 双候选模拟调用由 32 降为 24，评分和输出保持一致。
- 最终 186 项测试通过，构建成功。

## train/dev 策略搜索器 — 2026-11-26

- 实现 StrategyPolicy、PolicyCandidate 和 PolicySearchRunner。
- 候选可关闭 Few-shot、角色、拆解、结构化输出、Self-critique 和 ReAct；默认行为不变。
- 搜索限制同一 train/dev split，禁止 test，完整性与已知成本是入选前提。
- train 8 条双候选 Mock 搜索完成，32 次本地调用；不构成质量证据。
- 最终 185 项测试通过，构建成功。

## 质量执行器第二轮增强 — 2026-11-26

- 子 Agent 补充分层 round-robin 抽样、固定 seed 和报告内配对统计，12 项测试通过。
- 主 Agent 新增安全质量 CLI 和 3 项测试，真实模式保留全局开关、显式授权和预算。
- 主流程复测 18 项通过，CLI dev 自检完成。
- 最终 181 项测试通过，构建成功；真实模型仍待凭证和预算。

## 独立质量评测执行器 — 2026-11-26

### 完成

- 用户授权子 Agent 实现 `quality_runner.py`，主 Agent 复核并复测。
- 原始/PEA 两组共用 Gateway、模型和温度，输出逐案例与分类参考指标、Token、成本和错误。
- 实现 test 防泄漏、真实模型显式授权/预算/条数限制、预算停止和未知错误成本。
- 实现成对 bootstrap 置信区间与 win/tie/loss。
- 准备 8 条 dev 分层联调样本和人工盲评规范。
- 8 条 dev Mock 自检完成，16 次本地调用，A/B 八平，不构成质量证据。
- 最终 174 项测试通过，构建成功。

### 下一步

配置 OpenAI-compatible 凭证和 `PEA_COST_BUDGET_USD` 后，先运行 8 条 dev 真实联调，再扩大 train 策略搜索。test 仍锁定。

## 真实质量优化数据准备 — 2026-11-26

### 完成

- 对 Dolly 15,011 条记录进行标准化去重和固定种子分层切分。
- 旧 80 条开发样例及 5 条重叠记录全部排除，另移除 198 条重复。
- 生成 train 10,306、dev 2,208、test 2,214，锁定文件哈希与 test 使用边界。
- 实现可复现切分、实际重叠检查、Exact Match 和 Token F1。
- 编写真实模型对照、统计分析、成本目标和策略搜索协议。
- 最终 163 项测试通过，构建成功。

### 边界

本轮是质量优化的必要基础设施，不是质量提升结果。真实策略搜索必须等待 OpenAI-compatible 服务配置，并且只能使用 train/dev；test 不得用于调参。

## Harness 外部对照评测与优化 — 2026-11-26

### 完成

- 调研 Promptfoo、Dolly 15k 和 No Robots 的官方文档、来源与许可。
- 引入 80 条 Dolly 分层公共样例，保存原始哈希、固定抽样规则和本地未审核状态。
- 实现公开 Prompt 结构审计、英文缺陷变异测试和 Promptfoo Python Provider 桥接。
- Promptfoo 修复前独立复现 2 个英文缺陷，修复后 82/82 通过。
- 修复英文歧义、长度冲突、模糊需求澄清和动态英文长度解析。
- 增加歧义处理生成，并去重已有约束，消除中间版本的 Prompt 膨胀回归。
- 最终 156 项测试通过，构建成功；未执行外部模型调用。

### 证据

`docs/HARNESS_EVALUATION.md`、`benchmarks/EXTERNAL_DATASETS.md`、`benchmarks/results/` 和 `benchmarks/promptfoo/`。

### 限制

本轮未比较真实模型开放任务质量；Promptfoo 断言包含 PEA 特定缺陷，不是产品排名。语义评分、红队、多语言模板和持久化 Checkpointer 仍需后续改进。

## 模拟验收与 OpenAI-compatible 补充 — 2026-11-26

### 状态

项目负责人决定先模拟通过流程验收，正式人工审核、真实模型实验与 Docker 证据后补。已在 `docs/SIMULATED_ACCEPTANCE.md` 明确记录，不伪造正式状态。

### 完成

- 新增 `OPENAI_API_BASE`，通过 LiteLLM `api_base` 支持 OpenAI-compatible API。
- 校验 HTTP(S) Base URL，拒绝 URL 凭证、查询和片段。
- 使用本机 OpenAI 格式 HTTP 服务和实际 LiteLLM SDK 验证完整请求/响应。
- 运行 100 条三组 Mock 模拟：100/100 完成，404 次调用，费用 0。
- 保持人工审核与质量声明门禁为 false；三组 Mock 编码检查均分相同，不声称优化有效。
- 更新 README、API、部署、验收和测试文档。

### 测试

聚焦测试 16 passed，1 条 LiteLLM 弃用警告。最终完整回归 **148 passed，1 warning，10.48s**；`uv build` 通过。

## Sprint 6 — 2026-11-26

### 状态

全部计划内工程阶段已完成。最终验收仍有三个外部条件：Benchmark 人工审核、真实模型凭证/预算、可用 Docker 环境。

### 完成任务

- 动态评估复用原始 Prompt 基线，三轮迭代调用从 6 次降为 4 次。
- 增加可信 Host、可配置容器 Host、64 KiB 请求限制和安全响应头。
- 新增非 root 多目标 Dockerfile、Compose、`.dockerignore`、健康检查与持久化卷。
- 编写部署指南与 16 项最终验收清单。
- 新增成本、API 安全和部署配置测试。
- 完成 142 项累计测试和包构建。

### 主要文件

- 更新 `evaluation/evaluator.py`、`workflow/runner.py` 和 `api/app.py`。
- 新增 `Dockerfile`、`compose.yaml`、`.dockerignore`。
- 新增 `docs/DEPLOYMENT.md`、`docs/FINAL_ACCEPTANCE.md`。
- 新增成本与安全测试、`tests/test_deployment.py`。

### 测试结果

- 成本与评估相关测试：30 passed。
- 最终完整回归：**142 passed，0 failed，3.44s**。
- Compose YAML 解析和 Docker 静态配置检查通过。
- `uv build` 通过。
- Docker 镜像构建/运行未验证，真实模型调用为 0，费用为 0。

### 外部验收待办

1. 人工审核 100 条 Benchmark 并填写审计元数据。
2. 明确真实模型凭证、预算与范围，完成联调和 A/B/C 实验，人工复核质量。
3. 在 Docker 环境构建并运行 Compose，验证健康、UI、持久化与重启。

在上述事项完成前，不宣称真实优化效果或生产部署验收通过。

## Sprint 5 — 2026-11-26

### 状态

已完成可实际使用的本地产品：SQLite、历史版本、FastAPI、Streamlit 和导出。真实模型与 Benchmark 人工审核仍未完成。

### 完成任务

- 建立 runs 与 prompt_versions 表、SQLAlchemy ORM 和 Result Manager。
- 保存原始输入、每次版本、评估、策略、最佳标记、Token、成本和错误。
- 实现历史分页、状态筛选、版本统一 diff 和策略/分数比较。
- 实现 JSON 与 Markdown 导出。
- 实现 FastAPI 优化、澄清、取消、历史和导出端点。
- 每次运行使用独立 Runner，API 默认禁止真实付费提供商。
- 实现 Streamlit 优化、诊断、评估、版本、历史和下载页面。
- 完成 TestClient、真实 Uvicorn 和浏览器端到端验收。

### 主要文件

- `src/pea/models/history.py`。
- `src/pea/storage/orm.py`、`manager.py`、`exporter.py`。
- `src/pea/api/schemas.py`、`services.py`、`app.py`。
- `src/pea/ui/app.py`。
- 新增 `tests/test_storage.py`、`test_api.py`。

### 测试结果

- 首轮 135 passed、1 failed；修复重复保存时删除/插入顺序导致的唯一约束冲突。
- 最终 **136 passed，0 failed，3.08s**。
- 真实 API 优化与历史请求通过。
- 真实浏览器提交、结果展示、历史与下载控件通过。
- `uv build` 通过；真实模型调用和费用为 0。

### 当前限制

- 单实例本地 SQLite 与内存澄清 Runner，重启不能恢复中断。
- 未实现多用户认证，不应暴露公网。
- Benchmark 人工审核与真实模型效果验收仍是独立待办。

### 下一阶段

Sprint 6：完整测试、安全与成本检查、Docker、部署文档和最终验收。

## Sprint 4 — 2026-11-26

### 状态

评估与实验工程已完成；人工审核、真实模型批量实验和质量效果验收未完成。未执行真实模型调用，未引入 Docker。

### 完成任务

- 起草 100 条六类 Benchmark，包含完整任务字段、自然语言标准、机器检查和审核状态。
- 实现唯一 ID、精确分布、审核人/时间和真实实验门禁。
- 实现 BenchmarkGrader 的非空、JSON、Markdown、表格、长度、包含、正则和参考答案检查。
- 实现 A 原始、B 通用、C 自适应三组实验及重复运行。
- 实现指令、格式、约束、准确性、稳定性、Token、成本和耗时汇总。
- 实现 OpenAI/Anthropic 目标模型适配并接入 finalize。
- 将数据集作为 wheel 包资源，在临时环境安装后验证。
- 新增 `pea --validate-benchmark`，更新文档与测试。

### 主要文件

- `src/pea/models/benchmark.py`、`adapter.py`。
- `src/pea/evaluation/benchmark.py`、`grader.py`、`experiment.py`。
- `src/pea/adapters/model.py`。
- `src/pea/resources/benchmarks/tasks_draft.jsonl`、`benchmarks/README.md`。
- 新增 Benchmark、实验和模型适配测试。

### 测试结果

- 首轮 120 passed、4 failed，修正测试任务选择、未校验输入和空输出评分。
- 修正 Mock 组内重复调用夹具顺序后，最终 **125 passed，0 failed，1.64s**。
- 100 条数据校验通过，全部 `pending_human_review`。
- wheel 构建与临时环境安装后数据校验通过。
- 真实模型调用与费用均为 0。

### 未解决问题

- 需要真实审核人逐条审核 100 条任务并填写审核元数据。
- 需要合法 API 凭证和负责人明确预算后，才能执行真实对照实验。
- 语义完成度仍需人工评价，程序化检查不能证明整体质量提升。

### 下一阶段

Sprint 5：SQLite、历史与版本管理、FastAPI、Streamlit 和导出。Benchmark 人工审核与真实效果验收继续作为独立待办，不伪报完成。

## Sprint 3 — 2026-11-26

### 状态

已完成 LangGraph 主控工作流、澄清中断恢复、评估、Refiner、有界循环、取消和异常控制。未执行真实付费模型调用。

### 完成任务

- 核对 LangGraph 1.2.24 官方 Interrupt 文档和本地 API 签名。
- 建立 WorkflowState、EvaluationReport、IterationRecord、WorkflowResult 等契约。
- 实现静态 Evaluator 和默认关闭的可选动态原/优化 Prompt 对照。
- 实现 Refiner 将失败指标转换为修订任务并重新生成。
- 实现 LangGraph 节点、条件路由、最多三次生成和最佳版本保留。
- 使用 `interrupt()`、`Command(resume=...)`、`thread_id` 和 InMemorySaver 实现澄清恢复。
- 实现节点边界取消、失败短路、异常脱敏和预算停止。
- 新增 `pea --optimize ... --workflow`，完成测试与构建。

### 主要文件

- 新增 `src/pea/models/workflow.py`、`workflow/state.py`、`workflow/runner.py`。
- 新增 `src/pea/evaluation/evaluator.py`、`agents/refiner.py`。
- 更新 Generator 支持修订反馈，更新 CLI、启动状态和模型导出。
- 新增 `tests/test_evaluator.py`、`test_workflow.py` 并更新 CLI 测试。
- 更新 README、项目规格、架构、API 和测试报告。

### 核心实现

澄清节点不包裹通用异常捕获，遵循官方 Interrupt 规则。工作流把生成次数限制为 1–3，达到上限返回真实评分下的最佳版本。动态评估只报告可程序化验证指标，任务完成度与内容准确性保持未验证。

### 测试结果

- 首轮 98 passed、1 failed；发现“不超过”被误匹配为“超过”的长度解析缺陷，已修复诊断和动态评估。
- 最终 **99 passed，0 failed，1.26s**。
- LangGraph CLI 端到端通过，澄清恢复、循环、最佳版本、取消、异常和预算路径均通过。
- `uv build`：wheel 和源码包构建成功。
- 真实模型调用次数和费用均为 0。

### 当前限制

- 动态 Mock 对照不证明真实任务质量；需要 Sprint 4 Benchmark 和对照实验。
- Checkpointer 为内存实现，跨进程持久化留到 Sprint 5。
- 取消不能强制终止正在阻塞的提供商请求。
- 真实 OpenAI/Anthropic 联调仍待凭证。

### 下一阶段

Sprint 4：完整评估指标、100 条人工审核 Benchmark、三组对照实验、模型适配和成本分析。

## Sprint 2 — 2026-11-26

### 状态

已完成确定性 Prompt 理解与生成基线，并按持续 Sprint 指令准备进入工作流阶段。未使用真实模型，不产生 API 费用。

### 完成任务

- 建立意图、诊断、策略、修改理由和完整优化结果的 Pydantic 契约。
- 实现六类任务分类、复杂度、背景、输出、约束、示例、缺失信息与工具需求分析。
- 实现八维 Prompt 诊断、轻量优化判断、模糊表达与长度冲突检测。
- 建立八种策略的定义、适用条件和成本级别，实现动态策略规划。
- 实现确定性 Prompt 生成、逐项修改理由和严格结构化 JSON 解析。
- 实现 `StructuredPromptOptimizer` 阶段编排及 `pea --optimize` CLI。
- 完成单元、集成、异常和完整回归测试。

### 主要文件

- 新增 `src/pea/models/prompt.py`、`structured_output.py`。
- 新增 `src/pea/agents/` 中的意图、诊断、策略和生成模块。
- 新增 `src/pea/strategies/library.py`。
- 新增意图、诊断、策略、优化器测试，更新 CLI 与启动状态。
- 更新 README、项目规格、架构、API 和测试报告。

### 核心实现

各组件通过明确 Pydantic 数据结构连接，不依赖 LangGraph 也可独立测试。策略规划以任务和诊断为依据，Few-shot 只使用实际示例，角色只用于复杂专业任务，ReAct 明确要求真实工具可用，不编造检索过程。

### 测试结果

- 首轮 74 passed、1 failed；发现纯用户需求未检测长度冲突的真实缺陷，已修复。
- 补充前置/后置中文长度冲突表达后，最终 **77 passed，0 failed，0.34s**。
- CLI 真实优化流程通过，返回结构化 JSON，保留约束并仅选择适用策略。
- `uv build`：wheel 和源码包构建成功。
- 真实模型调用次数与费用均为 0。

### 当前限制

- 当前是规则基线，不声称具备已验证的模型语义理解或真实质量提升。
- `needs_clarification` 已生成，但暂停、提问和恢复等待 Sprint 3。
- Evaluator、Refiner 和最大三次迭代尚未实现。

### 下一阶段

Sprint 3：LangGraph 状态、节点、条件路由、Clarification、Evaluator、Refiner 和循环控制。

## Sprint 1 — 2026-11-26

### 状态

已完成。遵循项目负责人要求：优先稳定模型调用层，仅实现 OpenAI、Anthropic 和 Mock，不引入 Docker，不执行真实付费模型测试。

### 完成任务

- 将 Sprint 0 标记为已验收，并将两份 Sprint 0 报告作为环境与选型基线。
- 使用 Pydantic Settings 实现环境变量、`.env`、密钥、模型、超时、重试和预算配置。
- 建立不可变 Pydantic 请求、响应、消息和 Token 数据契约。
- 实现统一 `LLMGateway`、`LLMBackend` 替换接口和明确标识的 MockBackend。
- 实现 OpenAI/Anthropic 共用的 LiteLLM 适配器，统一请求、响应和异常。
- 实现有界指数退避、调用上限、累计已知成本预算、耗时和 Token 日志。
- 默认启用 LiteLLM 本地价格表并延迟导入，处理 Sprint 0 的远程加载警告。
- 增加 `pea --mock` 端到端自检。
- 完成单元、集成和异常测试，更新全部相关文档。

### 主要文件

- 新增 `src/pea/config.py`、`exceptions.py`、`logging_config.py`。
- 新增 `src/pea/models/` 和 `src/pea/gateway/`。
- 更新 `src/pea/__main__.py`、`bootstrap.py` 和 `.env.example`。
- 新增 `tests/conftest.py`、`test_config.py`、`test_models.py`、`test_mock_gateway.py`、`test_litellm_backend.py`。
- 更新 README、项目规格、架构、API 和测试报告。

### 核心实现

`LiteLLMBackend` 在实际调用前才导入 LiteLLM，默认先设置 `LITELLM_LOCAL_MODEL_COST_MAP=True`。OpenAI 与 Anthropic 共用适配器，但由独立配置提供模型和密钥。Gateway 关闭 LiteLLM 内部重试，统一控制重试、调用上限、耗时和成本。

Mock Token 明确标记为 `mock_estimate`；真实提供商未返回 Token 时保留 `None`；成本未知时返回 `None`，不伪报为 0。

### 测试结果

- 首轮 41 passed、1 failed；失败为 Mock Token 测试预期算术错误，修正后重新执行完整套件。
- 最终 `uv run pytest`：42 passed，0 failed，0.25s。
- `uv run pea`：通过。
- `uv run pea --mock`：通过，真实经过统一 Gateway，无外部模型请求。
- 真实 LiteLLM 本地价格表导入：通过，无远程价格表警告；本次约 5.286s，仅首次后端加载产生。
- `uv build`：wheel 和源码包构建成功。
- 真实模型调用次数和费用均为 0。

### 未解决问题

- 无 API Key，真实 OpenAI/Anthropic 联调、模型 ID 和凭证有效性仍未验收。
- 成本限制是进程内调用间保护，不能替代提供商侧硬预算；成本未知时无法预控实际费用。
- 本地价格表随 SDK 版本固定，后续升级需检查价格准确性。
- 本机未发现 Docker，按负责人要求本阶段未引入。

### 下一阶段

Sprint 2：意图理解、任务分类、Prompt 诊断、策略规划与生成。该阶段现已完成。

## Sprint 0 — 2026-11-26

### 状态

**已验收完成，项目负责人已批准进入 Sprint 1。**

### 已完成任务

- 检查 Windows、Python、Git、项目目录、全局相关包、模型 API 配置和 Docker。
- 核对 LangGraph、Pydantic、FastAPI、LiteLLM 官方文档与 PyPI 当前稳定版本。
- 创建 `src` 包布局、启动诊断 CLI、基础测试和项目文档。
- 生成环境检查与技术选型报告，作为 Sprint 1 的验收基线。

### 测试结果

- 依赖安装、直接依赖导入、两个启动入口均通过。
- Pytest：5 passed，0 failed，0.15s。
- 未执行真实模型调用，模型费用为 0。
- 当时观察到 LiteLLM 在线价格表超时警告，已在 Sprint 1 处理。
