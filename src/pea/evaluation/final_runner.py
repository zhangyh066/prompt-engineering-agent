from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from pea.evaluation.optimization_data import load_optimization_split
from pea.evaluation.quality_runner import (
    QualityReport,
    QualityRunner,
    QualityRunStatus,
    SelectionMode,
)
from pea.exceptions import ConfigurationError
from pea.models import Provider


class FinalQualityReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    quality_report: QualityReport
    test_sha256: str
    dev_report_sha256: str
    final_test_confirmed: Literal[True] = True
    test_access_logged: Literal[True] = True


class FinalEvaluationRunner(QualityRunner):
    def run_final(
        self,
        *,
        test_path: Path,
        manifest_path: Path,
        dev_report_path: Path,
        access_log_path: Path,
        confirm_final_test: bool,
        provider: Provider = Provider.MOCK,
        model: str | None = None,
        limit: int = 50,
        selection: SelectionMode = "stratified",
        seed: int = 20261126,
        allow_real_model: bool = False,
    ) -> FinalQualityReport:
        if not confirm_final_test:
            raise ConfigurationError("final test access requires confirm_final_test=True")
        if provider != Provider.MOCK and not self._settings.enable_real_providers:
            raise ConfigurationError(
                "final real-model evaluation requires PEA_ENABLE_REAL_PROVIDERS=True",
                provider=provider.value,
            )
        config = self._settings.provider_config(provider, model)

        dev_bytes = dev_report_path.read_bytes()
        dev_report = QualityReport.model_validate_json(dev_bytes)
        if (
            dev_report.split != "dev"
            or dev_report.status != QualityRunStatus.COMPLETED
            or dev_report.completed_case_count != dev_report.selected_case_count
        ):
            raise ConfigurationError("final evaluation requires a complete dev report")
        if dev_report.provider != provider or dev_report.model != config.model:
            raise ConfigurationError("dev report provider/model must match final evaluation")
        if provider != Provider.MOCK and not dev_report.allow_real_model:
            raise ConfigurationError("real final evaluation requires a real-model dev report")

        test_bytes = test_path.read_bytes()
        test_sha256 = hashlib.sha256(test_bytes).hexdigest()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["split_sha256"]["test"] != test_sha256:
            raise ConfigurationError("test file hash does not match the locked manifest")
        cases = load_optimization_split(test_path)
        if not cases or any(case.split != "test" for case in cases):
            raise ConfigurationError("final evaluation input must contain only test cases")

        report = super().run(
            cases,
            provider=provider,
            model=model,
            limit=limit,
            split="test",
            selection=selection,
            seed=seed,
            allow_real_model=allow_real_model,
            _allow_test=True,
        )
        access_log_path.parent.mkdir(parents=True, exist_ok=True)
        with access_log_path.open("a", encoding="utf-8") as access_log:
            access_log.write(
                json.dumps(
                    {
                        "accessed_at": datetime.now(timezone.utc).isoformat(),
                        "test_sha256": test_sha256,
                        "dev_report_sha256": hashlib.sha256(dev_bytes).hexdigest(),
                        "provider": provider.value,
                        "model": config.model,
                        "selected_cases": report.selected_case_count,
                        "selection": report.selection,
                        "seed": report.seed,
                        "allow_real_model": allow_real_model,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        return FinalQualityReport(
            quality_report=report,
            test_sha256=test_sha256,
            dev_report_sha256=hashlib.sha256(dev_bytes).hexdigest(),
        )
