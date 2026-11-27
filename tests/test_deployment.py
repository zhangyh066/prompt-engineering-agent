from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_compose_has_safe_local_network_and_persistent_data() -> None:
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))

    assert set(compose["services"]) == {"api", "ui"}
    assert compose["services"]["api"]["ports"] == ["127.0.0.1:8000:8000"]
    assert compose["services"]["ui"]["ports"] == ["127.0.0.1:8501:8501"]
    assert compose["services"]["api"]["volumes"] == ["pea-data:/data"]
    assert compose["services"]["ui"]["depends_on"]["api"]["condition"] == "service_healthy"
    assert compose["services"]["api"]["environment"]["PEA_ENABLE_REAL_PROVIDERS"] == "${PEA_ENABLE_REAL_PROVIDERS:-False}"


def test_dockerfile_uses_locked_dependencies_and_nonroot_runtime() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert "FROM python:3.12-slim AS runtime-base" in dockerfile
    assert "AS api" in dockerfile and "AS ui" in dockerfile
    assert "uv sync --locked" in dockerfile
    assert "USER pea" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "COPY ." not in dockerfile
    assert ".env" in dockerignore
    assert ".venv" in dockerignore
