import hashlib
import json
from pathlib import Path
import random
from typing import Literal

from importlib import resources
from pydantic import BaseModel, ConfigDict, Field

SOURCE_URL = "https://huggingface.co/datasets/databricks/databricks-dolly-15k/resolve/main/databricks-dolly-15k.jsonl"
SOURCE_LICENSE = "CC-BY-SA-3.0"
SELECTION_SEED = 20261126
SELECTION_COUNTS = {
    "creative_writing": 20,
    "brainstorming": 15,
    "summarization": 15,
    "information_extraction": 10,
    "closed_qa": 10,
    "classification": 10,
}
DEFAULT_RESOURCE = resources.files("pea").joinpath(
    "resources/benchmarks/dolly_public_sample.jsonl"
)


class ExternalCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    source: Literal["databricks-dolly-15k"]
    source_index: int = Field(ge=1)
    category: str
    instruction: str
    context: str
    reference_response: str
    local_review_status: Literal["not_reviewed"] = "not_reviewed"

    @property
    def prompt(self) -> str:
        if self.context:
            return f"{self.instruction}\n\nContext:\n{self.context}"
        return self.instruction


def import_dolly_sample(
    source: Path,
    destination: Path,
    provenance_path: Path,
) -> list[ExternalCase]:
    raw = source.read_bytes()
    grouped: dict[str, list[tuple[int, dict]]] = {name: [] for name in SELECTION_COUNTS}
    for index, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        category = record["category"]
        if category not in grouped:
            continue
        if not 20 <= len(record["instruction"]) <= 1200:
            continue
        if len(record.get("context") or "") > 3000 or len(record["response"]) > 4000:
            continue
        grouped[category].append((index, record))

    rng = random.Random(SELECTION_SEED)
    selected = []
    for category, count in SELECTION_COUNTS.items():
        candidates = grouped[category]
        if len(candidates) < count:
            raise ValueError(f"not enough Dolly records for {category}")
        rng.shuffle(candidates)
        for index, record in candidates[:count]:
            selected.append(
                ExternalCase(
                    case_id=f"dolly_{index:05}",
                    source="databricks-dolly-15k",
                    source_index=index,
                    category=category,
                    instruction=record["instruction"],
                    context=record.get("context") or "",
                    reference_response=record["response"],
                )
            )
    selected.sort(key=lambda item: item.source_index)

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "\n".join(item.model_dump_json() for item in selected) + "\n",
        encoding="utf-8",
    )
    provenance = {
        "source": "databricks-dolly-15k",
        "source_url": SOURCE_URL,
        "license": SOURCE_LICENSE,
        "license_url": "https://creativecommons.org/licenses/by-sa/3.0/",
        "attribution": "Databricks employees; subset selection and schema adaptation by PEA",
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_rows": len(raw.splitlines()),
        "selection_seed": SELECTION_SEED,
        "selection_counts": SELECTION_COUNTS,
        "selected_rows": len(selected),
        "local_review_status": "not_reviewed",
        "changes": "Filtered by length, deterministically sampled, combined schema, and retained original text",
        "known_limitations": "Source may contain typos, factual errors, bias, and non-representative employee interests",
    }
    provenance_path.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return selected


def load_external_cases(path: Path | None = None) -> list[ExternalCase]:
    source = path or DEFAULT_RESOURCE
    return [
        ExternalCase.model_validate_json(line)
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
