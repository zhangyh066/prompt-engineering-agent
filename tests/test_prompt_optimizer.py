import json

import pytest

from pea.agents import StructuredPromptOptimizer
from pea.exceptions import InvalidResponseError
from pea.models import (
    GeneratedPrompt,
    PromptChange,
    PromptOptimizationRequest,
    PromptOptimizationResult,
    StrategyType,
)
from pea.structured_output import StructuredOutputParser


def test_end_to_end_optimization_returns_typed_structured_result() -> None:
    raw_prompt = "写一封项目延期通知邮件，面向客户，不超过200字，输出邮件正文。"
    result = StructuredPromptOptimizer().optimize(
        PromptOptimizationRequest(
            user_request="请优化这个 Prompt，保持专业语气。",
            raw_prompt=raw_prompt,
        )
    )

    assert isinstance(result, PromptOptimizationResult)
    assert result.intent.goal == raw_prompt
    assert raw_prompt in result.generated_prompt.content
    assert "背景与使用场景" not in result.generated_prompt.content
    assert "## 验收标准" in result.generated_prompt.content
    assert result.generated_prompt.content.count("面向客户") == 1
    assert any("不超过200字" in item for item in result.intent.constraints)
    assert result.generated_prompt.changes
    assert all(change.reason for change in result.generated_prompt.changes)


def test_natural_language_request_can_generate_prompt_without_raw_prompt() -> None:
    result = StructuredPromptOptimizer().optimize(
        PromptOptimizationRequest(user_request="写一份新员工入职指南，输出 Markdown。")
    )

    assert result.diagnosis.overall_score == 0
    assert "新员工入职指南" in result.generated_prompt.content
    assert "使用 Markdown 格式" in result.generated_prompt.content
    assert result.generated_prompt.generation_method == "deterministic"


def test_good_prompt_uses_lightweight_generation() -> None:
    prompt = "写一条生日祝福，输出一句话。"
    result = StructuredPromptOptimizer().optimize(
        PromptOptimizationRequest(user_request="优化 Prompt", raw_prompt=prompt)
    )

    assert result.strategy_plan.lightweight is True
    assert result.generated_prompt.content.count("##") <= 3
    assert "专业视角" not in result.generated_prompt.content
    assert "用户提供的示例" not in result.generated_prompt.content


def test_conflicting_constraints_are_not_silently_resolved() -> None:
    result = StructuredPromptOptimizer().optimize(
        PromptOptimizationRequest(
            user_request="写一份至少500字但不超过100字的报告，输出表格。"
        )
    )

    assert "停止执行并列出冲突" in result.generated_prompt.content


def test_research_prompt_does_not_claim_tools_are_available() -> None:
    result = StructuredPromptOptimizer().optimize(
        PromptOptimizationRequest(user_request="调研竞品最新公开资料并给出来源，输出表格。")
    )

    assert "仅在当前环境确实提供" in result.generated_prompt.content
    assert "不得编造检索过程" in result.generated_prompt.content


def test_english_ambiguity_adds_explicit_handling() -> None:
    result = StructuredPromptOptimizer().optimize(
        PromptOptimizationRequest(
            user_request="Optimize prompt",
            raw_prompt="Write a summary. Make it somewhat appropriate and add related stuff etc.",
        )
    )

    assert "## 歧义处理" in result.generated_prompt.content
    assert "列出必要假设" in result.generated_prompt.content


def test_email_optimization_preserves_specific_content_and_filters_meta() -> None:
    raw_prompt = "给客户写封邮件，项目要延期到11月30日，原因是第三方接口延迟。语气专业点，别超过200字，要有补救措施和邮件主题。"
    result = StructuredPromptOptimizer().optimize(
        PromptOptimizationRequest(
            user_request="请优化这个 Prompt，保留所有要求。",
            raw_prompt=raw_prompt,
        )
    )

    assert "请优化这个 Prompt" not in result.generated_prompt.content
    assert all("保留所有要求" not in item for item in result.intent.constraints)
    assert "具体呈现用户提供的事实、日期、原因和补救或行动信息" in result.generated_prompt.content
    assert "行动请求清晰" not in result.generated_prompt.content

    with_extra_requirement = StructuredPromptOptimizer().optimize(
        PromptOptimizationRequest(
            user_request="请优化这个 Prompt，保持专业语气。",
            raw_prompt=raw_prompt,
        )
    )
    assert "保持专业语气" in with_extra_requirement.generated_prompt.content
    assert "请优化这个 Prompt" not in with_extra_requirement.generated_prompt.content


def test_structured_result_json_round_trip() -> None:
    result = StructuredPromptOptimizer().optimize(
        PromptOptimizationRequest(user_request="总结一份会议纪要，输出三个要点。")
    )

    restored = StructuredOutputParser.parse(
        PromptOptimizationResult,
        result.model_dump_json(),
    )

    assert restored == result
    assert json.loads(result.model_dump_json())["intent"]["task_type"] == "summarization"


def test_structured_parser_accepts_json_code_fence() -> None:
    generated = GeneratedPrompt(
        content="Task",
        changes=[PromptChange(description="Clarify", reason="Test")],
    )

    restored = StructuredOutputParser.parse(
        GeneratedPrompt,
        f"```json\n{generated.model_dump_json()}\n```",
    )

    assert restored == generated


def test_structured_parser_rejects_invalid_or_extra_fields() -> None:
    with pytest.raises(InvalidResponseError, match="GeneratedPrompt"):
        StructuredOutputParser.parse(GeneratedPrompt, "not json")

    with pytest.raises(InvalidResponseError):
        StructuredOutputParser.parse(
            GeneratedPrompt,
            json.dumps(
                {
                    "content": "Task",
                    "changes": [{"description": "x", "reason": "y", "strategies": []}],
                    "generation_method": "deterministic",
                    "unexpected": True,
                }
            ),
        )
