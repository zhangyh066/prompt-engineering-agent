import random
from statistics import mean

from pydantic import BaseModel, ConfigDict, Field


class PairedComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    samples: int = Field(ge=1)
    wins: int = Field(ge=0)
    ties: int = Field(ge=0)
    losses: int = Field(ge=0)
    mean_difference: float
    confidence: float = Field(gt=0.0, lt=1.0)
    ci_lower: float
    ci_upper: float
    interpretation: str


def compare_paired_scores(
    baseline: list[float],
    candidate: list[float],
    *,
    confidence: float = 0.95,
    bootstrap_samples: int = 2000,
    seed: int = 20261126,
) -> PairedComparison:
    if len(baseline) != len(candidate) or not baseline:
        raise ValueError("paired scores must have the same nonzero length")
    if not 0 < confidence < 1 or bootstrap_samples <= 0:
        raise ValueError("confidence must be in (0, 1) and bootstrap_samples positive")
    differences = [after - before for before, after in zip(baseline, candidate)]
    rng = random.Random(seed)
    resampled_means = []
    for _ in range(bootstrap_samples):
        sample = [differences[rng.randrange(len(differences))] for _ in differences]
        resampled_means.append(mean(sample))
    resampled_means.sort()
    lower_index = int((1 - confidence) / 2 * bootstrap_samples)
    upper_index = min(
        bootstrap_samples - 1,
        int((1 + confidence) / 2 * bootstrap_samples),
    )
    lower = resampled_means[lower_index]
    upper = resampled_means[upper_index]
    if lower > 0:
        interpretation = "Paired bootstrap interval supports a positive candidate difference"
    elif upper < 0:
        interpretation = "Paired bootstrap interval supports a negative candidate difference"
    else:
        interpretation = "Paired bootstrap interval includes zero; no clear difference is established"
    return PairedComparison(
        samples=len(differences),
        wins=sum(value > 0 for value in differences),
        ties=sum(value == 0 for value in differences),
        losses=sum(value < 0 for value in differences),
        mean_difference=mean(differences),
        confidence=confidence,
        ci_lower=lower,
        ci_upper=upper,
        interpretation=interpretation,
    )
