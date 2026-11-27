import pytest

from pea.agents import IntentAnalyzer, PromptDiagnostician
from pea.models import (
    DiagnosticDimension,
    OptimizationPriority,
    PromptOptimizationRequest,
)


def diagnose(user_request: str, raw_prompt: str | None = None):
    request = PromptOptimizationRequest(
        user_request=user_request,
        raw_prompt=raw_prompt,
    )
    intent = IntentAnalyzer().analyze(request)
    return PromptDiagnostician().diagnose(request, intent)


def assessment(result, dimension: DiagnosticDimension):
    return next(item for item in result.assessments if item.dimension == dimension)


def test_missing_raw_prompt_returns_eight_explicit_dimensions() -> None:
    result = diagnose("写一封客户回访邮件")

    assert len(result.assessments) == 8
    assert result.overall_score == 0
    assert result.priority == OptimizationPriority.HIGH
    assert result.needs_optimization is True


def test_well_structured_prompt_can_skip_major_optimization() -> None:
    prompt = (
        "你是一名资深数据分析师。请根据以下销售数据分析季度趋势，面向管理层。"
        "步骤：1. 检查数据；2. 计算同比和环比。"
        "输出 Markdown 表格，不超过500字，不得编造数据。"
    )

    result = diagnose(prompt, prompt)

    assert result.overall_score >= 90
    assert result.priority == OptimizationPriority.LOW
    assert result.needs_optimization is False
    assert result.strengths


def test_poor_prompt_identifies_output_and_ambiguity_problems() -> None:
    result = diagnose("优化 Prompt", "写一些东西，适当详细一点，相关内容等等。")

    assert assessment(result, DiagnosticDimension.OUTPUT_FORMAT).score == 1
    assert assessment(result, DiagnosticDimension.AMBIGUITY_RISK).score < 5
    assert result.needs_optimization is True
    assert result.suggestions


@pytest.mark.parametrize(
    "prompt",
    [
        "写一份至少500字但不超过100字的报告，输出表格。",
        "写一份100字以内但至少500字的报告，输出表格。",
        "写一份500字以上但不超过100字的报告，输出表格。",
        "Write a report with at least 500 words and no more than 100 words.",
    ],
)
def test_conflicting_length_constraints_are_detected(prompt: str) -> None:
    result = diagnose("优化 Prompt", prompt)

    assert assessment(result, DiagnosticDimension.CONSTRAINTS).score == 1
    assert assessment(result, DiagnosticDimension.EXECUTABILITY).score == 1
    assert result.priority == OptimizationPriority.HIGH
    assert any("冲突" in issue for issue in result.issues)


def test_english_ambiguity_is_detected() -> None:
    result = diagnose(
        "Optimize prompt",
        "Write a summary. Make it somewhat appropriate and add related stuff etc.",
    )

    assert assessment(result, DiagnosticDimension.AMBIGUITY_RISK).score <= 2


def test_simple_prompt_is_not_penalized_for_missing_role_or_steps() -> None:
    result = diagnose("优化 Prompt", "写一条生日祝福，输出一句话。")

    assert assessment(result, DiagnosticDimension.ROLE_SETTING).score == 4
    assert assessment(result, DiagnosticDimension.TASK_DECOMPOSITION).score == 5
