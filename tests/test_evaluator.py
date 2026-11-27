from decimal import Decimal

from pea.agents import StructuredPromptOptimizer
from pea.config import Settings
from pea.evaluation import PromptEvaluator
from pea.exceptions import ProviderTimeoutError
from pea.gateway import LLMGateway, MockBackend
from pea.models import (
    GeneratedPrompt,
    PromptChange,
    PromptOptimizationRequest,
    Provider,
)


def optimize(user_request: str, raw_prompt: str | None = None):
    request = PromptOptimizationRequest(
        user_request=user_request,
        raw_prompt=raw_prompt,
    )
    result = StructuredPromptOptimizer().optimize(request)
    return request, result.intent, result.generated_prompt


def test_static_evaluation_marks_dynamic_quality_as_unverified() -> None:
    request, intent, generated = optimize("写一条生日祝福，输出一句话。")

    report = PromptEvaluator().evaluate(request, intent, generated)

    assert report.passed is True
    assert report.static_score == 1.0
    assert report.dynamic_status == "not_run"
    assert "dynamic_execution" in report.unverified_aspects


def test_static_evaluation_detects_missing_goal_and_constraints() -> None:
    request, intent, _ = optimize("写一封邮件，不超过100字，输出 JSON。")
    generated = GeneratedPrompt(
        content="## 任务目标\n写邮件",
        changes=[PromptChange(description="change", reason="reason")],
    )

    report = PromptEvaluator().evaluate(request, intent, generated)

    assert report.passed is False
    assert report.score < 0.85
    assert len(report.issues) >= 2


def test_dynamic_evaluation_executes_original_and_optimized_prompts() -> None:
    request, intent, generated = optimize("写一条生日祝福。", "写一条生日祝福。")
    backend = MockBackend(["original output", "optimized output"])
    gateway = LLMGateway(
        Settings(_env_file=None),
        backends={Provider.MOCK: backend},
    )

    report = PromptEvaluator(gateway).evaluate(
        request,
        intent,
        generated,
        dynamic=True,
    )

    assert report.dynamic_status == "completed"
    assert report.baseline_output == "original output"
    assert report.optimized_output == "optimized output"
    assert report.baseline_dynamic_score == 1.0
    assert report.dynamic_score == 1.0
    assert report.cost_usd == Decimal("0")
    assert report.usage.source == "mock_estimate"
    assert len(backend.calls) == 2


def test_dynamic_comparison_checks_json_without_llm_self_scoring() -> None:
    request, intent, generated = optimize("生成结果，输出 JSON。", "生成结果，输出 JSON。")
    backend = MockBackend(["not json", '{"result": "ok"}'])
    gateway = LLMGateway(
        Settings(_env_file=None),
        backends={Provider.MOCK: backend},
    )

    report = PromptEvaluator(gateway).evaluate(
        request,
        intent,
        generated,
        dynamic=True,
    )

    assert report.baseline_dynamic_score == 0.5
    assert report.dynamic_score == 1.0
    assert report.passed is True
    assert "content_accuracy" in report.unverified_aspects


def test_dynamic_length_constraint_uses_actual_output() -> None:
    request, intent, generated = optimize("写一句问候，不超过5字。", "写一句问候，不超过5字。")
    backend = MockBackend(["123456", "你好"])
    gateway = LLMGateway(
        Settings(_env_file=None),
        backends={Provider.MOCK: backend},
    )

    report = PromptEvaluator(gateway).evaluate(
        request,
        intent,
        generated,
        dynamic=True,
    )

    assert report.baseline_dynamic_score == 0.5
    assert report.dynamic_score == 1.0
    assert any(item.name == "dynamic_length_constraint" for item in report.metrics)


def test_dynamic_failure_returns_static_result_with_warning() -> None:
    request, intent, generated = optimize("写一条生日祝福。")
    backend = MockBackend(
        ["baseline", ProviderTimeoutError("timeout", provider="mock")]
    )
    gateway = LLMGateway(
        Settings(_env_file=None, max_retries=0),
        backends={Provider.MOCK: backend},
    )

    report = PromptEvaluator(gateway).evaluate(
        request,
        intent,
        generated,
        dynamic=True,
    )

    assert report.dynamic_status == "failed"
    assert report.passed is True
    assert report.warnings
    assert "ProviderTimeoutError" in report.warnings[0]


def test_english_length_limits_are_parsed() -> None:
    assert PromptEvaluator._length_limits(
        ["Output at least 10 words and no more than 20 words."]
    ) == (10, 20, "word")


def test_dynamic_request_without_gateway_is_explicit() -> None:
    request, intent, generated = optimize("写一条生日祝福。")

    report = PromptEvaluator().evaluate(request, intent, generated, dynamic=True)

    assert report.dynamic_status == "not_run"
    assert report.warnings
