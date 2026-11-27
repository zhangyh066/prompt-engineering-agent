import pytest

from pea.config import Settings
from pea.evaluation import PromptEvaluator
from pea.exceptions import RateLimitError
from pea.gateway import LLMGateway, MockBackend
from pea.models import (
    EvaluationMetric,
    EvaluationReport,
    PromptOptimizationRequest,
    Provider,
    WorkflowStatus,
)
from pea.workflow import WorkflowRunner


class SequenceEvaluator(PromptEvaluator):
    def __init__(self, outcomes: list[tuple[float, bool]]) -> None:
        super().__init__()
        self._outcomes = iter(outcomes)
        self.calls = 0

    def evaluate(self, request, intent, generated, **kwargs) -> EvaluationReport:
        self.calls += 1
        score, passed = next(self._outcomes)
        return EvaluationReport(
            score=score,
            threshold=0.85,
            passed=passed,
            static_score=score,
            metrics=[
                EvaluationMetric(
                    name="output_structure",
                    score=score,
                    passed=passed,
                    details="测试评估反馈",
                    source="static",
                )
            ],
            issues=[] if passed else ["测试评估反馈"],
        )


def test_simple_workflow_completes_in_one_iteration() -> None:
    result = WorkflowRunner().run(
        PromptOptimizationRequest(user_request="写一条生日祝福，输出一句话。")
    )

    assert result.status == WorkflowStatus.COMPLETED
    assert result.optimization is not None
    assert len(result.iterations) == 1
    assert result.iterations[0].iteration == 1
    assert result.final_evaluation.passed is True
    assert result.error is None


def test_clarification_interrupts_and_resumes_same_thread() -> None:
    runner = WorkflowRunner()

    paused = runner.run(PromptOptimizationRequest(user_request="优化一下"))

    assert paused.status == WorkflowStatus.NEEDS_CLARIFICATION
    assert paused.clarification_questions
    assert paused.iterations == []
    assert paused.thread_id != "unknown"

    resumed = runner.resume(
        paused.thread_id,
        {"q1": "写一封客户回访邮件，不超过200字，输出邮件正文。"},
    )

    assert resumed.status == WorkflowStatus.COMPLETED
    assert resumed.thread_id == paused.thread_id
    assert resumed.optimization.intent.task_type == "email_office"
    assert "补充信息" in resumed.optimization.request.user_request
    assert len(resumed.iterations) == 1


def test_clarification_rejects_mismatched_answer_keys() -> None:
    runner = WorkflowRunner()
    paused = runner.run(PromptOptimizationRequest(user_request="优化一下"))

    result = runner.resume(paused.thread_id, {"wrong": "写一封邮件"})

    assert result.status == WorkflowStatus.FAILED
    assert "keys" in result.error


def test_workflow_refines_after_failed_evaluation() -> None:
    evaluator = SequenceEvaluator([(0.25, False), (1.0, True)])

    result = WorkflowRunner(evaluator=evaluator).run(
        PromptOptimizationRequest(user_request="写一条生日祝福，输出一句话。")
    )

    assert result.status == WorkflowStatus.COMPLETED
    assert len(result.iterations) == 2
    assert evaluator.calls == 2
    assert "本轮修订重点" in result.optimization.generated_prompt.content
    assert "测试评估反馈" in result.optimization.generated_prompt.content


def test_workflow_stops_at_three_generations_and_returns_best() -> None:
    evaluator = SequenceEvaluator([(0.2, False), (0.2, False), (0.2, False)])

    result = WorkflowRunner(evaluator=evaluator).run(
        PromptOptimizationRequest(user_request="写一条生日祝福，输出一句话。"),
        max_iterations=3,
    )

    assert result.status == WorkflowStatus.COMPLETED
    assert len(result.iterations) == 3
    assert evaluator.calls == 3
    assert result.optimization is not None
    assert result.final_evaluation.score == 0.2


def test_best_version_is_retained_even_when_later_version_passes() -> None:
    evaluator = SequenceEvaluator([(0.5, False), (0.9, False), (0.7, True)])

    result = WorkflowRunner(evaluator=evaluator).run(
        PromptOptimizationRequest(user_request="写一条生日祝福，输出一句话。")
    )

    assert len(result.iterations) == 3
    assert result.final_evaluation.score == 0.9
    assert result.optimization.generated_prompt == result.iterations[1].prompt


@pytest.mark.parametrize("max_iterations", [0, 4])
def test_invalid_iteration_limit_is_rejected(max_iterations: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 3"):
        WorkflowRunner().run(
            PromptOptimizationRequest(user_request="写一句问候"),
            max_iterations=max_iterations,
        )


def test_cancellation_before_start_stops_workflow() -> None:
    runner = WorkflowRunner()
    runner.cancel()

    result = runner.run(PromptOptimizationRequest(user_request="写一句问候"))

    assert result.status == WorkflowStatus.CANCELLED
    assert result.iterations == []
    assert result.optimization is None


class CancellingEvaluator(PromptEvaluator):
    def __init__(self, runner: WorkflowRunner) -> None:
        super().__init__()
        self._runner = runner

    def evaluate(self, request, intent, generated, **kwargs) -> EvaluationReport:
        report = super().evaluate(request, intent, generated, **kwargs)
        self._runner.cancel()
        return report


def test_cancellation_after_evaluation_prevents_finalization() -> None:
    runner = WorkflowRunner()
    runner._evaluator = CancellingEvaluator(runner)

    result = runner.run(PromptOptimizationRequest(user_request="写一句问候"))

    assert result.status == WorkflowStatus.CANCELLED
    assert len(result.iterations) == 1
    assert result.optimization is None


def test_unexpected_node_error_is_sanitized() -> None:
    class BrokenAnalyzer:
        def analyze(self, request):
            raise RuntimeError("sensitive internal detail")

    result = WorkflowRunner(analyzer=BrokenAnalyzer()).run(
        PromptOptimizationRequest(user_request="写一句问候")
    )

    assert result.status == WorkflowStatus.FAILED
    assert result.error == "workflow stopped after RuntimeError"
    assert "sensitive" not in result.error


def test_model_error_stops_refinement() -> None:
    class FailingEvaluator(PromptEvaluator):
        def evaluate(self, request, intent, generated, **kwargs):
            raise RateLimitError("limited", provider="mock")

    result = WorkflowRunner(evaluator=FailingEvaluator()).run(
        PromptOptimizationRequest(user_request="写一句问候")
    )

    assert result.status == WorkflowStatus.FAILED
    assert "RateLimitError" in result.error
    assert result.iterations == []


def test_workflow_dynamic_evaluation_uses_mock_gateway() -> None:
    backend = MockBackend(["baseline", "optimized"])
    gateway = LLMGateway(
        Settings(_env_file=None),
        backends={Provider.MOCK: backend},
    )

    result = WorkflowRunner(
        evaluator=PromptEvaluator(gateway)
    ).run(
        PromptOptimizationRequest(user_request="写一条生日祝福。"),
        dynamic_evaluation=True,
    )

    assert result.status == WorkflowStatus.COMPLETED
    assert result.final_evaluation.dynamic_status == "completed"
    assert result.final_evaluation.optimized_output == "optimized"
    assert len(backend.calls) == 2


def test_dynamic_budget_limit_stops_calls_and_returns_warning() -> None:
    backend = MockBackend()
    gateway = LLMGateway(
        Settings(_env_file=None, max_calls=1),
        backends={Provider.MOCK: backend},
    )

    result = WorkflowRunner(
        evaluator=PromptEvaluator(gateway)
    ).run(
        PromptOptimizationRequest(user_request="写一条生日祝福。"),
        dynamic_evaluation=True,
    )

    assert result.status == WorkflowStatus.COMPLETED
    assert result.final_evaluation.dynamic_status == "failed"
    assert "BudgetExceededError" in result.final_evaluation.warnings[0]
    assert len(backend.calls) == 1


def test_dynamic_baseline_is_reused_across_three_iterations() -> None:
    backend = MockBackend(["bad baseline", "bad", "bad", "bad"])
    gateway = LLMGateway(
        Settings(_env_file=None),
        backends={Provider.MOCK: backend},
    )

    result = WorkflowRunner(
        evaluator=PromptEvaluator(gateway)
    ).run(
        PromptOptimizationRequest(user_request="生成结果，输出 JSON。"),
        dynamic_evaluation=True,
        max_iterations=3,
    )

    assert len(result.iterations) == 3
    assert len(backend.calls) == 4
    assert all(
        record.evaluation.baseline_output == "bad baseline"
        for record in result.iterations
    )
    assert "baseline_execution" not in result.model_dump()["final_evaluation"]
