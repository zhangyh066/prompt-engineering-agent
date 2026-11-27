from datetime import datetime, timezone
import json

import pytest
from pydantic import ValidationError

from pea.evaluation.benchmark import BenchmarkLoader, validate_benchmark
from pea.evaluation.grader import BenchmarkGrader
from pea.exceptions import ConfigurationError
from pea.models.benchmark import (
    BenchmarkTask,
    CheckKind,
    OutputCheck,
    ReviewStatus,
)
from pea.models.prompt import TaskType


def task_by_id(task_id: str) -> BenchmarkTask:
    return next(task for task in BenchmarkLoader().load() if task.task_id == task_id)


def test_full_draft_benchmark_has_exact_distribution() -> None:
    tasks = BenchmarkLoader().load()
    report = validate_benchmark(tasks)

    assert report.total == 100
    assert report.unique_task_ids == 100
    assert report.pending_human_review == 100
    assert report.approved == 0
    assert report.ready_for_real_model_experiments is False
    assert report.distribution == {
        TaskType.BUSINESS_WRITING: 20,
        TaskType.CONTENT_CREATION: 20,
        TaskType.DATA_ANALYSIS: 15,
        TaskType.SUMMARIZATION: 15,
        TaskType.EMAIL_OFFICE: 15,
        TaskType.RESEARCH: 15,
    }


def test_real_experiment_loading_requires_human_approval() -> None:
    with pytest.raises(ConfigurationError, match="human approval"):
        BenchmarkLoader().load(require_approved=True)


def test_all_100_tasks_with_review_metadata_become_ready() -> None:
    reviewed_at = datetime.now(timezone.utc).isoformat()
    approved_tasks = []
    for task in BenchmarkLoader().load():
        data = task.model_dump(mode="json")
        data.update(
            review_status="approved",
            reviewer="test-human-reviewer",
            reviewed_at=reviewed_at,
        )
        approved_tasks.append(BenchmarkTask.model_validate(data))

    report = validate_benchmark(approved_tasks)

    assert report.approved == 100
    assert report.pending_human_review == 0
    assert report.ready_for_real_model_experiments is True


def test_duplicate_task_ids_are_rejected(tmp_path) -> None:
    task = BenchmarkLoader().load()[0]
    path = tmp_path / "duplicates.jsonl"
    path.write_text(
        task.model_dump_json() + "\n" + task.model_dump_json(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="unique"):
        BenchmarkLoader().load(path, require_full=False)


def test_approved_task_requires_reviewer_and_timestamp() -> None:
    task = BenchmarkLoader().load()[0]
    data = task.model_dump(mode="json")
    data["review_status"] = "approved"

    with pytest.raises(ValidationError, match="reviewer"):
        BenchmarkTask.model_validate(data)

    data.update(
        reviewer="human-reviewer",
        reviewed_at=datetime.now(timezone.utc).isoformat(),
    )
    approved = BenchmarkTask.model_validate(data)
    assert approved.review_status == ReviewStatus.APPROVED


@pytest.mark.parametrize(
    "check",
    [
        {"kind": "max_characters", "value": 0},
        {"kind": "contains"},
        {"kind": "regex", "value": "["},
    ],
)
def test_invalid_output_checks_are_rejected(check: dict) -> None:
    with pytest.raises(ValidationError):
        OutputCheck.model_validate(check)


def test_reference_json_is_compared_semantically() -> None:
    task = task_by_id("data_001")

    score = BenchmarkGrader().grade(task, '{\n  "total": 550\n}')

    assert score.passed is True
    assert score.score == 1.0
    assert "semantic_task_completion" in score.unverified_aspects
    assert "content_accuracy" not in score.unverified_aspects


def test_inaccurate_reference_result_fails() -> None:
    task = task_by_id("data_001")

    score = BenchmarkGrader().grade(task, '{"total": 500}')

    assert score.passed is False
    assert score.score < 1.0


def test_missing_output_fails_checks() -> None:
    task = BenchmarkLoader().load()[1]

    score = BenchmarkGrader().grade(task, None)

    assert score.passed is False
    assert all(not metric.passed for metric in score.metrics)
