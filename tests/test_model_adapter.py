import pytest

from pea.adapters import ModelAdapter
from pea.agents import StructuredPromptOptimizer
from pea.exceptions import ConfigurationError
from pea.models import PromptOptimizationRequest, Provider
from pea.models.adapter import TargetModel
from pea.workflow import WorkflowRunner


def optimize(text: str):
    return StructuredPromptOptimizer().optimize(
        PromptOptimizationRequest(user_request=text)
    )


def test_openai_target_preserves_model_and_output_limit() -> None:
    result = optimize("生成销售摘要，输出 JSON。")
    target = TargetModel(
        provider=Provider.OPENAI,
        model="gpt-test",
        supports_json_mode=True,
        max_output_tokens=500,
    )

    adapted = ModelAdapter().adapt(
        result.generated_prompt,
        result.intent,
        target,
    )
    request = adapted.to_completion_request()

    assert adapted.provider == Provider.OPENAI
    assert len(adapted.messages) == 1
    assert adapted.messages[0].role == "user"
    assert request.model == "gpt-test"
    assert request.max_tokens == 500
    assert request.temperature == 0.0


def test_anthropic_conservative_json_fallback() -> None:
    result = optimize("生成销售摘要，输出 JSON。")
    target = TargetModel(
        provider=Provider.ANTHROPIC,
        model="claude-test",
        supports_json_mode=False,
    )

    adapted = ModelAdapter().adapt(
        result.generated_prompt,
        result.intent,
        target,
    )

    assert adapted.provider == Provider.ANTHROPIC
    assert "直接输出合法 JSON" in adapted.messages[-1].content
    assert "不要使用 Markdown 代码围栏" in adapted.messages[-1].content
    assert adapted.changes


def test_role_is_split_into_system_message_when_supported() -> None:
    result = optimize(
        "调研行业竞品的最新公开资料，首先检索来源，其次比较产品功能和价格，"
        "同时给出证据、结论与风险，不得编造来源，输出 Markdown 表格。"
        "需要区分事实与推断，并说明信息日期和不确定性，面向管理层。"
        "补充市场规模、渠道变化、主要机会、潜在威胁和后续行动建议。"
    )

    adapted = ModelAdapter().adapt(
        result.generated_prompt,
        result.intent,
        TargetModel(provider=Provider.OPENAI, model="gpt-test"),
    )

    assert len(adapted.messages) == 2
    assert adapted.messages[0].role == "system"
    assert adapted.messages[1].role == "user"
    assert "专业视角" not in adapted.messages[1].content


def test_no_system_support_keeps_role_in_user_message() -> None:
    result = optimize(
        "调研行业竞品的最新公开资料，首先检索来源，其次比较产品功能和价格，"
        "同时给出证据、结论与风险，不得编造来源，输出 Markdown 表格。"
        "需要区分事实与推断，并说明信息日期和不确定性，面向管理层。"
        "补充市场规模、渠道变化、主要机会、潜在威胁和后续行动建议。"
    )

    adapted = ModelAdapter().adapt(
        result.generated_prompt,
        result.intent,
        TargetModel(
            provider=Provider.ANTHROPIC,
            model="claude-test",
            supports_system_message=False,
        ),
    )

    assert len(adapted.messages) == 1
    assert "专业视角" in adapted.messages[0].content
    assert adapted.warnings


def test_mismatched_target_model_prefix_is_rejected() -> None:
    result = optimize("写一句问候")

    with pytest.raises(ConfigurationError, match="prefix"):
        ModelAdapter().adapt(
            result.generated_prompt,
            result.intent,
            TargetModel(provider=Provider.OPENAI, model="anthropic/claude-test"),
        )


def test_workflow_returns_optional_adapted_prompt() -> None:
    result = WorkflowRunner().run(
        PromptOptimizationRequest(user_request="写一句生日祝福"),
        target_model=TargetModel(provider=Provider.OPENAI, model="gpt-test"),
    )

    assert result.status == "completed"
    assert result.adapted_prompt is not None
    assert result.adapted_prompt.provider == Provider.OPENAI
    assert result.adapted_prompt.to_completion_request().model == "gpt-test"
