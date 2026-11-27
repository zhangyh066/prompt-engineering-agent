from typing import Literal

import pytest

from pea.config import Settings
from pea.evaluation.optimization_data import OptimizationCase
from pea.evaluation.policy_search import PolicySearchRunner
from pea.exceptions import ConfigurationError
from pea.gateway import LLMGateway, MockBackend
from pea.models import Provider
from pea.models.policy import PolicyCandidate, StrategyPolicy


def make_case(
    case_id: str,
    source_index: int,
    split: Literal["train", "dev", "test"] = "train",
    category: str = "classification",
) -> OptimizationCase:
    return OptimizationCase(
        case_id=case_id,
        source="databricks-dolly-15k",
        source_index=source_index,
        category=category,
        instruction=f"Instruction {source_index}",
        context="",
        reference_response="expected",
        split=split,
    )


def test_policy_search_uses_same_cases_and_selects_complete_candidate() -> None:
    backend = MockBackend()
    settings = Settings(_env_file=None)
    gateway = LLMGateway(settings, backends={Provider.MOCK: backend})
    candidates = [
        PolicyCandidate(name="default", policy=StrategyPolicy()),
        PolicyCandidate(
            name="minimal",
            policy=StrategyPolicy(
                few_shot=False,
                role_prompting=False,
                task_decomposition=False,
                structured_output=False,
                self_critique=False,
                react=False,
            ),
        ),
    ]

    report = PolicySearchRunner(gateway, settings=settings).run(
        [
            make_case("train-1", 1),
            make_case("train-2", 2, category="closed_qa"),
        ],
        candidates,
        limit=2,
        seed=37,
    )

    assert report.selected_candidate == "default"
    assert set(report.candidate_reports) == {"default", "minimal"}
    assert set(report.objective_scores) == {"default", "minimal"}
    assert all(value is not None for value in report.objective_scores.values())
    assert report.quality_claim_allowed is False
    assert report.baseline_cache_hits == 2
    assert len(backend.calls) == 6
    for quality_report in report.candidate_reports.values():
        assert quality_report.selected_case_count == 2
        assert quality_report.completed_case_count == 2
        assert quality_report.seed == 37


def test_policy_search_rejects_mixed_or_test_splits_before_calls() -> None:
    backend = MockBackend()
    settings = Settings(_env_file=None)
    gateway = LLMGateway(settings, backends={Provider.MOCK: backend})
    candidates = [PolicyCandidate(name="default", policy=StrategyPolicy())]

    with pytest.raises(ConfigurationError, match="same non-test split"):
        PolicySearchRunner(gateway, settings=settings).run(
            [make_case("train", 1), make_case("hidden-test", 2, split="test")],
            candidates,
            split="train",
        )
    assert backend.calls == []


def test_policy_search_requires_unique_candidates() -> None:
    settings = Settings(_env_file=None)
    gateway = LLMGateway(settings, backends={Provider.MOCK: MockBackend()})
    candidate = PolicyCandidate(name="default", policy=StrategyPolicy())

    with pytest.raises(ValueError, match="unique"):
        PolicySearchRunner(gateway, settings=settings).run(
            [make_case("train", 1)],
            [candidate, candidate],
        )
