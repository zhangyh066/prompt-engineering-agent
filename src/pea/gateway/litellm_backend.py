from collections.abc import Callable
from decimal import Decimal
import importlib
import logging
import os
from typing import Any

from pea.config import ProviderConfig
from pea.exceptions import (
    AuthenticationError,
    InvalidResponseError,
    LLMError,
    ProviderError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitError,
)
from pea.models import BackendResult, CompletionRequest, TokenUsage

logger = logging.getLogger(__name__)


class LiteLLMBackend:
    def __init__(
        self,
        *,
        local_model_cost_map: bool = True,
        module_loader: Callable[[str], Any] = importlib.import_module,
    ) -> None:
        self._local_model_cost_map = local_model_cost_map
        self._module_loader = module_loader
        self._litellm: Any = None

    def _get_litellm(self) -> Any:
        if self._litellm is None:
            if self._local_model_cost_map:
                os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
            self._litellm = self._module_loader("litellm")
        return self._litellm

    def complete(
        self,
        request: CompletionRequest,
        config: ProviderConfig,
    ) -> BackendResult:
        litellm = self._get_litellm()
        parameters: dict[str, Any] = {
            "model": config.litellm_model,
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in request.messages
            ],
            "temperature": request.temperature,
            "timeout": request.timeout_seconds or config.timeout_seconds,
            "num_retries": 0,
        }
        if config.api_key is not None:
            parameters["api_key"] = config.api_key.get_secret_value()
        if request.max_tokens is not None:
            parameters["max_tokens"] = request.max_tokens
        if config.api_base is not None:
            parameters["api_base"] = config.api_base

        try:
            raw_response = litellm.completion(**parameters)
            result = self._normalize_response(raw_response, config)
        except LLMError:
            raise
        except Exception as error:
            raise translate_provider_error(error, config) from error

        result = result.model_copy(
            update={"cost_usd": self._calculate_cost(litellm, raw_response, config)}
        )
        return result

    def _normalize_response(
        self,
        response: Any,
        config: ProviderConfig,
    ) -> BackendResult:
        try:
            choice = response.choices[0]
            content = choice.message.content
            if not isinstance(content, str) or not content.strip():
                raise InvalidResponseError(
                    "provider returned no text content",
                    provider=config.provider.value,
                )

            raw_usage = getattr(response, "usage", None)
            usage = TokenUsage(
                prompt_tokens=self._optional_int(
                    getattr(raw_usage, "prompt_tokens", None),
                    config,
                ),
                completion_tokens=self._optional_int(
                    getattr(raw_usage, "completion_tokens", None),
                    config,
                ),
                total_tokens=self._optional_int(
                    getattr(raw_usage, "total_tokens", None),
                    config,
                ),
                source="provider",
            )
            finish_reason = getattr(choice, "finish_reason", None)
            return BackendResult(
                response_id=str(getattr(response, "id", None) or "unknown"),
                provider=config.provider,
                model=str(getattr(response, "model", None) or config.litellm_model),
                content=content,
                usage=usage,
                finish_reason=(
                    str(finish_reason) if finish_reason is not None else None
                ),
            )
        except LLMError:
            raise
        except (AttributeError, IndexError, TypeError, ValueError) as error:
            raise InvalidResponseError(
                "provider returned a malformed response",
                provider=config.provider.value,
            ) from error

    @staticmethod
    def _optional_int(value: Any, config: ProviderConfig) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError) as error:
            raise InvalidResponseError(
                "provider returned invalid token usage",
                provider=config.provider.value,
            ) from error

    @staticmethod
    def _calculate_cost(
        litellm: Any,
        response: Any,
        config: ProviderConfig,
    ) -> Decimal | None:
        try:
            value = litellm.completion_cost(completion_response=response)
            return Decimal(str(value))
        except Exception as error:
            logger.warning(
                "cost calculation unavailable provider=%s error_type=%s",
                config.provider.value,
                type(error).__name__,
            )
            return None


def translate_provider_error(error: Exception, config: ProviderConfig) -> LLMError:
    provider = config.provider.value
    error_type = type(error).__name__
    message = f"{provider} request failed with {error_type}"

    if error_type in {"AuthenticationError", "PermissionDeniedError"}:
        return AuthenticationError(message, provider=provider)
    if error_type == "RateLimitError":
        return RateLimitError(message, provider=provider)
    if error_type in {"Timeout", "APITimeoutError"} or isinstance(error, TimeoutError):
        return ProviderTimeoutError(message, provider=provider)
    if error_type in {
        "APIConnectionError",
        "InternalServerError",
        "ServiceUnavailableError",
    }:
        return ProviderUnavailableError(message, provider=provider)
    return ProviderError(message, provider=provider)
