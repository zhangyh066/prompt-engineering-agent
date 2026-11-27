import json

import pytest

from pea.config import Settings
from pea.evaluation import PromptEvaluator
from pea.gateway import LLMGateway, MockBackend
from pea.models import PromptOptimizationRequest, Provider, WorkflowStatus
from pea.storage import ResultExporter, RunNotFoundError, SQLiteResultManager
from pea.workflow import WorkflowRunner


class SequenceEvaluator(PromptEvaluator):
    def __init__(self) -> None:
        super().__init__()
        self.scores = iter([0.25, 1.0])

    def evaluate(self, request, intent, generated, **kwargs):
        report = super().evaluate(request, intent, generated, **kwargs)
        score = next(self.scores)
        return report.model_copy(update={"score": score, "passed": score == 1.0})


def test_storage_saves_history_versions_and_comparison(tmp_path) -> None:
    manager = SQLiteResultManager(tmp_path / "history.db")
    result = WorkflowRunner(evaluator=SequenceEvaluator()).run(
        PromptOptimizationRequest(
            user_request="优化 Prompt",
            raw_prompt="写一条生日祝福，输出一句话。",
        )
    )

    run_id = manager.save_workflow_result(result)
    first_detail = manager.get_run(run_id)
    manager.save_workflow_result(result)
    second_detail = manager.get_run(run_id)

    assert first_detail.summary.user_request == "优化 Prompt"
    assert first_detail.summary.raw_prompt == "写一条生日祝福，输出一句话。"
    assert len(second_detail.versions) == 2
    assert second_detail.versions[1].is_best is True
    assert second_detail.summary.total_cost_usd is None
    comparison = manager.compare_versions(run_id, 1, 2)
    assert comparison.score_change == 0.75
    assert "本轮修订重点" in comparison.unified_diff
    assert len(manager.list_runs()) == 1


def test_clarification_run_preserves_original_request_and_updates(tmp_path) -> None:
    manager = SQLiteResultManager(tmp_path / "history.db")
    runner = WorkflowRunner()
    paused = runner.run(
        PromptOptimizationRequest(
            user_request="优化一下",
            raw_prompt="原始内容",
        )
    )
    manager.save_workflow_result(paused)

    paused_detail = manager.get_run(paused.thread_id)
    assert paused_detail.summary.user_request == "优化一下"
    assert paused_detail.summary.raw_prompt == "原始内容"
    assert paused_detail.versions == []

    resumed = runner.resume(
        paused.thread_id,
        {"q1": "写一封客户回访邮件，输出邮件正文。"},
    )
    manager.save_workflow_result(resumed)

    detail = manager.get_run(paused.thread_id)
    assert detail.summary.status == WorkflowStatus.COMPLETED
    assert "补充信息" in detail.summary.user_request
    assert len(detail.versions) == 1
    assert len(manager.list_runs(status=WorkflowStatus.COMPLETED)) == 1


def test_dynamic_result_records_tokens_cost_and_exports(tmp_path) -> None:
    manager = SQLiteResultManager(tmp_path / "history.db")
    settings = Settings(_env_file=None)
    gateway = LLMGateway(settings, backends={Provider.MOCK: MockBackend()})
    result = WorkflowRunner(evaluator=PromptEvaluator(gateway)).run(
        PromptOptimizationRequest(user_request="写一条生日祝福。"),
        dynamic_evaluation=True,
    )
    manager.save_workflow_result(result)

    detail = manager.get_run(result.thread_id)
    json_export = ResultExporter.to_json(detail)
    markdown_export = ResultExporter.to_markdown(detail)

    assert detail.summary.total_tokens > 0
    assert detail.summary.total_cost_usd == 0
    assert json.loads(json_export)["summary"]["run_id"] == result.thread_id
    assert "最终最佳 Prompt" in markdown_export
    assert "版本 1" in markdown_export


def test_missing_run_and_version_raise_not_found(tmp_path) -> None:
    manager = SQLiteResultManager(tmp_path / "history.db")

    with pytest.raises(RunNotFoundError):
        manager.get_run("missing")
    with pytest.raises(ValueError):
        manager.list_runs(limit=101)
