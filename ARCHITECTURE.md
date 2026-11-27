# PEA 架构设计

## 真实质量优化数据边界

`optimization_data.py` 对 15,011 条 Dolly 记录去重并生成固定种子的 train/dev/test；旧 80 条及近重复全部排除。测试文件哈希锁定，只能最终评估。`reference_metrics.py` 提供分类 Exact Match、问答/抽取 Token F1，并将开放任务 F1 明确标为辅助指标。

真实策略搜索只能在 train 上执行，dev 负责选优，test 只终评。详见 `docs/REAL_QUALITY_EVALUATION.md`。

## 外部 Harness 审计层

`external_data.py` 保存公共数据的来源、许可、原始哈希和确定性抽样；`harness_audit.py` 评估目标保留、输出结构、Prompt 膨胀、策略克制和已知缺陷检测；`promptfoo_bridge.py` 让 Promptfoo 通过 Python Provider 独立执行 PEA 断言。

该层不使用 PEA 内部 Evaluator 给自己打分，也不把结构断言当作语义质量。审计结果和修复前后对照见 `docs/HARNESS_EVALUATION.md`。

## Sprint 5：持久化与产品界面

### SQLite Result Manager

`runs` 保存原始需求、原始 Prompt、状态、提供商、模型、Token、成本、警告和最终结构化结果；`prompt_versions` 以 `(run_id, version_number)` 唯一约束保存每轮内容、策略、修改理由、评估和最佳标记。

`SQLiteResultManager` 支持保存/恢复更新、历史分页、状态筛选、运行详情和版本比较。重复保存先 flush 删除旧版本再重建，保证幂等。`ResultExporter` 输出 JSON 和 Markdown。

### FastAPI

- 每次优化创建独立 WorkflowRunner，避免取消串扰。
- 活跃 Runner 仅在澄清等待时保留；终止后释放。
- API 默认拒绝真实提供商，必须同时配置 `PEA_ENABLE_REAL_PROVIDERS=True` 和对应模型/密钥。
- 默认绑定回环地址，无多用户认证，不应直接暴露公网。
- 提供优化、澄清、取消、历史、版本比较和导出端点。
- 提供 `/v1/chat/completions` OpenAI-compatible Prompt 优化接口，返回标准 chat.completion，不伪造 usage。
- 可信 Host 可配置，声明请求体最大 64 KiB；响应使用 `no-store` 和安全响应头。
- Docker 多目标镜像使用非 root 用户、锁定依赖、健康检查和持久化卷；当前仅有静态配置验证。

### Streamlit

通过 HTTP 调用 FastAPI，不直接操作数据库。产品界面分为优化工作台、历史与版本、评测中心和系统状态四个工作区；支持详略/探索偏好、目标模型适配、原始/优化对比、统一 diff、公共审计和下载。真实浏览器已验证偏好提交、API 调用、结果、历史与评测展示。

## Sprint 4：评估、Benchmark 与模型适配

### Benchmark 数据与审核门禁

100 条任务存储在 `src/pea/resources/benchmarks/tasks_draft.jsonl`，作为 wheel 包资源加载。六类分布为 20/20/15/15/15/15，每条包含需求、原始 Prompt、目标、输出、约束、自然语言标准、机器检查、参考答案和审核元数据。

当前所有任务为 `pending_human_review`。只有 100 条均具有 `approved`、真实审核人和审核时间，才允许真实提供商批量实验。草稿只能显式以 Mock 运行，报告中的 `quality_claim_allowed` 为 `false`。

### 三组实验

```text
A Original -> 原始 Prompt -> 执行与编码检查
B Generic  -> 通用清晰化模板 -> 执行与相同编码检查
C Adaptive -> 分类、诊断、策略、生成、动态评估、有界迭代 -> 相同编码检查
```

三组共用 Gateway、提供商、模型、温度和工具权限。C 的额外执行与迭代成本全部计入。实验按组执行重复运行，输出一致才记为稳定；单次运行时稳定性为 `None`。

汇总包括指令遵循、格式合格率、约束遵循、参考答案准确率、多次稳定性、Token、成本和耗时。语义任务完成度始终需要人工复核，不以 LLM 自评或关键词检查替代。

### Model Adapter

`TargetModel` 显式声明提供商、模型、system/JSON 能力和输出 Token 上限。适配器拆分专业视角到 system 消息；未声明 JSON 模式时追加保守 JSON 指令；不支持 system 时保留在用户消息并警告。模型前缀必须匹配提供商。工作流在 finalize 阶段可选返回 `AdaptedPrompt`，不自动发起真实调用。

## Sprint 3：LangGraph 主控工作流

`WorkflowRunner` 是主控 Orchestrator，节点逻辑复用 Sprint 2 组件，评估与修订独立成模块。

```text
START
  -> analyze
       -> 信息不足：clarify --interrupt / resume--> analyze
       -> 信息足够：diagnose
       -> 失败或取消：END
  -> diagnose -> plan -> generate -> evaluate
       -> 达标：finalize
       -> 未达标且少于三次：refine -> generate
       -> 达到三次：finalize，返回历史最佳版本
       -> 失败或取消：END
  -> finalize -> END
```

### 状态与持久化边界

`WorkflowState` 是 TypedDict，包含请求、意图、诊断、策略、当前/最佳 Prompt、评估、迭代记录、澄清问题、状态和错误。`iterations` 使用追加 reducer，保留每轮记录。

当前使用 `InMemorySaver`：
- 每次运行生成 `thread_id`。
- `clarify` 调用 `interrupt()`，并提供 `ClarificationAnswers` Pydantic 响应 schema。
- `resume(thread_id, answers)` 使用相同检查点和 `Command(resume=...)` 恢复。
- 中断节点不包裹通用 `try/except`，符合 LangGraph 规则。
- 内存状态不能跨进程恢复；SQLite 持久化在 Sprint 5 实现。

### 循环与最佳版本

初始生成记为第 1 次，最多允许 3 次。每次评估生成不可变 `IterationRecord`，只有得分严格更高时才替换最佳版本。达到上限不表示质量达标，但最终状态为 `completed`，返回最佳版本及其真实评估分数，不伪报通过。

### 取消与异常

- `cancel()` 使用线程安全 Event；每个受保护节点执行前检查。
- 正在执行的阻塞模型调用不能被强制终止，但取消后不再进入新的节点。
- 已失败或取消的状态会绕过剩余业务节点和模型调用。
- 预期 LLM 异常保留安全分类；未知异常只对外暴露类型，不泄露内部错误正文。
- 澄清节点只处理恢复数据，不捕获 LangGraph 中断异常。

## Evaluator 与 Refiner

### 静态评估

检查原始目标保留、用户约束保留、输出结构完整和修改理由完整。静态分数不冒充任务执行质量。

### 可选动态评估

启用且配置 Gateway 时，使用相同提供商分别执行原始 Prompt（无原始 Prompt 时使用用户需求）和优化 Prompt：
- 检查非空、合法 JSON、Markdown/表格结构及长度约束。
- 保存原/优化输出、动态分数、Token、耗时和成本。
- 明确列出 `task_completion` 和 `content_accuracy` 为未验证指标。
- 默认不启用；首轮最多两次调用，后续迭代复用原始基线，仅执行新候选。三轮调用从 6 次降为 4 次，受 Gateway 重试、预算和调用上限约束。
- 动态调用失败时返回静态结果和明确警告；已发生的调用可能产生费用。

完整任务质量评估、人工标准和三组 Benchmark 对照属于 Sprint 4。

### Refiner

将失败指标转换为具体修订说明，必要时补充 Structured Output 或 Constraint-based 策略。Generator 根据反馈重新生成并记录修订理由，而不是只修改评分或无限重试。

## Sprint 1–2 基础模块

- `gateway`：统一调用、Mock、LiteLLM 双提供商、异常、重试、预算和用量。
- `agents/intent.py`：任务分类、复杂度、背景、约束、示例、缺失信息和工具需求。
- `agents/diagnosis.py`：八维诊断、冲突检测和优化优先级。
- `agents/strategy.py` / `strategies/`：八种策略定义与适用性选择。
- `agents/generator.py`：确定性生成、逐项修改理由和修订重点。
- `structured_output.py`：Pydantic JSON 严格解析。
- LiteLLM 默认本地价格表并延迟导入；模型日志不记录 Prompt 或密钥。

## 当前目录

```text
prompt-agent/
├── pyproject.toml / uv.lock / .env.example
├── README.md / PROJECT_SPEC.md / ARCHITECTURE.md
├── DEVELOPMENT_LOG.md / API.md / TEST_REPORT.md
├── docs/
├── src/pea/
│   ├── config.py / exceptions.py / logging_config.py
│   ├── models/       # llm.py、prompt.py、workflow.py
│   ├── gateway/      # 统一调用与双提供商适配
│   ├── agents/       # 意图、诊断、策略、生成、Refiner
│   ├── strategies/   # 策略库
│   ├── evaluation/   # Evaluator、Benchmark、Grader、ExperimentRunner
│   ├── adapters/     # 双提供商目标模型适配
│   ├── resources/    # 随 wheel 打包的 100 条 Benchmark 草稿
│   ├── storage/      # SQLAlchemy ORM、Result Manager、导出
│   ├── api/          # FastAPI 与应用服务
│   ├── ui/           # Streamlit 页面
│   └── workflow/     # state.py、runner.py
├── benchmarks/       # 数据审核指南
└── tests/            # 136 项累计测试
```

## 当前限制

- 意图与生成仍是规则基线，需通过模型增强和 Benchmark 验证复杂语义。
- 动态指标不能判断事实准确性、语义完成度或真实业务质量。
- 澄清检查点是进程内状态，取消是节点边界控制。
- 真实 OpenAI/Anthropic 联调仍需合法测试凭证。
- 100 条 Benchmark 尚需逐条人工审核，真实模型对照和语义质量尚未验收。
- SQLite 当前面向单实例本地使用；多实例并发、用户认证和权限隔离需在生产部署前另行设计。
- Docker 与最终部署验收尚未实现。
