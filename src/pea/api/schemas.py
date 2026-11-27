from pydantic import BaseModel, ConfigDict, Field

from pea.models import OptimizationPreferences, PromptOptimizationRequest, Provider
from pea.models.adapter import TargetModel


class OptimizeAPIRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_request: str = Field(min_length=1, max_length=20_000)
    raw_prompt: str | None = Field(default=None, max_length=20_000)
    preferences: OptimizationPreferences = Field(default_factory=OptimizationPreferences)
    max_iterations: int = Field(default=3, ge=1, le=3)
    dynamic_evaluation: bool = False
    provider: Provider = Provider.MOCK
    target_model: TargetModel | None = None

    def to_prompt_request(self) -> PromptOptimizationRequest:
        return PromptOptimizationRequest(
            user_request=self.user_request,
            raw_prompt=self.raw_prompt,
            preferences=self.preferences,
        )


class CancelAPIResponse(BaseModel):
    run_id: str
    status: str = "cancellation_requested"
