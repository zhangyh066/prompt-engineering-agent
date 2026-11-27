# 外部数据集来源

## Databricks Dolly 15k 公共样例

- 来源：https://huggingface.co/datasets/databricks/databricks-dolly-15k
- 原始文件：https://huggingface.co/datasets/databricks/databricks-dolly-15k/resolve/main/databricks-dolly-15k.jsonl
- 许可：CC BY-SA 3.0
- 许可文本：https://creativecommons.org/licenses/by-sa/3.0/
- 原始作者：Databricks 员工。
- PEA 修改：按长度过滤、固定种子分层抽样、转换为审计 schema，并保留原始指令、上下文和回答。
- 原始 SHA256：`2df9083338b4abd6bceb5635764dab5d833b393b55759dffb0959b6fcbf794ec`。

适配后的 80 条样例按 CC BY-SA 3.0 使用，详细转换记录见 `src/pea/resources/benchmarks/dolly_public_sample.provenance.json`。本地审核状态保持 `not_reviewed`，来源回答可能存在错误、偏差或代表性限制。

## No Robots（已调研，当前未引入）

- 页面：https://huggingface.co/datasets/HuggingFaceH4/no_robots
- 许可：CC BY-NC 4.0。
- 当前未引入原因：本轮优先使用许可更宽松的 Dolly，并避免在结构审计中额外引入多轮对话归一化。后续使用必须单独保留非商业许可边界。

## 不建议直接作为质量金标的来源

社区 Awesome Prompts、角色扮演合集和未经审核的模型生成指令集可以用于鲁棒性测试，但通常没有可靠参考答案，不应直接用于声称任务质量提升。
