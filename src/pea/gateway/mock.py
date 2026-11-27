from collections import deque
from collections.abc import Iterable
from decimal import Decimal

from pea.config import ProviderConfig
from pea.models import BackendResult, CompletionRequest, TokenUsage


class MockBackend:
    def __init__(self, outcomes: Iterable[str | Exception] | None = None) -> None:
        self._outcomes = deque(outcomes or ())
        self.calls: list[tuple[CompletionRequest, ProviderConfig]] = []

    def complete(
        self,
        request: CompletionRequest,
        config: ProviderConfig,
    ) -> BackendResult:
        self.calls.append((request, config))
        outcome = self._outcomes.popleft() if self._outcomes else "Mock response"
        if isinstance(outcome, Exception):
            raise outcome

        prompt_tokens = sum(max(1, len(message.content.split())) for message in request.messages)
        completion_tokens = max(1, len(outcome.split()))
        return BackendResult(
            response_id=f"mock-{len(self.calls)}",
            provider=config.provider,
            model=config.model,
            content=outcome,
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                source="mock_estimate",
            ),
            cost_usd=Decimal("0"),
            finish_reason="stop",
        )
