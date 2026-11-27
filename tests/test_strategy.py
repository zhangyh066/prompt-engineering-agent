from pea.agents import IntentAnalyzer, PromptDiagnostician, StrategyPlanner
from pea.models import PromptOptimizationRequest, StrategyType


def plan_for(user_request: str, raw_prompt: str | None = None):
    request = PromptOptimizationRequest(
        user_request=user_request,
        raw_prompt=raw_prompt,
    )
    analyzer = IntentAnalyzer()
    intent = analyzer.analyze(request)
    diagnosis = PromptDiagnostician().diagnose(request, intent)
    return StrategyPlanner().plan(intent, diagnosis)


def strategies(plan) -> set[StrategyType]:
    return {item.strategy for item in plan.selected}


def test_good_simple_prompt_uses_only_zero_shot() -> None:
    plan = plan_for("优化 Prompt", "写一条生日祝福，输出一句话。")

    assert strategies(plan) == {StrategyType.ZERO_SHOT}
    assert plan.lightweight is True


def test_constraints_and_output_format_select_targeted_strategies() -> None:
    plan = plan_for("写一份产品说明，输出 JSON，不得超过300字。")

    selected = strategies(plan)
    assert StrategyType.CONSTRAINT_BASED in selected
    assert StrategyType.STRUCTURED_OUTPUT in selected
    assert StrategyType.FEW_SHOT not in selected
    assert StrategyType.ROLE_PROMPTING not in selected


def test_few_shot_requires_actual_examples() -> None:
    without_examples = plan_for("写一条产品文案，输出标题和正文。")
    with_examples = plan_for(
        "按示例风格写产品文案。",
        "写产品文案。\n示例：轻盈一整天，从一杯咖啡开始。",
    )

    assert StrategyType.FEW_SHOT not in strategies(without_examples)
    assert StrategyType.FEW_SHOT in strategies(with_examples)


def test_latest_research_selects_react_instead_of_self_critique() -> None:
    plan = plan_for(
        "调研行业竞品的最新公开资料，首先检索来源，其次比较产品功能和价格，"
        "同时给出证据、结论与风险，不得编造来源，输出 Markdown 表格。"
        "需要区分事实与推断，并说明信息日期和不确定性。"
    )

    selected = strategies(plan)
    assert StrategyType.REACT in selected
    assert StrategyType.SELF_CRITIQUE not in selected
    assert all(item.reason for item in plan.selected)


def test_policy_can_disable_optional_strategies() -> None:
    from pea.models.policy import StrategyPolicy

    request = PromptOptimizationRequest(
        user_request=(
            "调研行业竞品的最新公开资料，首先检索来源，其次比较产品功能和价格，"
            "同时给出证据、结论与风险，不得编造来源，输出 Markdown 表格。"
            "需要区分事实与推断，并说明信息日期和不确定性。"
        ),
        raw_prompt="调研竞品。\n示例：产品A与产品B的比较表。",
    )
    intent = IntentAnalyzer().analyze(request)
    diagnosis = PromptDiagnostician().diagnose(request, intent)
    policy = StrategyPolicy(
        few_shot=False,
        role_prompting=False,
        task_decomposition=False,
        structured_output=False,
        self_critique=False,
        react=False,
    )

    plan = StrategyPlanner(policy=policy).plan(intent, diagnosis)
    selected = strategies(plan)

    assert StrategyType.ZERO_SHOT in selected
    assert StrategyType.FEW_SHOT not in selected
    assert StrategyType.ROLE_PROMPTING not in selected
    assert StrategyType.TASK_DECOMPOSITION not in selected
    assert StrategyType.STRUCTURED_OUTPUT not in selected
    assert StrategyType.SELF_CRITIQUE not in selected
    assert StrategyType.REACT not in selected


def test_every_strategy_has_cost_and_reason() -> None:
    plan = plan_for("写一份至少500字但不超过100字的报告，输出表格。")

    assert all(item.expected_cost in {"low", "medium", "high"} for item in plan.selected)
    assert all(item.reason for item in plan.selected)
    assert len(strategies(plan)) == len(plan.selected)
