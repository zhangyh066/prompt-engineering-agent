import pytest

from pea.evaluation.reference_metrics import (
    exact_match,
    normalize_answer,
    score_reference,
    token_f1,
)


def test_answer_normalization_and_exact_match() -> None:
    assert normalize_answer("The, Answer!") == "answer"
    assert exact_match("The, Answer!", "answer") == 1.0


def test_token_f1_handles_partial_overlap() -> None:
    assert token_f1("cat", "cat dog") == pytest.approx(2 / 3)
    assert token_f1("", "") == 1.0
    assert token_f1("cat", "dog") == 0.0


def test_classification_uses_accuracy_as_primary_metric() -> None:
    score = score_reference("classification", "Label A", "label a")

    assert score.primary_metric == "exact_match"
    assert score.primary_score == 1.0


def test_closed_qa_uses_f1_with_accuracy_limitation() -> None:
    score = score_reference("closed_qa", "cat", "cat dog")

    assert score.primary_metric == "token_f1"
    assert score.primary_score == pytest.approx(2 / 3)
    assert "not complete factual correctness" in score.interpretation


def test_open_ended_f1_is_auxiliary_only() -> None:
    score = score_reference("creative_writing", "short story", "short story")

    assert score.primary_metric == "auxiliary_token_f1"
    assert "human usefulness" in score.interpretation
