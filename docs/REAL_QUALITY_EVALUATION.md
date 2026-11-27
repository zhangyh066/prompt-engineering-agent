# 真实任务质量评测与数据驱动优化

## 核心结论

可以用 Dolly 15k 提升 PEA，但必须把“用于优化的数据”和“用于证明提升的数据”分开。此前 80 条公共样例已经用于英文缺陷修复，只能算开发数据，不能用于最终质量声明。

当前已完成防泄漏切分和参考指标，**尚未执行真实模型策略搜索，因此没有正确率或可用性提升的实证结论**。

## 已锁定的数据切分

固定种子：`20261126`。按标准化指令与上下文去重，并排除旧 80 条及其近重复。

| 集合 | 数量 | 允许用途 |
|---|---:|---|
| train | 10,306 | 策略搜索、模板候选、Few-shot 检索和成本调参 |
| dev | 2,208 | 选择策略、阈值、版本和早停 |
| test | 2,214 | 最终一次性评估，禁止调参 |
| legacy dev | 80 | 已使用过的开发样例，不能作为最终测试 |

另移除重复 198 条、与旧开发样例重叠 5 条。切分覆盖全部 8 个 Dolly 类别。

清单与 SHA256：`benchmarks/results/dolly_split_manifest.json`。实际文件位于被 Git 忽略的 `data/benchmark_splits/`，避免把大型生成数据隐式打包。

## 不再把 Promptfoo 当作优化产品对手

合理对照组应为：

- A：原始 Prompt。
- B：通用清晰化 Prompt。
- C：PEA 分类与策略，无迭代。
- D：PEA 完整评估迭代。
- E：真正可运行的外部优化器，例如 DSPy 优化策略或有凭证的 PromptPerfect 类产品。

Promptfoo 可独立运行断言、输出结果和执行部分外部优化器，但它本身不是自动 Prompt 优化产品。所有组必须使用相同基础模型、参数、工具和输入，完整记录 Token、成本与耗时。

## 指标不能只有一个“正确率”

| 任务 | 主要质量指标 | 辅助指标 |
|---|---|---|
| classification | Exact Match Accuracy、必要时 Macro-F1 | 格式率、失败率 |
| closed_qa | Token F1、人工事实正确性 | Exact Match、忠实上下文 |
| information_extraction | Token F1、字段/内容完整性 | 漏抽与误抽率 |
| summarization | 人工忠实性、覆盖率、简洁性偏好 | ROUGE/F1 仅作辅助 |
| creative_writing / brainstorming | 盲评可用性、指令遵循、具体性、多样性 | 参考 F1 不能代表质量 |
| general/open QA | 人工正确性、证据与有用性 | 约束、格式和稳定性 |

所有任务同时报告格式合格率、约束遵循、失败率、多次运行稳定性、Token、成本和耗时。应按类别报告并进行宏平均，避免 open QA 数量优势掩盖其他类别退化。

## 如何用 train/dev 优化 PEA

1. **离散策略搜索**：在 train 的分层小样本上搜索各任务策略组合、诊断阈值、最大迭代次数和早停条件。每次搜索受调用与费用上限约束。
2. **任务特定模板**：只保留在 train 有收益、dev 可复现的模板，不根据测试集人工改写规则。
3. **Few-shot 检索**：只从 train 检索相似示例；必须在 dev 证明收益高于额外 Token 成本，否则禁用。
4. **消融实验**：分别去掉诊断、角色、拆解、Self-critique 和 Refiner，识别真正有效组件。
5. **成本目标**：优化 `质量奖励 - λ × 成本`，同时保留质量-成本 Pareto 曲线，避免只追分不计费用。
6. **模型增强生成**：可使用 OpenAI-compatible 服务生成结构化候选，但必须保留 Pydantic 约束、原始意图和审核轨迹。
7. **版本锁定**：dev 选出唯一策略工件后锁定哈希，再在 test 上运行一次；失败结果也必须保留。

直接模仿参考回答的 Token F1 可能提升字面重合，却降低开放任务多样性，因此不能作为所有类别的统一奖励。

## 如何证明“优于其他产品”

- 同一批未见测试输入、相同基础模型和工具权限。
- 至少三次运行，报告配对 win/tie/loss、效应量和 95% 置信区间。
- 分类/问答使用配对统计检验；人工评分采用随机、盲评和评测者一致性检查。
- LLM Judge 只能作为辅助，必须先用人工标注校准，且不能与待测生成器简单共用自评。
- 同时报告成本与延迟；只有质量提升但调用成本失控，不能无条件称为更优。
- 在独立中文任务或私有近期任务上复验，降低 Dolly 公开数据被基础模型记忆的影响。

只有锁定测试集上的主要指标、置信区间和人工可用性都支持时，才能使用“优于”的表述。

成对差值、bootstrap 置信区间和 win/tie/loss 的可执行实现位于 `src/pea/evaluation/statistics.py`；人工盲评与分歧裁决规范位于 `benchmarks/HUMAN_REVIEW_RUBRIC.md`。

策略搜索实现位于 `src/pea/evaluation/policy_search.py`。它按候选 StrategyPolicy 运行相同 train/dev 样本，以 `平均参考指标 - cost_penalty × 已知成本` 排序；不完整或成本未知的候选不入选。原始基线已在候选间共享，缓存命中不计入新增调用、Token、成本或耗时；train 8 条双候选模拟调用由 32 降为 24。

## 已实现的质量执行器

`src/pea/evaluation/quality_runner.py` 使用相同 Gateway、模型和温度执行原始与 PEA 两组 Prompt，并生成逐案例与分类汇总。真实模型必须显式 `allow_real_model=True`、配置 `PEA_COST_BUDGET_USD`，且单次最多 50 条；test 输入会在任何调用前拒绝。

8 条 dev 分层样本定义在 `benchmarks/results/dev_smoke_manifest.json`。Mock 自检完成 16 次本地调用，A/B 八平，仅验证执行链路。真实首次联调可复用相同样本，成功后才能扩大 train 搜索。

成对 bootstrap 与统计解释位于 `src/pea/evaluation/statistics.py`，人工盲评规范位于 `benchmarks/HUMAN_REVIEW_RUBRIC.md`。

本地 Mock 自检：

```bash
uv run python -m pea.evaluation.quality_cli --split dev --manifest benchmarks/results/dev_smoke_manifest.json --limit 8 --output benchmarks/results/dev_smoke_mock.json
```

真实 OpenAI-compatible 联调（另需真实提供商开关和成本预算）：

```bash
uv run python -m pea.evaluation.quality_cli --split dev --manifest benchmarks/results/dev_smoke_manifest.json --provider openai --limit 8 --allow-real-model --output benchmarks/results/dev_smoke_openai.json
```

最终评估由 `src/pea/evaluation/final_runner.py` 执行：校验 test SHA256、完整同提供商/模型 dev 报告和显式确认，并追加访问日志。Mock dev 不能解锁真实模型终评；调参 QualityRunner 默认仍拒绝 test。

## 下一步真实实验配置

使用：

```bash
OPENAI_API_BASE=https://your-endpoint/v1
OPENAI_API_KEY=your-key
OPENAI_MODEL=your-model
```

先进行小样本联调和预算验证，再依次运行 train 搜索、dev 选优和 test 终评。当前没有真实凭证，本轮不会伪造搜索奖励或质量提升。
