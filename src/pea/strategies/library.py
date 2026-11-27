from dataclasses import dataclass
from typing import Literal

from pea.models import StrategyType


@dataclass(frozen=True, slots=True)
class StrategyDefinition:
    strategy: StrategyType
    description: str
    applicability: str
    expected_cost: Literal["low", "medium", "high"]


_DEFINITIONS = {
    StrategyType.ZERO_SHOT: StrategyDefinition(
        strategy=StrategyType.ZERO_SHOT,
        description="使用清晰、直接的指令完成任务",
        applicability="所有任务的最小基线，不添加示例或推理要求",
        expected_cost="low",
    ),
    StrategyType.FEW_SHOT: StrategyDefinition(
        strategy=StrategyType.FEW_SHOT,
        description="利用用户提供的示例约束风格或格式",
        applicability="仅当原始材料中确实存在可复用示例",
        expected_cost="medium",
    ),
    StrategyType.ROLE_PROMPTING: StrategyDefinition(
        strategy=StrategyType.ROLE_PROMPTING,
        description="引入与任务直接相关的专业视角",
        applicability="复杂的数据或研究任务，且原 Prompt 未提供有效角色",
        expected_cost="low",
    ),
    StrategyType.TASK_DECOMPOSITION: StrategyDefinition(
        strategy=StrategyType.TASK_DECOMPOSITION,
        description="将多环节任务组织为明确的执行步骤",
        applicability="复杂任务或原 Prompt 缺少必要执行顺序",
        expected_cost="medium",
    ),
    StrategyType.STRUCTURED_OUTPUT: StrategyDefinition(
        strategy=StrategyType.STRUCTURED_OUTPUT,
        description="明确输出结构、格式和必要交付物",
        applicability="已有格式要求、输出规范缺失或结果需要复核",
        expected_cost="low",
    ),
    StrategyType.CONSTRAINT_BASED: StrategyDefinition(
        strategy=StrategyType.CONSTRAINT_BASED,
        description="保留并突出用户约束和冲突处理要求",
        applicability="用户给出约束，或诊断发现约束冲突",
        expected_cost="low",
    ),
    StrategyType.SELF_CRITIQUE: StrategyDefinition(
        strategy=StrategyType.SELF_CRITIQUE,
        description="提交前按目标、格式和约束检查结果",
        applicability="复杂研究或分析任务且质量风险较高；不要求展示推理过程",
        expected_cost="high",
    ),
    StrategyType.REACT: StrategyDefinition(
        strategy=StrategyType.REACT,
        description="在具备工具时交替获取证据和处理任务",
        applicability="明确需要最新信息、检索或外部工具的研究任务",
        expected_cost="high",
    ),
}


class StrategyLibrary:
    def get(self, strategy: StrategyType) -> StrategyDefinition:
        return _DEFINITIONS[strategy]

    def all(self) -> tuple[StrategyDefinition, ...]:
        return tuple(_DEFINITIONS.values())
