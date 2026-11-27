# Harness 外部对照评测

## 结论

PEA 的单主控、显式状态、有界迭代、预算和历史版本控制已经通过结构化外部测试。与 Promptfoo 相比，PEA 的优势是内置诊断、策略规划、澄清和自动修订；不足是语义质量证据、红队、自定义断言生态、提供商广度和跨进程恢复。

**不给出“PEA 优于 Promptfoo”或“接近完美产品”的结论。** Promptfoo 是评测与红队工具，PEA 是优化工作流；本次 82 个场景主要检查 PEA 的结构保持和已定义缺陷，不是开放任务质量排名。

## 外部参照与数据来源

- Promptfoo GitHub：https://github.com/promptfoo/promptfoo
- Promptfoo Python Provider：https://www.promptfoo.dev/docs/providers/python/
- Promptfoo Assertions：https://www.promptfoo.dev/docs/configuration/expected-outputs/
- Dolly 数据：https://huggingface.co/datasets/databricks/databricks-dolly-15k
- Dolly 项目与限制：https://github.com/databrickslabs/dolly

Promptfoo 0.126.0 以 MIT 许可开源，支持本地评测、Python Provider、确定性/模型断言、模型对照、CI/CD 和红队。Dolly 15k 为 CC BY-SA 3.0，指令和回答由 Databricks 员工编写；来源明确提示可能存在错别字、事实错误、偏差和样本代表性限制。

## 数据集与可复现性

从 15,011 条原始记录中按固定种子 `20261126` 分层选择 80 条：

| 类别 | 数量 |
|---|---:|
| creative_writing | 20 |
| brainstorming | 15 |
| summarization | 15 |
| information_extraction | 10 |
| closed_qa | 10 |
| classification | 10 |

原始 SHA256：`2df9083338b4abd6bceb5635764dab5d833b393b55759dffb0959b6fcbf794ec`。

样例和完整来源信息位于 `src/pea/resources/benchmarks/`。所有样例保留 `local_review_status=not_reviewed`，没有把外部回答直接当作已审核标准答案。

## 评测方法

### 公开提示词结构审计

- 原始目标是否完整保留。
- 是否有明确输出结构。
- 优化后/原始 Prompt 长度比。
- 是否机械添加 Few-shot 或简单任务角色。
- 轻量策略命中率。

### 已知标签变异测试

在公开提示词上注入确定性的英文缺陷：

- `somewhat / related stuff / etc.`：应识别歧义。
- `at least 500 words + no more than 100 words`：应识别冲突。
- 缺少输出规范：应识别输出格式问题。
- `Help me with this`：应请求必要澄清。

### Promptfoo 独立执行

Promptfoo 通过 Python Provider 调用真实 PEA 优化器，对 80 条公开样例和 2 个变异场景执行自身 `contains` 断言。PEA 内部 Evaluator 不参与 Promptfoo 判定。未配置外部模型，未产生 API 费用。

## 修复前后结果

| 指标 | 修复前 | 修复后 |
|---|---:|---:|
| 公开样例目标保留 | 100% | 100% |
| 输出结构 | 100% | 100% |
| 缺少输出格式检测 | 100% | 100% |
| 英文歧义检测 | 0% | 100% |
| 英文长度冲突检测 | 0% | 100% |
| 英文模糊需求澄清 | 0% | 100% |
| 无示例 Few-shot | 0% | 0% |
| 简单任务角色添加 | 0% | 0% |
| 平均 Prompt 膨胀 | 1.4058× | 1.4058× |
| 中位 Prompt 膨胀 | 1.2344× | 1.2344× |
| Promptfoo | 80/82 | **82/82** |

原始结果保存在 `benchmarks/results/harness_before.json`、`harness_after.json` 和 `promptfoo_summary.json`。

## 根据结果完成的优化

1. 增加英文模糊需求、约束和歧义表达识别。
2. 增加英文长度上下限冲突检测，并同步动态长度评估。
3. 对高风险歧义生成明确的解释、假设和范围控制要求。
4. 已存在于原目标中的约束不再重复抄写，避免为提高检测率增加 Prompt 膨胀。
5. 增加可复现外部数据导入、来源哈希、许可证和 Promptfoo 桥接测试。

中间版本曾因英文约束重复导致平均膨胀升至 1.4734×；最终去重后恢复到 1.4058×，82/82 仍保持。

## 与 Promptfoo 的能力对照

| 维度 | PEA 当前状态 | Promptfoo 参照 |
|---|---|---|
| 主要定位 | Prompt 诊断、生成、评估和迭代 | 评测、模型比较和红队 |
| 人工澄清 | 内置 interrupt/resume | 不是核心工作流 |
| 自动修订 | 内置 Refiner 和三次上限 | 主要由用户/外部优化器实现 |
| 本地断言 | 基础格式、长度、引用检查 | 更广泛的确定性、模型和自定义断言 |
| 红队 | 尚未实现 | 核心能力 |
| Provider 生态 | OpenAI、Anthropic、Mock、OpenAI-compatible | 大量模型与应用 Provider |
| 历史与版本 | SQLite、diff、导出 | Eval 结果与分享 UI，定位不同 |
| 成本与调用上限 | 进程内预算、重试和基线复用 | cost/latency 断言与缓存等 |
| CI/独立执行 | 本次新增 Promptfoo 桥接 | 成熟 CLI 和 CI/CD |
| 语义质量 | 未验证，需真实模型和人工复核 | 支持模型评分，但仍需校准与人工证据 |

后续 LLM 子 Agent 语义联调发现长参考上下文会干扰任务分类与复杂度；已分离指令与 Context 分析并复测。两轮报告位于 `benchmarks/results/llm_subagent_dev_simulation*.json`，该模拟不构成生产 API 质量证明。

## 后续优先级

真实质量评测的防泄漏切分与协议见 `docs/REAL_QUALITY_EVALUATION.md`。旧 80 条只能作为开发数据，最终测试集已独立锁定。

1. 用 OpenAI-compatible 实际服务运行经审核样例，比较原始、通用和自适应三组输出。
2. 增加参考答案指标与人工成对偏好，校准任何 LLM Judge，禁止自评直接形成质量结论。
3. 复用 Promptfoo 的红队、自定义断言和 CI，而不是重复建设成熟能力。
4. 增加语言一致的生成模板；当前英文 Prompt 仍可能得到中文脚手架。
5. 将内存 Checkpointer 替换为持久化实现，支持跨进程澄清恢复。
