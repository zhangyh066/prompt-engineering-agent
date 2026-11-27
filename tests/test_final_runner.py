import hashlib
import json

import pytest

from pea.config import Settings
from pea.evaluation.final_runner import FinalEvaluationRunner
from pea.evaluation.optimization_data import OptimizationCase
from pea.evaluation.quality_runner import QualityRunner
from pea.exceptions import ConfigurationError
from pea.gateway import LLMGateway, MockBackend
from pea.models import Provider


def make_case(split: str, index: int = 1) -> OptimizationCase:
    return OptimizationCase(
        case_id=f"{split}-{index}",
        source="databricks-dolly-15k",
        source_index=index,
        category="classification",
        instruction=f"Instruction {index}",
        context="",
        reference_response="expected",
        split=split,
    )


def write_dev_report(tmp_path) -> None:
    settings = Settings(_env_file=None)
    gateway = LLMGateway(
        settings,
        backends={Provider.MOCK: MockBackend(["expected", "expected"])},
    )
    report = QualityRunner(gateway, settings=settings).run(
        [make_case("dev")],
        split="dev",
    )
    (tmp_path / "dev.json").write_text(
        report.model_dump_json(),
        encoding="utf-8",
    )


def write_test_fixture(tmp_path, *, corrupt_hash: bool = False) -> None:
    path = tmp_path / "test.jsonl"
    path.write_text(make_case("test").model_dump_json(), encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {"split_sha256": {"test": "0" * 64 if corrupt_hash else digest}}
        ),
        encoding="utf-8",
    )


def run_mock_final(tmp_path):
    write_dev_report(tmp_path)
    write_test_fixture(tmp_path)
    backend = MockBackend(["expected", "expected"])
    settings = Settings(_env_file=None)
    gateway = LLMGateway(settings, backends={Provider.MOCK: backend})
    report = FinalEvaluationRunner(gateway, settings=settings).run_final(
        test_path=tmp_path / "test.jsonl",
        manifest_path=tmp_path / "manifest.json",
        dev_report_path=tmp_path / "dev.json",
        access_log_path=tmp_path / "access.jsonl",
        confirm_final_test=True,
    )
    return report, backend


def test_final_runner_allows_verified_test_and_appends_audit_log(tmp_path) -> None:
    report, backend = run_mock_final(tmp_path)
    second_backend = MockBackend(["expected", "expected"])
    settings = Settings(_env_file=None)
    second_report = FinalEvaluationRunner(
        LLMGateway(settings, backends={Provider.MOCK: second_backend}),
        settings=settings,
    ).run_final(
        test_path=tmp_path / "test.jsonl",
        manifest_path=tmp_path / "manifest.json",
        dev_report_path=tmp_path / "dev.json",
        access_log_path=tmp_path / "access.jsonl",
        confirm_final_test=True,
    )

    assert report.quality_report.split == "test"
    assert report.quality_report.selected_case_count == 1
    assert report.quality_report.completed_case_count == 1
    assert report.final_test_confirmed is True
    assert report.test_access_logged is True
    assert second_report.test_sha256 == report.test_sha256
    assert len(backend.calls) == 2
    log_lines = (tmp_path / "access.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(log_lines) == 2
    assert all(json.loads(line)["test_sha256"] == report.test_sha256 for line in log_lines)


def test_final_runner_rejects_wrong_hash_before_calls(tmp_path) -> None:
    write_dev_report(tmp_path)
    write_test_fixture(tmp_path, corrupt_hash=True)
    backend = MockBackend()
    settings = Settings(_env_file=None)
    gateway = LLMGateway(settings, backends={Provider.MOCK: backend})

    with pytest.raises(ConfigurationError, match="hash"):
        FinalEvaluationRunner(gateway, settings=settings).run_final(
            test_path=tmp_path / "test.jsonl",
            manifest_path=tmp_path / "manifest.json",
            dev_report_path=tmp_path / "dev.json",
            access_log_path=tmp_path / "access.jsonl",
            confirm_final_test=True,
        )
    assert backend.calls == []


def test_final_runner_requires_confirmation_before_reading_test(tmp_path) -> None:
    settings = Settings(_env_file=None)
    gateway = LLMGateway(settings, backends={Provider.MOCK: MockBackend()})

    with pytest.raises(ConfigurationError, match="confirm_final_test"):
        FinalEvaluationRunner(gateway, settings=settings).run_final(
            test_path=tmp_path / "missing-test.jsonl",
            manifest_path=tmp_path / "missing-manifest.json",
            dev_report_path=tmp_path / "missing-dev.json",
            access_log_path=tmp_path / "access.jsonl",
            confirm_final_test=False,
        )


def test_mock_dev_cannot_unlock_real_openai_final(tmp_path) -> None:
    write_dev_report(tmp_path)
    write_test_fixture(tmp_path)
    settings = Settings(
        _env_file=None,
        enable_real_providers=True,
        openai_api_key="test-key",
        openai_model="gpt-test",
        cost_budget_usd=1,
    )
    backend = MockBackend()
    gateway = LLMGateway(settings, backends={Provider.OPENAI: backend})

    with pytest.raises(ConfigurationError, match="provider/model"):
        FinalEvaluationRunner(gateway, settings=settings).run_final(
            test_path=tmp_path / "test.jsonl",
            manifest_path=tmp_path / "manifest.json",
            dev_report_path=tmp_path / "dev.json",
            access_log_path=tmp_path / "access.jsonl",
            confirm_final_test=True,
            provider=Provider.OPENAI,
            allow_real_model=True,
        )
    assert backend.calls == []
