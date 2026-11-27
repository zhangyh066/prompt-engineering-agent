from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaskType(StrEnum):
    BUSINESS_WRITING = "business_writing"
    CONTENT_CREATION = "content_creation"
    DATA_ANALYSIS = "data_analysis"
    SUMMARIZATION = "summarization"
    EMAIL_OFFICE = "email_office"
    RESEARCH = "research"
    GENERAL = "general"


class Complexity(StrEnum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


class DiagnosticDimension(StrEnum):
    GOAL_CLARITY = "goal_clarity"
    CONTEXT_COMPLETENESS = "context_completeness"
    ROLE_SETTING = "role_setting"
    TASK_DECOMPOSITION = "task_decomposition"
    OUTPUT_FORMAT = "output_format"
    CONSTRAINTS = "constraints"
    AMBIGUITY_RISK = "ambiguity_risk"
    EXECUTABILITY = "executability"


class OptimizationPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StrategyType(StrEnum):
    ZERO_SHOT = "zero_shot"
    FEW_SHOT = "few_shot"
    ROLE_PROMPTING = "role_prompting"
    TASK_DECOMPOSITION = "task_decomposition"
    STRUCTURED_OUTPUT = "structured_output"
    CONSTRAINT_BASED = "constraint_based"
    SELF_CRITIQUE = "self_critique"
    REACT = "react"


class DetailLevel(StrEnum):
    CONCISE = "concise"
    BALANCED = "balanced"
    DETAILED = "detailed"


class ExplorationLevel(StrEnum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    EXPLORATORY = "exploratory"


class OptimizationPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    detail_level: DetailLevel = DetailLevel.BALANCED
    exploration_level: ExplorationLevel = ExplorationLevel.BALANCED


class PromptOptimizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_request: str = Field(min_length=1, max_length=20_000)
    raw_prompt: str | None = Field(default=None, max_length=20_000)
    preferences: OptimizationPreferences = Field(default_factory=OptimizationPreferences)

    @field_validator("user_request")
    @classmethod
    def request_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("user request must not be blank")
        return value.strip()

    @field_validator("raw_prompt")
    @classmethod
    def empty_raw_prompt_becomes_none(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value.strip()


class IntentAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    goal: str = Field(min_length=1)
    task_type: TaskType
    complexity: Complexity
    output_requirements: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    context: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    needs_clarification: bool
    requires_tools: bool
    analysis_method: Literal["rule_based"] = "rule_based"


class DimensionAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dimension: DiagnosticDimension
    score: int = Field(ge=0, le=5)
    findings: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class PromptDiagnosis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    overall_score: float = Field(ge=0.0, le=100.0)
    priority: OptimizationPriority
    assessments: list[DimensionAssessment]
    strengths: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    needs_optimization: bool


class SelectedStrategy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy: StrategyType
    reason: str
    expected_cost: Literal["low", "medium", "high"]


class StrategyPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    selected: list[SelectedStrategy] = Field(min_length=1)
    lightweight: bool
    rationale: str


class PromptChange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    description: str
    reason: str
    strategies: list[StrategyType] = Field(default_factory=list)


class GeneratedPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    content: str = Field(min_length=1)
    changes: list[PromptChange] = Field(min_length=1)
    generation_method: Literal["deterministic"] = "deterministic"


class PromptOptimizationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request: PromptOptimizationRequest
    intent: IntentAnalysis
    diagnosis: PromptDiagnosis
    strategy_plan: StrategyPlan
    generated_prompt: GeneratedPrompt
