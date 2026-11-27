from pydantic import BaseModel, ConfigDict, Field

from pea.models.llm import ChatMessage, CompletionRequest, Provider


class TargetModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Provider
    model: str = Field(min_length=1)
    supports_system_message: bool = True
    supports_json_mode: bool = False
    max_output_tokens: int | None = Field(default=None, gt=0)


class AdaptedPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Provider
    model: str
    messages: list[ChatMessage] = Field(min_length=1)
    max_output_tokens: int | None = Field(default=None, gt=0)
    changes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def to_completion_request(self) -> CompletionRequest:
        return CompletionRequest(
            provider=self.provider,
            model=self.model,
            messages=self.messages,
            max_tokens=self.max_output_tokens,
            temperature=0.0,
        )
