import re

from pea.agents._text import contains_any, unique
from pea.models import (
    Complexity,
    DiagnosticDimension,
    DimensionAssessment,
    IntentAnalysis,
    OptimizationPriority,
    PromptDiagnosis,
    PromptOptimizationRequest,
    TaskType,
)

_ACTION_MARKERS = (
    "写",
    "生成",
    "分析",
    "总结",
    "创作",
    "制定",
    "优化",
    "提取",
    "调研",
    "翻译",
    "write",
    "analyze",
    "summarize",
    "create",
)
_VAGUE_MARKERS = (
    "一些",
    "等等",
    "适当",
    "好一点",
    "尽量好",
    "相关内容",
    "什么的",
    "somewhat",
    "related stuff",
    "etc.",
    "and so on",
    "a bit",
)
_ROLE_MARKERS = ("你是", "角色", "作为", "act as", "role:")
_STEP_MARKERS = ("步骤", "首先", "其次", "第一", "第二", "1.", "step")
_OUTPUT_MARKERS = ("输出", "返回", "格式", "表格", "json", "markdown", "列表")


class PromptDiagnostician:
    def diagnose(
        self,
        request: PromptOptimizationRequest,
        intent: IntentAnalysis,
    ) -> PromptDiagnosis:
        if request.raw_prompt is None:
            return self._empty_diagnosis(
                self._has_length_conflict(request.user_request)
            )

        prompt = request.raw_prompt
        lowered = prompt.lower()
        length_conflict = self._has_length_conflict(prompt)
        assessments = [
            self._goal_assessment(prompt, lowered),
            self._context_assessment(prompt, intent),
            self._role_assessment(lowered, intent),
            self._decomposition_assessment(lowered, intent.complexity),
            self._output_assessment(lowered, intent),
            self._constraint_assessment(intent, length_conflict),
            self._ambiguity_assessment(lowered),
            self._executability_assessment(
                prompt,
                lowered,
                intent,
                length_conflict,
            ),
        ]
        overall_score = round(
            sum(item.score for item in assessments) / (len(assessments) * 5) * 100,
            2,
        )
        strengths = unique(
            finding
            for item in assessments
            if item.score >= 4
            for finding in item.findings
        )
        issues = unique(
            finding
            for item in assessments
            if item.score <= 2
            for finding in item.findings
        )
        suggestions = unique(
            suggestion for item in assessments for suggestion in item.suggestions
        )
        if length_conflict or overall_score < 50:
            priority = OptimizationPriority.HIGH
        elif overall_score < 80:
            priority = OptimizationPriority.MEDIUM
        else:
            priority = OptimizationPriority.LOW

        return PromptDiagnosis(
            overall_score=overall_score,
            priority=priority,
            assessments=assessments,
            strengths=strengths,
            issues=issues,
            suggestions=suggestions,
            needs_optimization=length_conflict or overall_score < 90,
        )

    @staticmethod
    def _empty_diagnosis(length_conflict: bool = False) -> PromptDiagnosis:
        labels = {
            DiagnosticDimension.GOAL_CLARITY: "明确任务目标和动作",
            DiagnosticDimension.CONTEXT_COMPLETENESS: "保留必要背景与受众信息",
            DiagnosticDimension.ROLE_SETTING: "仅在任务需要时添加专业视角",
            DiagnosticDimension.TASK_DECOMPOSITION: "按复杂度决定是否拆解任务",
            DiagnosticDimension.OUTPUT_FORMAT: "明确输出格式和验收标准",
            DiagnosticDimension.CONSTRAINTS: "保留并明确关键约束",
            DiagnosticDimension.AMBIGUITY_RISK: "消除模糊表述",
            DiagnosticDimension.EXECUTABILITY: "形成可直接执行的 Prompt",
        }
        conflict_finding = "用户需求中检测到上下文字数约束冲突"
        assessments = [
            DimensionAssessment(
                dimension=dimension,
                score=0,
                findings=[
                    "未提供原始 Prompt，无法评价该维度",
                    *(
                        [conflict_finding]
                        if length_conflict
                        and dimension
                        in {
                            DiagnosticDimension.CONSTRAINTS,
                            DiagnosticDimension.EXECUTABILITY,
                        }
                        else []
                    ),
                ],
                suggestions=[suggestion],
            )
            for dimension, suggestion in labels.items()
        ]
        issues = ["未提供原始 Prompt，需要从用户需求构建"]
        suggestions = list(labels.values())
        if length_conflict:
            issues.append(conflict_finding)
            suggestions.append("统一最小与最大长度要求，不得擅自选择其一")
        return PromptDiagnosis(
            overall_score=0.0,
            priority=OptimizationPriority.HIGH,
            assessments=assessments,
            issues=issues,
            suggestions=suggestions,
            needs_optimization=True,
        )

    @staticmethod
    def _goal_assessment(prompt: str, lowered: str) -> DimensionAssessment:
        if contains_any(lowered, _ACTION_MARKERS) and len(prompt.strip()) >= 10:
            return DimensionAssessment(
                dimension=DiagnosticDimension.GOAL_CLARITY,
                score=5,
                findings=["包含明确的任务动作"],
            )
        if contains_any(lowered, _ACTION_MARKERS):
            score = 4
        else:
            score = 2
        return DimensionAssessment(
            dimension=DiagnosticDimension.GOAL_CLARITY,
            score=score,
            findings=["任务动作或目标不够清晰"] if score <= 2 else ["任务目标基本可识别"],
            suggestions=["使用明确动词说明要完成的任务"] if score < 5 else [],
        )

    @staticmethod
    def _context_assessment(
        prompt: str,
        intent: IntentAnalysis,
    ) -> DimensionAssessment:
        if intent.context or contains_any(prompt.lower(), ("背景", "面向", "针对", "受众", "context", "目标客户")):
            return DimensionAssessment(
                dimension=DiagnosticDimension.CONTEXT_COMPLETENESS,
                score=5,
                findings=["包含背景、受众或应用场景信息"],
            )
        score = 3 if intent.complexity == Complexity.SIMPLE else 2
        return DimensionAssessment(
            dimension=DiagnosticDimension.CONTEXT_COMPLETENESS,
            score=score,
            findings=["未明确说明背景或受众"],
            suggestions=["补充会影响结果的背景、受众或使用场景"],
        )

    @staticmethod
    def _role_assessment(lowered: str, intent: IntentAnalysis) -> DimensionAssessment:
        if contains_any(lowered, _ROLE_MARKERS):
            return DimensionAssessment(
                dimension=DiagnosticDimension.ROLE_SETTING,
                score=5,
                findings=["已提供角色或专业视角"],
            )
        if intent.complexity == Complexity.SIMPLE:
            return DimensionAssessment(
                dimension=DiagnosticDimension.ROLE_SETTING,
                score=4,
                findings=["简单任务不强制要求角色设定"],
            )
        return DimensionAssessment(
            dimension=DiagnosticDimension.ROLE_SETTING,
            score=3,
            findings=["未设置角色；仅在专业视角能改善结果时需要补充"],
        )

    @staticmethod
    def _decomposition_assessment(
        lowered: str,
        complexity: Complexity,
    ) -> DimensionAssessment:
        if contains_any(lowered, _STEP_MARKERS):
            return DimensionAssessment(
                dimension=DiagnosticDimension.TASK_DECOMPOSITION,
                score=5,
                findings=["已提供任务步骤或执行顺序"],
            )
        if complexity == Complexity.SIMPLE:
            return DimensionAssessment(
                dimension=DiagnosticDimension.TASK_DECOMPOSITION,
                score=5,
                findings=["简单任务无需额外拆解"],
            )
        score = 2 if complexity == Complexity.COMPLEX else 3
        return DimensionAssessment(
            dimension=DiagnosticDimension.TASK_DECOMPOSITION,
            score=score,
            findings=["任务具有多个环节，但缺少明确执行顺序"],
            suggestions=["按输入处理、核心任务和输出检查拆分步骤"],
        )

    @staticmethod
    def _output_assessment(lowered: str, intent: IntentAnalysis) -> DimensionAssessment:
        if intent.output_requirements or contains_any(lowered, _OUTPUT_MARKERS):
            return DimensionAssessment(
                dimension=DiagnosticDimension.OUTPUT_FORMAT,
                score=5,
                findings=["包含输出形式或格式要求"],
            )
        return DimensionAssessment(
            dimension=DiagnosticDimension.OUTPUT_FORMAT,
            score=1,
            findings=["缺少可验证的输出格式要求"],
            suggestions=["明确输出结构、格式和必要字段"],
        )

    @staticmethod
    def _constraint_assessment(
        intent: IntentAnalysis,
        length_conflict: bool,
    ) -> DimensionAssessment:
        if length_conflict:
            return DimensionAssessment(
                dimension=DiagnosticDimension.CONSTRAINTS,
                score=1,
                findings=["检测到上下文字数约束冲突"],
                suggestions=["统一最小与最大长度要求，保留用户最终确认的约束"],
            )
        if intent.constraints:
            return DimensionAssessment(
                dimension=DiagnosticDimension.CONSTRAINTS,
                score=5,
                findings=["包含明确的约束条件"],
            )
        return DimensionAssessment(
            dimension=DiagnosticDimension.CONSTRAINTS,
            score=3,
            findings=["未提供额外约束；不应机械添加限制"],
        )

    @staticmethod
    def _ambiguity_assessment(lowered: str) -> DimensionAssessment:
        found = [marker for marker in _VAGUE_MARKERS if marker in lowered]
        score = max(1, 5 - 2 * len(found))
        return DimensionAssessment(
            dimension=DiagnosticDimension.AMBIGUITY_RISK,
            score=score,
            findings=(
                [f"存在模糊表述：{', '.join(found)}"] if found else ["未发现常见模糊表述"]
            ),
            suggestions=["将模糊词替换为可观察、可验收的要求"] if found else [],
        )

    @staticmethod
    def _executability_assessment(
        prompt: str,
        lowered: str,
        intent: IntentAnalysis,
        length_conflict: bool,
    ) -> DimensionAssessment:
        if length_conflict:
            return DimensionAssessment(
                dimension=DiagnosticDimension.EXECUTABILITY,
                score=1,
                findings=["约束冲突使任务无法同时满足"],
                suggestions=["先解决约束冲突，再执行 Prompt"],
            )
        if (
            len(prompt.strip()) >= 10
            and contains_any(lowered, _ACTION_MARKERS)
            and (intent.output_requirements or contains_any(lowered, _OUTPUT_MARKERS))
        ):
            return DimensionAssessment(
                dimension=DiagnosticDimension.EXECUTABILITY,
                score=5,
                findings=["任务动作和输出要求可直接执行"],
            )
        return DimensionAssessment(
            dimension=DiagnosticDimension.EXECUTABILITY,
            score=2,
            findings=["任务还缺少直接执行所需的信息"],
            suggestions=["明确输入、处理动作和最终交付物"],
        )

    @staticmethod
    def _has_length_conflict(prompt: str) -> bool:
        units = r"(?:字|词|words?|characters?)"
        maximums = [
            int(value)
            for value in re.findall(
                rf"(?:不超过|最多|至多|以内|小于|no more than|at most|maximum|max|less than|under)\s*(\d+)\s*{units}",
                prompt,
                re.IGNORECASE,
            )
        ]
        maximums.extend(
            int(value)
            for value in re.findall(
                rf"(\d+)\s*{units}\s*(?:以内|以下|之内)",
                prompt,
                re.IGNORECASE,
            )
        )
        minimums = [
            int(value)
            for value in re.findall(
                rf"(?:至少|不少于|大于|(?<!不)超过|at least|no less than|minimum|min)\s*(\d+)\s*{units}",
                prompt,
                re.IGNORECASE,
            )
        ]
        minimums.extend(
            int(value)
            for value in re.findall(
                rf"(\d+)\s*{units}\s*以上",
                prompt,
                re.IGNORECASE,
            )
        )
        return bool(maximums and minimums and min(maximums) < max(minimums))
