import json

import pytest

from pea.evaluation.optimization_data import OptimizationCase
from pea.evaluation.quality_cli import main
from pea.exceptions import ConfigurationError


def write_dev_cases(data_dir) -> None:
    data_dir.mkdir()
    cases = [
        OptimizationCase(
            case_id=f"dev-{index}",
            source="databricks-dolly-15k",
            source_index=index,
            category="classification" if index == 1 else "closed_qa",
            instruction=f"Instruction {index}",
            context="",
            reference_response="answer",
            split="dev",
        )
        for index in range(1, 3)
    ]
    (data_dir / "dolly_dev.jsonl").write_text(
        "\n".join(case.model_dump_json() for case in cases),
        encoding="utf-8",
    )


def test_mock_quality_cli_writes_bounded_report(tmp_path, capsys) -> None:
    data_dir = tmp_path / "splits"
    write_dev_cases(data_dir)
    output = tmp_path / "quality.json"

    exit_code = main(
        [
            "--split",
            "dev",
            "--data-dir",
            str(data_dir),
            "--limit",
            "2",
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["selected_case_count"] == 2
    assert report["completed_case_count"] == 2
    assert report["quality_claim_allowed"] is False
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "completed"


def test_real_quality_cli_requires_global_enable_before_loading_data(tmp_path) -> None:
    with pytest.raises(ConfigurationError, match="PEA_ENABLE_REAL_PROVIDERS"):
        main(
            [
                "--provider",
                "openai",
                "--allow-real-model",
                "--data-dir",
                str(tmp_path / "missing"),
            ]
        )


def test_quality_cli_rejects_test_split_argument() -> None:
    with pytest.raises(SystemExit):
        main(["--split", "test"])
