from statistics import mean, median
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pea.agents._text import goal_is_preserved
from pea.agents import IntentAnalyzer, PromptDiagnostician, StructuredPromptOptimizer
from pea.models import (
    Complexity,
    DiagnosticDimension,
    PromptOptimizationRequest,
    StrategyType,
)
from pea.evaluation.external_data import ExternalCase


class HarnessAuditReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    public_cases: int = Field(ge=1)
    goal_preservation_rate: float = Field(ge=0.0, le=1.0)
    output_structure_rate: float = Field(ge=0.0, le=1.0)
    mean_prompt_expansion_ratio: float = Field(ge=0.0)
    median_prompt_expansion_ratio: float = Field(ge=0.0)
    lightweight_plan_rate: float = Field(ge=0.0, le=1.0)
    few_shot_without_example_rate: float = Field(ge=0.0, le=1.0)
    role_on_simple_rate: float = Field(ge=0.0, le=1.0)
    mutation_detection: dict[str, float]
    source_categories: dict[str, int]
    semantic_quality_measured: bool = False


class HarnessAuditor:
    def __init__(self) -> None:
        self._optimizer = StructuredPromptOptimizer()
        self._analyzer = IntentAnalyzer()
        self._diagnostician = PromptDiagnostician()

    def run(self, cases: list[ExternalCase]) -> HarnessAuditReport:
        if not cases:
            raise ValueError("public harness audit requires cases")
        results = [self._audit_case(case) for case in cases]
        return HarnessAuditReport(
            public_cases=len(cases),
            goal_preservation_rate=mean(item["goal_preserved"] for item in results),
            output_structure_rate=mean(item["output_structure"] for item in results),
            mean_prompt_expansion_ratio=mean(item["expansion"] for item in results),
            median_prompt_expansion_ratio=median(item["expansion"] for item in results),
            lightweight_plan_rate=mean(item["lightweight"] for item in results),
            few_shot_without_example_rate=mean(item["few_shot_without_example"] for item in results),
            role_on_simple_rate=mean(item["role_on_simple"] for item in results),
            mutation_detection=self._mutation_detection(cases[:20]),
            source_categories={
                category: sum(case.category == category for case in cases)
                for category in sorted({case.category for case in cases})
            },
        )

    def _audit_case(self, case: ExternalCase) -> dict[str, Any]:
        result = self._optimizer.optimize(
            PromptOptimizationRequest(
                user_request="Optimize this prompt without changing its intent.",
                raw_prompt=case.prompt,
            )
        )
        strategies = {
            item.strategy for item in result.strategy_plan.selected
        }
        return {
            "goal_preserved": float(
                goal_is_preserved(case.prompt, result.generated_prompt.content)
            ),
            "output_structure": float("## 输出要求" in result.generated_prompt.content),
            "expansion": len(result.generated_prompt.content) / max(1, len(case.prompt)),
            "lightweight": float(result.strategy_plan.lightweight),
            "few_shot_without_example": float(
                StrategyType.FEW_SHOT in strategies and not result.intent.examples
            ),
            "role_on_simple": float(
                StrategyType.ROLE_PROMPTING in strategies
                and result.intent.complexity == Complexity.SIMPLE
            ),
        }

    def _mutation_detection(self, cases: list[ExternalCase]) -> dict[str, float]:
        missing_output = []
        ambiguity = []
        conflict = []
        for case in cases:
            request = PromptOptimizationRequest(
                user_request="Optimize this prompt.",
                raw_prompt=case.instruction,
            )
            intent = self._analyzer.analyze(request)
            diagnosis = self._diagnostician.diagnose(request, intent)
            scores = {item.dimension: item.score for item in diagnosis.assessments}
            missing_output.append(scores[DiagnosticDimension.OUTPUT_FORMAT] <= 2)

            ambiguous_request = PromptOptimizationRequest(
                user_request="Optimize this prompt.",
                raw_prompt=f"{case.instruction}\nMake it somewhat appropriate and add related stuff etc.",
            )
            ambiguous_intent = self._analyzer.analyze(ambiguous_request)
            ambiguous_diagnosis = self._diagnostician.diagnose(
                ambiguous_request,
                ambiguous_intent,
            )
            ambiguous_scores = {
                item.dimension: item.score
                for item in ambiguous_diagnosis.assessments
            }
            ambiguity.append(ambiguous_scores[DiagnosticDimension.AMBIGUITY_RISK] < 5)

            conflict_request = PromptOptimizationRequest(
                user_request="Optimize this prompt.",
                raw_prompt=f"{case.instruction}\nOutput at least 500 words and no more than 100 words.",
            )
            conflict_intent = self._analyzer.analyze(conflict_request)
            conflict_diagnosis = self._diagnostician.diagnose(
                conflict_request,
                conflict_intent,
            )
            conflict_scores = {
                item.dimension: item.score
                for item in conflict_diagnosis.assessments
            }
            conflict.append(conflict_scores[DiagnosticDimension.CONSTRAINTS] == 1)

        vague_intent = self._analyzer.analyze(
            PromptOptimizationRequest(user_request="Help me with this")
        )
        return {
            "missing_output": mean(missing_output),
            "english_ambiguity": mean(ambiguity),
            "english_length_conflict": mean(conflict),
            "english_vague_clarification": float(vague_intent.needs_clarification),
        }
