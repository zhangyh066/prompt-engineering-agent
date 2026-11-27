from threading import Lock
from uuid import uuid4

from pea.api.schemas import OptimizeAPIRequest
from pea.config import Settings
from pea.evaluation import PromptEvaluator
from pea.gateway import LLMGateway, create_gateway
from pea.models import ClarificationAnswers, Provider, WorkflowResult, WorkflowStatus
from pea.storage import RunNotFoundError, SQLiteResultManager
from pea.workflow import WorkflowRunner


class RealProviderDisabledError(PermissionError):
    pass


class ApplicationServices:
    def __init__(
        self,
        settings: Settings,
        manager: SQLiteResultManager,
        gateway: LLMGateway | None = None,
    ) -> None:
        self.settings = settings
        self.manager = manager
        self.gateway = gateway or create_gateway(settings)
        self._runners: dict[str, WorkflowRunner] = {}
        self._lock = Lock()

    def optimize(self, request: OptimizeAPIRequest) -> WorkflowResult:
        if request.provider != Provider.MOCK and not self.settings.enable_real_providers:
            raise RealProviderDisabledError(request.provider.value)
        config = self.settings.provider_config(request.provider)
        run_id = uuid4().hex
        runner = WorkflowRunner(evaluator=PromptEvaluator(self.gateway))
        with self._lock:
            self._runners[run_id] = runner
        try:
            result = runner.run(
                request.to_prompt_request(),
                max_iterations=request.max_iterations,
                dynamic_evaluation=request.dynamic_evaluation,
                provider=request.provider,
                target_model=request.target_model,
                thread_id=run_id,
            )
            self.manager.save_workflow_result(
                result,
                provider=request.provider,
                model=config.model,
            )
            return result
        finally:
            self._release_if_terminal(run_id, locals().get("result"))

    def clarify(
        self,
        run_id: str,
        answers: ClarificationAnswers,
    ) -> WorkflowResult:
        with self._lock:
            runner = self._runners.get(run_id)
        if runner is None:
            raise RunNotFoundError(run_id)
        previous = self.manager.get_run(run_id)
        result = runner.resume(run_id, answers.answers)
        self.manager.save_workflow_result(
            result,
            provider=previous.summary.provider,
            model=previous.summary.model,
        )
        self._release_if_terminal(run_id, result)
        return result

    def cancel(self, run_id: str) -> None:
        with self._lock:
            runner = self._runners.get(run_id)
        if runner is None:
            raise RunNotFoundError(run_id)
        runner.cancel()

    def _release_if_terminal(
        self,
        run_id: str,
        result: WorkflowResult | None,
    ) -> None:
        if result is None or result.status != WorkflowStatus.NEEDS_CLARIFICATION:
            with self._lock:
                self._runners.pop(run_id, None)
