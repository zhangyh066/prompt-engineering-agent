from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pea.models.adapter import AdaptedPrompt
from pea.models.llm import CompletionResponse, Provider, TokenUsage
from pea.models.prompt import (
    GeneratedPrompt,
    PromptOptimizationRequest,
    PromptOptimizationResult,
    StrategyPlan,
)


class WorkflowStatus(StrEnum):
    RUNNING = "running"
    NEEDS_CLARIFICATION = "needs_clarification"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EvaluationMetric(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    details: str
    source: Literal["static", "dynamic"]


class EvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    score: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(gt=0.0, le=1.0)
    passed: bool
    static_score: float = Field(ge=0.0, le=1.0)
    dynamic_score: float | None = Field(default=None, ge=0.0, le=1.0)
    baseline_dynamic_score: float | None = Field(default=None, ge=0.0, le=1.0)
    metrics: list[EvaluationMetric]
    issues: list[str] = Field(default_factory=list)
    dynamic_status: Literal["not_run", "completed", "failed"] = "not_run"
    provider: Provider | None = None
    optimized_output: str | None = None
    baseline_output: str | None = None
    baseline_execution: CompletionResponse | None = Field(default=None, exclude=True, repr=False)
    usage: TokenUsage | None = None
    cost_usd: Decimal | None = Field(default=None, ge=0)
    latency_seconds: float = Field(default=0.0, ge=0.0)
    warnings: list[str] = Field(default_factory=list)
    unverified_aspects: list[str] = Field(default_factory=list)


class IterationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    iteration: int = Field(ge=1, le=3)
    prompt: GeneratedPrompt
    strategy_plan: StrategyPlan
    evaluation: EvaluationReport


class ClarificationAnswers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: dict[str, str]

    @field_validator("answers")
    @classmethod
    def answers_must_not_be_blank(cls, value: dict[str, str]) -> dict[str, str]:
        if not value or any(not item.strip() for item in value.values()):
            raise ValueError("clarification answers must not be empty or blank")
        return value


class WorkflowResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: WorkflowStatus
    thread_id: str
    request: PromptOptimizationRequest
    optimization: PromptOptimizationResult | None = None
    adapted_prompt: AdaptedPrompt | None = None
    iterations: list[IterationRecord] = Field(default_factory=list)
    final_evaluation: EvaluationReport | None = None
    clarification_questions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
