import json
import re

from pea.models.benchmark import BenchmarkTask, CheckKind, OutputCheck, RunScore
from pea.models.workflow import EvaluationMetric

_FORMAT_CHECKS = {CheckKind.VALID_JSON, CheckKind.MARKDOWN, CheckKind.TABLE}


class BenchmarkGrader:
    def grade(self, task: BenchmarkTask, output: str | None) -> RunScore:
        text = output or ""
        metrics = [self._check(task, check, text) for check in task.checks]
        score = sum(item.score for item in metrics) / len(metrics)
        unverified = ["semantic_task_completion"]
        if not any(check.kind == CheckKind.REFERENCE_ANSWER for check in task.checks):
            unverified.append("content_accuracy")
        return RunScore(
            score=score,
            passed=all(item.passed for item in metrics),
            metrics=metrics,
            unverified_aspects=unverified,
        )

    def _check(
        self,
        task: BenchmarkTask,
        check: OutputCheck,
        output: str,
    ) -> EvaluationMetric:
        kind = check.kind
        if not output.strip():
            return EvaluationMetric(
                name=kind.value,
                score=0.0,
                passed=False,
                details="执行结果为空，所有交付检查均失败",
                source="dynamic",
            )
        passed = False
        details = kind.value
        if kind == CheckKind.NON_EMPTY:
            passed = bool(output.strip())
            details = "执行结果必须非空"
        elif kind == CheckKind.VALID_JSON:
            try:
                json.loads(output)
                passed = True
            except (json.JSONDecodeError, TypeError):
                pass
            details = "执行结果必须是合法 JSON"
        elif kind == CheckKind.MARKDOWN:
            passed = any(marker in output for marker in ("#", "- ", "|", "```"))
            details = "执行结果必须包含 Markdown 结构"
        elif kind == CheckKind.TABLE:
            passed = "|" in output and "\n" in output
            details = "执行结果必须包含表格结构"
        elif kind in {CheckKind.MAX_CHARACTERS, CheckKind.MIN_CHARACTERS}:
            actual = len(output.strip())
            expected = int(check.value)
            passed = actual <= expected if kind == CheckKind.MAX_CHARACTERS else actual >= expected
            details = f"字符数 {actual}，检查阈值 {expected}"
        elif kind == CheckKind.CONTAINS:
            passed = str(check.value) in output
            details = f"执行结果必须包含：{check.value}"
        elif kind == CheckKind.REGEX:
            passed = re.search(str(check.value), output, re.DOTALL) is not None
            details = f"执行结果必须匹配正则：{check.value}"
        elif kind == CheckKind.REFERENCE_ANSWER:
            if task.reference_answer is None:
                passed = False
                details = "缺少参考答案，无法执行内容准确性检查"
            else:
                passed = self._matches_reference(output, task.reference_answer)
                details = "执行结果与审核参考答案比较"

        return EvaluationMetric(
            name=kind.value,
            score=float(passed),
            passed=passed,
            details=details,
            source="dynamic",
        )

    @staticmethod
    def _matches_reference(output: str, reference: str) -> bool:
        try:
            return json.loads(output) == json.loads(reference)
        except json.JSONDecodeError:
            return output.strip() == reference.strip()


def is_format_metric(metric: EvaluationMetric) -> bool:
    return metric.name in {kind.value for kind in _FORMAT_CHECKS}


def is_constraint_metric(metric: EvaluationMetric) -> bool:
    return metric.name in {CheckKind.MAX_CHARACTERS.value, CheckKind.MIN_CHARACTERS.value}


def is_accuracy_metric(metric: EvaluationMetric) -> bool:
    return metric.name == CheckKind.REFERENCE_ANSWER.value
