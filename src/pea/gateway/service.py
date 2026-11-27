from collections.abc import Callable, Mapping
from decimal import Decimal
import logging
from threading import Lock
import time

from pea.config import Settings, get_settings
from pea.exceptions import (
    BudgetExceededError,
    ConfigurationError,
    LLMError,
    ProviderError,
)
from pea.gateway.base import LLMBackend
from pea.gateway.litellm_backend import LiteLLMBackend
from pea.gateway.mock import MockBackend
from pea.models import CompletionRequest, CompletionResponse, Provider

logger = logging.getLogger(__name__)


class LLMGateway:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        backends: Mapping[Provider, LLMBackend] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._settings = settings or get_settings()
        if backends is None:
            litellm_backend = LiteLLMBackend(
                local_model_cost_map=self._settings.litellm_local_model_cost_map,
            )
            backends = {
                Provider.MOCK: MockBackend(),
                Provider.OPENAI: litellm_backend,
                Provider.ANTHROPIC: litellm_backend,
            }
        self._backends = dict(backends)
        self._sleeper = sleeper
        self._clock = clock
        self._call_count = 0
        self._total_cost_usd = Decimal("0")
        self._lock = Lock()

    @property
    def call_count(self) -> int:
        with self._lock:
            return self._call_count

    @property
    def total_cost_usd(self) -> Decimal:
        with self._lock:
            return self._total_cost_usd

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        provider = request.provider or self._settings.default_provider
        config = self._settings.provider_config(provider, request.model)
        backend = self._backends.get(provider)
        if backend is None:
            raise ConfigurationError(
                f"no backend registered for {provider.value}",
                provider=provider.value,
            )

        started = self._clock()
        max_attempts = self._settings.max_retries + 1
        for attempt in range(1, max_attempts + 1):
            self._reserve_call(provider)
            logger.info(
                "llm request started provider=%s model=%s attempt=%d",
                provider.value,
                config.model,
                attempt,
            )
            try:
                result = backend.complete(request, config)
            except LLMError as error:
                if error.retryable and attempt < max_attempts:
                    delay = self._retry_delay(attempt)
                    logger.warning(
                        "llm request retry provider=%s attempt=%d error_type=%s delay=%.3f",
                        provider.value,
                        attempt,
                        type(error).__name__,
                        delay,
                    )
                    self._sleeper(delay)
                    continue
                logger.error(
                    "llm request failed provider=%s attempt=%d error_type=%s",
                    provider.value,
                    attempt,
                    type(error).__name__,
                )
                raise
            except Exception as error:
                logger.error(
                    "llm request failed provider=%s attempt=%d error_type=%s",
                    provider.value,
                    attempt,
                    type(error).__name__,
                )
                raise ProviderError(
                    f"{provider.value} backend failed with {type(error).__name__}",
                    provider=provider.value,
                ) from error

            elapsed = max(0.0, self._clock() - started)
            response = CompletionResponse(
                **result.model_dump(),
                latency_seconds=elapsed,
                attempts=attempt,
            )
            if result.cost_usd is not None:
                with self._lock:
                    self._total_cost_usd += result.cost_usd
            logger.info(
                "llm request succeeded provider=%s model=%s attempts=%d "
                "prompt_tokens=%s completion_tokens=%s total_tokens=%s "
                "cost_usd=%s latency_seconds=%.6f",
                provider.value,
                response.model,
                attempt,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
                response.usage.total_tokens,
                str(response.cost_usd) if response.cost_usd is not None else "unknown",
                elapsed,
            )
            return response

        raise ProviderError(
            "retry loop ended without a response",
            provider=provider.value,
        )

    def _reserve_call(self, provider: Provider) -> None:
        with self._lock:
            if (
                self._settings.cost_budget_usd is not None
                and self._total_cost_usd >= self._settings.cost_budget_usd
            ):
                raise BudgetExceededError(
                    "configured cost budget is exhausted",
                    provider=provider.value,
                )
            if self._call_count >= self._settings.max_calls:
                raise BudgetExceededError(
                    "configured call limit is exhausted",
                    provider=provider.value,
                )
            self._call_count += 1

    def _retry_delay(self, attempt: int) -> float:
        exponential_delay = self._settings.retry_base_delay_seconds * (2 ** (attempt - 1))
        return min(exponential_delay, self._settings.retry_max_delay_seconds)


def create_gateway(settings: Settings | None = None) -> LLMGateway:
    return LLMGateway(settings=settings)
