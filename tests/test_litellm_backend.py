from decimal import Decimal
import os
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import SecretStr

from pea.config import ProviderConfig
from pea.exceptions import (
    AuthenticationError,
    InvalidResponseError,
    ProviderError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitError,
)
from pea.gateway import LiteLLMBackend
from pea.models import ChatMessage, CompletionRequest, Provider


class FakeLiteLLM:
    def __init__(
        self,
        response: Any = None,
        error: Exception | None = None,
        cost_error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.cost_error = cost_error
        self.calls: list[dict[str, Any]] = []

    def completion(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response

    def completion_cost(self, completion_response: Any) -> str:
        if self.cost_error is not None:
            raise self.cost_error
        return "0.00123"


def make_response(content: str = "normalized response") -> SimpleNamespace:
    return SimpleNamespace(
        id="response-1",
        model="provider-model",
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=8,
            completion_tokens=3,
            total_tokens=11,
        ),
    )


@pytest.mark.parametrize(
    ("provider", "model", "expected_model"),
    [
        (Provider.OPENAI, "gpt-test", "openai/gpt-test"),
        (Provider.ANTHROPIC, "claude-test", "anthropic/claude-test"),
    ],
)
def test_litellm_backend_builds_provider_request_without_network(
    monkeypatch: pytest.MonkeyPatch,
    provider: Provider,
    model: str,
    expected_model: str,
) -> None:
    fake = FakeLiteLLM(make_response())
    environment_during_import: dict[str, str | None] = {}

    def loader(name: str) -> FakeLiteLLM:
        assert name == "litellm"
        environment_during_import["local_map"] = os.environ.get(
            "LITELLM_LOCAL_MODEL_COST_MAP"
        )
        return fake

    backend = LiteLLMBackend(local_model_cost_map=True, module_loader=loader)
    config = ProviderConfig(
        provider=provider,
        model=model,
        api_key=SecretStr("test-provider-key"),
        timeout_seconds=12.0,
    )
    request = CompletionRequest(
        provider=provider,
        messages=[ChatMessage(role="user", content="test request")],
        max_tokens=64,
        temperature=0.3,
    )

    result = backend.complete(request, config)

    assert environment_during_import["local_map"] == "True"
    assert fake.calls == [
        {
            "model": expected_model,
            "messages": [{"role": "user", "content": "test request"}],
            "temperature": 0.3,
            "timeout": 12.0,
            "num_retries": 0,
            "api_key": "test-provider-key",
            "max_tokens": 64,
        }
    ]
    assert result.content == "normalized response"
    assert result.usage.prompt_tokens == 8
    assert result.usage.total_tokens == 11
    assert result.usage.source == "provider"
    assert result.cost_usd == Decimal("0.00123")


def test_request_timeout_overrides_provider_default() -> None:
    fake = FakeLiteLLM(make_response())
    backend = LiteLLMBackend(module_loader=lambda _: fake)
    config = ProviderConfig(
        provider=Provider.OPENAI,
        model="gpt-test",
        api_key=SecretStr("test-key"),
        timeout_seconds=30.0,
    )
    request = CompletionRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        timeout_seconds=4.0,
    )

    backend.complete(request, config)

    assert fake.calls[0]["timeout"] == 4.0


class AuthenticationFailure(Exception):
    pass


AuthenticationFailure.__name__ = "AuthenticationError"


class RateLimitFailure(Exception):
    pass


RateLimitFailure.__name__ = "RateLimitError"


class TimeoutFailure(Exception):
    pass


TimeoutFailure.__name__ = "APITimeoutError"


class UnavailableFailure(Exception):
    pass


UnavailableFailure.__name__ = "ServiceUnavailableError"


@pytest.mark.parametrize(
    ("error", "expected_type", "retryable"),
    [
        (AuthenticationFailure("secret detail"), AuthenticationError, False),
        (RateLimitFailure("secret detail"), RateLimitError, True),
        (TimeoutFailure("secret detail"), ProviderTimeoutError, True),
        (UnavailableFailure("secret detail"), ProviderUnavailableError, True),
        (ValueError("secret detail"), ProviderError, False),
    ],
)
def test_provider_errors_are_mapped_and_sanitized(
    error: Exception,
    expected_type: type[Exception],
    retryable: bool,
) -> None:
    fake = FakeLiteLLM(error=error)
    backend = LiteLLMBackend(module_loader=lambda _: fake)
    config = ProviderConfig(
        provider=Provider.OPENAI,
        model="gpt-test",
        api_key=SecretStr("test-key"),
    )
    request = CompletionRequest(
        messages=[ChatMessage(role="user", content="Hello")]
    )

    with pytest.raises(expected_type) as captured:
        backend.complete(request, config)

    assert captured.value.retryable is retryable
    assert "secret detail" not in str(captured.value)
    assert "test-key" not in str(captured.value)


def test_empty_provider_content_is_rejected() -> None:
    fake = FakeLiteLLM(make_response(content=""))
    backend = LiteLLMBackend(module_loader=lambda _: fake)
    config = ProviderConfig(provider=Provider.OPENAI, model="gpt-test")
    request = CompletionRequest(
        messages=[ChatMessage(role="user", content="Hello")]
    )

    with pytest.raises(InvalidResponseError, match="no text content"):
        backend.complete(request, config)


def test_cost_failure_is_explicitly_unknown() -> None:
    fake = FakeLiteLLM(make_response(), cost_error=ValueError("unknown model"))
    backend = LiteLLMBackend(module_loader=lambda _: fake)
    config = ProviderConfig(provider=Provider.OPENAI, model="gpt-test")
    request = CompletionRequest(
        messages=[ChatMessage(role="user", content="Hello")]
    )

    result = backend.complete(request, config)

    assert result.content == "normalized response"
    assert result.cost_usd is None


def test_missing_usage_remains_unknown_instead_of_zero() -> None:
    response = make_response()
    response.usage = None
    fake = FakeLiteLLM(response)
    backend = LiteLLMBackend(module_loader=lambda _: fake)
    config = ProviderConfig(provider=Provider.OPENAI, model="gpt-test")
    request = CompletionRequest(
        messages=[ChatMessage(role="user", content="Hello")]
    )

    result = backend.complete(request, config)

    assert result.usage.prompt_tokens is None
    assert result.usage.completion_tokens is None
    assert result.usage.total_tokens is None
