from pea.models.history import RunDetail


class ResultExporter:
    @staticmethod
    def to_json(detail: RunDetail) -> str:
        return detail.model_dump_json(indent=2)

    @staticmethod
    def to_markdown(detail: RunDetail) -> str:
        summary = detail.summary
        sections = [
            "# Prompt Engineering Agent 运行报告",
            f"- 运行 ID：`{summary.run_id}`",
            f"- 状态：{summary.status.value}",
            f"- 任务类型：{summary.task_type.value if summary.task_type else '待定'}",
            f"- 提供商 / 模型：{summary.provider.value} / {summary.model}",
            f"- 版本数：{summary.version_count}",
            f"- 总 Token：{summary.total_tokens if summary.total_tokens is not None else '未知'}",
            f"- 总成本（USD）：{summary.total_cost_usd if summary.total_cost_usd is not None else '未知'}",
            f"- 执行耗时：{summary.total_latency_seconds:.6f}s",
            "## 原始需求",
            summary.user_request,
        ]
        if summary.raw_prompt:
            sections.extend(["## 原始 Prompt", summary.raw_prompt])
        if detail.optimization is not None:
            sections.extend(
                [
                    "## 最终最佳 Prompt",
                    detail.optimization.generated_prompt.content,
                    "## 修改理由",
                    *[
                        f"- {change.description}：{change.reason}"
                        for change in detail.optimization.generated_prompt.changes
                    ],
                ]
            )
        sections.append("## 版本评估")
        for version in detail.versions:
            sections.extend(
                [
                    f"### 版本 {version.version}{'（最佳）' if version.is_best else ''}",
                    f"- 得分：{version.evaluation.score:.4f}",
                    f"- 达标：{version.evaluation.passed}",
                    f"- 动态评估：{version.evaluation.dynamic_status}",
                    f"- 策略：{', '.join(item.value for item in version.strategies)}",
                    "```text",
                    version.content,
                    "```",
                ]
            )
        if summary.warnings:
            sections.extend(["## 警告", *[f"- {item}" for item in summary.warnings]])
        if summary.error:
            sections.extend(["## 错误", summary.error])
        return "\n\n".join(sections)
