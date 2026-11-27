from collections import Counter
import re
import string
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReferenceScore(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    exact_match: float = Field(ge=0.0, le=1.0)
    token_f1: float = Field(ge=0.0, le=1.0)
    primary_metric: Literal["exact_match", "token_f1", "auxiliary_token_f1"]
    primary_score: float = Field(ge=0.0, le=1.0)
    interpretation: str


def normalize_answer(text: str) -> str:
    lowered = text.lower()
    without_punctuation = lowered.translate(str.maketrans("", "", string.punctuation))
    tokens = [
        token
        for token in without_punctuation.split()
        if token not in {"a", "an", "the"}
    ]
    return " ".join(tokens)


def exact_match(prediction: str, reference: str) -> float:
    return float(normalize_answer(prediction) == normalize_answer(reference))


def token_f1(prediction: str, reference: str) -> float:
    prediction_tokens = normalize_answer(prediction).split()
    reference_tokens = normalize_answer(reference).split()
    if not prediction_tokens or not reference_tokens:
        return float(prediction_tokens == reference_tokens)
    common = Counter(prediction_tokens) & Counter(reference_tokens)
    overlap = sum(common.values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(prediction_tokens)
    recall = overlap / len(reference_tokens)
    return 2 * precision * recall / (precision + recall)


def score_reference(
    category: str,
    prediction: str,
    reference: str,
) -> ReferenceScore:
    exact = exact_match(prediction, reference)
    f1 = token_f1(prediction, reference)
    if category == "classification":
        return ReferenceScore(
            exact_match=exact,
            token_f1=f1,
            primary_metric="exact_match",
            primary_score=exact,
            interpretation="Classification accuracy uses normalized exact match",
        )
    if category in {"closed_qa", "information_extraction"}:
        return ReferenceScore(
            exact_match=exact,
            token_f1=f1,
            primary_metric="token_f1",
            primary_score=f1,
            interpretation="Token F1 is a reference overlap metric, not complete factual correctness",
        )
    return ReferenceScore(
        exact_match=exact,
        token_f1=f1,
        primary_metric="auxiliary_token_f1",
        primary_score=f1,
        interpretation="Open-ended tasks require human usefulness and faithfulness review; token F1 is auxiliary only",
    )
