from collections.abc import Callable, Mapping
from threading import Event
from typing import Any
from uuid import uuid4
import logging

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from pea.agents import IntentAnalyzer, PromptDiagnostician, PromptGenerator, StrategyPlanner
from pea.adapters import ModelAdapter
from pea.agents.refiner import Refiner
from pea.evaluation import PromptEvaluator
from pea.exceptions import LLMError
from pea.models import (
    ClarificationAnswers,
    GeneratedPrompt,
    PromptOptimizationRequest,
    PromptOptimizationResult,
    Provider,
    WorkflowResult,
    WorkflowStatus,
)
from pea.models.adapter import TargetModel
from pea.models.workflow import IterationRecord
from pea.workflow.state import WorkflowState

logger = logging.getLogger(__name__)


class WorkflowCancelled(Exception):
    pass


class WorkflowRunner:
    def __init__(
        self,
        *,
        analyzer: IntentAnalyzer | None = None,
        diagnostician: PromptDiagnostician | None = None,
        planner: StrategyPlanner | None = None,
        generator: PromptGenerator | None = None,
        evaluator: PromptEvaluator | None = None,
        refiner: Refiner | None = None,
        adapter: ModelAdapter | None = None,
        checkpointer: Any = None,
    ) -> None:
        self._analyzer = analyzer or IntentAnalyzer()
        self._diagnostician = diagnostician or PromptDiagnostician()
        self._planner = planner or StrategyPlanner()
        self._generator = generator or PromptGenerator()
        self._evaluator = evaluator or PromptEvaluator()
        self._refiner = refiner or Refiner()
        self._adapter = adapter or ModelAdapter()
        self._cancelled = Event()
        self._graph = self._build_graph(checkpointer or InMemorySaver())

    def run(
        self,
        request: PromptOptimizationRequest,
        *,
        max_iterations: int = 3,
        dynamic_evaluation: bool = False,
        provider: Provider = Provider.MOCK,
        target_model: TargetModel | None = None,
        thread_id: str | None = None,
    ) -> WorkflowResult:
        if not 1 <= max_iterations <= 3:
            raise ValueError("max_iterations must be between 1 and 3")
        if thread_id is not None and not thread_id.strip():
            raise ValueError("thread_id must not be blank")
        thread_id = thread_id or uuid4().hex
        state = self._graph.invoke(
            {
                "request": request,
                "thread_id": thread_id,
                "max_iterations": max_iterations,
                "dynamic_evaluation": dynamic_evaluation,
                "provider": provider,
                "target_model": target_model,
                "status": WorkflowStatus.RUNNING,
                "iteration": 0,
                "iterations": [],
                "best_score": -1.0,
                "refinement_notes": [],
                "clarification_questions": [],
                "warnings": [],
            },
            config=self._config(thread_id),
        )
        return self._result(state)

    def resume(
        self,
        thread_id: str,
        answers: Mapping[str, str],
    ) -> WorkflowResult:
        response = ClarificationAnswers(answers=dict(answers))
        state = self._graph.invoke(
            Command(resume=response.model_dump()),
            config=self._config(thread_id),
        )
        return self._result(state)

    def cancel(self) -> None:
        self._cancelled.set()
        logger.info("workflow cancellation requested")

    def _build_graph(self, checkpointer: Any):
        graph = StateGraph(WorkflowState)
        graph.add_node("analyze", self._protected(self._analyze))
        graph.add_node("clarify", self._clarify)
        graph.add_node("diagnose", self._protected(self._diagnose))
        graph.add_node("plan", self._protected(self._plan))
        graph.add_node("generate", self._protected(self._generate))
        graph.add_node("evaluate", self._protected(self._evaluate))
        graph.add_node("refine", self._protected(self._refine))
        graph.add_node("finalize", self._protected(self._finalize))

        graph.add_edge(START, "analyze")
        graph.add_conditional_edges(
            "analyze",
            self._route_after_analysis,
            {"clarify": "clarify", "diagnose": "diagnose", END: END},
        )
        graph.add_conditional_edges(
            "clarify",
            self._route_after_clarification,
            {"analyze": "analyze", END: END},
        )
        graph.add_edge("diagnose", "plan")
        graph.add_edge("plan", "generate")
        graph.add_edge("generate", "evaluate")
        graph.add_conditional_edges(
            "evaluate",
            self._route_after_evaluation,
            {"refine": "refine", "finalize": "finalize", END: END},
        )
        graph.add_edge("refine", "generate")
        graph.add_edge("finalize", END)
        return graph.compile(checkpointer=checkpointer)

    def _protected(
        self,
        function: Callable[[WorkflowState], dict[str, Any]],
    ) -> Callable[[WorkflowState], dict[str, Any]]:
        def node(state: WorkflowState) -> dict[str, Any]:
            if state.get("status") in {WorkflowStatus.FAILED, WorkflowStatus.CANCELLED}:
                return {}
            try:
                self._raise_if_cancelled()
                return function(state)
            except WorkflowCancelled:
                return {"status": WorkflowStatus.CANCELLED}
            except LLMError as error:
                logger.error(
                    "workflow model operation failed error_type=%s",
                    type(error).__name__,
                )
                return {
                    "status": WorkflowStatus.FAILED,
                    "error": f"{type(error).__name__}: {error}",
                }
            except Exception as error:
                logger.error(
                    "workflow node failed error_type=%s",
                    type(error).__name__,
                )
                return {
                    "status": WorkflowStatus.FAILED,
                    "error": f"workflow stopped after {type(error).__name__}",
                }

        return node

    def _analyze(self, state: WorkflowState) -> dict[str, Any]:
        intent = self._analyzer.analyze(state["request"])
        if intent.needs_clarification:
            questions = [
                f"请补充：{item}" for item in intent.missing_information
            ]
            return {
                "intent": intent,
                "status": WorkflowStatus.NEEDS_CLARIFICATION,
                "clarification_questions": questions,
            }
        return {"intent": intent, "status": WorkflowStatus.RUNNING}

    def _clarify(self, state: WorkflowState) -> dict[str, Any]:
        if self._cancelled.is_set():
            return {"status": WorkflowStatus.CANCELLED}
        resume_value = interrupt(
            {"questions": state["clarification_questions"]},
            response_schema=ClarificationAnswers,
        )
        response = (
            resume_value
            if isinstance(resume_value, ClarificationAnswers)
            else ClarificationAnswers.model_validate(resume_value)
        )
        expected_keys = {
            f"q{index}"
            for index in range(1, len(state["clarification_questions"]) + 1)
        }
        if set(response.answers) != expected_keys:
            return {
                "status": WorkflowStatus.FAILED,
                "error": "clarification answer keys do not match the questions",
            }
        supplements = "\n".join(
            f"{question}：{response.answers[f'q{index}']}"
            for index, question in enumerate(
                state["clarification_questions"],
                start=1,
            )
        )
        request = state["request"].model_copy(
            update={
                "user_request": (
                    f"{state['request'].user_request}\n补充信息：\n{supplements}"
                )
            }
        )
        return {"request": request, "status": WorkflowStatus.RUNNING}

    def _diagnose(self, state: WorkflowState) -> dict[str, Any]:
        return {
            "diagnosis": self._diagnostician.diagnose(
                state["request"],
                state["intent"],
            )
        }

    def _plan(self, state: WorkflowState) -> dict[str, Any]:
        return {
            "strategy_plan": self._planner.plan(
                state["intent"],
                state["diagnosis"],
            )
        }

    def _generate(self, state: WorkflowState) -> dict[str, Any]:
        iteration = state.get("iteration", 0) + 1
        generated = self._generator.generate(
            state["request"],
            state["intent"],
            state["diagnosis"],
            state["strategy_plan"],
            refinement_notes=state.get("refinement_notes"),
        )
        return {
            "current_prompt": generated,
            "iteration": iteration,
            "status": WorkflowStatus.RUNNING,
        }

    def _evaluate(self, state: WorkflowState) -> dict[str, Any]:
        report = self._evaluator.evaluate(
            state["request"],
            state["intent"],
            state["current_prompt"],
            dynamic=state["dynamic_evaluation"],
            provider=state["provider"],
            baseline_response=state.get("baseline_execution"),
        )
        record = IterationRecord(
            iteration=state["iteration"],
            prompt=state["current_prompt"],
            strategy_plan=state["strategy_plan"],
            evaluation=report,
        )
        updates: dict[str, Any] = {
            "current_evaluation": report,
            "iterations": [record],
        }
        if report.baseline_execution is not None:
            updates["baseline_execution"] = report.baseline_execution
        if report.score > state.get("best_score", -1.0):
            updates.update(
                {
                    "best_score": report.score,
                    "best_prompt": state["current_prompt"],
                    "best_plan": state["strategy_plan"],
                    "best_evaluation": report,
                }
            )
        return updates

    def _refine(self, state: WorkflowState) -> dict[str, Any]:
        plan, notes = self._refiner.refine(
            state["strategy_plan"],
            state["current_evaluation"],
        )
        return {"strategy_plan": plan, "refinement_notes": notes}

    def _finalize(self, state: WorkflowState) -> dict[str, Any]:
        evaluation = state["best_evaluation"]
        optimization = PromptOptimizationResult(
            request=state["request"],
            intent=state["intent"],
            diagnosis=state["diagnosis"],
            strategy_plan=state["best_plan"],
            generated_prompt=state["best_prompt"],
        )
        adapted = None
        if state.get("target_model") is not None:
            adapted = self._adapter.adapt(
                state["best_prompt"],
                state["intent"],
                state["target_model"],
            )
        return {
            "optimization": optimization,
            "adapted_prompt": adapted,
            "status": WorkflowStatus.COMPLETED,
            "warnings": evaluation.warnings,
        }

    @staticmethod
    def _route_after_analysis(state: WorkflowState) -> str:
        status = state["status"]
        if status in {WorkflowStatus.FAILED, WorkflowStatus.CANCELLED}:
            return END
        if status == WorkflowStatus.NEEDS_CLARIFICATION:
            return "clarify"
        return "diagnose"

    @staticmethod
    def _route_after_clarification(state: WorkflowState) -> str:
        if state["status"] in {WorkflowStatus.FAILED, WorkflowStatus.CANCELLED}:
            return END
        return "analyze"

    @staticmethod
    def _route_after_evaluation(state: WorkflowState) -> str:
        if state["status"] in {WorkflowStatus.FAILED, WorkflowStatus.CANCELLED}:
            return END
        if state["current_evaluation"].passed:
            return "finalize"
        if state["iteration"] >= state["max_iterations"]:
            return "finalize"
        return "refine"

    def _raise_if_cancelled(self) -> None:
        if self._cancelled.is_set():
            raise WorkflowCancelled

    @staticmethod
    def _config(thread_id: str) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": thread_id}}

    @staticmethod
    def _result(state: Mapping[str, Any]) -> WorkflowResult:
        evaluation = state.get("best_evaluation")
        return WorkflowResult(
            status=state.get("status", WorkflowStatus.FAILED),
            thread_id=state.get("thread_id", "unknown"),
            request=state["request"],
            optimization=state.get("optimization"),
            adapted_prompt=state.get("adapted_prompt"),
            iterations=list(state.get("iterations", [])),
            final_evaluation=evaluation,
            clarification_questions=list(state.get("clarification_questions", [])),
            warnings=list(evaluation.warnings if evaluation else state.get("warnings", [])),
            error=state.get("error"),
        )
