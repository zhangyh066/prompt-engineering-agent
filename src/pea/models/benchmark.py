from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Literal
import re

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pea.models.llm import Provider, TokenUsage
from pea.models.prompt import TaskType
from pea.models.workflow import EvaluationMetric


class ReviewStatus(StrEnum):
    PENDING_HUMAN_REVIEW = "pending_human_review"
    APPROVED = "approved"


class CheckKind(StrEnum):
    NON_EMPTY = "non_empty"
    VALID_JSON = "valid_json"
    MARKDOWN = "markdown"
    TABLE = "table"
    MAX_CHARACTERS = "max_characters"
    MIN_CHARACTERS = "min_characters"
    CONTAINS = "contains"
    REGEX = "regex"
    REFERENCE_ANSWER = "reference_answer"


class OutputCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: CheckKind
    value: str | int | None = None

    @model_validator(mode="after")
    def validate_value(self) -> "OutputCheck":
        requires_value = {
            CheckKind.MAX_CHARACTERS,
            CheckKind.MIN_CHARACTERS,
            CheckKind.CONTAINS,
            CheckKind.REGEX,
        }
        if self.kind in requires_value and self.value is None:
            raise ValueError(f"{self.kind.value} requires a value")
        if self.kind in {CheckKind.MAX_CHARACTERS, CheckKind.MIN_CHARACTERS}:
            if not isinstance(self.value, int) or self.value <= 0:
                raise ValueError("length check values must be positive integers")
        if self.kind == CheckKind.REGEX:
            try:
                re.compile(str(self.value))
            except re.error as error:
                raise ValueError("invalid regular expression") from error
        return self


class BenchmarkTask(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(pattern=r"^[a-z]+_[0-9]{3}$")
    category: TaskType
    user_request: str = Field(min_length=1)
    raw_prompt: str | None = None
    target_task: str = Field(min_length=1)
    output_requirements: list[str] = Field(min_length=1)
    constraints: list[str] = Field(min_length=1)
    evaluation_criteria: list[str] = Field(min_length=1)
    checks: list[OutputCheck] = Field(min_length=1)
    reference_answer: str | None = None
    review_status: ReviewStatus = ReviewStatus.PENDING_HUMAN_REVIEW
    reviewer: str | None = None
    reviewed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_review(self) -> "BenchmarkTask":
        if self.category == TaskType.GENERAL:
            raise ValueError("benchmark tasks must use a concrete task category")
        if self.review_status == ReviewStatus.APPROVED:
            if not self.reviewer or self.reviewed_at is None:
                raise ValueError("approved tasks require reviewer and reviewed_at")
        return self


class BenchmarkValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    total: int = Field(ge=0)
    distribution: dict[TaskType, int]
    unique_task_ids: int = Field(ge=0)
    pending_human_review: int = Field(ge=0)
    approved: int = Field(ge=0)
    ready_for_real_model_experiments: bool


class ModelExecution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Provider
    model: str
    output: str | None = None
    usage: TokenUsage | None = None
    cost_usd: Decimal | None = Field(default=None, ge=0)
    latency_seconds: float = Field(default=0.0, ge=0.0)
    attempts: int = Field(default=0, ge=0)
    workflow_iterations: int | None = Field(default=None, ge=0, le=3)
    error: str | None = None


class RunScore(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    metrics: list[EvaluationMetric]
    unverified_aspects: list[str] = Field(default_factory=list)


class GroupExperimentResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    runs: list[ModelExecution]
    scores: list[RunScore]
    average_score: float = Field(ge=0.0, le=1.0)
    stability_score: float | None = Field(default=None, ge=0.0, le=1.0)
    total_tokens: int | None = Field(default=None, ge=0)
    total_cost_usd: Decimal | None = Field(default=None, ge=0)
    total_latency_seconds: float = Field(ge=0.0)


class GroupName(StrEnum):
    ORIGINAL = "original"
    GENERIC = "generic"
    ADAPTIVE = "adaptive"


class ExperimentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    category: TaskType
    groups: dict[GroupName, GroupExperimentResult]


class GroupSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    group: GroupName
    tasks: int = Field(ge=0)
    average_quality: float = Field(ge=0.0, le=1.0)
    average_stability: float | None = Field(default=None, ge=0.0, le=1.0)
    instruction_following_rate: float = Field(ge=0.0, le=1.0)
    output_format_pass_rate: float = Field(ge=0.0, le=1.0)
    constraint_following_rate: float = Field(ge=0.0, le=1.0)
    content_accuracy_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    total_tokens: int | None = Field(default=None, ge=0)
    total_cost_usd: Decimal | None = Field(default=None, ge=0)
    total_latency_seconds: float = Field(ge=0.0)


class ExperimentStatus(StrEnum):
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    BUDGET_EXHAUSTED = "budget_exhausted"


class ExperimentReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ExperimentStatus
    dataset_reviewed: bool
    provider: Provider
    model: str
    repetitions: int = Field(ge=1, le=5)
    records: list[ExperimentRecord]
    summaries: dict[GroupName, GroupSummary]
    quality_claim_allowed: bool
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
