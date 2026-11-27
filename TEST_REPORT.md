# 测试报告

## 0.2.0 产品前端与发布验收 — 2026-11-27

- 新增四工作区 Streamlit：优化工作台、历史与版本、评测中心、系统状态。
- 浏览器实际选择详细+探索，API结果显示偏好并生成备选路径与反证。
- Benchmark/公共审计 API、历史下载和系统状态均通过真实浏览器验证。
- 发布前完整回归：**198 passed，1 warning，10.02s**；0.2.0 wheel与源码包构建成功。
- GitHub CI、PRD、路线图、贡献、安全和许可证已配置。

## 产品短板分析与生成偏好增强 — 2026-11-27

- `docs/PRODUCT_CRITIQUE.md` 记录语义生成、偏好学习、反事实、策略记忆和协作等核心短板。
- 新增详细/均衡/简洁偏好，详细信息优先于形式简洁，简洁模式聚焦去重。
- 新增探索式备选路径与反证，要求替代假设、反对证据和主方案切换条件；简单任务不添加。
- API 请求契约支持 OptimizationPreferences，默认行为兼容。
- 聚焦测试15 passed；完整回归：**197 passed，1 warning，12.06s**；构建通过。

## 动态生成器与复杂 Prompt 重构 — 2026-11-27

- PromptGenerator 拆分任务目标与输入材料，去除重复背景，增加任务特定执行步骤和验收标准。
- 输出提取只保留交付要求，避免复制任务前缀；大写Context、管理层用途和普通约束清理均修复。
- 已明确输出规范的简单Prompt不再机械选择Structured Output。
- 复杂研究案例实际生成8个模块，保留预算、来源、对比表、12个月计划和事实/推断边界。
- 相关测试63 passed；完整回归：**194 passed，1 warning，12.19s**；构建通过。
- 案例：`benchmarks/results/complex_prompt_optimization_example.json`，不含执行结果。

## 人工邮件评审驱动修复 — 2026-11-27

- 用户指出优化版补救措施不如原版详细、字数减少并不等于优化，接受该评审证据。
- 修复通用邮件模板以行动请求/礼貌语替代具体信息的问题，优先保留事实、日期、原因和补救行动。
- 过滤纯优化元指令，同时保留“保持专业语气”等附加要求，并补充“保持/keep”约束识别。
- 同一案例由新子Agent复测，v2补救措施更具体，但是否优于原版仍交由用户判断，不自动宣称改善。
- 完整回归：**192 passed，1 warning，15.02s**；构建通过。

实例：`benchmarks/results/manual_review_example.json`、`manual_review_example_v2.json`。

## 最终端到端模拟联调 — 2026-11-27

- Dev 候选、最终 test 访问、原始/PEA 生成、参考评分和两名独立模拟盲评全部完成。
- 最终参考均分：原始 0.4690、PEA 0.4457；平均差 -0.0232，95% CI [-0.1411, 0.0486]，无明确差异。
- 模拟盲评：评审1 PEA 2胜6平，评审2 PEA 1胜7平；原始均0胜，偏好一致率87.5%，重大失败均为0。
- 所有人工/API均为子Agent模拟，不构成真实正确率或产品优越性证据。
- 最终 test 已用于模拟，禁止继续据此调参；正式评估需新 holdout。
- 完整回归：**191 passed，1 warning，16.88s**；构建通过。

完整报告：`docs/SIMULATION_FINAL_REPORT.md`。

## LLM 子 Agent 语义联调与上下文修复 — 2026-11-26

- 两个独立子 Agent 分别生成原始/优化组回答，输入去除参考答案，主流程随后评分。
- 首次模拟优化组 0胜3平5负，参考均分 0.3268→0.2478；未隐藏负面结果。
- 定位到长上下文关键词驱动任务分类、上下文长度驱动复杂度，简单抽取被误加研究策略。
- IntentAnalyzer 已分离指令与嵌入式 Context，新增回归；43 项相关聚焦测试通过。
- 新优化组子 Agent 复测：优化均分 0.2478→0.3151，原始组 0.3268；与原始组 2胜2平4负，CI 跨0。
- 具体子 Agent 型号/强度不可指定，Token/成本/延迟不可核验；结果不是生产 API 正确率或竞品证据。
- 完整回归：**191 passed，1 warning，10.59s**；构建通过。

报告：`llm_subagent_dev_simulation.json`、`llm_subagent_dev_simulation_after_context_fix.json`。

## FinalEvaluationRunner — 2026-11-26

- 最终 Runner 校验锁定 test SHA256、完整同提供商/模型 dev 报告和显式最终确认。
- 真实终评要求真实 dev 报告与全局提供商开关，Mock dev 不能解锁真实终评。
- test 访问日志采用追加方式，记录数据哈希、dev 哈希、模型、样本和 seed。
- 所有测试只用临时 test 夹具，真实锁定 test 未读取。
- 聚焦测试 17 passed，最终完整回归：**190 passed，1 warning，11.04s**；构建通过。

## 跨候选基线缓存 — 2026-11-26

- QualityRunner 支持原始执行缓存，保留输出和参考评分，不重复计入新调用、Token、成本或耗时。
- QualityGroupSummary 区分 attempted_calls 与 cached_calls。
- PolicySearchRunner 在全部候选间共享缓存，8 条 train、2 候选调用由 32 降为 24，缓存命中 8。
- 缓存相关聚焦测试 16 passed；完整回归：**186 passed，1 warning，10.45s**；构建通过。
- 未执行外部模型调用，缓存优化不代表任务质量提升。

## train/dev 策略搜索器 — 2026-11-26

- 新增 StrategyPolicy 候选开关，默认行为兼容；Zero-shot 与约束安全处理保留。
- PolicySearchRunner 仅接受同一 train 或 dev split，混合/test 输入在调用前拒绝。
- 候选共用案例和 Gateway，全局预算累计；不完整或成本未知候选不参与最佳选择。
- 支持 `质量奖励 - cost_penalty × 成本`，Mock 验证平局确定性选择。
- train 8 条、2 候选模拟完成，32 次本地调用，外部模型调用 0。
- 聚焦测试 9 passed，最终完整回归：**185 passed，1 warning，11.14s**；构建通过。
- 当前模拟不证明策略质量提升，真实搜索仍待 OpenAI-compatible 配置与预算。

## 质量执行器第二轮增强 — 2026-11-26

- 子 Agent 新增固定 seed 分层 round-robin 抽样，质量执行器测试达到 12 passed。
- QualityReport 内置成对 win/tie/loss、bootstrap 置信区间；无完整评分对时为 None。
- 新增 `quality_cli.py`，仅允许 train/dev，真实模式需命令行授权、全局开关和预算。
- 主流程复测质量执行器、CLI 和统计共 18 passed；CLI 8 条 dev 自检通过。
- 不含这两个未完成模块时，其余回归先行达到 166 passed。
- 最终完整回归：**181 passed，1 warning，10.42s**；`uv build` 通过。
- 外部模型调用仍为 0，尚未产生真实正确率提升证据。

## 独立质量评测执行器 — 2026-11-26

- 用户授权的子 Agent 实现 `QualityRunner`，主 Agent 复核代码、边界与测试。
- 同一 Gateway/模型/温度执行原始与 PEA Prompt，按类别汇总 Exact Match、Token F1、成本和耗时。
- test 在选择前拒绝；真实模型要求显式开关、非空成本预算和最多 50 条。
- 子 Agent 测试 8 passed；主流程复测质量执行器与统计共 11 passed。
- 8 条 dev 分层 Mock 自检完成：8 个类别、16 次本地调用、A/B 八平，外部模型调用 0。
- 成对 bootstrap、win/tie/loss 和人工盲评规范已加入。
- 最终完整回归：**174 passed，1 warning，10.24s**；`uv build` 通过。
- 当前结果只是执行器与统计自检，不是正确率提升或竞品优劣证据。

详见 `docs/REAL_QUALITY_EVALUATION.md` 与 `benchmarks/results/dev_smoke_summary.json`。

## 真实质量优化数据准备 — 2026-11-26

- Dolly 15,011 条去重并切分：train 10,306、dev 2,208、test 2,214。
- 排除旧开发样例 80、重复 198、旧样例重叠 5；旧 80 条不再用于最终测试。
- 三个切分文件 SHA256 复核通过，集合间及与旧样例的 ID/内容重叠均为 0。
- 固定种子重建结果一致，test 锁定为最终评估专用。
- 新增分类 Exact Match、问答/抽取 Token F1；开放任务 F1 明确为辅助指标。
- 最终完整回归：**163 passed，1 warning，10.88s**；`uv build` 通过。
- 未执行真实模型策略搜索，不声称正确率或可用性已经提升。

协议见 `docs/REAL_QUALITY_EVALUATION.md`。

## Harness 外部对照评测 — 2026-11-26

- 公共 Dolly 样例：80 条，固定种子分层抽样，保留 CC BY-SA 3.0 和原始 SHA256。
- Promptfoo 0.126.0 实际运行：修复前 80/82，修复后 **82/82**；无外部模型调用。
- 英文歧义、英文长度冲突、英文模糊需求澄清：检测率均由 0% 提升至 100%。
- 目标保留、输出结构保持 100%，Few-shot 和简单角色过度添加保持 0%。
- 约束去重后，平均/中位 Prompt 膨胀保持 1.4058× / 1.2344×，未以长度换检测率。
- 最终完整回归：**156 passed，1 warning，10.96s**；`uv build` 通过。
- 该结果是结构与变异审计，不是开放任务语义质量排名。

详见 `docs/HARNESS_EVALUATION.md`。

## 模拟验收与 OpenAI-compatible 补充 — 2026-11-26

- 100 条三组 Mock 实验：`completed`，100/100 条，404 次 Mock 调用，外部费用 0。
- A/B/C 编码检查平均分均为 0.4916666667，不能据此声称质量提升。
- `dataset_reviewed=false`、`quality_claim_allowed=false`，模拟通过不修改正式审核门禁。
- 本地 OpenAI-compatible HTTP 集成通过实际 LiteLLM SDK：`/v1/chat/completions`、Bearer 鉴权、模型/消息和 Token 响应正确。
- OpenAI API Base 配置及非法 URL 测试通过。
- LiteLLM 出现一条 `There is no current event loop` 弃用警告，不影响本地请求结果。
- 聚焦测试：16 passed，1 warning。
- 最终完整回归：**148 passed，1 warning，10.48s**；`uv build` 通过。

详细模拟边界见 `docs/SIMULATED_ACCEPTANCE.md`。

## Sprint 6 — 2026-11-26

### 最终工程验证

| 检查 | 结果 |
|---|---|
| 完整测试 | **142 passed，0 failed**，3.44s |
| 成本优化 | 三轮动态迭代复用原始基线，调用由 6 次降为 4 次；基线不跨任务共享、不进入导出 JSON |
| API 安全 | 安全响应头、可信 Host、容器 Host 配置、64 KiB 请求限制、真实提供商默认禁用通过 |
| Docker 静态验证 | Compose YAML 解析、双目标、非 root、锁文件、健康检查、本机端口和数据卷检查通过 |
| Python 包 | `uv build` 通过 |
| 真实模型与费用 | 调用 0，费用 0 |

### 最终验收限制

- 本机无 Docker、Podman、Buildah 或 Hadolint，未实际构建或运行镜像。
- 100 条 Benchmark 仍待人工审核。
- 真实 OpenAI/Anthropic 联调和对照实验未运行。
- 语义完成度、事实准确性和业务效果需要人工复核。

最终逐项状态见 `docs/FINAL_ACCEPTANCE.md`，部署操作见 `docs/DEPLOYMENT.md`。

## Sprint 5 — 2026-11-26

### 自动化与实际产品验收

| 检查 | 结果 |
|---|---|
| 完整回归 | **136 passed，0 failed**，3.08s |
| SQLite | 保存、重复保存幂等、恢复更新、历史筛选、最佳版本和 Token/成本通过 |
| FastAPI TestClient | 优化、澄清、取消、历史、比较、导出、400/403/404/422 均通过 |
| 真实本地 API | Uvicorn 启动，健康检查、POST 优化和 GET 历史通过 |
| 真实 Streamlit | 浏览器输入需求并点击优化，显示 `completed`、一个版本和修改理由 |
| 历史 UI | 显示原始需求、最佳版本、Prompt 内容及 JSON/Markdown 下载控件 |
| 安全 | API 默认拒绝真实提供商；启用后缺密钥仍返回 400；无真实模型调用 |
| 构建 | `uv build` 通过，检查 API、UI、存储和 Benchmark 包资源 |

验收服务已在检查后停止，运行数据库已清理。测试未产生模型 API 费用。

### 缺陷与修正

首轮 135 passed、1 failed。重复保存同一运行时，SQLAlchemy 将新版本插入排在旧版本删除之前，触发 `(run_id, version_number)` 唯一约束。已在替换版本前显式 flush 删除操作，完整回归后 136 项通过。

### 限制

SQLite 与内存 Runner 面向单实例本地产品。取消不能强制终止正在阻塞的模型请求，服务重启后不能恢复内存澄清状态。多用户认证和生产级并发不属于当前本地交付。

## Sprint 4 — 2026-11-26

### 实际执行结果

| 检查 | 结果 |
|---|---|
| 完整回归 | **125 passed，0 failed**，最终 1.64s |
| Benchmark 校验 | 100 条、100 个唯一 ID，分布 20/20/15/15/15/15；全部待人工审核 |
| 审核门禁 | 默认拒绝草稿实验；草稿即使提供假真实凭证也只能 Mock；100 条具备审核元数据后就绪检查通过 |
| 三组 Mock 实验 | A/B/C 参数与评分汇总、两次稳定性、Token 和成本记录通过；质量声明门禁为 false |
| 异常与预算 | 非预算错误进入记录；预算耗尽立即停止批次 |
| 模型适配 | OpenAI/Anthropic、system 拆分、JSON 回退、Token 上限和模型前缀校验通过 |
| 包构建与安装 | `uv build` 通过；wheel 包含 100 条包资源；临时环境安装 wheel 后 `--validate-benchmark` 通过 |
| 真实模型调用 | 0；API 费用 0 |

### 测试修正

- 首轮 120 passed、4 failed：测试误把首条商务任务当作 `data_001`；空输出错误通过最大长度检查；一处测试用未校验 `model_copy` 注入字典。已修正测试选择并修复空输出评分。
- 后续一次失败来自 Mock 响应顺序按“重复→组”排列，而实验实际按“组→重复”执行。检查调用日志确认无额外隐藏调用后修正夹具，最终 125 项通过。

### 尚未完成

100 条任务尚未逐条人工审核，真实模型对照实验未运行，语义任务完成度和真实优化效果未验收。Mock 分数只证明实验管线和编码检查行为正确。

## Sprint 3 — 2026-11-26

### 测试边界

使用真实 LangGraph 1.2.24、InMemorySaver、Pydantic 中断响应和 Mock Gateway。未调用真实 OpenAI/Anthropic，模型调用费用为 0。

### 实际执行结果

| 检查 | 结果 |
|---|---|
| `uv run pytest` | **99 passed，0 failed**，1.26s |
| LangGraph CLI 端到端 | `pea --optimize ... --workflow` 返回 `completed`，一轮达标，评估分数 1.0 |
| 澄清中断与恢复 | 首次返回 `needs_clarification` 和线程 ID；相同线程使用 `Command(resume=...)` 后完成 |
| 迭代控制 | 失败后 Refiner 重新生成；最多三次；保留得分最高的版本 |
| 动态对照 | Mock 分别执行原始与优化 Prompt，检查 JSON、长度、Token 和成本 |
| 异常与取消 | 认证/限流等模型异常、未知异常脱敏、开始前与评估后取消均通过 |
| 预算 | 动态评估需要两次调用而 `max_calls=1` 时停止第二次并返回明确警告 |
| `uv build` | wheel 和源码包构建成功 |

### 新增覆盖

- LangGraph START/END、节点、条件边、循环和状态追加。
- 澄清问题、结构化答案、错误答案键、相同线程恢复。
- 一次达标、二次修订达标、三次上限和最佳版本保留。
- 静态目标/约束/输出/修改理由检查。
- 动态非空、JSON、长度和原/优化分数，未验证指标明确标记。
- 动态调用失败、未配置 Gateway、预算耗尽和静态结果警告。
- 取消、非法迭代次数、节点异常和模型异常。

### 缺陷与修正

首轮 98 passed、1 failed。发现“不超过5字”中的“超过”被正则误判为下限，导致“你好”被错误判定为不满足长度。已同时修复诊断和动态评估的负向匹配，完整回归后 99 项通过。

### 验证限制

动态测试是真实 Gateway + Mock 执行，不是真实模型质量实验。任务完成度、内容准确性仍明确未验证；内存 Checkpointer 不能跨进程恢复。

## Sprint 2 — 2026-11-26

### 测试边界

Sprint 2 使用确定性规则实现意图分析、诊断、策略选择和生成，不需要模型 API。完整测试未向模型提供商发送请求，模型 API 调用次数和费用均为 0。

### 实际执行结果

| 检查 | 命令或方式 | 结果 |
|---|---|---|
| 完整回归测试 | `uv run pytest` | **77 passed，0 failed**，0.34s |
| CLI 端到端优化 | `uv run pea --optimize ... --raw-prompt ...` | 通过；返回可解析 JSON，任务类型为邮件办公，保留 200 字约束 |
| 动态策略检查 | 上述真实 CLI 请求 | 仅选择 Zero-shot 与 Constraint-based，未添加角色、Few-shot 或 ReAct |
| 结构化结果 | Pydantic 与 JSON round-trip | 通过；严格拒绝非法 JSON 和额外字段 |
| 包构建 | `uv build` | wheel 和源码包均构建成功 |

### 新增覆盖

- 六类任务及通用任务分类、简单/复杂任务识别。
- 输出要求、约束、背景、示例和工具需求提取。
- 必要信息缺失判断与正常任务不过度追问。
- 八维诊断、无原始 Prompt、优秀 Prompt 轻量处理和模糊表达。
- 前置与后置中文长度表达：`至少500字`、`500字以上`、`不超过100字`、`100字以内` 的冲突检测。
- 策略适用性、去重、选择理由和成本级别；Few-shot 必须有实际示例。
- ReAct 与 Self-critique 不机械叠加，简单任务不添加角色或拆解。
- 从自然语言或原始 Prompt 生成结构化结果和逐项修改理由。
- 约束冲突不被静默取舍，工具不可用时不得编造检索过程。
- CLI 优化入口和完整 JSON 结果。

### 缺陷与修正

- 首轮 74 passed、1 failed，发现纯自然语言需求未进入字数冲突诊断，只有 `raw_prompt` 被检查。已统一用户请求与原始 Prompt 的冲突检测，并增加回归测试。
- 随后补充后置长度表达测试，最终累计 77 项全部通过。

### 验证限制

当前验证证明规则基线的行为和接口正确，不证明优化后的 Prompt 在真实模型上质量更高。动态执行、评估迭代与对照实验仍属于后续 Sprint。

## Sprint 1 — 2026-11-26

### 测试边界

本轮全部自动化测试使用 MockBackend 或注入的假 LiteLLM 模块。没有向 OpenAI、Anthropic 或其他模型提供商发送请求，没有使用 API Key，模型 API 费用为 0。

### 实际执行结果

| 检查 | 命令或方式 | 结果 |
|---|---|---|
| 自动化测试 | `uv run pytest` | **42 passed，0 failed**，最终耗时 0.25s |
| Mock 端到端 | `uv run pea --mock` | 通过真实 Settings、Gateway、MockBackend 返回统一 JSON；Token 标记为 `mock_estimate`，成本 0 |
| 普通启动 | `uv run pea` | 通过；只报告 OpenAI/Anthropic 配置状态，阶段为 Sprint 1 |
| LiteLLM 延迟导入 | 新 Python 进程检查 `sys.modules` | 导入 Gateway 时 LiteLLM 未加载；首次需要后端时才加载 |
| LiteLLM 本地价格表 | 真实 LiteLLM 1.111.0 导入，无模型调用 | 成功；未再出现远程价格表超时警告；本次本地导入约 5.286s |
| 包构建 | `uv build` | wheel 和源码包均构建成功 |

### 自动化覆盖

- 配置：默认 Mock、本地价格表、环境变量别名、密钥脱敏、缺失模型/密钥、模型前缀和非法重试配置。
- 数据契约：消息角色与空白内容、消息列表、温度范围和请求类型校验。
- 双提供商：OpenAI 与 Anthropic 的模型前缀、消息、密钥、温度、Token、超时和 `num_retries=0` 参数。
- 响应：文本、Token、成本、空响应、缺失 Token 和成本计算失败。
- 异常：认证、限流、超时、服务不可用、未知异常、异常消息脱敏。
- 重试：可重试错误恢复、最大重试次数、认证错误不重试、退避间隔。
- 限制：累计成本预算、包含失败尝试的调用上限。
- 日志：包含提供商和用量，不包含测试 Prompt 或密钥。
- CLI：普通诊断和完整 Mock 调用均返回有效 JSON。

### 测试修正记录

首轮为 41 通过、1 失败。失败来自测试将 Mock 的 1 个输入词和 2 个输出词误算为总计 4；修正预期为 3 后完整套件 42 项通过。该失败不是模型实现缺陷。

### 未验证事项

- 未进行真实 OpenAI/Anthropic 网络联调，不能声称凭证有效、模型 ID 可用或真实响应质量已验收。
- 本地价格表导入约 5.286s 是一次性 SDK 加载成本；远程价格表请求已被默认禁用，普通诊断和 Mock 不承担该开销。
- 尚未实现流式响应、工具调用、Prompt 优化工作流或动态质量评估。

## Sprint 0 — 2026-11-26（已验收）

### 环境

Windows 10 10.0.18363；系统 Python 3.13.5；项目 CPython 3.12.13；uv 0.11.19。

### 结果

- `uv sync --extra dev`：解析 105 个包并安装成功，生成 `uv.lock`。
- FastAPI、LangGraph、LiteLLM、Pydantic、Pydantic Settings、SQLAlchemy、Streamlit、Uvicorn 导入通过。
- `uv run pea` 和 `uv run python -m pea`：均通过。
- `uv run pytest`：5 passed，0 failed，0.15s。
- 真实模型调用为 0，费用为 0。
- 当时观察到 LiteLLM 在线价格表超时警告；该问题已在 Sprint 1 通过默认本地价格表和延迟导入处理。
