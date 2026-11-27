from pea.agents import StructuredPromptOptimizer
from pea.models import (
    DetailLevel,
    ExplorationLevel,
    OptimizationPreferences,
    PromptOptimizationRequest,
)


def optimize_with_preferences(preferences: OptimizationPreferences, text: str):
    return StructuredPromptOptimizer().optimize(
        PromptOptimizationRequest(
            user_request=text,
            preferences=preferences,
        )
    )


def test_detailed_and_concise_preferences_change_generation_intent() -> None:
    detailed = optimize_with_preferences(
        OptimizationPreferences(detail_level=DetailLevel.DETAILED),
        "写一封项目延期邮件，说明原因、日期和补救措施。",
    )
    concise = optimize_with_preferences(
        OptimizationPreferences(detail_level=DetailLevel.CONCISE),
        "写一封项目延期邮件，说明原因、日期和补救措施。",
    )

    assert "不因追求简短删减关键内容" in detailed.generated_prompt.content
    assert "信息完整度优先于形式上的简洁" in detailed.generated_prompt.content
    assert "以最短篇幅保留关键交付物和约束" in concise.generated_prompt.content
    assert "没有重复背景或通用套话" in concise.generated_prompt.content


def test_exploratory_mode_adds_real_alternative_requirements() -> None:
    text = (
        "调研三个竞争产品的功能、价格、部署和集成能力，比较公开事实、推断和未知信息，"
        "形成对比表、进入建议和十二个月实施计划。必须引用来源和日期，不得编造价格或市场份额，"
        "并说明所有方案的成本、风险和适用条件。"
    )
    exploratory = optimize_with_preferences(
        OptimizationPreferences(exploration_level=ExplorationLevel.EXPLORATORY),
        text,
    )
    default = optimize_with_preferences(OptimizationPreferences(), text)

    assert "## 备选路径与反证" in exploratory.generated_prompt.content
    assert "什么新证据会推翻主结论" in exploratory.generated_prompt.content
    assert "何时应放弃主方案" in exploratory.generated_prompt.content
    assert "## 备选路径与反证" not in default.generated_prompt.content


def test_simple_task_does_not_get_exploratory_bloat() -> None:
    result = optimize_with_preferences(
        OptimizationPreferences(exploration_level=ExplorationLevel.EXPLORATORY),
        "写一句生日祝福",
    )

    assert "## 备选路径与反证" not in result.generated_prompt.content
