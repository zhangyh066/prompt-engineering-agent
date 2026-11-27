from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from pea.agents import StructuredPromptOptimizer, StrategyPlanner
from pea.config import Settings, get_settings
from pea.evaluation.optimization_data import OptimizationCase
from pea.evaluation.quality_runner import QualityGroup, QualityReport, QualityRunner, QualityRunStatus
from pea.exceptions import ConfigurationError
from pea.gateway import LLMGateway
from pea.models import Provider
from pea.models.policy import PolicyCandidate


class PolicySearchReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    split: Literal["train", "dev"]
    selected_candidate: str | None
    baseline_cache_enabled: Literal[True] = True
    baseline_cache_hits: int = Field(ge=0)
    objective_scores: dict[str, float | None]
    candidate_reports: dict[str, QualityReport]
    cost_penalty: float = Field(ge=0.0)
    human_review_required: Literal[True] = True
    quality_claim_allowed: Literal[False] = False
    warnings: list[str]


class PolicySearchRunner:
    def __init__(
        self,
        gateway: LLMGateway,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._gateway = gateway
        self._settings = settings or get_settings()

    def run(
        self,
        cases: list[OptimizationCase],
        candidates: list[PolicyCandidate],
        *,
        split: Literal["train", "dev"] = "train",
        provider: Provider = Provider.MOCK,
        limit: int = 10,
        seed: int = 20261126,
        allow_real_model: bool = False,
        cost_penalty: float = 0.0,
    ) -> PolicySearchReport:
        if not cases:
            raise ValueError("policy search requires cases")
        if any(case.split != split for case in cases):
            raise ConfigurationError(
                f"policy search split={split} only accepts cases from the same non-test split"
            )
        if not candidates:
            raise ValueError("policy search requires candidates")
        names = [candidate.name for candidate in candidates]
        if len(names) != len(set(names)):
            raise ValueError("policy candidate names must be unique")
        if cost_penalty < 0:
            raise ValueError("cost_penalty must be nonnegative")

        reports: dict[str, QualityReport] = {}
        objectives: dict[str, float | None] = {}
        original_cache = {}
        for candidate in candidates:
            optimizer = StructuredPromptOptimizer(
                planner=StrategyPlanner(policy=candidate.policy)
            )
            report = QualityRunner(
                self._gateway,
                settings=self._settings,
                optimizer=optimizer,
            ).run(
                cases,
                provider=provider,
                limit=limit,
                split=split,
                selection="stratified",
                seed=seed,
                allow_real_model=allow_real_model,
                original_cache=original_cache,
            )
            reports[candidate.name] = report
            summary = report.group_summaries[QualityGroup.OPTIMIZED]
            if (
                report.status != QualityRunStatus.COMPLETED
                or report.completed_case_count != report.selected_case_count
                or summary.average_primary_score is None
                or summary.total_cost_usd is None
            ):
                objectives[candidate.name] = None
            else:
                objectives[candidate.name] = (
                    summary.average_primary_score
                    - cost_penalty * float(summary.total_cost_usd)
                )

        eligible = [
            (candidate.name, objectives[candidate.name])
            for candidate in candidates
            if objectives[candidate.name] is not None
        ]
        selected = max(eligible, key=lambda item: item[1])[0] if eligible else None
        return PolicySearchReport(
            split=split,
            selected_candidate=selected,
            baseline_cache_hits=sum(
                report.original_cache_hits for report in reports.values()
            ),
            objective_scores=objectives,
            candidate_reports=reports,
            cost_penalty=cost_penalty,
            warnings=[
                "Search scores use reference overlap and do not establish open-ended semantic quality.",
                "Original baselines are shared across candidates; cache hits do not count as new calls or costs.",
                "Only complete candidates with known costs are eligible for selection.",
            ],
        )
