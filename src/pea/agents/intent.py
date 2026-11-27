import re

from pea.agents._text import contains_any, split_clauses, unique
from pea.models import (
    Complexity,
    IntentAnalysis,
    PromptOptimizationRequest,
    TaskType,
)

_TASK_KEYWORDS = (
    (TaskType.EMAIL_OFFICE, ("邮件", "email", "e-mail", "回信", "工作汇报", "请假")),
    (TaskType.SUMMARIZATION, ("总结", "摘要", "概括", "提炼", "会议纪要", "summar")),
    (TaskType.DATA_ANALYSIS, ("数据分析", "数据集", "统计", "趋势", "可视化", "sql", "表格分析")),
    (TaskType.RESEARCH, ("调研", "研究", "检索", "搜索", "竞品", "资料", "research")),
    (TaskType.BUSINESS_WRITING, ("商务", "商业", "提案", "方案", "合同", "汇报", "business")),
    (TaskType.CONTENT_CREATION, ("文案", "文章", "创作", "故事", "公众号", "小红书", "脚本", "标题", "content")),
)

_OUTPUT_MARKERS = (
    "输出格式",
    "输出要求",
    "输出",
    "return",
    "返回格式",
    "格式为",
    "以表格",
    "使用表格",
    "输出json",
    "输出 json",
    "markdown",
    "项目符号",
    "字数",
)
_CONSTRAINT_MARKERS = (
    "必须",
    "不要",
    "不能",
    "不得",
    "不超过",
    "至少",
    "最多",
    "保留",
    "仅限",
    "只用",
    "避免",
    "禁止",
    "以内",
    "以上",
    "must",
    "do not",
    "don't",
    "cannot",
    "no more than",
    "at least",
    "at most",
    "avoid",
    "only",
    "maximum",
    "minimum",
    "保持",
    "keep",
)
_CONTEXT_MARKERS = (
    "面向",
    "针对",
    "背景",
    "根据",
    "读者",
    "受众",
    "客户",
    "使用场景",
    "用于",
    "提供给",
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


def _clean_optimization_meta(value: str) -> str:
    if re.fullmatch(
        r"(?:please\s+)?optimi[sz]e\s+(?:this\s+)?prompt(?:\s+without\s+changing\s+its\s+intent)?[.!\s]*",
        value,
        re.IGNORECASE,
    ):
        return ""
    cleaned = re.sub(
        r"^\s*(?:请|麻烦|帮我)?\s*(?:优化|改进|润色)(?:一下)?(?:这个|此|以下)?\s*prompt\s*[，,：:、]?\s*",
        "",
        value,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"[，,、]?\s*(?:并)?(?:保留|不改变)(?:所有|全部|原有)?(?:要求|意图|约束|关键约束)[。.!！\s]*$",
        "",
        cleaned,
    )
    if not cleaned.strip():
        return ""
    return cleaned.strip()

class IntentAnalyzer:
    def analyze(self, request: PromptOptimizationRequest) -> IntentAnalysis:
        source = request.raw_prompt or request.user_request
        primary_instruction = source.split("\n\nContext:", 1)[0]
        directive_parts = [primary_instruction]
        if request.raw_prompt is not None:
            meta_directive = _clean_optimization_meta(request.user_request)
            if meta_directive and meta_directive != primary_instruction:
                directive_parts.append(meta_directive)
        directive_text = "\n".join(unique(directive_parts))
        lowered = directive_text.lower()
        clauses = split_clauses(directive_text)
        task_type = self._classify(primary_instruction.lower())
        output_requirements = self._output_requirements(clauses, lowered)
        constraints = unique(
            clause
            for clause in clauses
            if contains_any(clause.lower(), _CONSTRAINT_MARKERS)
            or re.search(r"\d+\s*(字|词|words?|characters?)", clause.lower())
        )
        context = unique(
            clause for clause in clauses if contains_any(clause.lower(), _CONTEXT_MARKERS)
        )
        examples = self._examples(directive_text)
        requires_tools = task_type == TaskType.RESEARCH and contains_any(
            lowered,
            ("最新", "实时", "联网", "检索", "搜索", "竞品", "资料调研"),
        )
        missing_information = self._missing_information(request, task_type)
        complexity = self._complexity(
            directive_text,
            task_type,
            constraints,
            examples,
        )

        return IntentAnalysis(
            goal=request.raw_prompt or request.user_request,
            task_type=task_type,
            complexity=complexity,
            output_requirements=output_requirements,
            constraints=constraints,
            context=context,
            examples=examples,
            missing_information=missing_information,
            needs_clarification=bool(missing_information),
            requires_tools=requires_tools,
        )

    @staticmethod
    def _classify(text: str) -> TaskType:
        scores = {
            task_type: sum(1 for keyword in keywords if keyword in text)
            for task_type, keywords in _TASK_KEYWORDS
        }
        best_type = max(scores, key=scores.get)
        return best_type if scores[best_type] > 0 else TaskType.GENERAL

    @staticmethod
    def _output_requirements(clauses: list[str], text: str) -> list[str]:
        requirements = []
        for clause in clauses:
            positions = [
                clause.lower().find(marker)
                for marker in _OUTPUT_MARKERS
                if marker in clause.lower()
            ]
            if positions:
                requirements.append(clause[min(positions):].strip())
        format_rules = (
            ("json", "输出必须为合法 JSON"),
            ("表格", "使用表格呈现结果"),
            ("markdown", "使用 Markdown 格式"),
            ("项目符号", "使用项目符号组织结果"),
            ("列表", "使用列表组织结果"),
        )
        requirements.extend(
            rule for marker, rule in format_rules if marker in text
        )
        return unique(requirements)

    @staticmethod
    def _examples(text: str) -> list[str]:
        pattern = re.compile(
            r"(?:^|\n)\s*(?:示例|例子|example)\s*\d*\s*[:：]\s*([^\n]+)",
            re.IGNORECASE,
        )
        return unique(match.group(1).strip() for match in pattern.finditer(text))[:3]

    @staticmethod
    def _missing_information(
        request: PromptOptimizationRequest,
        task_type: TaskType,
    ) -> list[str]:
        normalized = request.user_request.strip()
        vague_requests = {
            "优化一下",
            "帮我写个东西",
            "做分析",
            "写点东西",
            "处理一下",
            "help me with this",
            "improve it",
            "write something",
            "do this",
            "fix this",
        }
        missing = []
        if len(normalized) < 4 or normalized.lower() in vague_requests:
            missing.append("具体任务目标、使用场景和期望输出")
        if (
            task_type == TaskType.DATA_ANALYSIS
            and contains_any(normalized, ("根据以下数据", "分析以下数据", "分析如下数据"))
            and request.raw_prompt is None
            and len(normalized) < 40
        ):
            missing.append("待分析的数据、数据字段或明确的数据来源")
        return unique(missing)

    @staticmethod
    def _complexity(
        text: str,
        task_type: TaskType,
        constraints: list[str],
        examples: list[str],
    ) -> Complexity:
        score = 0
        if len(text) > 160:
            score += 2
        elif len(text) > 60:
            score += 1
        if len(constraints) >= 3:
            score += 1
        if task_type in {TaskType.DATA_ANALYSIS, TaskType.RESEARCH}:
            score += 1
        if contains_any(text, ("同时", "并且", "分步骤", "多阶段", "第一步", "其次")):
            score += 1
        if examples:
            score += 1
        if score >= 3:
            return Complexity.COMPLEX
        if score >= 1:
            return Complexity.MODERATE
        return Complexity.SIMPLE
