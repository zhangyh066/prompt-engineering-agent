from pea.agents.diagnosis import PromptDiagnostician
from pea.agents.intent import IntentAnalyzer
from pea.agents.strategy import StrategyPlanner
from pea.models import (
    Complexity,
    DetailLevel,
    DiagnosticDimension,
    ExplorationLevel,
    GeneratedPrompt,
    IntentAnalysis,
    OptimizationPreferences,
    PromptChange,
    PromptDiagnosis,
    PromptOptimizationRequest,
    PromptOptimizationResult,
    StrategyPlan,
    StrategyType,
    TaskType,
)
from pea.strategies import StrategyLibrary

_DEFAULT_OUTPUTS = {
    TaskType.BUSINESS_WRITING: "交付结构清晰、语气符合商务场景的完整文本",
    TaskType.CONTENT_CREATION: "交付符合目标渠道、受众和风格要求的完整成稿",
    TaskType.DATA_ANALYSIS: "依次给出关键结论、数据依据和必要的表格；区分事实与推断",
    TaskType.SUMMARIZATION: "给出简明摘要和关键要点，不遗漏原文的重要限定条件",
    TaskType.EMAIL_OFFICE: "交付可直接使用的邮件主题和正文；完整保留并具体呈现用户提供的事实、日期、原因和补救或行动信息，不得用通用礼貌语替代具体信息",
    TaskType.RESEARCH: "给出结论、支持证据、可核查来源和仍然不确定的信息",
    TaskType.GENERAL: "直接交付完整任务结果，避免解释 Prompt 本身",
}

_ROLES = {
    TaskType.DATA_ANALYSIS: "你是一名严谨的数据分析师，擅长区分数据事实、计算结果与业务推断。",
    TaskType.RESEARCH: "你是一名严谨的研究分析员，重视证据质量、来源可核查性和不确定性说明。",
}


class PromptGenerator:
    def __init__(self, library: StrategyLibrary | None = None) -> None:
        self._library = library or StrategyLibrary()

    def generate(
        self,
        request: PromptOptimizationRequest,
        intent: IntentAnalysis,
        diagnosis: PromptDiagnosis,
        plan: StrategyPlan,
        refinement_notes: list[str] | None = None,
    ) -> GeneratedPrompt:
        strategies = {item.strategy for item in plan.selected}
        ambiguity_score = next(
            item.score
            for item in diagnosis.assessments
            if item.dimension == DiagnosticDimension.AMBIGUITY_RISK
        )
        objective, embedded_context = self._split_goal(intent.goal)
        sections = []

        if StrategyType.ROLE_PROMPTING in strategies:
            sections.append(f"## 专业视角\n{_ROLES[intent.task_type]}")

        sections.append(f"## 任务目标\n{objective}")

        additional_context = [
            item
            for item in intent.context
            if item not in objective and item not in embedded_context
        ]
        if embedded_context or additional_context:
            context_parts = []
            if embedded_context:
                context_parts.append(embedded_context)
            context_parts.extend(f"- {item}" for item in additional_context)
            sections.append("## 输入材料与上下文\n" + "\n".join(context_parts))

        if ambiguity_score <= 2:
            sections.append(
                "## 歧义处理\n"
                "先指出模糊表述及可能的解释；无法从上下文确定时，列出必要假设。"
                "不得自行扩大任务范围或把模糊要求当作明确事实。"
            )

        if StrategyType.FEW_SHOT in strategies:
            sections.append(
                "## 用户提供的示例\n"
                + "\n".join(f"- {item}" for item in intent.examples)
                + "\n保持示例所体现的有效风格或格式，但不要照抄其具体内容。"
            )

        if StrategyType.TASK_DECOMPOSITION in strategies:
            steps = self._execution_steps(intent.task_type)
            sections.append(
                "## 执行步骤\n"
                + "\n".join(
                    f"{index}. {step}" for index, step in enumerate(steps, start=1)
                )
            )

        if StrategyType.REACT in strategies:
            sections.append(
                "## 工具与证据\n"
                "仅在当前环境确实提供检索或相关工具时使用工具。先获取与问题直接相关的资料，"
                "记录可核查来源，再形成结论；工具不可用或证据不足时明确说明，不得编造检索过程、数据或来源。"
            )

        if (
            request.preferences.exploration_level == ExplorationLevel.EXPLORATORY
            and intent.complexity != Complexity.SIMPLE
        ):
            sections.append(
                "## 备选路径与反证\n"
                + self._exploration_guidance(intent.task_type)
            )

        if refinement_notes:
            sections.append(
                "## 本轮修订重点\n"
                + "\n".join(f"- {item}" for item in refinement_notes)
            )

        output_items = list(
            intent.output_requirements or [_DEFAULT_OUTPUTS[intent.task_type]]
        )
        if request.preferences.detail_level == DetailLevel.DETAILED:
            output_items.append(
                "优先保证信息完整、论据充分和细节具体；除非用户给出明确长度上限，不因追求简短删减关键内容"
            )
        elif request.preferences.detail_level == DetailLevel.CONCISE:
            output_items.append(
                "删除重复背景和无关解释，以最短篇幅保留关键交付物和约束"
            )
        sections.append("## 输出要求\n" + "\n".join(f"- {item}" for item in output_items))

        constraint_items = [
            item for item in intent.constraints if item not in intent.goal
        ]
        if StrategyType.CONSTRAINT_BASED in strategies and any(
            "冲突" in issue for issue in diagnosis.issues
        ):
            constraint_items.append("若约束之间存在冲突，停止执行并列出冲突，不得自行选择其一")
        if intent.task_type in {TaskType.DATA_ANALYSIS, TaskType.RESEARCH}:
            constraint_items.append("信息或证据不足时明确说明，不得编造数据、事实或来源")
        if constraint_items:
            sections.append(
                "## 必须遵守的约束\n"
                + "\n".join(f"- {item}" for item in dict.fromkeys(constraint_items))
            )

        acceptance = self._acceptance_criteria(
            intent,
            strategies,
            ambiguity_score,
            request.preferences,
        )
        sections.append(
            "## 验收标准\n" + "\n".join(f"- {item}" for item in acceptance)
        )

        if StrategyType.SELF_CRITIQUE in strategies:
            sections.append(
                "## 提交前检查\n"
                "逐项对照输出要求与验收标准；发现问题时先修正再提交。"
                "不要输出内部分析或推理过程，只提交最终结果。"
            )

        changes = [
            PromptChange(
                description=(
                    "保留原始任务并进行轻量结构整理"
                    if plan.lightweight and request.raw_prompt is not None
                    else "拆分任务目标、输入材料、输出要求和验收标准"
                ),
                reason="减少背景重复，使执行者知道要做什么、依据什么输入以及如何判定结果合格",
                strategies=[StrategyType.ZERO_SHOT],
            )
        ]
        changes.extend(
            PromptChange(
                description=self._library.get(item.strategy).description,
                reason=item.reason,
                strategies=[item.strategy],
            )
            for item in plan.selected
            if item.strategy != StrategyType.ZERO_SHOT
        )
        if ambiguity_score <= 2:
            changes.append(
                PromptChange(
                    description="增加模糊表述识别与假设说明",
                    reason="诊断发现歧义风险，需要避免执行者自行扩大任务或猜测用户意图",
                    strategies=[StrategyType.ZERO_SHOT],
                )
            )
        if refinement_notes:
            changes.append(
                PromptChange(
                    description="根据上一轮评估反馈重新生成 Prompt",
                    reason="；".join(refinement_notes),
                    strategies=[item.strategy for item in plan.selected],
                )
            )
        return GeneratedPrompt(content="\n\n".join(sections), changes=changes)

    @staticmethod
    def _split_goal(goal: str) -> tuple[str, str]:
        objective, separator, context = goal.partition("\n\nContext:")
        return (objective or goal, context.strip() if separator else "")

    @staticmethod
    def _execution_steps(task_type: TaskType) -> list[str]:
        if task_type == TaskType.RESEARCH:
            return [
                "明确研究问题、比较对象、范围和所需证据，固定比较口径。",
                "获取并评估来源，记录发布日期、适用区域和关键证据；工具不可用时明确限制。",
                "按统一口径比较方案，区分公开事实、合理推断和未知信息。",
                "形成建议与实施计划，逐项对照输出要求和验收标准。",
            ]
        if task_type == TaskType.DATA_ANALYSIS:
            return [
                "检查字段、单位、缺失值和分析口径，不擅自修补数据。",
                "完成必要计算并保留数据依据，区分事实、计算结果和业务推断。",
                "解释异常与限制，再形成结论和建议。",
                "核对数值、图表和输出结构是否一致。",
            ]
        if task_type == TaskType.SUMMARIZATION:
            return [
                "识别原文的核心结论、关键事实、限定条件和行动项。",
                "按重要程度压缩内容，不添加原文之外的事实或结论。",
                "核对摘要是否遗漏会改变理解的重要条件。",
            ]
        return [
            "识别输入、目标受众和必要背景；信息不足时明确指出。",
            "围绕任务目标完成核心内容，不添加无关任务。",
            "按输出要求和验收标准检查具体信息、格式和约束。",
        ]

    @staticmethod
    def _exploration_guidance(task_type: TaskType) -> str:
        if task_type in {TaskType.RESEARCH, TaskType.DATA_ANALYSIS}:
            return (
                "提出至少一个替代假设或实施路径，列出支持与反对证据。"
                "明确什么新证据会推翻主结论，以及何时应切换到替代方案；不要只寻找支持最初判断的材料。"
            )
        if task_type in {
            TaskType.BUSINESS_WRITING,
            TaskType.CONTENT_CREATION,
            TaskType.EMAIL_OFFICE,
        }:
            return (
                "给出两种实质不同的切入角度，说明各自的适用场景、收益和代价。"
                "选择主方案时明确放弃另一方案的理由，不为凑多样性重复同一观点。"
            )
        return (
            "给出一个与主解释不同的合理解读，说明两种解读各自的证据边界。"
            "如果证据不足，保留分歧而不是编造争议。"
        )

    @staticmethod
    def _acceptance_criteria(
        intent: IntentAnalysis,
        strategies: set[StrategyType],
        ambiguity_score: int,
        preferences: OptimizationPreferences,
    ) -> list[str]:
        criteria = [
            "覆盖任务目标要求的全部交付物，保留事实、日期、数字和重要限定条件"
        ]
        if intent.task_type == TaskType.RESEARCH:
            criteria.extend(
                [
                    "关键结论具有可核查来源和日期，比较对象采用一致口径",
                    "公开事实、合理推断和未知信息明确分开，建议与实施计划对应研究证据",
                ]
            )
        elif intent.task_type == TaskType.DATA_ANALYSIS:
            criteria.extend(
                [
                    "计算口径、单位和数据依据清楚，数值与结论一致",
                    "事实、计算结果和业务推断明确分开，异常和限制不被隐藏",
                ]
            )
        elif intent.task_type == TaskType.SUMMARIZATION:
            criteria.append("摘要忠实原文、覆盖关键内容，不遗漏会改变理解的限定条件")
        elif intent.task_type in {
            TaskType.BUSINESS_WRITING,
            TaskType.CONTENT_CREATION,
            TaskType.EMAIL_OFFICE,
        }:
            criteria.append("成稿可直接使用，具体信息完整，不用空泛表达替代实际内容")
        else:
            criteria.append("直接回答任务问题，不添加无关内容")

        if intent.constraints:
            criteria.append("逐项满足字数、数量、语言和禁止事项；约束冲突时停止并指出")
        if StrategyType.STRUCTURED_OUTPUT in strategies:
            criteria.append("输出结构可逐项核对；要求机器可读时必须能够直接解析")
        if ambiguity_score <= 2:
            criteria.append("必要假设、歧义和未知信息均有明确标注")
        if preferences.detail_level == DetailLevel.DETAILED:
            criteria.append("关键论点具有具体事实、示例或证据支撑，信息完整度优先于形式上的简洁")
        elif preferences.detail_level == DetailLevel.CONCISE:
            criteria.append("没有重复背景或通用套话，每项内容都直接服务任务目标")
        if preferences.exploration_level == ExplorationLevel.EXPLORATORY:
            criteria.append("至少一个替代方案或反证具有明确适用条件，并说明何时应放弃主方案")
        return list(dict.fromkeys(criteria))


class StructuredPromptOptimizer:
    def __init__(
        self,
        analyzer: IntentAnalyzer | None = None,
        diagnostician: PromptDiagnostician | None = None,
        planner: StrategyPlanner | None = None,
        generator: PromptGenerator | None = None,
    ) -> None:
        self._analyzer = analyzer or IntentAnalyzer()
        self._diagnostician = diagnostician or PromptDiagnostician()
        self._planner = planner or StrategyPlanner()
        self._generator = generator or PromptGenerator()

    def optimize(
        self,
        request: PromptOptimizationRequest,
    ) -> PromptOptimizationResult:
        intent = self._analyzer.analyze(request)
        diagnosis = self._diagnostician.diagnose(request, intent)
        plan = self._planner.plan(intent, diagnosis)
        generated = self._generator.generate(request, intent, diagnosis, plan)
        return PromptOptimizationResult(
            request=request,
            intent=intent,
            diagnosis=diagnosis,
            strategy_plan=plan,
            generated_prompt=generated,
        )
