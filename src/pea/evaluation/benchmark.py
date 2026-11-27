import json
from collections import Counter
from importlib import resources
from pathlib import Path

from pydantic import ValidationError

from pea.exceptions import ConfigurationError
from pea.models.benchmark import (
    BenchmarkTask,
    BenchmarkValidationReport,
    ReviewStatus,
)
from pea.models.prompt import TaskType

EXPECTED_DISTRIBUTION = {
    TaskType.BUSINESS_WRITING: 20,
    TaskType.CONTENT_CREATION: 20,
    TaskType.DATA_ANALYSIS: 15,
    TaskType.SUMMARIZATION: 15,
    TaskType.EMAIL_OFFICE: 15,
    TaskType.RESEARCH: 15,
}
DEFAULT_BENCHMARK_RESOURCE = resources.files("pea").joinpath(
    "resources/benchmarks/tasks_draft.jsonl"
)


class BenchmarkLoader:
    def load(
        self,
        path: Path | None = None,
        *,
        require_full: bool = True,
        require_approved: bool = False,
    ) -> list[BenchmarkTask]:
        source = path or DEFAULT_BENCHMARK_RESOURCE
        try:
            lines = source.read_text(encoding="utf-8").splitlines()
        except OSError as error:
            raise ConfigurationError(f"benchmark file is unavailable: {source}") from error

        tasks = []
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                tasks.append(BenchmarkTask.model_validate_json(line))
            except (ValidationError, ValueError) as error:
                raise ConfigurationError(
                    f"benchmark task validation failed at line {line_number}"
                ) from error

        report = validate_benchmark(tasks)
        if report.unique_task_ids != report.total:
            raise ConfigurationError("benchmark task IDs must be unique")
        if require_full and report.distribution != EXPECTED_DISTRIBUTION:
            raise ConfigurationError("benchmark distribution does not match the 100-task specification")
        if require_approved and not report.ready_for_real_model_experiments:
            raise ConfigurationError("all 100 benchmark tasks require human approval before real experiments")
        return tasks


def validate_benchmark(tasks: list[BenchmarkTask]) -> BenchmarkValidationReport:
    counts = Counter(task.category for task in tasks)
    approved = sum(task.review_status == ReviewStatus.APPROVED for task in tasks)
    return BenchmarkValidationReport(
        total=len(tasks),
        distribution=dict(counts),
        unique_task_ids=len({task.task_id for task in tasks}),
        pending_human_review=len(tasks) - approved,
        approved=approved,
        ready_for_real_model_experiments=(
            dict(counts) == EXPECTED_DISTRIBUTION and approved == 100
        ),
    )
