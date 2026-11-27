class LLMError(Exception):
    default_retryable = False

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.retryable = self.default_retryable if retryable is None else retryable


class ConfigurationError(LLMError):
    pass


class AuthenticationError(LLMError):
    pass


class RateLimitError(LLMError):
    default_retryable = True


class ProviderTimeoutError(LLMError):
    default_retryable = True


class ProviderUnavailableError(LLMError):
    default_retryable = True


class InvalidResponseError(LLMError):
    pass


class BudgetExceededError(LLMError):
    pass


class ProviderError(LLMError):
    pass
