import pytest

from pea.config import Settings
from pea.evaluation.benchmark import BenchmarkLoader
from pea.evaluation.experiment import ExperimentRunner
from pea.exceptions import ConfigurationError, RateLimitError
from pea.gateway import LLMGateway, MockBackend
from pea.models import Provider
from pea.models.benchmark import ExperimentStatus, GroupName, OutputCheck


def task_by_id(task_id: str):
    return next(task for task in BenchmarkLoader().load() if task.task_id == task_id)


def test_draft_experiment_requires_explicit_mock_opt_in() -> None:
    tasks = BenchmarkLoader().load()
    backend = MockBackend()
    gateway = LLMGateway(
        Settings(_env_file=None),
        backends={Provider.MOCK: backend},
    )

    with pytest.raises(ConfigurationError, match="allow_draft"):
        ExperimentRunner(gateway, settings=Settings(_env_file=None)).run(tasks)
    assert backend.calls == []


def test_draft_data_cannot_run_real_provider_even_with_fake_credentials() -> None:
    tasks = BenchmarkLoader().load()
    settings = Settings(
        _env_file=None,
        openai_api_key="test-key",
        openai_model="gpt-test",
    )
    gateway = LLMGateway(settings)

    with pytest.raises(ConfigurationError, match="only run with Mock"):
        ExperimentRunner(gateway, settings=settings).run(
            tasks,
            provider=Provider.OPENAI,
            allow_draft=True,
        )


def test_three_group_mock_experiment_reports_scores_without_quality_claim() -> None:
    task = task_by_id("data_001")
    outcomes = ["bad"] * 4
    for _ in range(2):
        outcomes.extend(["bad", '{"total": 550}'])
    backend = MockBackend(outcomes)
    settings = Settings(_env_file=None)
    gateway = LLMGateway(settings, backends={Provider.MOCK: backend})

    report = ExperimentRunner(gateway, settings=settings).run(
        [task],
        repetitions=2,
        allow_draft=True,
    )

    assert report.status == ExperimentStatus.COMPLETED
    assert report.dataset_reviewed is False
    assert report.quality_claim_allowed is False
    assert report.repetitions == 2
    assert len(report.records) == 1
    original = report.summaries[GroupName.ORIGINAL]
    adaptive = report.summaries[GroupName.ADAPTIVE]
    assert adaptive.average_quality == 1.0
    assert original.average_quality < adaptive.average_quality
    assert adaptive.average_stability == 1.0
    assert adaptive.output_format_pass_rate == 1.0
    assert adaptive.content_accuracy_rate == 1.0
    assert adaptive.total_tokens is not None
    assert adaptive.total_cost_usd == 0
    assert len(backend.calls) == 8


def test_single_run_stability_is_not_measured() -> None:
    task = BenchmarkLoader().load()[1]
    settings = Settings(_env_file=None)
    backend = MockBackend()
    gateway = LLMGateway(settings, backends={Provider.MOCK: backend})

    report = ExperimentRunner(gateway, settings=settings).run(
        [task],
        allow_draft=True,
    )

    assert report.records[0].groups[GroupName.ORIGINAL].stability_score is None
    assert report.summaries[GroupName.ORIGINAL].average_stability is None
    assert any("not measured" in item for item in report.warnings)


def test_budget_exhaustion_stops_batch_immediately() -> None:
    tasks = BenchmarkLoader().load()
    settings = Settings(_env_file=None, max_calls=1)
    backend = MockBackend()
    gateway = LLMGateway(settings, backends={Provider.MOCK: backend})

    report = ExperimentRunner(gateway, settings=settings).run(
        tasks,
        allow_draft=True,
    )

    assert report.status == ExperimentStatus.BUDGET_EXHAUSTED
    assert report.records == []
    assert len(backend.calls) == 1
    assert report.summaries[GroupName.ORIGINAL].tasks == 0


def test_non_budget_provider_error_is_recorded() -> None:
    task = BenchmarkLoader().load()[1].model_copy(
        update={
            "raw_prompt": None,
            "user_request": "写一条生日祝福。",
            "target_task": "写一条生日祝福",
            "output_requirements": ["输出一句话"],
            "constraints": ["保持简洁"],
            "evaluation_criteria": ["结果非空"],
            "checks": [OutputCheck(kind="non_empty")],
        }
    )
    settings = Settings(_env_file=None, max_retries=0)
    backend = MockBackend([RateLimitError("limited", provider="mock")])
    gateway = LLMGateway(settings, backends={Provider.MOCK: backend})

    report = ExperimentRunner(gateway, settings=settings).run(
        [task],
        allow_draft=True,
    )

    assert report.status == ExperimentStatus.COMPLETED_WITH_ERRORS
    assert report.records[0].groups[GroupName.ORIGINAL].runs[0].error == "RateLimitError"
    assert report.records[0].groups[GroupName.ADAPTIVE].runs[0].output == "Mock response"


@pytest.mark.parametrize("repetitions", [0, 6])
def test_invalid_repetition_count_is_rejected(repetitions: int) -> None:
    task = BenchmarkLoader().load()[0]
    settings = Settings(_env_file=None)
    gateway = LLMGateway(settings, backends={Provider.MOCK: MockBackend()})

    with pytest.raises(ValueError, match="repetitions"):
        ExperimentRunner(gateway, settings=settings).run(
            [task],
            repetitions=repetitions,
            allow_draft=True,
        )
