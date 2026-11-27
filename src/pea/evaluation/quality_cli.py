import argparse
from collections.abc import Sequence
import json
from pathlib import Path

from pea.config import get_settings
from pea.evaluation.optimization_data import load_optimization_split
from pea.evaluation.quality_runner import QualityRunner
from pea.exceptions import ConfigurationError
from pea.gateway import create_gateway
from pea.models import Provider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run bounded PEA quality comparisons")
    parser.add_argument("--split", choices=["train", "dev"], default="dev")
    parser.add_argument("--data-dir", type=Path, default=Path("data/benchmark_splits"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--provider", choices=["mock", "openai", "anthropic"], default="mock")
    parser.add_argument("--model")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--selection", choices=["stratified", "sequential"], default="stratified")
    parser.add_argument("--seed", type=int, default=20261126)
    parser.add_argument("--allow-real-model", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    provider = Provider(args.provider)
    settings = get_settings()
    if provider != Provider.MOCK and not settings.enable_real_providers:
        raise ConfigurationError(
            "real quality runs also require PEA_ENABLE_REAL_PROVIDERS=True",
            provider=provider.value,
        )

    cases = load_optimization_split(
        args.data_dir / f"dolly_{args.split}.jsonl"
    )
    if args.manifest is not None:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        if manifest.get("split") != args.split:
            raise ConfigurationError("quality manifest split does not match --split")
        case_ids = {item["case_id"] for item in manifest["cases"]}
        cases = [case for case in cases if case.case_id in case_ids]

    gateway = create_gateway(settings)
    report = QualityRunner(gateway, settings=settings).run(
        cases,
        provider=provider,
        model=args.model,
        limit=args.limit,
        split=args.split,
        selection=args.selection,
        seed=args.seed,
        allow_real_model=args.allow_real_model,
    )
    output = args.output or Path(
        f"benchmarks/results/quality_{args.split}_{provider.value}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report.status.value,
                "split": report.split,
                "provider": report.provider.value,
                "selected_cases": report.selected_case_count,
                "completed_cases": report.completed_case_count,
                "output": str(output),
                "quality_claim_allowed": report.quality_claim_allowed,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
