from pea.models import (
    Complexity,
    DiagnosticDimension,
    IntentAnalysis,
    PromptDiagnosis,
    SelectedStrategy,
    StrategyPlan,
    StrategyType,
    TaskType,
)
from pea.models.policy import StrategyPolicy
from pea.strategies.library import StrategyLibrary


class StrategyPlanner:
    def __init__(
        self,
        library: StrategyLibrary | None = None,
        policy: StrategyPolicy | None = None,
    ) -> None:
        self._library = library or StrategyLibrary()
        self._policy = policy or StrategyPolicy()

    def plan(
        self,
        intent: IntentAnalysis,
        diagnosis: PromptDiagnosis,
    ) -> StrategyPlan:
        selected: list[SelectedStrategy] = []

        def add(strategy: StrategyType, reason: str) -> None:
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

        add(
            StrategyType.ZERO_SHOT,
            "以清晰的直接指令作为最小优化基线，不默认添加示例或角色",
        )

        scores = {
            assessment.dimension: assessment.score
            for assessment in diagnosis.assessments
        }
        if intent.constraints or scores[DiagnosticDimension.CONSTRAINTS] <= 2:
            add(
                StrategyType.CONSTRAINT_BASED,
                "保留用户约束；如有冲突则明确要求指出，而不是擅自取舍",
            )
        if self._policy.structured_output and (
            intent.task_type in {TaskType.DATA_ANALYSIS, TaskType.RESEARCH}
            or scores[DiagnosticDimension.OUTPUT_FORMAT] <= 2
        ):
            add(
                StrategyType.STRUCTURED_OUTPUT,
                "将交付物、输出格式和必要内容转化为可检查要求",
            )
        if self._policy.task_decomposition and (
            intent.complexity == Complexity.COMPLEX
            or (
                intent.complexity == Complexity.MODERATE
                and scores[DiagnosticDimension.TASK_DECOMPOSITION] <= 2
            )
        ):
            add(
                StrategyType.TASK_DECOMPOSITION,
                "任务包含多个环节，明确处理步骤以降低遗漏风险",
            )
        if self._policy.few_shot and intent.examples:
            add(
                StrategyType.FEW_SHOT,
                "原始材料包含实际示例，可复用于稳定风格和格式",
            )
        if self._policy.role_prompting and (
            intent.complexity == Complexity.COMPLEX
            and intent.task_type in {TaskType.DATA_ANALYSIS, TaskType.RESEARCH}
            and scores[DiagnosticDimension.ROLE_SETTING] < 5
        ):
            add(
                StrategyType.ROLE_PROMPTING,
                "复杂专业任务需要与目标直接相关的分析视角",
            )
        if self._policy.react and intent.requires_tools:
            add(
                StrategyType.REACT,
                "任务明确依赖最新资料或检索，只有在工具可用时才执行证据获取",
            )
        elif self._policy.self_critique and (
            intent.complexity == Complexity.COMPLEX
            and intent.task_type in {TaskType.DATA_ANALYSIS, TaskType.RESEARCH}
            and diagnosis.overall_score < 70
        ):
            add(
                StrategyType.SELF_CRITIQUE,
                "复杂专业任务且原 Prompt 风险较高，增加不展示推理过程的提交前检查",
            )

        lightweight = not diagnosis.needs_optimization or (
            intent.complexity == Complexity.SIMPLE and len(selected) <= 2
        )
        return StrategyPlan(
            selected=selected,
            lightweight=lightweight,
            rationale=(
                f"选择 {len(selected)} 项策略；依据任务类型、复杂度和诊断缺陷，"
                "未机械叠加不适用策略"
            ),
        )
