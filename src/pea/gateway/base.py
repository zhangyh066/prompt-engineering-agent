from typing import Protocol

from pea.config import ProviderConfig
from pea.models import BackendResult, CompletionRequest


class LLMBackend(Protocol):
    def complete(
        self,
        request: CompletionRequest,
        config: ProviderConfig,
    ) -> BackendResult: ...
