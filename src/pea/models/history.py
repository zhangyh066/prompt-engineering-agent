from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from pea.models.adapter import AdaptedPrompt
from pea.models.llm import Provider
from pea.models.prompt import PromptOptimizationResult, StrategyType, TaskType
from pea.models.workflow import EvaluationReport, WorkflowStatus


class StoredVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int = Field(ge=1)
    content: str
    generation_method: str
    changes: list[dict]
    strategies: list[StrategyType]
    evaluation: EvaluationReport
    is_best: bool
    created_at: datetime


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    status: WorkflowStatus
    user_request: str
    raw_prompt: str | None
    task_type: TaskType | None
    provider: Provider
    model: str
    version_count: int = Field(ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    total_cost_usd: Decimal | None = Field(default=None, ge=0)
    total_latency_seconds: float = Field(ge=0.0)
    warnings: list[str]
    error: str | None
    created_at: datetime
    updated_at: datetime


class RunDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: RunSummary
    optimization: PromptOptimizationResult | None
    adapted_prompt: AdaptedPrompt | None
    clarification_questions: list[str]
    versions: list[StoredVersion]


class VersionComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    left: StoredVersion
    right: StoredVersion
    unified_diff: str
    score_change: float
    added_strategies: list[StrategyType]
    removed_strategies: list[StrategyType]
