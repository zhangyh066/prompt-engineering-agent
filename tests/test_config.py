from decimal import Decimal

import pytest
from pydantic import SecretStr, ValidationError

from pea.config import ProviderConfig, Settings
from pea.exceptions import ConfigurationError
from pea.models import Provider


def test_defaults_use_mock_and_local_cost_map() -> None:
    settings = Settings(_env_file=None)

    assert settings.default_provider == Provider.MOCK
    assert settings.litellm_local_model_cost_map is True
    assert settings.max_retries == 2
    assert settings.max_calls == 100
    assert settings.cost_budget_usd is None


@pytest.mark.parametrize(
    ("provider", "model", "expected"),
    [
        (Provider.OPENAI, "gpt-test", "openai/gpt-test"),
        (Provider.ANTHROPIC, "claude-test", "anthropic/claude-test"),
        (Provider.ANTHROPIC, "anthropic/claude-test", "anthropic/claude-test"),
    ],
)
def test_real_provider_config_builds_litellm_model(
    provider: Provider,
    model: str,
    expected: str,
) -> None:
    values = {
        Provider.OPENAI: {
            "openai_api_key": SecretStr("test-openai-key"),
            "openai_model": model,
        },
        Provider.ANTHROPIC: {
            "anthropic_api_key": SecretStr("test-anthropic-key"),
            "anthropic_model": model,
        },
    }

    config = Settings(_env_file=None, **values[provider]).provider_config(provider)

    assert config.litellm_model == expected
    assert config.timeout_seconds == 30.0
    assert config.api_key is not None


def test_real_provider_requires_model() -> None:
    settings = Settings(_env_file=None, openai_api_key="test-key")

    with pytest.raises(ConfigurationError, match="OPENAI_MODEL"):
        settings.provider_config(Provider.OPENAI)


def test_real_provider_requires_key_even_with_model_override() -> None:
    settings = Settings(_env_file=None)

    with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY"):
        settings.provider_config(Provider.ANTHROPIC, "claude-test")


def test_mismatched_model_prefix_is_rejected() -> None:
    config = ProviderConfig(
        provider=Provider.OPENAI,
        model="anthropic/claude-test",
        api_key=SecretStr("test-key"),
    )

    with pytest.raises(ConfigurationError, match="prefix"):
        _ = config.litellm_model


def test_secrets_are_masked_in_representations() -> None:
    settings = Settings(
        _env_file=None,
        openai_api_key="test-sensitive-key",
        openai_model="gpt-test",
    )
    config = settings.provider_config(Provider.OPENAI)

    assert "test-sensitive-key" not in repr(settings)
    assert "test-sensitive-key" not in repr(config)


def test_environment_aliases_are_loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PEA_DEFAULT_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-from-env")
    monkeypatch.setenv("PEA_MAX_RETRIES", "4")
    monkeypatch.setenv("PEA_COST_BUDGET_USD", "0.75")

    settings = Settings(_env_file=None)

    assert settings.default_provider == Provider.OPENAI
    assert settings.max_retries == 4
    assert settings.cost_budget_usd == Decimal("0.75")
    assert settings.provider_config(Provider.OPENAI).model == "gpt-from-env"


def test_openai_compatible_base_is_configured() -> None:
    settings = Settings(
        _env_file=None,
        openai_api_key="test-key",
        openai_model="compatible-model",
        openai_api_base="http://127.0.0.1:9000/v1/",
    )

    config = settings.provider_config(Provider.OPENAI)

    assert config.api_base == "http://127.0.0.1:9000/v1"
    assert config.litellm_model == "openai/compatible-model"


@pytest.mark.parametrize(
    "base_url",
    [
        "not-a-url",
        "ftp://example.com/v1",
        "https://user:password@example.com/v1",
        "https://example.com/v1?api_key=secret",
    ],
)
def test_invalid_openai_compatible_base_is_rejected(base_url: str) -> None:
    with pytest.raises(ValidationError, match="OPENAI_API_BASE"):
        Settings(_env_file=None, openai_api_base=base_url)


def test_invalid_retry_delay_range_is_rejected() -> None:
    with pytest.raises(ValidationError, match="base delay"):
        Settings(
            _env_file=None,
            retry_base_delay_seconds=3.0,
            retry_max_delay_seconds=1.0,
        )
