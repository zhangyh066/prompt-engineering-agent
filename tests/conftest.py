from collections.abc import Iterator

import pytest

from pea.config import get_settings

ENVIRONMENT_NAMES = (
    "PEA_DEFAULT_PROVIDER",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_API_BASE",
    "ANTHROPIC_MODEL",
    "PEA_REQUEST_TIMEOUT_SECONDS",
    "PEA_MAX_RETRIES",
    "PEA_RETRY_BASE_DELAY_SECONDS",
    "PEA_RETRY_MAX_DELAY_SECONDS",
    "PEA_COST_BUDGET_USD",
    "PEA_MAX_CALLS",
    "PEA_LITELLM_LOCAL_MODEL_COST_MAP",
    "PEA_LOG_LEVEL",
    "PEA_DATABASE_PATH",
    "PEA_ENABLE_REAL_PROVIDERS",
    "PEA_TRUSTED_HOSTS",
    "LITELLM_LOCAL_MODEL_COST_MAP",
)


@pytest.fixture(autouse=True)
def isolate_model_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in ENVIRONMENT_NAMES:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
