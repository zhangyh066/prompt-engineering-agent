from pydantic import BaseModel, ConfigDict, Field


class StrategyPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    few_shot: bool = True
    role_prompting: bool = True
    task_decomposition: bool = True
    structured_output: bool = True
    self_critique: bool = True
    react: bool = True


class PolicyCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    policy: StrategyPolicy
