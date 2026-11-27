from decimal import Decimal
from typing import Literal

import pytest

from pea.config import Settings
from pea.evaluation.optimization_data import OptimizationCase
from pea.evaluation.quality_runner import (
    QualityExecutionStatus,
    QualityGroup,
    QualityRunner,
    QualityRunStatus,
)
from pea.exceptions import ConfigurationError, ProviderTimeoutError
from pea.gateway import LLMGateway, MockBackend
from pea.models import Provider


def make_case(
    case_id: str,
    *,
    source_index: int = 1,
    split: Literal["train", "dev", "test"] = "train",
    category: str = "classification",
    instruction: str = "Classify this example.",
    reference_response: str = "yes",
) -> OptimizationCase:
    return OptimizationCase(
        case_id=case_id,
        source="databricks-dolly-15k",
        source_index=source_index,
        category=category,
        instruction=instruction,
        context="",
        reference_response=reference_response,
        split=split,
    )


def make_gateway(
    backend: MockBackend,
    settings: Settings | None = None,
    *,
    provider: Provider = Provider.MOCK,
) -> LLMGateway:
    return LLMGateway(settings, backends={provider: backend})


def test_mock_comparison_scores_and_aggregates_by_category() -> None:
    cases = [
        make_case("classification-train"),
        make_case(
            "qa-dev",
            source_index=2,
            split="dev",
            category="closed_qa",
            instruction="Answer with three words.",
            reference_response="alpha beta gamma",
        ),
    ]
    backend = MockBackend(["yes", "no", "alpha beta gamma", "alpha beta"])
    settings = Settings(_env_file=None)

    report = QualityRunner(
        make_gateway(backend, settings),
        settings=settings,
    ).run(cases, model="mock-quality", selection="sequential")

    assert report.status == QualityRunStatus.COMPLETED
    assert report.selected_case_count == 2
    assert report.completed_case_count == 2
    assert report.human_review_required is True
    assert report.quality_claim_allowed is False
    assert report.semantic_quality_measured is False

    first = report.cases[0]
    assert first.original.output == "yes"
    assert first.optimized.output == "no"
    assert first.original.score is not None
    assert first.optimized.score is not None
    assert first.original.score.exact_match == 1.0
    assert first.original.score.token_f1 == 1.0
    assert first.original.score.primary_score == 1.0
    assert first.optimized.score.primary_score == 0.0

    second = report.cases[1]
    assert second.optimized.score is not None
    assert second.optimized.score.exact_match == 0.0
    assert second.optimized.score.token_f1 == pytest.approx(0.8)
    assert second.optimized.score.primary_score == pytest.approx(0.8)

    original = report.group_summaries[QualityGroup.ORIGINAL]
    optimized = report.group_summaries[QualityGroup.OPTIMIZED]
    assert original.average_exact_match == 1.0
    assert original.average_token_f1 == 1.0
    assert original.average_primary_score == 1.0
    assert optimized.average_exact_match == 0.0
    assert optimized.average_token_f1 == pytest.approx(0.4)
    assert optimized.average_primary_score == pytest.approx(0.4)
    assert original.total_cost_usd == Decimal("0")
    assert optimized.total_cost_usd == Decimal("0")
    assert original.total_tokens is not None and original.total_tokens > 0
    assert optimized.total_tokens is not None and optimized.total_tokens > 0
    assert original.total_latency_seconds is not None
    assert optimized.total_latency_seconds is not None
    assert report.total_cost_usd == Decimal("0")
    assert report.total_tokens == original.total_tokens + optimized.total_tokens

    assert report.categories["classification"].case_count == 1
    assert (
        report.categories["classification"]
        .groups[QualityGroup.OPTIMIZED]
        .average_primary_score
        == 0.0
    )
    assert (
        report.categories["closed_qa"]
        .groups[QualityGroup.OPTIMIZED]
        .average_primary_score
        == pytest.approx(0.8)
    )

    assert len(backend.calls) == 4
    requests = [request for request, _ in backend.calls]
    assert {request.provider for request in requests} == {Provider.MOCK}
    assert {request.model for request in requests} == {"mock-quality"}
    assert {request.temperature for request in requests} == {0.0}
    assert requests[0].messages[0].content == cases[0].prompt
    assert requests[1].messages[0].content == first.optimized_prompt


def test_test_split_is_rejected_before_limit_selection_or_calls() -> None:
    backend = MockBackend()
    settings = Settings(_env_file=None)
    gateway = make_gateway(backend, settings)

    with pytest.raises(ConfigurationError, match="test cases are forbidden"):
        QualityRunner(gateway, settings=settings).run(
            [
                make_case("train-case"),
                make_case("hidden-test", source_index=2, split="test"),
            ],
            limit=1,
        )

    assert backend.calls == []
    assert gateway.call_count == 0


@pytest.mark.parametrize(
    ("settings", "limit", "allow_real_model", "message"),
    [
        (
            Settings(_env_file=None, cost_budget_usd=Decimal("1")),
            1,
            False,
            "allow_real_model=True",
        ),
        (
            Settings(_env_file=None),
            1,
            True,
            "cost_budget_usd",
        ),
        (
            Settings(_env_file=None, cost_budget_usd=Decimal("1")),
            51,
            True,
            "limit <= 50",
        ),
    ],
)
def test_real_model_guards_fire_before_any_call(
    settings: Settings,
    limit: int,
    allow_real_model: bool,
    message: str,
) -> None:
    backend = MockBackend()
    gateway = make_gateway(backend, settings, provider=Provider.OPENAI)

    with pytest.raises(ConfigurationError, match=message):
        QualityRunner(gateway, settings=settings).run(
            [make_case("train-case")],
            provider=Provider.OPENAI,
            limit=limit,
            allow_real_model=allow_real_model,
        )

    assert backend.calls == []
    assert gateway.call_count == 0


def test_budget_exhaustion_stops_calls_and_preserves_partial_report() -> None:
    backend = MockBackend(["yes", "yes", "must not be requested"])
    settings = Settings(_env_file=None, max_calls=2)
    gateway = make_gateway(backend, settings)

    report = QualityRunner(gateway, settings=settings).run(
        [
            make_case("complete-case"),
            make_case("partial-case", source_index=2),
        ],
        selection="sequential",
    )

    assert report.status == QualityRunStatus.BUDGET_EXHAUSTED
    assert report.completed_case_count == 1
    assert len(backend.calls) == 2
    assert report.cases[0].original.output == "yes"
    assert report.cases[0].optimized.output == "yes"
    assert report.cases[0].original.score is not None
    assert report.cases[0].optimized.score is not None
    assert report.paired_comparison is not None
    assert report.paired_comparison.samples == 1

    partial = report.cases[1]
    assert partial.original.status == QualityExecutionStatus.BUDGET_EXHAUSTED
    assert partial.original.output is None
    assert partial.original.score is None
    assert partial.original.cost_usd is None
    assert partial.original.error is not None
    assert partial.original.error.error_type == "BudgetExceededError"
    assert partial.optimized.status == QualityExecutionStatus.NOT_RUN
    assert partial.optimized.output is None
    assert report.group_summaries[QualityGroup.ORIGINAL].total_cost_usd is None
    assert report.group_summaries[QualityGroup.OPTIMIZED].total_cost_usd == Decimal("0")
    assert any("later calls were not made" in warning for warning in report.warnings)


def test_llm_error_is_recorded_without_fake_output_or_zero_cost() -> None:
    backend = MockBackend(
        [ProviderTimeoutError("mock timeout", provider="mock"), "yes"]
    )
    settings = Settings(_env_file=None, max_retries=0)
    gateway = make_gateway(backend, settings)

    report = QualityRunner(gateway, settings=settings).run([make_case("error-case")])

    assert report.status == QualityRunStatus.COMPLETED_WITH_ERRORS
    assert len(backend.calls) == 2
    original = report.cases[0].original
    assert original.status == QualityExecutionStatus.FAILED
    assert original.output is None
    assert original.score is None
    assert original.usage is None
    assert original.cost_usd is None
    assert original.latency_seconds is None
    assert original.error is not None
    assert original.error.error_type == "ProviderTimeoutError"
    assert original.error.group == QualityGroup.ORIGINAL

    optimized = report.cases[0].optimized
    assert optimized.status == QualityExecutionStatus.COMPLETED
    assert optimized.output == "yes"
    assert optimized.score is not None
    assert optimized.score.primary_score == 1.0
    assert optimized.cost_usd == Decimal("0")
    assert report.group_summaries[QualityGroup.ORIGINAL].average_primary_score is None
    assert report.group_summaries[QualityGroup.ORIGINAL].total_cost_usd is None
    assert report.total_cost_usd is None
    assert report.total_tokens is None


def test_default_limit_selects_at_most_ten_cases() -> None:
    backend = MockBackend()
    settings = Settings(_env_file=None)
    gateway = make_gateway(backend, settings)
    cases = [make_case(f"case-{index}", source_index=index) for index in range(1, 12)]

    report = QualityRunner(gateway, settings=settings).run(cases)

    assert report.limit == 10
    assert report.selection == "stratified"
    assert report.seed == 20261126
    assert report.selected_case_count == 10
    assert len(report.cases) == 10
    assert len(backend.calls) == 20



def test_stratified_selection_covers_categories_after_split_filter() -> None:
    backend = MockBackend()
    settings = Settings(_env_file=None)
    gateway = make_gateway(backend, settings)
    cases = [
        make_case("train-distractor", source_index=1, split="train"),
        make_case("classification-1", source_index=2, split="dev"),
        make_case("classification-2", source_index=3, split="dev"),
        make_case(
            "closed-qa-1",
            source_index=4,
            split="dev",
            category="closed_qa",
        ),
        make_case(
            "summarization-1",
            source_index=5,
            split="dev",
            category="summarization",
        ),
    ]

    report = QualityRunner(gateway, settings=settings).run(
        cases,
        split="dev",
        limit=4,
    )

    assert report.selection == "stratified"
    assert report.seed == 20261126
    assert [record.category for record in report.cases] == [
        "classification",
        "closed_qa",
        "summarization",
        "classification",
    ]
    assert {record.split for record in report.cases} == {"dev"}
    assert "train-distractor" not in {record.case_id for record in report.cases}
    assert len(backend.calls) == 8


def test_stratified_selection_is_reproducible_for_fixed_seed() -> None:
    cases = [
        make_case("classification-1", source_index=1),
        make_case("classification-2", source_index=2),
        make_case("classification-3", source_index=3),
        make_case("closed-qa-1", source_index=4, category="closed_qa"),
        make_case("closed-qa-2", source_index=5, category="closed_qa"),
        make_case("summarization-1", source_index=6, category="summarization"),
        make_case("summarization-2", source_index=7, category="summarization"),
    ]
    settings = Settings(_env_file=None)
    first_backend = MockBackend()
    second_backend = MockBackend()

    first = QualityRunner(
        make_gateway(first_backend, settings),
        settings=settings,
    ).run(cases, limit=6, seed=37)
    second = QualityRunner(
        make_gateway(second_backend, settings),
        settings=settings,
    ).run(cases, limit=6, seed=37)

    assert [record.case_id for record in first.cases] == [
        record.case_id for record in second.cases
    ]
    assert first.paired_comparison == second.paired_comparison
    assert first.seed == second.seed == 37


def test_paired_comparison_reports_wins_ties_losses_and_interval() -> None:
    cases = [
        make_case("win", source_index=1),
        make_case("tie", source_index=2),
        make_case("loss", source_index=3),
    ]
    backend = MockBackend(["no", "yes", "yes", "yes", "yes", "no"])
    settings = Settings(_env_file=None)

    report = QualityRunner(
        make_gateway(backend, settings),
        settings=settings,
    ).run(cases, selection="sequential", seed=19)

    comparison = report.paired_comparison
    assert comparison is not None
    assert comparison.samples == 3
    assert comparison.wins == 1
    assert comparison.ties == 1
    assert comparison.losses == 1
    assert comparison.mean_difference == 0.0
    assert comparison.confidence == 0.95
    assert comparison.ci_lower <= 0.0 <= comparison.ci_upper
    assert report.quality_claim_allowed is False
    assert report.human_review_required is True


def test_original_execution_cache_reuses_scores_without_new_cost() -> None:
    case = make_case("cache-case")
    cache = {}
    first_backend = MockBackend(["original output", "first optimized"])
    first_settings = Settings(_env_file=None)
    first_report = QualityRunner(
        make_gateway(first_backend, first_settings),
        settings=first_settings,
    ).run([case], original_cache=cache)

    second_backend = MockBackend(["second optimized"])
    second_settings = Settings(_env_file=None)
    second_report = QualityRunner(
        make_gateway(second_backend, second_settings),
        settings=second_settings,
    ).run([case], original_cache=cache)

    assert len(first_backend.calls) == 2
    assert len(second_backend.calls) == 1
    assert first_report.original_cache_hits == 0
    assert second_report.original_cache_hits == 1
    assert second_report.cases[0].original.output == "original output"
    assert second_report.cases[0].optimized.output == "second optimized"
    assert second_report.cases[0].original.from_cache is True
    assert second_report.cases[0].original.score == first_report.cases[0].original.score
    original_summary = second_report.group_summaries[QualityGroup.ORIGINAL]
    assert original_summary.attempted_calls == 0
    assert original_summary.cached_calls == 1
    assert original_summary.completed_calls == 1
    assert original_summary.total_tokens == 0
    assert original_summary.total_cost_usd == Decimal("0")
    assert original_summary.total_latency_seconds == 0.0


def test_paired_comparison_is_none_without_complete_score_pairs() -> None:
    backend = MockBackend(
        [
            ProviderTimeoutError("original timeout", provider="mock"),
            ProviderTimeoutError("optimized timeout", provider="mock"),
        ]
    )
    settings = Settings(_env_file=None, max_retries=0)

    report = QualityRunner(
        make_gateway(backend, settings),
        settings=settings,
    ).run([make_case("no-pair")])

    assert report.paired_comparison is None
    assert any(
        "Paired comparison unavailable" in warning for warning in report.warnings
    )
    assert report.quality_claim_allowed is False
    assert len(backend.calls) == 2
