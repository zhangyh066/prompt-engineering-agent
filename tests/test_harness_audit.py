import json
from pathlib import Path

from pea.evaluation.external_data import load_external_cases
from pea.evaluation.harness_audit import HarnessAuditor
from pea.evaluation.promptfoo_bridge import write_promptfoo_config


PROVENANCE_PATH = Path(
    "src/pea/resources/benchmarks/dolly_public_sample.provenance.json"
)


def test_public_sample_has_stable_provenance_and_review_boundary() -> None:
    cases = load_external_cases()
    provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))

    assert len(cases) == 80
    assert len({case.case_id for case in cases}) == 80
    assert all(case.local_review_status == "not_reviewed" for case in cases)
    assert provenance["license"] == "CC-BY-SA-3.0"
    assert provenance["raw_rows"] == 15011
    assert len(provenance["raw_sha256"]) == 64
    assert provenance["selection_seed"] == 20261126


def test_harness_audit_detects_supported_mutations() -> None:
    report = HarnessAuditor().run(load_external_cases())

    assert report.goal_preservation_rate == 1.0
    assert report.output_structure_rate == 1.0
    assert report.few_shot_without_example_rate == 0.0
    assert report.role_on_simple_rate == 0.0
    assert report.mutation_detection == {
        "missing_output": 1.0,
        "english_ambiguity": 1.0,
        "english_length_conflict": 1.0,
        "english_vague_clarification": 1.0,
    }
    assert report.semantic_quality_measured is False


def test_promptfoo_bridge_contains_public_and_mutation_cases(tmp_path) -> None:
    destination = tmp_path / "promptfooconfig.yaml"
    write_promptfoo_config(load_external_cases()[:2], destination)
    config = json.loads(destination.read_text(encoding="utf-8"))

    assert len(config["tests"]) == 4
    assert config["providers"] == [{"id": "file://pea_provider.py"}]
    assert config["tests"][-2]["assert"][0]["value"] == "停止执行并列出冲突"
    assert config["tests"][-1]["assert"][0]["value"] == "## 歧义处理"
