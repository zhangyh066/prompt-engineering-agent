# PEA Benchmark 数据集

## 当前状态

`src/pea/resources/benchmarks/tasks_draft.jsonl` 包含 100 条任务草稿，全部标记为 `pending_human_review`。这些任务由开发 Agent 起草，**尚未经过人工审核，不能作为标准答案或真实质量结论的依据**。

| 类型 | 数量 |
|---|---:|
| 商务写作 | 20 |
| 内容创作 | 20 |
| 数据分析 | 15 |
| 信息总结 | 15 |
| 邮件与办公 | 15 |
| 资料调研 | 15 |
| 合计 | 100 |

## 每条任务包含

- `user_request`：原始需求。
- `raw_prompt`：原始 Prompt，可为 `null`。
- `target_task`：目标任务。
- `output_requirements`：输出要求。
- `constraints`：必须遵守的约束。
- `evaluation_criteria`：供人工审核的自然语言评价标准。
- `checks`：可程序化执行的非空、格式、长度、包含、正则或参考答案检查。
- `reference_answer`：适用时的参考结果；草稿状态下不具有标准答案效力。
- `review_status`、`reviewer`、`reviewed_at`：审核状态与审计信息。

## 人工审核要求

审核人需要逐条检查：

1. 任务是否真实、独立、清晰且属于声明类别。
2. 原始 Prompt 与需求是否符合对照实验设计。
3. 输出要求和约束是否必要、无意外冲突。
4. 评价标准是否覆盖任务完成度、指令遵循、格式、准确性和约束。
5. 机器检查是否确实可验证，不以关键词检查冒充语义质量。
6. 参考答案是否正确、可复现，并适用于任务；否则置为 `null` 并移除对应检查。
7. 不涉及未经授权的隐私、机密或有害内容。

审核通过后，逐条设置：

```json
{
  "review_status": "approved",
  "reviewer": "真实审核人标识",
  "reviewed_at": "ISO 8601 时间"
}
```

不能只修改状态而省略审核人或时间；Pydantic 会拒绝。只有在 100 条全部满足审核要求且分布正确时，`ready_for_real_model_experiments` 才为 `true`。

## 本地校验

```bash
uv run pea --validate-benchmark
```

该命令只解析和校验数据，不执行模型调用。

## 对照实验边界

- A：原始 Prompt。
- B：通用优化 Prompt，不使用任务分类。
- C：任务分类、策略选择、评估和有界迭代。
- 三组使用相同 Gateway 提供商、模型和温度，均不提供外部工具。
- 草稿只能显式使用 Mock 运行；Mock 报告中的 `quality_claim_allowed` 必须为 `false`。
- 即使真实模型运行完成，程序化分数也只覆盖编码检查；语义任务完成度仍需人工复核，不能仅凭 LLM 自评声称优化有效。
