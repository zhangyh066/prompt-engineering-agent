import hashlib
import json
from pathlib import Path
import random
from typing import Literal

from pydantic import BaseModel, ConfigDict

from pea.evaluation.external_data import ExternalCase, SELECTION_SEED, SOURCE_LICENSE, SOURCE_URL

SplitName = Literal["train", "dev", "test"]


class OptimizationCase(ExternalCase):
    split: SplitName


def normalize_for_leakage(instruction: str, context: str) -> str:
    return " ".join(f"{instruction}\n{context}".lower().split())


def build_dolly_splits(
    source: Path,
    legacy_dev_cases: list[ExternalCase],
    output_dir: Path,
    manifest_path: Path,
) -> dict:
    raw = source.read_bytes()
    legacy_indices = {case.source_index for case in legacy_dev_cases}
    legacy_keys = {
        normalize_for_leakage(case.instruction, case.context)
        for case in legacy_dev_cases
    }
    seen = set(legacy_keys)
    grouped: dict[str, list[ExternalCase]] = {}
    duplicates_removed = 0
    legacy_overlap_removed = 0
    legacy_excluded = 0

    for index, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        if index in legacy_indices:
            legacy_excluded += 1
            continue
        record = json.loads(line)
        instruction = record["instruction"]
        context = record.get("context") or ""
        key = normalize_for_leakage(instruction, context)
        if key in legacy_keys:
            legacy_overlap_removed += 1
            continue
        if key in seen:
            duplicates_removed += 1
            continue
        seen.add(key)
        grouped.setdefault(record["category"], []).append(
            ExternalCase(
                case_id=f"dolly_{index:05}",
                source="databricks-dolly-15k",
                source_index=index,
                category=record["category"],
                instruction=instruction,
                context=context,
                reference_response=record["response"],
            )
        )

    splits: dict[str, list[OptimizationCase]] = {"train": [], "dev": [], "test": []}
    for category, cases in sorted(grouped.items()):
        rng = random.Random(f"{SELECTION_SEED}:{category}")
        rng.shuffle(cases)
        train_end = int(len(cases) * 0.70)
        dev_end = int(len(cases) * 0.85)
        for split_name, selected in (
            ("train", cases[:train_end]),
            ("dev", cases[train_end:dev_end]),
            ("test", cases[dev_end:]),
        ):
            splits[split_name].extend(
                OptimizationCase(**case.model_dump(), split=split_name)
                for case in selected
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    split_files = {}
    counts = {}
    for split_name, cases in splits.items():
        cases.sort(key=lambda item: item.source_index)
        content = (
            "\n".join(case.model_dump_json() for case in cases) + "\n"
        ).encode()
        path = output_dir / f"dolly_{split_name}.jsonl"
        path.write_bytes(content)
        split_files[split_name] = hashlib.sha256(content).hexdigest()
        counts[split_name] = {
            "total": len(cases),
            "categories": {
                category: sum(case.category == category for case in cases)
                for category in sorted({case.category for case in cases})
            },
        }

    manifest = {
        "source": "databricks-dolly-15k",
        "source_url": SOURCE_URL,
        "license": SOURCE_LICENSE,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_rows": len(raw.splitlines()),
        "seed": SELECTION_SEED,
        "ratios": {"train": 0.70, "dev": 0.15, "test": 0.15},
        "deduplication": "Whitespace-normalized lowercase instruction+context",
        "duplicates_removed": duplicates_removed,
        "legacy_development_cases_excluded": legacy_excluded,
        "legacy_overlap_removed": legacy_overlap_removed,
        "legacy_development_note": "The earlier 80 public cases were used for bug fixing and cannot be final test data",
        "counts": counts,
        "split_sha256": split_files,
        "test_locked": True,
        "test_usage": "Final evaluation only; never strategy search, prompt authoring, or model selection",
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def load_optimization_split(path: Path) -> list[OptimizationCase]:
    return [
        OptimizationCase.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
