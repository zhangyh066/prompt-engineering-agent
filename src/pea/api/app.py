from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from pea import __version__
from pea.api.schemas import CancelAPIResponse, OptimizeAPIRequest
from pea.api.services import ApplicationServices, RealProviderDisabledError
from pea.config import Settings, get_settings
from pea.exceptions import ConfigurationError
from pea.evaluation.benchmark import BenchmarkLoader, validate_benchmark
from pea.evaluation.external_data import load_external_cases
from pea.evaluation.harness_audit import HarnessAuditReport, HarnessAuditor
from pea.models import ClarificationAnswers, WorkflowResult, WorkflowStatus
from pea.models.benchmark import BenchmarkValidationReport
from pea.models.history import RunDetail, RunSummary, VersionComparison
from pea.storage import ResultExporter, RunNotFoundError, SQLiteResultManager


def create_app(
    settings: Settings | None = None,
    manager: SQLiteResultManager | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_manager = manager or SQLiteResultManager(resolved_settings.database_path)
    services = ApplicationServices(resolved_settings, resolved_manager)
    app = FastAPI(
        title="Prompt Engineering Agent API",
        version="0.2.0",
        description="Local Prompt optimization, history, evaluation, and export API",
    )
    app.state.services = services
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            host.strip()
            for host in resolved_settings.trusted_hosts.split(",")
            if host.strip()
        ],
    )

    @app.middleware("http")
    async def secure_request(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if request.method in {"POST", "PUT", "PATCH"} and content_length:
            try:
                declared_size = int(content_length)
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "invalid content length"})
            if declared_size > 64 * 1024:
                return JSONResponse(status_code=413, content={"detail": "request body too large"})
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "stage": "Beta", "version": __version__}

    @app.post("/api/v1/optimizations", response_model=WorkflowResult)
    def optimize(request: OptimizeAPIRequest) -> WorkflowResult:
        try:
            return services.optimize(request)
        except RealProviderDisabledError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{error.args[0]} is disabled; set PEA_ENABLE_REAL_PROVIDERS=True to allow paid calls",
            ) from error
        except ConfigurationError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except ValidationError as error:
            raise HTTPException(status_code=422, detail="invalid optimization request") from error

    @app.post(
        "/api/v1/optimizations/{run_id}/clarifications",
        response_model=WorkflowResult,
    )
    def clarify(run_id: str, answers: ClarificationAnswers) -> WorkflowResult:
        try:
            return services.clarify(run_id, answers)
        except RunNotFoundError as error:
            raise HTTPException(status_code=404, detail="active clarification run not found") from error
        except ValidationError as error:
            raise HTTPException(status_code=422, detail="invalid clarification answers") from error

    @app.post(
        "/api/v1/optimizations/{run_id}/cancel",
        response_model=CancelAPIResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def cancel(run_id: str) -> CancelAPIResponse:
        try:
            services.cancel(run_id)
            return CancelAPIResponse(run_id=run_id)
        except RunNotFoundError as error:
            raise HTTPException(status_code=404, detail="active run not found") from error

    @app.get("/api/v1/benchmarks/status", response_model=BenchmarkValidationReport)
    def benchmark_status() -> BenchmarkValidationReport:
        return validate_benchmark(BenchmarkLoader().load())

    @app.get("/api/v1/evaluations/public-audit", response_model=HarnessAuditReport)
    def public_audit() -> HarnessAuditReport:
        return HarnessAuditor().run(load_external_cases())

    @app.get("/api/v1/history", response_model=list[RunSummary])
    def history(
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        run_status: WorkflowStatus | None = Query(default=None),
    ) -> list[RunSummary]:
        return resolved_manager.list_runs(limit=limit, offset=offset, status=run_status)

    @app.get("/api/v1/history/{run_id}", response_model=RunDetail)
    def history_detail(run_id: str) -> RunDetail:
        return get_run(resolved_manager, run_id)

    @app.get(
        "/api/v1/history/{run_id}/compare",
        response_model=VersionComparison,
    )
    def compare(
        run_id: str,
        left: int = Query(ge=1),
        right: int = Query(ge=1),
    ) -> VersionComparison:
        try:
            return resolved_manager.compare_versions(run_id, left, right)
        except RunNotFoundError as error:
            raise HTTPException(status_code=404, detail="run or version not found") from error

    @app.get("/api/v1/history/{run_id}/export")
    def export(
        run_id: str,
        format: Literal["json", "markdown"] = "json",
    ) -> Response:
        detail = get_run(resolved_manager, run_id)
        if format == "json":
            content = ResultExporter.to_json(detail)
            media_type = "application/json"
            extension = "json"
        else:
            content = ResultExporter.to_markdown(detail)
            media_type = "text/markdown; charset=utf-8"
            extension = "md"
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="pea-{run_id}.{extension}"'
            },
        )

    return app


def get_run(manager: SQLiteResultManager, run_id: str) -> RunDetail:
    try:
        return manager.get_run(run_id)
    except RunNotFoundError as error:
        raise HTTPException(status_code=404, detail="run not found") from error
