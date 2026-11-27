from decimal import Decimal
import json
import re

from pea.agents._text import goal_is_preserved
from pea.exceptions import LLMError
from pea.gateway import LLMGateway
from pea.models import (
    ChatMessage,
    CompletionRequest,
    CompletionResponse,
    EvaluationMetric,
    EvaluationReport,
    GeneratedPrompt,
    IntentAnalysis,
    PromptOptimizationRequest,
    Provider,
    TokenUsage,
)


class PromptEvaluator:
    def __init__(
        self,
        gateway: LLMGateway | None = None,
        *,
        threshold: float = 0.85,
    ) -> None:
        if not 0 < threshold <= 1:
            raise ValueError("evaluation threshold must be in (0, 1]")
        self._gateway = gateway
        self._threshold = threshold

    def evaluate(
        self,
        request: PromptOptimizationRequest,
        intent: IntentAnalysis,
        generated: GeneratedPrompt,
        *,
        dynamic: bool = False,
        provider: Provider = Provider.MOCK,
        baseline_response: CompletionResponse | None = None,
    ) -> EvaluationReport:
        static_metrics = self._static_metrics(intent, generated)
        static_score = sum(item.score for item in static_metrics) / len(static_metrics)
        static_passed = static_score >= self._threshold
        issues = [item.details for item in static_metrics if not item.passed]

        if not dynamic:
            return EvaluationReport(
                score=static_score,
                threshold=self._threshold,
                passed=static_passed,
                static_score=static_score,
                metrics=static_metrics,
                issues=issues,
                unverified_aspects=[
                    "dynamic_execution",
                    "task_completion",
                    "content_accuracy",
                ],
            )

        if self._gateway is None:
            return EvaluationReport(
                score=static_score,
                threshold=self._threshold,
                passed=static_passed,
                static_score=static_score,
                metrics=static_metrics,
                issues=issues,
                warnings=["dynamic evaluation was requested but no gateway is configured"],
                unverified_aspects=["dynamic_execution", "task_completion", "content_accuracy"],
            )

        baseline = baseline_response
        try:
            if baseline is None:
                baseline = self._execute(
                    request.raw_prompt or request.user_request,
                    provider,
                )
            optimized = self._execute(generated.content, provider)
        except LLMError as error:
            return EvaluationReport(
                score=static_score,
                threshold=self._threshold,
                passed=static_passed,
                static_score=static_score,
                metrics=static_metrics,
                issues=issues,
                dynamic_status="failed",
                provider=provider,
                baseline_execution=baseline,
                warnings=[
                    f"dynamic evaluation failed with {type(error).__name__}; "
                    "static result is returned and earlier attempts may have consumed cost"
                ],
                unverified_aspects=[
                    "dynamic_execution",
                    "task_completion",
                    "content_accuracy",
                ],
            )

        dynamic_metrics = self._dynamic_metrics(optimized.content, intent)
        baseline_metrics = self._dynamic_metrics(baseline.content, intent)
        dynamic_score = self._mean(dynamic_metrics)
        baseline_score = self._mean(baseline_metrics)
        issues.extend(item.details for item in dynamic_metrics if not item.passed)
        passed = static_passed and dynamic_score >= self._threshold
        return EvaluationReport(
            score=(static_score + dynamic_score) / 2,
            threshold=self._threshold,
            passed=passed,
            static_score=static_score,
            dynamic_score=dynamic_score,
            baseline_dynamic_score=baseline_score,
            metrics=[*static_metrics, *dynamic_metrics],
            issues=issues,
            dynamic_status="completed",
            provider=provider,
            optimized_output=optimized.content,
            baseline_output=baseline.content,
            baseline_execution=baseline,
            usage=self._aggregate_usage(baseline, optimized),
            cost_usd=self._aggregate_cost(baseline, optimized),
            latency_seconds=baseline.latency_seconds + optimized.latency_seconds,
            unverified_aspects=["task_completion", "content_accuracy"],
        )

    def _static_metrics(
        self,
        intent: IntentAnalysis,
        generated: GeneratedPrompt,
    ) -> list[EvaluationMetric]:
        content = generated.content
        missing_constraints = [
            item for item in intent.constraints if item not in content
        ]
        missing_outputs = [
            item for item in intent.output_requirements if item not in content
        ]
        goal_preserved = goal_is_preserved(intent.goal, content)
        return [
            EvaluationMetric(
                name="goal_preservation",
                score=float(goal_preserved),
                passed=goal_preserved,
                details=(
                    "原始任务目标已保留"
                    if goal_preserved
                    else "优化 Prompt 未完整保留原始任务目标"
                ),
                source="static",
            ),
            EvaluationMetric(
                name="constraint_preservation",
                score=float(not missing_constraints),
                passed=not missing_constraints,
                details=(
                    "用户约束已保留"
                    if not missing_constraints
                    else f"缺少约束：{missing_constraints}"
                ),
                source="static",
            ),
            EvaluationMetric(
                name="output_structure",
                score=float("## 输出要求" in content and not missing_outputs),
                passed="## 输出要求" in content and not missing_outputs,
                details=(
                    "输出要求完整"
                    if "## 输出要求" in content and not missing_outputs
                    else f"输出结构或要求缺失：{missing_outputs}"
                ),
                source="static",
            ),
            EvaluationMetric(
                name="change_rationale",
                score=float(bool(generated.changes) and all(item.reason for item in generated.changes)),
                passed=bool(generated.changes) and all(item.reason for item in generated.changes),
                details="每项修改均应有明确理由",
                source="static",
            ),
        ]

    def _execute(self, prompt: str, provider: Provider) -> CompletionResponse:
        return self._gateway.complete(
            CompletionRequest(
                provider=provider,
                messages=[ChatMessage(role="user", content=prompt)],
            )
        )

    @staticmethod
    def _dynamic_metrics(
        output: str,
        intent: IntentAnalysis,
    ) -> list[EvaluationMetric]:
        metrics = [
            EvaluationMetric(
                name="dynamic_non_empty",
                score=float(bool(output.strip())),
                passed=bool(output.strip()),
                details="执行结果必须非空",
                source="dynamic",
            )
        ]
        requirements = " ".join(intent.output_requirements).lower()
        if "json" in requirements:
            try:
                json.loads(output)
                valid_json = True
            except (json.JSONDecodeError, TypeError):
                valid_json = False
            metrics.append(
                EvaluationMetric(
                    name="dynamic_json_format",
                    score=float(valid_json),
                    passed=valid_json,
                    details="执行结果必须是合法 JSON",
                    source="dynamic",
                )
            )
        if "markdown" in requirements:
            valid_markdown = any(marker in output for marker in ("#", "- ", "|", "```"))
            metrics.append(
                EvaluationMetric(
                    name="dynamic_markdown_format",
                    score=float(valid_markdown),
                    passed=valid_markdown,
                    details="执行结果必须包含 Markdown 结构",
                    source="dynamic",
                )
            )
        if "表格" in requirements:
            valid_table = "|" in output and "\n" in output
            metrics.append(
                EvaluationMetric(
                    name="dynamic_table_format",
                    score=float(valid_table),
                    passed=valid_table,
                    details="执行结果必须包含表格结构",
                    source="dynamic",
                )
            )

        minimum, maximum, unit = PromptEvaluator._length_limits(intent.constraints)
        if minimum is not None or maximum is not None:
            observed = len(output.split()) if unit == "word" else len(output.strip())
            valid_length = (minimum is None or observed >= minimum) and (
                maximum is None or observed <= maximum
            )
            metrics.append(
                EvaluationMetric(
                    name="dynamic_length_constraint",
                    score=float(valid_length),
                    passed=valid_length,
                    details=(
                        f"长度检查：实际 {observed}，最小 {minimum}，最大 {maximum}，单位 {unit}"
                    ),
                    source="dynamic",
                )
            )
        return metrics

    @staticmethod
    def _length_limits(constraints: list[str]) -> tuple[int | None, int | None, str]:
        text = " ".join(constraints)
        unit = "word" if re.search(r"词|words?", text, re.IGNORECASE) else "character"
        units = r"(?:字|词|words?|characters?)"
        maximums = [
            int(value)
            for pair in re.findall(
                rf"(?:不超过|最多|至多|小于|no more than|at most|maximum|max|less than|under)\s*(\d+)\s*{units}|(\d+)\s*{units}\s*(?:以内|以下|之内)",
                text,
                re.IGNORECASE,
            )
            for value in pair
            if value
        ]
        minimums = [
            int(value)
            for pair in re.findall(
                rf"(?:至少|不少于|大于|(?<!不)超过|at least|no less than|minimum|min)\s*(\d+)\s*{units}|(\d+)\s*{units}\s*以上",
                text,
                re.IGNORECASE,
            )
            for value in pair
            if value
        ]
        return (
            max(minimums) if minimums else None,
            min(maximums) if maximums else None,
            unit,
        )

    @staticmethod
    def _mean(metrics: list[EvaluationMetric]) -> float:
        return sum(item.score for item in metrics) / len(metrics)

    @staticmethod
    def _aggregate_usage(
        baseline: CompletionResponse,
        optimized: CompletionResponse,
    ) -> TokenUsage:
        def total(name: str) -> int | None:
            values = [getattr(baseline.usage, name), getattr(optimized.usage, name)]
            return None if any(value is None for value in values) else sum(values)

        return TokenUsage(
            prompt_tokens=total("prompt_tokens"),
            completion_tokens=total("completion_tokens"),
            total_tokens=total("total_tokens"),
            source=optimized.usage.source,
        )

    @staticmethod
    def _aggregate_cost(
        baseline: CompletionResponse,
        optimized: CompletionResponse,
    ) -> Decimal | None:
        if baseline.cost_usd is None or optimized.cost_usd is None:
            return None
        return baseline.cost_usd + optimized.cost_usd
