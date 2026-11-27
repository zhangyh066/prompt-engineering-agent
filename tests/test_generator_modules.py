from pea.agents import StructuredPromptOptimizer
from pea.models import PromptOptimizationRequest


def test_embedded_context_is_split_without_content_duplication() -> None:
    raw_prompt = (
        "Summarize the main conclusion in three bullet points.\n\n"
        "Context:\nThe unique source fact is important. Researchers must not invent results."
    )

    result = StructuredPromptOptimizer().optimize(
        PromptOptimizationRequest(user_request="Optimize", raw_prompt=raw_prompt)
    )
    content = result.generated_prompt.content

    assert "## 输入材料与上下文" in content
    assert "## 背景与使用场景" not in content
    assert "The unique source fact is important." in content
    assert content.count("The unique source fact is important.") == 1
    assert "Researchers must not invent results." in content
    assert "## 验收标准" in content


def test_complex_research_prompt_has_task_specific_modules() -> None:
    raw_prompt = (
        "调研某公司进入企业知识管理市场的竞争方案。请比较飞书、钉钉、企业微信生态中的知识管理方案及两家独立厂商，"
        "重点分析权限、部署、检索、集成和总拥有成本。输出先给结论，再给对比表和12个月进入计划；"
        "必须区分公开事实、合理推断和未知信息；引用来源及发布日期；不得编造价格或市场份额；"
        "不要给法律结论；如信息不足，列出需要补充的数据。\n\n"
        "Context:\n目标客户：200-2000人规模的制造企业；产品：支持中文检索、权限管理和私有化部署；"
        "预算：首年不超过80万元；区域：中国大陆。"
    )

    result = StructuredPromptOptimizer().optimize(
        PromptOptimizationRequest(
            user_request="请优化以下 Prompt，用于管理层竞品研究，保留所有约束。",
            raw_prompt=raw_prompt,
        )
    )
    content = result.generated_prompt.content

    for section in (
        "## 专业视角",
        "## 任务目标",
        "## 输入材料与上下文",
        "## 执行步骤",
        "## 工具与证据",
        "## 输出要求",
        "## 必须遵守的约束",
        "## 验收标准",
    ):
        assert section in content
    assert "明确研究问题、比较对象、范围和所需证据" in content
    assert "关键结论具有可核查来源和日期" in content
    assert content.count("首年不超过80万元") == 1
    assert "保留所有约束" not in content
    assert "用于管理层竞品研究" in content
    assert any("输出先给结论" in item for item in result.intent.output_requirements)
    assert result.diagnosis.assessments[1].score == 5
    assert "## 提交前检查" not in content
