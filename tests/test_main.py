import json

import pytest

from pea.__main__ import main


def test_main_outputs_valid_json(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["version"] == "0.2.0"
    assert output["stage"] == "Beta"


def test_mock_command_executes_unified_gateway(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["--mock"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["provider"] == "mock"
    assert output["content"] == "Mock response"
    assert output["usage"]["source"] == "mock_estimate"
    assert output["cost_usd"] == "0"


def test_optimize_command_returns_structured_prompt_result(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "--optimize",
            "优化 Prompt",
            "--raw-prompt",
            "写一封客户回访邮件，不超过200字，输出邮件正文。",
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["intent"]["task_type"] == "email_office"
    assert output["generated_prompt"]["generation_method"] == "deterministic"
    assert "客户回访邮件" in output["generated_prompt"]["content"]


def test_workflow_command_runs_langgraph(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["--optimize", "写一句生日祝福", "--workflow"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["status"] == "completed"
    assert len(output["iterations"]) == 1
    assert output["optimization"]["generated_prompt"]["content"]


def test_validate_benchmark_command_checks_100_draft_tasks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["--validate-benchmark"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["total"] == 100
    assert output["unique_task_ids"] == 100
    assert output["pending_human_review"] == 100
    assert output["ready_for_real_model_experiments"] is False
