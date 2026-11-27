import json
from pathlib import Path

from pea.evaluation.external_data import ExternalCase


def write_promptfoo_config(
    cases: list[ExternalCase],
    destination: Path,
) -> None:
    tests = []
    for case in cases:
        preservation_assertions = [
            {"type": "contains", "value": part}
            for part in case.prompt.split("\n\nContext:")
            if part
        ]
        tests.append(
            {
                "description": f"{case.case_id} public prompt preservation",
                "vars": {"prompt": case.prompt},
                "assert": [
                    *preservation_assertions,
                    {"type": "contains", "value": "## 输出要求"},
                ],
            }
        )

    conflict_prompt = (
        f"{cases[0].instruction}\n"
        "Output at least 500 words and no more than 100 words."
    )
    tests.append(
        {
            "description": "English conflicting length constraints must be surfaced",
            "vars": {"prompt": conflict_prompt},
            "assert": [{"type": "contains", "value": "停止执行并列出冲突"}],
        }
    )
    ambiguous_prompt = (
        f"{cases[0].instruction}\n"
        "Make it somewhat appropriate and add related stuff etc."
    )
    tests.append(
        {
            "description": "English ambiguity must produce explicit handling",
            "vars": {"prompt": ambiguous_prompt},
            "assert": [{"type": "contains", "value": "## 歧义处理"}],
        }
    )
    config = {
        "description": "PEA harness independent structural assertions",
        "prompts": ["{{prompt}}"],
        "providers": [{"id": "file://pea_provider.py"}],
        "tests": tests,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
