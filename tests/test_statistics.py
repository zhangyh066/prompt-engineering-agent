import pytest

from pea.evaluation.statistics import compare_paired_scores


def test_paired_comparison_reports_clear_improvement() -> None:
    result = compare_paired_scores(
        [0.0, 0.0, 0.0],
        [1.0, 1.0, 1.0],
        bootstrap_samples=500,
    )

    assert result.wins == 3
    assert result.ties == 0
    assert result.losses == 0
    assert result.mean_difference == 1.0
    assert result.ci_lower == 1.0
    assert result.ci_upper == 1.0
    assert "positive" in result.interpretation


def test_paired_comparison_is_deterministic_and_handles_ties() -> None:
    arguments = {
        "baseline": [0.0, 1.0, 0.5, 0.5],
        "candidate": [0.0, 0.0, 1.0, 0.5],
        "bootstrap_samples": 500,
    }

    first = compare_paired_scores(**arguments)
    second = compare_paired_scores(**arguments)

    assert first == second
    assert first.wins == 1
    assert first.ties == 2
    assert first.losses == 1
    assert first.mean_difference == -0.125


def test_paired_comparison_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        compare_paired_scores([], [])
    with pytest.raises(ValueError):
        compare_paired_scores([0.0], [0.0, 1.0])
    with pytest.raises(ValueError):
        compare_paired_scores([0.0], [0.0], confidence=1.0)
