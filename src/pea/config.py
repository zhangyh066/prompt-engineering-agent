from decimal import Decimal
from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from pea.exceptions import ConfigurationError
from pea.models import Provider


class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Provider
    model: str
    api_key: SecretStr | None = None
    api_base: str | None = None
    timeout_seconds: float = Field(default=30.0, gt=0.0, le=300.0)

    @property
    def litellm_model(self) -> str:
        if self.provider == Provider.MOCK:
            return self.model
        prefix = f"{self.provider.value}/"
        if "/" in self.model and not self.model.startswith(prefix):
            raise ConfigurationError(
                "model prefix does not match the selected provider",
                provider=self.provider.value,
            )
        return self.model if self.model.startswith(prefix) else f"{prefix}{self.model}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    default_provider: Provider = Field(
        default=Provider.OPENAI,
        validation_alias="PEA_DEFAULT_PROVIDER",
    )
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="OPENAI_API_KEY",
    )
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="ANTHROPIC_API_KEY",
    )
    openai_model: str | None = Field(default=None, validation_alias="OPENAI_MODEL")
    openai_api_base: str | None = Field(
        default=None,
        validation_alias="OPENAI_API_BASE",
    )
    anthropic_model: str | None = Field(
        default=None,
        validation_alias="ANTHROPIC_MODEL",
    )
    request_timeout_seconds: float = Field(
        default=30.0,
        validation_alias="PEA_REQUEST_TIMEOUT_SECONDS",
        gt=0.0,
        le=300.0,
    )
    max_retries: int = Field(
        default=2,
        validation_alias="PEA_MAX_RETRIES",
        ge=0,
        le=5,
    )
    retry_base_delay_seconds: float = Field(
        default=0.2,
        validation_alias="PEA_RETRY_BASE_DELAY_SECONDS",
        ge=0.0,
    )
    retry_max_delay_seconds: float = Field(
        default=2.0,
        validation_alias="PEA_RETRY_MAX_DELAY_SECONDS",
        ge=0.0,
    )
    cost_budget_usd: Decimal | None = Field(
        default=None,
        validation_alias="PEA_COST_BUDGET_USD",
        ge=0,
    )
    max_calls: int = Field(
        default=100,
        validation_alias="PEA_MAX_CALLS",
        gt=0,
        le=10_000,
    )
    litellm_local_model_cost_map: bool = Field(
        default=True,
        validation_alias="PEA_LITELLM_LOCAL_MODEL_COST_MAP",
    )
    log_level: str = Field(default="INFO", validation_alias="PEA_LOG_LEVEL")
    database_path: str = Field(
        default="data/pea.db",
        validation_alias="PEA_DATABASE_PATH",
    )
    enable_real_providers: bool = Field(
        default=False,
        validation_alias="PEA_ENABLE_REAL_PROVIDERS",
    )
    trusted_hosts: str = Field(
        default="127.0.0.1,localhost,testserver",
        validation_alias="PEA_TRUSTED_HOSTS",
    )

    @field_validator("openai_api_base")
    @classmethod
    def validate_openai_api_base(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "OPENAI_API_BASE must be an HTTP(S) base URL without credentials, query, or fragment"
            )
        return normalized

    @model_validator(mode="after")
    def validate_retry_delays(self) -> "Settings":
        if self.retry_max_delay_seconds < self.retry_base_delay_seconds:
            raise ValueError("retry maximum delay must be at least the base delay")
        return self

    def provider_config(
        self,
        provider: Provider,
        model_override: str | None = None,
    ) -> ProviderConfig:
        if provider == Provider.MOCK:
            return ProviderConfig(
                provider=provider,
                model=model_override or "mock-local",
                timeout_seconds=self.request_timeout_seconds,
            )

        if provider == Provider.OPENAI:
            configured_model = self.openai_model
            api_key = self.openai_api_key
            api_base = self.openai_api_base
            model_variable = "OPENAI_MODEL"
            key_variable = "OPENAI_API_KEY"
        elif provider == Provider.ANTHROPIC:
            configured_model = self.anthropic_model
            api_key = self.anthropic_api_key
            api_base = None
            model_variable = "ANTHROPIC_MODEL"
            key_variable = "ANTHROPIC_API_KEY"
        else:
            raise ConfigurationError(
                f"unsupported provider: {provider}",
                provider=str(provider),
            )

        selected_model = model_override if model_override is not None else configured_model
        if selected_model is None or not selected_model.strip():
            raise ConfigurationError(
                f"{model_variable} is required for {provider.value}",
                provider=provider.value,
            )
        if api_key is None or not api_key.get_secret_value().strip():
            raise ConfigurationError(
                f"{key_variable} is required for {provider.value}",
                provider=provider.value,
            )

        return ProviderConfig(
            provider=provider,
            model=selected_model.strip(),
            api_key=api_key,
            api_base=api_base,
            timeout_seconds=self.request_timeout_seconds,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
