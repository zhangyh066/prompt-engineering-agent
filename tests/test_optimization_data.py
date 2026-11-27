import json
from pathlib import Path

from pea.evaluation.external_data import ExternalCase
from pea.evaluation.optimization_data import build_dolly_splits, load_optimization_split


MANIFEST_PATH = Path("benchmarks/results/dolly_split_manifest.json")


def make_legacy_case() -> ExternalCase:
    return ExternalCase(
        case_id="dolly_00001",
        source="databricks-dolly-15k",
        source_index=1,
        category="classification",
        instruction="Classify this Example",
        context="Context",
        reference_response="label",
    )


def write_raw(path: Path) -> None:
    records = [
        {
            "instruction": "Classify this example",
            "context": "context",
            "response": "label",
            "category": "classification",
        },
        {
            "instruction": " classify   this EXAMPLE ",
            "context": " CONTEXT ",
            "response": "label",
            "category": "classification",
        },
    ]
    records.extend(
        {
            "instruction": f"Instruction {index}",
            "context": "",
            "response": f"Response {index}",
            "category": "classification",
        }
        for index in range(2, 10)
    )
    path.write_text(
        "\n".join(json.dumps(record) for record in records),
        encoding="utf-8",
    )


def test_split_builder_is_reproducible_and_excludes_legacy_overlap(tmp_path) -> None:
    source = tmp_path / "raw.jsonl"
    write_raw(source)

    first = build_dolly_splits(
        source,
        [make_legacy_case()],
        tmp_path / "first",
        tmp_path / "first_manifest.json",
    )
    second = build_dolly_splits(
        source,
        [make_legacy_case()],
        tmp_path / "second",
        tmp_path / "second_manifest.json",
    )

    assert first == second
    assert first["legacy_development_cases_excluded"] == 1
    assert first["legacy_overlap_removed"] == 1
    assert first["counts"]["train"]["total"] == 5
    assert first["counts"]["dev"]["total"] == 1
    assert first["counts"]["test"]["total"] == 2
    all_cases = [
        case
        for split in ("train", "dev", "test")
        for case in load_optimization_split(tmp_path / "first" / f"dolly_{split}.jsonl")
    ]
    assert {case.source_index for case in all_cases}.isdisjoint({1, 2})


def test_actual_manifest_accounts_for_every_raw_row_and_locks_test() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    split_total = sum(item["total"] for item in manifest["counts"].values())

    assert manifest["raw_rows"] == 15011
    assert split_total + 198 + 80 + 5 == 15011
    assert manifest["counts"]["test"]["total"] == 2214
    assert manifest["test_locked"] is True
    assert len(manifest["split_sha256"]["test"]) == 64
