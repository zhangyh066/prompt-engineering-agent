import operator
from typing import Annotated, TypedDict

from pea.models import (
    CompletionResponse,
    GeneratedPrompt,
    IntentAnalysis,
    PromptDiagnosis,
    PromptOptimizationRequest,
    PromptOptimizationResult,
    Provider,
    StrategyPlan,
    WorkflowStatus,
)
from pea.models.adapter import AdaptedPrompt, TargetModel
from pea.models.workflow import EvaluationReport, IterationRecord


class WorkflowState(TypedDict, total=False):
    request: PromptOptimizationRequest
    thread_id: str
    max_iterations: int
    dynamic_evaluation: bool
    provider: Provider
    target_model: TargetModel | None
    status: WorkflowStatus
    intent: IntentAnalysis
    diagnosis: PromptDiagnosis
    strategy_plan: StrategyPlan
    current_prompt: GeneratedPrompt
    current_evaluation: EvaluationReport
    baseline_execution: CompletionResponse
    best_prompt: GeneratedPrompt
    best_plan: StrategyPlan
    best_evaluation: EvaluationReport
    best_score: float
    iteration: int
    iterations: Annotated[list[IterationRecord], operator.add]
    refinement_notes: list[str]
    clarification_questions: list[str]
    optimization: PromptOptimizationResult
    adapted_prompt: AdaptedPrompt
    warnings: list[str]
    error: str | None
