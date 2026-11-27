from decimal import Decimal
import logging

from pea.config import Settings, get_settings
from pea.evaluation.benchmark import validate_benchmark
from pea.evaluation.evaluator import PromptEvaluator
from pea.evaluation.grader import (
    BenchmarkGrader,
    is_accuracy_metric,
    is_constraint_metric,
    is_format_metric,
)
from pea.exceptions import BudgetExceededError, ConfigurationError, LLMError
from pea.gateway import LLMGateway
from pea.models import (
    ChatMessage,
    CompletionRequest,
    CompletionResponse,
    PromptOptimizationRequest,
    Provider,
    WorkflowStatus,
)
from pea.models.benchmark import (
    BenchmarkTask,
    ExperimentRecord,
    ExperimentReport,
    ExperimentStatus,
    GroupExperimentResult,
    GroupName,
    GroupSummary,
    ModelExecution,
    RunScore,
)
from pea.models.workflow import EvaluationMetric
from pea.workflow import WorkflowRunner

logger = logging.getLogger(__name__)


class ExperimentRunner:
    def __init__(
        self,
        gateway: LLMGateway,
        *,
        settings: Settings | None = None,
        grader: BenchmarkGrader | None = None,
        threshold: float = 0.85,
    ) -> None:
        self._gateway = gateway
        self._settings = settings or get_settings()
        self._grader = grader or BenchmarkGrader()
        self._threshold = threshold

    def run(
        self,
        tasks: list[BenchmarkTask],
        *,
        provider: Provider = Provider.MOCK,
        repetitions: int = 1,
        max_tasks: int | None = None,
        allow_draft: bool = False,
    ) -> ExperimentReport:
        if not 1 <= repetitions <= 5:
            raise ValueError("repetitions must be between 1 and 5")
        if max_tasks is not None and max_tasks <= 0:
            raise ValueError("max_tasks must be positive")
        if not tasks:
            raise ValueError("at least one benchmark task is required")

        dataset_reviewed = validate_benchmark(tasks).ready_for_real_model_experiments
        selected = tasks[:max_tasks] if max_tasks is not None else tasks
        selected_reviewed = all(
            task.review_status.value == "approved" for task in selected
        )
        if not selected_reviewed:
            if not allow_draft:
                raise ConfigurationError("draft benchmark tasks require allow_draft=True")
            if provider != Provider.MOCK:
                raise ConfigurationError("unreviewed benchmark tasks can only run with Mock")

        config = self._settings.provider_config(provider)
        warnings = ["comparisons are limited to encoded checks and require human semantic review"]
        if not selected_reviewed:
            warnings.append("draft tasks were used; no quality improvement claim is allowed")
        if repetitions == 1:
            warnings.append("multiple-run stability was not measured")

        records: list[ExperimentRecord] = []
        status = ExperimentStatus.COMPLETED
        for task in selected:
            try:
                groups = {
                    group: self._run_group(
                        task,
                        group,
                        provider,
                        config.model,
                        repetitions,
                    )
                    for group in GroupName
                }
                records.append(
                    ExperimentRecord(
                        task_id=task.task_id,
                        category=task.category,
                        groups=groups,
                    )
                )
            except BudgetExceededError as error:
                logger.warning(
                    "benchmark budget exhausted task=%s error_type=%s",
                    task.task_id,
                    type(error).__name__,
                )
                status = ExperimentStatus.BUDGET_EXHAUSTED
                warnings.append(f"budget exhausted before completing {task.task_id}")
                break

        if status == ExperimentStatus.COMPLETED and any(
            execution.error
            for record in records
            for group in record.groups.values()
            for execution in group.runs
        ):
            status = ExperimentStatus.COMPLETED_WITH_ERRORS

        summaries = self._summaries(records)
        quality_claim_allowed = (
            dataset_reviewed
            and len(records) == 100
            and provider != Provider.MOCK
            and status == ExperimentStatus.COMPLETED
            and all(
                not score.unverified_aspects
                for record in records
                for group in record.groups.values()
                for score in group.scores
            )
        )
        return ExperimentReport(
            status=status,
            dataset_reviewed=dataset_reviewed,
            provider=provider,
            model=config.model,
            repetitions=repetitions,
            records=records,
            summaries=summaries,
            quality_claim_allowed=quality_claim_allowed,
            warnings=warnings,
        )

    def _run_group(
        self,
        task: BenchmarkTask,
        group: GroupName,
        provider: Provider,
        model: str,
        repetitions: int,
    ) -> GroupExperimentResult:
        executions = [
            self._execute_group(task, group, provider, model)
            for _ in range(repetitions)
        ]
        scores = [self._grader.grade(task, execution.output) for execution in executions]
        outputs = [execution.output for execution in executions]
        if len(executions) == 1:
            stability = None
        elif any(output is None for output in outputs):
            stability = 0.0
        else:
            stability = float(len(set(outputs)) == 1)
        return GroupExperimentResult(
            runs=executions,
            scores=scores,
            average_score=sum(score.score for score in scores) / len(scores),
            stability_score=stability,
            total_tokens=self._total_tokens(executions),
            total_cost_usd=self._total_cost(executions),
            total_latency_seconds=sum(item.latency_seconds for item in executions),
        )

    def _execute_group(
        self,
        task: BenchmarkTask,
        group: GroupName,
        provider: Provider,
        model: str,
    ) -> ModelExecution:
        try:
            if group == GroupName.ADAPTIVE:
                return self._execute_adaptive(task, provider, model)
            prompt = (
                self._original_prompt(task)
                if group == GroupName.ORIGINAL
                else self._generic_prompt(task)
            )
            response = self._gateway.complete(
                CompletionRequest(
                    provider=provider,
                    messages=[ChatMessage(role="user", content=prompt)],
                    temperature=0.0,
                )
            )
            return self._from_response(response)
        except BudgetExceededError:
            raise
        except LLMError as error:
            return ModelExecution(
                provider=provider,
                model=model,
                error=type(error).__name__,
            )

    def _execute_adaptive(
        self,
        task: BenchmarkTask,
        provider: Provider,
        model: str,
    ) -> ModelExecution:
        runner = WorkflowRunner(
            evaluator=PromptEvaluator(self._gateway, threshold=self._threshold)
        )
        result = runner.run(
            PromptOptimizationRequest(
                user_request=task.user_request,
                raw_prompt=task.raw_prompt,
            ),
            dynamic_evaluation=True,
            provider=provider,
        )
        evaluation = result.final_evaluation
        if (
            result.status != WorkflowStatus.COMPLETED
            or result.optimization is None
            or evaluation is None
        ):
            return ModelExecution(
                provider=provider,
                model=model,
                error=f"workflow_{result.status.value}",
            )
        if evaluation.dynamic_status != "completed":
            return ModelExecution(
                provider=provider,
                model=model,
                workflow_iterations=len(result.iterations),
                error="dynamic_evaluation_unavailable",
                usage=evaluation.usage,
                cost_usd=evaluation.cost_usd,
                latency_seconds=evaluation.latency_seconds,
            )
        return ModelExecution(
            provider=provider,
            model=model,
            output=evaluation.optimized_output,
            usage=evaluation.usage,
            cost_usd=evaluation.cost_usd,
            latency_seconds=evaluation.latency_seconds,
            workflow_iterations=len(result.iterations),
        )

    @staticmethod
    def _original_prompt(task: BenchmarkTask) -> str:
        return task.raw_prompt or task.user_request

    @staticmethod
    def _generic_prompt(task: BenchmarkTask) -> str:
        requirements = "\n".join(f"- {item}" for item in task.output_requirements)
        constraints = "\n".join(f"- {item}" for item in task.constraints)
        return (
            f"请清晰、准确地完成以下任务：\n{ExperimentRunner._original_prompt(task)}\n\n"
            f"输出要求：\n{requirements}\n\n约束：\n{constraints}\n"
            "直接交付完整结果，不要解释执行过程。"
        )

    @staticmethod
    def _from_response(response: CompletionResponse) -> ModelExecution:
        return ModelExecution(
            provider=response.provider,
            model=response.model,
            output=response.content,
            usage=response.usage,
            cost_usd=response.cost_usd,
            latency_seconds=response.latency_seconds,
            attempts=response.attempts,
        )

    @staticmethod
    def _total_tokens(executions: list[ModelExecution]) -> int | None:
        if any(item.usage is None or item.usage.total_tokens is None for item in executions):
            return None
        return sum(item.usage.total_tokens for item in executions if item.usage)

    @staticmethod
    def _total_cost(executions: list[ModelExecution]) -> Decimal | None:
        if any(item.cost_usd is None for item in executions):
            return None
        return sum((item.cost_usd for item in executions), Decimal("0"))

    def _summaries(
        self,
        records: list[ExperimentRecord],
    ) -> dict[GroupName, GroupSummary]:
        return {
            name: self._group_summary(
                name,
                [record.groups[name] for record in records],
            )
            for name in GroupName
        }

    @staticmethod
    def _group_summary(
        name: GroupName,
        groups: list[GroupExperimentResult],
    ) -> GroupSummary:
        scores = [score for group in groups for score in group.scores]
        metrics = [metric for score in scores for metric in score.metrics]
        instruction_metrics = [
            metric
            for metric in metrics
            if not is_format_metric(metric) and not is_accuracy_metric(metric)
        ]
        format_metrics = [metric for metric in metrics if is_format_metric(metric)]
        constraint_metrics = [metric for metric in metrics if is_constraint_metric(metric)]
        accuracy_metrics = [metric for metric in metrics if is_accuracy_metric(metric)]
        stability_values = [
            group.stability_score
            for group in groups
            if group.stability_score is not None
        ]
        return GroupSummary(
            group=name,
            tasks=len(groups),
            average_quality=(
                sum(group.average_score for group in groups) / len(groups) if groups else 0.0
            ),
            average_stability=(
                sum(stability_values) / len(stability_values) if stability_values else None
            ),
            instruction_following_rate=ExperimentRunner._pass_rate(instruction_metrics),
            output_format_pass_rate=ExperimentRunner._pass_rate(format_metrics),
            constraint_following_rate=ExperimentRunner._pass_rate(constraint_metrics),
            content_accuracy_rate=(
                ExperimentRunner._pass_rate(accuracy_metrics) if accuracy_metrics else None
            ),
            total_tokens=ExperimentRunner._sum_optional(
                [group.total_tokens for group in groups]
            ),
            total_cost_usd=ExperimentRunner._sum_optional_decimal(
                [group.total_cost_usd for group in groups]
            ),
            total_latency_seconds=sum(group.total_latency_seconds for group in groups),
        )

    @staticmethod
    def _pass_rate(metrics: list[EvaluationMetric]) -> float:
        return (
            sum(metric.passed for metric in metrics) / len(metrics)
            if metrics
            else 0.0
        )

    @staticmethod
    def _sum_optional(values: list[int | None]) -> int | None:
        if any(value is None for value in values):
            return None
        return sum(value for value in values if value is not None)

    @staticmethod
    def _sum_optional_decimal(values: list[Decimal | None]) -> Decimal | None:
        if any(value is None for value in values):
            return None
        return sum((value for value in values if value is not None), Decimal("0"))
