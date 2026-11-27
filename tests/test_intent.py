import pytest

from pea.agents import IntentAnalyzer
from pea.models import Complexity, PromptOptimizationRequest, TaskType


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("写一封给客户的专业邮件，说明交付延期", TaskType.EMAIL_OFFICE),
        ("为小红书创作一篇护肤品种草文案", TaskType.CONTENT_CREATION),
        ("分析销售数据的季度趋势并输出表格", TaskType.DATA_ANALYSIS),
        ("总结以下会议内容并提炼行动项", TaskType.SUMMARIZATION),
        ("写一份商务合作提案", TaskType.BUSINESS_WRITING),
        ("调研竞品的最新公开资料", TaskType.RESEARCH),
        ("帮我制定学习计划", TaskType.GENERAL),
    ],
)
def test_task_classification(text: str, expected: TaskType) -> None:
    intent = IntentAnalyzer().analyze(PromptOptimizationRequest(user_request=text))

    assert intent.task_type == expected


def test_extracts_output_constraints_context_and_examples() -> None:
    request = PromptOptimizationRequest(
        user_request="面向初学者写一份数据分析报告，输出 JSON，不超过800字，不要编造数据。",
        raw_prompt="分析销售趋势。\n示例：{\"conclusion\": \"增长\"}",
    )

    intent = IntentAnalyzer().analyze(request)

    assert intent.goal == request.raw_prompt
    assert intent.task_type == TaskType.DATA_ANALYSIS
    assert "输出必须为合法 JSON" in intent.output_requirements
    assert any("不超过800字" in item for item in intent.constraints)
    assert any("不要编造数据" in item for item in intent.constraints)
    assert any("面向初学者" in item for item in intent.context)
    assert intent.examples == ['{"conclusion": "增长"}']


@pytest.mark.parametrize("text", ["优化一下", "做分析", "写点东西", "Help me with this"])
def test_vague_requests_require_clarification(text: str) -> None:
    intent = IntentAnalyzer().analyze(PromptOptimizationRequest(user_request=text))

    assert intent.needs_clarification is True
    assert intent.missing_information


def test_normal_request_does_not_over_ask() -> None:
    intent = IntentAnalyzer().analyze(
        PromptOptimizationRequest(user_request="写一句生日祝福")
    )

    assert intent.needs_clarification is False
    assert intent.missing_information == []


def test_reference_context_does_not_drive_classification_or_complexity() -> None:
    raw_prompt = (
        "Based on the passage, describe the first solid-state device and its use.\n\n"
        "Context:\n"
        + ("Researchers must not ignore that prior research studied this topic. " * 12)
    )
    request = PromptOptimizationRequest(
        user_request="Optimize",
        raw_prompt=raw_prompt,
    )

    intent = IntentAnalyzer().analyze(request)

    assert intent.task_type != TaskType.RESEARCH
    assert intent.complexity != Complexity.COMPLEX
    assert intent.constraints == []
    assert intent.goal == request.raw_prompt


def test_research_with_latest_information_requires_tools() -> None:
    intent = IntentAnalyzer().analyze(
        PromptOptimizationRequest(user_request="调研竞品的最新公开资料并给出出处")
    )

    assert intent.task_type == TaskType.RESEARCH
    assert intent.requires_tools is True


def test_complexity_distinguishes_simple_and_multi_step_tasks() -> None:
    analyzer = IntentAnalyzer()
    simple = analyzer.analyze(PromptOptimizationRequest(user_request="写一句生日祝福"))
    complex_request = PromptOptimizationRequest(
        user_request=(
            "面向管理层完成销售数据分析，首先检查数据质量，其次计算同比和环比，"
            "同时给出趋势解释和异常原因，并且提出后续行动建议。"
            "必须区分事实和推断，不要编造数据，不超过800字，输出 Markdown 表格。"
            "补充必要的分析背景、指标定义和结论限制，最后给出可执行建议。"
        )
    )

    complex_intent = analyzer.analyze(complex_request)

    assert simple.complexity == Complexity.SIMPLE
    assert complex_intent.complexity == Complexity.COMPLEX
