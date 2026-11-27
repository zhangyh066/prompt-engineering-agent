from decimal import Decimal
import logging

import pytest

from pea.config import ProviderConfig, Settings
from pea.exceptions import (
    AuthenticationError,
    BudgetExceededError,
    ConfigurationError,
    ProviderError,
    RateLimitError,
)
from pea.gateway import LLMGateway, MockBackend
from pea.models import (
    BackendResult,
    ChatMessage,
    CompletionRequest,
    Provider,
    TokenUsage,
)


def make_request(provider: Provider = Provider.MOCK) -> CompletionRequest:
    return CompletionRequest(
        provider=provider,
        messages=[ChatMessage(role="user", content="test-private-prompt")],
    )


def test_mock_gateway_returns_normalized_response() -> None:
    backend = MockBackend(["local result"])
    clock_values = iter([10.0, 10.25])
    gateway = LLMGateway(
        Settings(_env_file=None),
        backends={Provider.MOCK: backend},
        clock=lambda: next(clock_values),
    )

    response = gateway.complete(make_request())

    assert response.content == "local result"
    assert response.provider == Provider.MOCK
    assert response.model == "mock-local"
    assert response.latency_seconds == 0.25
    assert response.attempts == 1
    assert response.usage.source == "mock_estimate"
    assert response.usage.total_tokens == 3
    assert response.cost_usd == Decimal("0")
    assert gateway.call_count == 1


def test_retryable_error_is_retried_with_bounded_delay() -> None:
    backend = MockBackend(
        [RateLimitError("limited", provider="mock"), "recovered"]
    )
    delays: list[float] = []
    clock_values = iter([1.0, 1.5])
    gateway = LLMGateway(
        Settings(
            _env_file=None,
            max_retries=2,
            retry_base_delay_seconds=0.25,
            retry_max_delay_seconds=2.0,
        ),
        backends={Provider.MOCK: backend},
        sleeper=delays.append,
        clock=lambda: next(clock_values),
    )

    response = gateway.complete(make_request())

    assert response.content == "recovered"
    assert response.attempts == 2
    assert response.latency_seconds == 0.5
    assert delays == [0.25]
    assert gateway.call_count == 2


def test_retry_limit_is_enforced() -> None:
    backend = MockBackend(
        [
            RateLimitError("first", provider="mock"),
            RateLimitError("second", provider="mock"),
        ]
    )
    gateway = LLMGateway(
        Settings(_env_file=None, max_retries=1, retry_base_delay_seconds=0),
        backends={Provider.MOCK: backend},
        sleeper=lambda _: None,
    )

    with pytest.raises(RateLimitError, match="second"):
        gateway.complete(make_request())

    assert len(backend.calls) == 2
    assert gateway.call_count == 2


def test_authentication_error_is_not_retried() -> None:
    backend = MockBackend([AuthenticationError("denied", provider="mock")])
    gateway = LLMGateway(
        Settings(_env_file=None, max_retries=5),
        backends={Provider.MOCK: backend},
    )

    with pytest.raises(AuthenticationError):
        gateway.complete(make_request())

    assert len(backend.calls) == 1


def test_unexpected_backend_error_is_wrapped() -> None:
    backend = MockBackend([RuntimeError("sensitive provider detail")])
    gateway = LLMGateway(
        Settings(_env_file=None),
        backends={Provider.MOCK: backend},
    )

    with pytest.raises(ProviderError) as captured:
        gateway.complete(make_request())

    assert "RuntimeError" in str(captured.value)
    assert "sensitive provider detail" not in str(captured.value)


def test_missing_backend_is_a_configuration_error() -> None:
    gateway = LLMGateway(Settings(_env_file=None), backends={})

    with pytest.raises(ConfigurationError, match="no backend"):
        gateway.complete(make_request())


class FixedCostBackend:
    def complete(
        self,
        request: CompletionRequest,
        config: ProviderConfig,
    ) -> BackendResult:
        return BackendResult(
            response_id="paid-test-response",
            provider=config.provider,
            model=config.model,
            content="ok",
            usage=TokenUsage(
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2,
                source="provider",
            ),
            cost_usd=Decimal("0.25"),
        )


def test_cost_budget_stops_subsequent_calls() -> None:
    gateway = LLMGateway(
        Settings(_env_file=None, cost_budget_usd=Decimal("0.25")),
        backends={Provider.MOCK: FixedCostBackend()},
    )

    first = gateway.complete(make_request())

    assert first.cost_usd == Decimal("0.25")
    assert gateway.total_cost_usd == Decimal("0.25")
    with pytest.raises(BudgetExceededError, match="cost budget"):
        gateway.complete(make_request())
    assert gateway.call_count == 1


def test_call_limit_counts_failed_attempts() -> None:
    backend = MockBackend([RateLimitError("limited", provider="mock")])
    gateway = LLMGateway(
        Settings(
            _env_file=None,
            max_calls=1,
            max_retries=1,
            retry_base_delay_seconds=0,
        ),
        backends={Provider.MOCK: backend},
        sleeper=lambda _: None,
    )

    with pytest.raises(BudgetExceededError, match="call limit"):
        gateway.complete(make_request())

    assert len(backend.calls) == 1
    assert gateway.call_count == 1


def test_gateway_logs_do_not_contain_prompt_or_api_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    backend = MockBackend(["safe result"])
    settings = Settings(
        _env_file=None,
        openai_api_key="test-sensitive-key",
        openai_model="gpt-test",
    )
    gateway = LLMGateway(
        settings,
        backends={Provider.OPENAI: backend},
    )

    with caplog.at_level(logging.INFO):
        gateway.complete(make_request(Provider.OPENAI))

    assert "test-private-prompt" not in caplog.text
    assert "test-sensitive-key" not in caplog.text
    assert "provider=openai" in caplog.text
