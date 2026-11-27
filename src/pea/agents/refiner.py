from pea.models import (
    EvaluationReport,
    SelectedStrategy,
    StrategyPlan,
    StrategyType,
)
from pea.strategies import StrategyLibrary


class Refiner:
    def __init__(self, library: StrategyLibrary | None = None) -> None:
        self._library = library or StrategyLibrary()

    def refine(
        self,
        plan: StrategyPlan,
        evaluation: EvaluationReport,
    ) -> tuple[StrategyPlan, list[str]]:
        selected = list(plan.selected)
        notes = []

        def ensure(strategy: StrategyType, reason: str) -> None:
            if any(item.strategy == strategy for item in selected):
                return
            definition = self._library.get(strategy)
            selected.append(
                SelectedStrategy(
                    strategy=strategy,
                    reason=reason,
                    expected_cost=definition.expected_cost,
                )
            )

        for metric in evaluation.metrics:
            if metric.passed:
                continue
            notes.append(f"修复 {metric.name}：{metric.details}")
            if "format" in metric.name or "structure" in metric.name:
                ensure(
                    StrategyType.STRUCTURED_OUTPUT,
                    "评估发现输出结构不合格，需要重新明确格式和必要字段",
                )
            if "constraint" in metric.name or "length" in metric.name:
                ensure(
                    StrategyType.CONSTRAINT_BASED,
                    "评估发现约束未满足，需要将失败项转化为明确修订任务",
                )

        if not notes:
            notes.append("根据评估报告重新检查目标、输出和约束，不只改写措辞")
        updated = StrategyPlan(
            selected=selected,
            lightweight=False,
            rationale=f"根据第 {len(evaluation.metrics)} 项评估指标反馈进行有界修订",
        )
        return updated, list(dict.fromkeys(notes))
