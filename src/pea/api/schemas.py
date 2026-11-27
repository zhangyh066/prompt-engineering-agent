from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pea.models import OptimizationPreferences, PromptOptimizationRequest, Provider
from pea.models.adapter import TargetModel


class OptimizeAPIRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_request: str = Field(min_length=1, max_length=20_000)
    raw_prompt: str | None = Field(default=None, max_length=20_000)
    preferences: OptimizationPreferences = Field(default_factory=OptimizationPreferences)
    max_iterations: int = Field(default=3, ge=1, le=3)
    dynamic_evaluation: bool = False
    provider: Provider | None = None
    target_model: TargetModel | None = None

    def to_prompt_request(self) -> PromptOptimizationRequest:
        return PromptOptimizationRequest(
            user_request=self.user_request,
            raw_prompt=self.raw_prompt,
            preferences=self.preferences,
        )


class OpenAIChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class OpenAIChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str = "pea-optimizer"
    messages: list[OpenAIChatMessage] = Field(min_length=1)
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False

    @model_validator(mode="after")
    def require_user_message(self) -> "OpenAIChatRequest":
        if not any(
            message.role == "user" and message.content.strip()
            for message in self.messages
        ):
            raise ValueError("at least one nonblank user message is required")
        return self


class CancelAPIResponse(BaseModel):
    run_id: str
    status: str = "cancellation_requested"
