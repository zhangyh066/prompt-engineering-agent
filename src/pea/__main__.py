import argparse
from collections.abc import Sequence
import json

from pea.agents import StructuredPromptOptimizer
from pea.bootstrap import collect_bootstrap_status
from pea.config import get_settings
from pea.gateway import create_gateway
from pea.evaluation.benchmark import BenchmarkLoader, validate_benchmark
from pea.logging_config import configure_logging
from pea.models import (
    ChatMessage,
    CompletionRequest,
    PromptOptimizationRequest,
    Provider,
)
from pea.workflow import WorkflowRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prompt Engineering Agent")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--mock",
        action="store_true",
        help="run one local Mock request without calling a model provider",
    )
    actions.add_argument(
        "--optimize",
        metavar="REQUEST",
        help="optimize a natural-language request using the deterministic baseline",
    )
    actions.add_argument(
        "--validate-benchmark",
        action="store_true",
        help="validate the local 100-task benchmark draft without model calls",
    )
    parser.add_argument(
        "--raw-prompt",
        help="optional original Prompt to diagnose and optimize",
    )
    parser.add_argument(
        "--workflow",
        action="store_true",
        help="run optimization through the LangGraph workflow",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.raw_prompt is not None and args.optimize is None:
        parser.error("--raw-prompt requires --optimize")
    if args.workflow and args.optimize is None:
        parser.error("--workflow requires --optimize")
    if args.optimize is not None and not args.optimize.strip():
        parser.error("--optimize must not be blank")

    if args.validate_benchmark:
        tasks = BenchmarkLoader().load()
        print(validate_benchmark(tasks).model_dump_json(indent=2))
    elif args.optimize is not None:
        request = PromptOptimizationRequest(
            user_request=args.optimize,
            raw_prompt=args.raw_prompt,
        )
        if args.workflow:
            result = WorkflowRunner().run(request)
        else:
            result = StructuredPromptOptimizer().optimize(request)
        print(result.model_dump_json(indent=2))
    elif args.mock:
        settings = get_settings()
        configure_logging(settings.log_level)
        response = create_gateway(settings).complete(
            CompletionRequest(
                provider=Provider.MOCK,
                messages=[
                    ChatMessage(
                        role="user",
                        content="Return a deterministic local health-check response.",
                    )
                ],
            )
        )
        print(response.model_dump_json(indent=2))
    else:
        print(json.dumps(collect_bootstrap_status(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
