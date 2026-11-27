from datetime import datetime, timezone
from decimal import Decimal
import difflib
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, selectinload

from pea.models import (
    EvaluationReport,
    PromptOptimizationResult,
    Provider,
    StrategyType,
    TaskType,
    WorkflowResult,
    WorkflowStatus,
)
from pea.models.adapter import AdaptedPrompt
from pea.models.history import RunDetail, RunSummary, StoredVersion, VersionComparison
from pea.storage.orm import Base, RunRecord, VersionRecord


class RunNotFoundError(KeyError):
    pass


class SQLiteResultManager:
    def __init__(self, path: str | Path) -> None:
        database_path = Path(path).resolve()
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self._engine)

    def save_workflow_result(
        self,
        result: WorkflowResult,
        *,
        provider: Provider = Provider.MOCK,
        model: str = "mock-local",
    ) -> str:
        now = datetime.now(timezone.utc)
        optimization = result.optimization
        with Session(self._engine) as session, session.begin():
            run = session.get(RunRecord, result.thread_id)
            if run is None:
                run = RunRecord(
                    id=result.thread_id,
                    status=result.status.value,
                    user_request=self._user_request(result),
                    raw_prompt=self._raw_prompt(result),
                    provider=provider.value,
                    model=model,
                    total_latency_seconds=0.0,
                    clarification_questions_json=[],
                    warnings_json=[],
                    created_at=now,
                    updated_at=now,
                )
                session.add(run)

            run.status = result.status.value
            run.user_request = self._user_request(result)
            run.raw_prompt = self._raw_prompt(result)
            run.task_type = (
                optimization.intent.task_type.value if optimization is not None else None
            )
            run.provider = provider.value
            run.model = model
            run.total_tokens = self._total_tokens(result)
            run.total_cost_usd = self._total_cost(result)
            run.total_latency_seconds = sum(
                record.evaluation.latency_seconds for record in result.iterations
            )
            run.optimization_json = (
                optimization.model_dump(mode="json") if optimization is not None else None
            )
            run.adapted_prompt_json = (
                result.adapted_prompt.model_dump(mode="json")
                if result.adapted_prompt is not None
                else None
            )
            run.clarification_questions_json = result.clarification_questions
            run.warnings_json = result.warnings
            run.error = result.error
            run.updated_at = now

            best_iteration = self._best_iteration(result)
            run.versions.clear()
            session.flush()
            for record in result.iterations:
                run.versions.append(
                    VersionRecord(
                        version_number=record.iteration,
                        content=record.prompt.content,
                        generation_method=record.prompt.generation_method,
                        changes_json=[
                            change.model_dump(mode="json")
                            for change in record.prompt.changes
                        ],
                        strategies_json=[
                            item.strategy.value for item in record.strategy_plan.selected
                        ],
                        evaluation_json=record.evaluation.model_dump(mode="json"),
                        is_best=record.iteration == best_iteration,
                        created_at=now,
                    )
                )
        return result.thread_id

    def list_runs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: WorkflowStatus | None = None,
    ) -> list[RunSummary]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("limit must be 1–100 and offset must be nonnegative")
        with Session(self._engine) as session:
            statement = (
                select(RunRecord)
                .options(selectinload(RunRecord.versions))
                .order_by(RunRecord.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            if status is not None:
                statement = statement.where(RunRecord.status == status.value)
            records = session.scalars(statement).all()
            return [self._to_summary(record) for record in records]

    def get_run(self, run_id: str) -> RunDetail:
        with Session(self._engine) as session:
            record = session.get(RunRecord, run_id)
            if record is None:
                raise RunNotFoundError(run_id)
            return self._to_detail(record)

    def compare_versions(
        self,
        run_id: str,
        left_version: int,
        right_version: int,
    ) -> VersionComparison:
        detail = self.get_run(run_id)
        versions = {item.version: item for item in detail.versions}
        if left_version not in versions or right_version not in versions:
            raise RunNotFoundError(f"version in {run_id}")
        left = versions[left_version]
        right = versions[right_version]
        left_strategies = set(left.strategies)
        right_strategies = set(right.strategies)
        return VersionComparison(
            run_id=run_id,
            left=left,
            right=right,
            unified_diff="\n".join(
                difflib.unified_diff(
                    left.content.splitlines(),
                    right.content.splitlines(),
                    fromfile=f"version-{left_version}",
                    tofile=f"version-{right_version}",
                    lineterm="",
                )
            ),
            score_change=right.evaluation.score - left.evaluation.score,
            added_strategies=sorted(right_strategies - left_strategies),
            removed_strategies=sorted(left_strategies - right_strategies),
        )

    @staticmethod
    def _best_iteration(result: WorkflowResult) -> int | None:
        if result.final_evaluation is None:
            return None
        for record in result.iterations:
            if record.evaluation == result.final_evaluation:
                return record.iteration
        return None

    @staticmethod
    def _user_request(result: WorkflowResult) -> str:
        return result.request.user_request

    @staticmethod
    def _raw_prompt(result: WorkflowResult) -> str | None:
        return result.request.raw_prompt

    @staticmethod
    def _total_tokens(result: WorkflowResult) -> int | None:
        if not result.iterations:
            return None
        usages = [record.evaluation.usage for record in result.iterations]
        if any(item is None or item.total_tokens is None for item in usages):
            return None
        return sum(item.total_tokens for item in usages if item and item.total_tokens is not None)

    @staticmethod
    def _total_cost(result: WorkflowResult) -> Decimal | None:
        if not result.iterations:
            return None
        costs = [record.evaluation.cost_usd for record in result.iterations]
        if any(cost is None for cost in costs):
            return None
        return sum((cost for cost in costs if cost is not None), Decimal("0"))

    @staticmethod
    def _to_summary(record: RunRecord) -> RunSummary:
        return RunSummary(
            run_id=record.id,
            status=record.status,
            user_request=record.user_request,
            raw_prompt=record.raw_prompt,
            task_type=record.task_type,
            provider=record.provider,
            model=record.model,
            version_count=len(record.versions),
            total_tokens=record.total_tokens,
            total_cost_usd=record.total_cost_usd,
            total_latency_seconds=record.total_latency_seconds,
            warnings=record.warnings_json,
            error=record.error,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _to_detail(record: RunRecord) -> RunDetail:
        versions = [
            StoredVersion(
                version=item.version_number,
                content=item.content,
                generation_method=item.generation_method,
                changes=item.changes_json,
                strategies=item.strategies_json,
                evaluation=EvaluationReport.model_validate(item.evaluation_json),
                is_best=item.is_best,
                created_at=item.created_at,
            )
            for item in record.versions
        ]
        return RunDetail(
            summary=SQLiteResultManager._to_summary(record),
            optimization=(
                PromptOptimizationResult.model_validate(record.optimization_json)
                if record.optimization_json is not None
                else None
            ),
            adapted_prompt=(
                AdaptedPrompt.model_validate(record.adapted_prompt_json)
                if record.adapted_prompt_json is not None
                else None
            ),
            clarification_questions=record.clarification_questions_json,
            versions=versions,
        )
