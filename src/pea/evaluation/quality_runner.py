from collections.abc import Iterable
from decimal import Decimal
from enum import StrEnum
import random
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from pea.agents import StructuredPromptOptimizer
from pea.config import Settings, get_settings
from pea.evaluation.optimization_data import OptimizationCase, SplitName
from pea.evaluation.reference_metrics import ReferenceScore, score_reference
from pea.evaluation.statistics import PairedComparison, compare_paired_scores
from pea.exceptions import BudgetExceededError, ConfigurationError, LLMError
from pea.gateway import LLMGateway
from pea.models import (
    ChatMessage,
    CompletionRequest,
    CompletionResponse,
    PromptOptimizationRequest,
    Provider,
    TokenUsage,
)

DEFAULT_QUALITY_LIMIT = 10
DEFAULT_QUALITY_SEED = 20261126
MAX_REAL_MODEL_LIMIT = 50
SelectionMode = Literal["sequential", "stratified"]


class QualityGroup(StrEnum):
    ORIGINAL = "original"
    OPTIMIZED = "optimized"


class QualityRunStatus(StrEnum):
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    BUDGET_EXHAUSTED = "budget_exhausted"


class QualityExecutionStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    BUDGET_EXHAUSTED = "budget_exhausted"
    NOT_RUN = "not_run"


class QualityError(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    group: QualityGroup
    error_type: str
    message: str


class QualityExecution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: QualityExecutionStatus
    output: str | None = None
    score: ReferenceScore | None = None
    usage: TokenUsage | None = None
    cost_usd: Decimal | None = Field(default=None, ge=0)
    latency_seconds: float | None = Field(default=None, ge=0.0)
    attempts: int | None = Field(default=None, ge=1)
    from_cache: bool = False
    error: QualityError | None = None


class QualityCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    category: str
    split: SplitName
    original_prompt: str
    optimized_prompt: str
    original: QualityExecution
    optimized: QualityExecution


class QualityGroupSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    group: QualityGroup
    selected_cases: int = Field(ge=0)
    attempted_calls: int = Field(ge=0)
    cached_calls: int = Field(default=0, ge=0)
    completed_calls: int = Field(ge=0)
    scored_calls: int = Field(ge=0)
    average_exact_match: float | None = Field(default=None, ge=0.0, le=1.0)
    average_token_f1: float | None = Field(default=None, ge=0.0, le=1.0)
    average_primary_score: float | None = Field(default=None, ge=0.0, le=1.0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    total_cost_usd: Decimal | None = Field(default=None, ge=0)
    total_latency_seconds: float | None = Field(default=None, ge=0.0)
    errors: list[QualityError] = Field(default_factory=list)


class QualityCategorySummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: str
    case_count: int = Field(ge=0)
    groups: dict[QualityGroup, QualityGroupSummary]


class QualityReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: QualityRunStatus
    provider: Provider
    model: str
    temperature: Literal[0.0] = 0.0
    limit: int = Field(ge=1)
    split: Literal["train", "dev", "test"] | None = None
    selection: SelectionMode
    seed: int
    allow_real_model: bool
    selected_case_count: int = Field(ge=1)
    original_cache_hits: int = Field(default=0, ge=0)
    completed_case_count: int = Field(ge=0)
    cases: list[QualityCaseResult]
    group_summaries: dict[QualityGroup, QualityGroupSummary]
    categories: dict[str, QualityCategorySummary]
    paired_comparison: PairedComparison | None = None
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    total_cost_usd: Decimal | None = Field(default=None, ge=0)
    total_latency_seconds: float | None = Field(default=None, ge=0.0)
    errors: list[QualityError] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    human_review_required: Literal[True] = True
    quality_claim_allowed: Literal[False] = False
    semantic_quality_measured: Literal[False] = False


class QualityRunner:
    def __init__(
        self,
        gateway: LLMGateway,
        *,
        settings: Settings | None = None,
        optimizer: StructuredPromptOptimizer | None = None,
    ) -> None:
        self._gateway = gateway
        self._settings = settings or get_settings()
        self._optimizer = optimizer or StructuredPromptOptimizer()

    def run(
        self,
        cases: list[OptimizationCase],
        *,
        provider: Provider = Provider.MOCK,
        model: str | None = None,
        limit: int = DEFAULT_QUALITY_LIMIT,
        split: Literal["train", "dev", "test"] | None = None,
        selection: SelectionMode = "stratified",
        seed: int = DEFAULT_QUALITY_SEED,
        allow_real_model: bool = False,
        original_cache: dict[str, QualityExecution] | None = None,
        _allow_test: bool = False,
    ) -> QualityReport:
        self._validate(cases, provider, limit, allow_real_model, _allow_test)
        eligible = [case for case in cases if split is None or case.split == split]
        if not eligible:
            raise ValueError("at least one train/dev case is required")
        selected = self._select_cases(eligible, limit, selection, seed)
        config = self._settings.provider_config(provider, model)
        records = [
            QualityCaseResult(
                case_id=case.case_id,
                category=case.category,
                split=case.split,
                original_prompt=case.prompt,
                optimized_prompt=self._optimized_prompt(case),
                original=QualityExecution(status=QualityExecutionStatus.NOT_RUN),
                optimized=QualityExecution(status=QualityExecutionStatus.NOT_RUN),
            )
            for case in selected
        ]

        budget_case_id: str | None = None
        for index, case in enumerate(selected):
            record = records[index]
            prompts = {
                QualityGroup.ORIGINAL: record.original_prompt,
                QualityGroup.OPTIMIZED: record.optimized_prompt,
            }
            for group in (QualityGroup.ORIGINAL, QualityGroup.OPTIMIZED):
                cached = (
                    original_cache.get(case.case_id)
                    if group == QualityGroup.ORIGINAL and original_cache is not None
                    else None
                )
                if cached is not None:
                    execution = cached.model_copy(update={"from_cache": True})
                else:
                    execution = self._execute(
                        case,
                        group,
                        prompts[group],
                        provider,
                        config.model,
                    )
                    if (
                        group == QualityGroup.ORIGINAL
                        and original_cache is not None
                        and execution.status == QualityExecutionStatus.COMPLETED
                    ):
                        original_cache[case.case_id] = execution
                records[index] = record = record.model_copy(
                    update={group.value: execution}
                )
                if execution.status == QualityExecutionStatus.BUDGET_EXHAUSTED:
                    budget_case_id = case.case_id
                    break
            if budget_case_id is not None:
                break

        summaries = self._group_summaries(records)
        errors = [
            error
            for group in (QualityGroup.ORIGINAL, QualityGroup.OPTIMIZED)
            for error in summaries[group].errors
        ]
        if budget_case_id is not None:
            status = QualityRunStatus.BUDGET_EXHAUSTED
        elif errors:
            status = QualityRunStatus.COMPLETED_WITH_ERRORS
        else:
            status = QualityRunStatus.COMPLETED
        paired_comparison = self._paired_comparison(records, seed)
        warnings = [
            "Reference overlap metrics do not measure open-ended semantic quality "
            "or establish superiority over competing systems."
        ]
        if paired_comparison is None:
            warnings.append(
                "Paired comparison unavailable: no cases have both original and "
                "optimized scores."
            )
        if budget_case_id is not None:
            warnings.append(
                f"Budget exhausted while running {budget_case_id}; later calls were not made."
            )
        elif errors:
            warnings.append(
                "Some calls failed; their outputs, scores, usage, cost, and latency are unknown."
            )

        return QualityReport(
            status=status,
            provider=provider,
            model=config.model,
            limit=limit,
            split=split,
            selection=selection,
            seed=seed,
            allow_real_model=allow_real_model,
            selected_case_count=len(selected),
            original_cache_hits=sum(
                record.original.from_cache for record in records
            ),
            completed_case_count=sum(
                record.original.status == QualityExecutionStatus.COMPLETED
                and record.optimized.status == QualityExecutionStatus.COMPLETED
                for record in records
            ),
            cases=records,
            group_summaries=summaries,
            categories=self._category_summaries(records),
            paired_comparison=paired_comparison,
            prompt_tokens=self._sum_int(
                [summary.prompt_tokens for summary in summaries.values()]
            ),
            completion_tokens=self._sum_int(
                [summary.completion_tokens for summary in summaries.values()]
            ),
            total_tokens=self._sum_int(
                [summary.total_tokens for summary in summaries.values()]
            ),
            total_cost_usd=self._sum_decimal(
                [summary.total_cost_usd for summary in summaries.values()]
            ),
            total_latency_seconds=self._sum_float(
                [summary.total_latency_seconds for summary in summaries.values()]
            ),
            errors=errors,
            warnings=warnings,
        )

    @staticmethod
    def _select_cases(
        cases: list[OptimizationCase],
        limit: int,
        selection: SelectionMode,
        seed: int,
    ) -> list[OptimizationCase]:
        if selection == "sequential":
            return cases[:limit]
        if selection != "stratified":
            raise ValueError("selection must be 'sequential' or 'stratified'")

        grouped: dict[str, list[OptimizationCase]] = {}
        for case in cases:
            grouped.setdefault(case.category, []).append(case)
        categories = sorted(grouped)
        rng = random.Random(seed)
        for category in categories:
            rng.shuffle(grouped[category])

        selected: list[OptimizationCase] = []
        offsets = {category: 0 for category in categories}
        while len(selected) < limit:
            added = False
            for category in categories:
                offset = offsets[category]
                if offset >= len(grouped[category]):
                    continue
                selected.append(grouped[category][offset])
                offsets[category] = offset + 1
                added = True
                if len(selected) == limit:
                    break
            if not added:
                break
        return selected

    @staticmethod
    def _paired_comparison(
        records: list[QualityCaseResult],
        seed: int,
    ) -> PairedComparison | None:
        pairs: list[tuple[float, float]] = []
        for record in records:
            original_score = record.original.score
            optimized_score = record.optimized.score
            if original_score is None or optimized_score is None:
                continue
            pairs.append((original_score.primary_score, optimized_score.primary_score))
        if not pairs:
            return None
        return compare_paired_scores(
            [pair[0] for pair in pairs],
            [pair[1] for pair in pairs],
            seed=seed,
        )

    def _validate(
        self,
        cases: list[OptimizationCase],
        provider: Provider,
        limit: int,
        allow_real_model: bool,
        allow_test: bool,
    ) -> None:
        if not cases:
            raise ValueError("at least one train/dev case is required")
        if any(case.split == "test" for case in cases) and not allow_test:
            raise ConfigurationError(
                "quality tuning runs only allow train/dev cases; test cases are forbidden"
            )
        if limit < 1:
            raise ValueError("limit must be positive")
        if provider == Provider.MOCK:
            return
        if not allow_real_model:
            raise ConfigurationError(
                "real model execution requires explicit allow_real_model=True",
                provider=provider.value,
            )
        if limit > MAX_REAL_MODEL_LIMIT:
            raise ConfigurationError(
                f"real model execution requires limit <= {MAX_REAL_MODEL_LIMIT}",
                provider=provider.value,
            )
        if self._settings.cost_budget_usd is None:
            raise ConfigurationError(
                "real model execution requires settings.cost_budget_usd",
                provider=provider.value,
            )

    def _execute(
        self,
        case: OptimizationCase,
        group: QualityGroup,
        prompt: str,
        provider: Provider,
        model: str,
    ) -> QualityExecution:
        try:
            response = self._gateway.complete(
                CompletionRequest(
                    messages=[ChatMessage(role="user", content=prompt)],
                    provider=provider,
                    model=model,
                    temperature=0.0,
                )
            )
        except BudgetExceededError as error:
            return self._failed_execution(
                case,
                group,
                error,
                QualityExecutionStatus.BUDGET_EXHAUSTED,
            )
        except LLMError as error:
            return self._failed_execution(
                case,
                group,
                error,
                QualityExecutionStatus.FAILED,
            )
        return self._completed_execution(case, response)

    def _optimized_prompt(self, case: OptimizationCase) -> str:
        request = PromptOptimizationRequest(
            user_request="Optimize this prompt without changing its intent.",
            raw_prompt=case.prompt,
        )
        return self._optimizer.optimize(request).generated_prompt.content

    @staticmethod
    def _completed_execution(
        case: OptimizationCase,
        response: CompletionResponse,
    ) -> QualityExecution:
        return QualityExecution(
            status=QualityExecutionStatus.COMPLETED,
            output=response.content,
            score=score_reference(
                case.category,
                response.content,
                case.reference_response,
            ),
            usage=response.usage,
            cost_usd=response.cost_usd,
            latency_seconds=response.latency_seconds,
            attempts=response.attempts,
        )

    @staticmethod
    def _failed_execution(
        case: OptimizationCase,
        group: QualityGroup,
        error: LLMError,
        status: Literal[
            QualityExecutionStatus.FAILED,
            QualityExecutionStatus.BUDGET_EXHAUSTED,
        ],
    ) -> QualityExecution:
        return QualityExecution(
            status=status,
            error=QualityError(
                case_id=case.case_id,
                group=group,
                error_type=type(error).__name__,
                message=str(error),
            ),
        )

    @staticmethod
    def _group_summaries(
        records: list[QualityCaseResult],
    ) -> dict[QualityGroup, QualityGroupSummary]:
        return {
            group: QualityRunner._summarize_group(
                group,
                [
                    record.original
                    if group == QualityGroup.ORIGINAL
                    else record.optimized
                    for record in records
                ],
            )
            for group in (QualityGroup.ORIGINAL, QualityGroup.OPTIMIZED)
        }

    @staticmethod
    def _summarize_group(
        group: QualityGroup,
        executions: list[QualityExecution],
    ) -> QualityGroupSummary:
        attempted = [
            execution
            for execution in executions
            if execution.status != QualityExecutionStatus.NOT_RUN
            and not execution.from_cache
        ]
        scores = [
            execution.score
            for execution in executions
            if execution.score is not None
        ]
        return QualityGroupSummary(
            group=group,
            selected_cases=len(executions),
            attempted_calls=len(attempted),
            cached_calls=sum(execution.from_cache for execution in executions),
            completed_calls=sum(
                execution.status == QualityExecutionStatus.COMPLETED
                for execution in executions
            ),
            scored_calls=len(scores),
            average_exact_match=QualityRunner._mean(
                [score.exact_match for score in scores]
            ),
            average_token_f1=QualityRunner._mean([score.token_f1 for score in scores]),
            average_primary_score=QualityRunner._mean(
                [score.primary_score for score in scores]
            ),
            prompt_tokens=QualityRunner._sum_int(
                [
                    execution.usage.prompt_tokens if execution.usage else None
                    for execution in attempted
                ]
            ),
            completion_tokens=QualityRunner._sum_int(
                [
                    execution.usage.completion_tokens if execution.usage else None
                    for execution in attempted
                ]
            ),
            total_tokens=QualityRunner._sum_int(
                [
                    execution.usage.total_tokens if execution.usage else None
                    for execution in attempted
                ]
            ),
            total_cost_usd=QualityRunner._sum_decimal(
                [execution.cost_usd for execution in attempted]
            ),
            total_latency_seconds=QualityRunner._sum_float(
                [execution.latency_seconds for execution in attempted]
            ),
            errors=[
                execution.error
                for execution in attempted
                if execution.error is not None
            ],
        )

    @staticmethod
    def _category_summaries(
        records: list[QualityCaseResult],
    ) -> dict[str, QualityCategorySummary]:
        categories: dict[str, QualityCategorySummary] = {}
        for category in sorted({record.category for record in records}):
            category_records = [
                record for record in records if record.category == category
            ]
            categories[category] = QualityCategorySummary(
                category=category,
                case_count=len(category_records),
                groups=QualityRunner._group_summaries(category_records),
            )
        return categories

    @staticmethod
    def _mean(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    @staticmethod
    def _sum_int(values: Iterable[int | None]) -> int | None:
        materialized = list(values)
        if any(value is None for value in materialized):
            return None
        return sum(value for value in materialized if value is not None)

    @staticmethod
    def _sum_decimal(values: Iterable[Decimal | None]) -> Decimal | None:
        materialized = list(values)
        if any(value is None for value in materialized):
            return None
        return sum(
            (value for value in materialized if value is not None),
            Decimal("0"),
        )

    @staticmethod
    def _sum_float(values: Iterable[float | None]) -> float | None:
        materialized = list(values)
        if any(value is None for value in materialized):
            return None
        return sum(value for value in materialized if value is not None)


__all__ = [
    "DEFAULT_QUALITY_LIMIT",
    "DEFAULT_QUALITY_SEED",
    "MAX_REAL_MODEL_LIMIT",
    "SelectionMode",
    "QualityCaseResult",
    "QualityCategorySummary",
    "QualityError",
    "QualityExecution",
    "QualityExecutionStatus",
    "QualityGroup",
    "QualityGroupSummary",
    "QualityReport",
    "QualityRunner",
    "QualityRunStatus",
]
