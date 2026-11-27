import json

import pytest
from fastapi.testclient import TestClient

from pea.api import create_app
from pea.config import Settings
from pea.storage import SQLiteResultManager


@pytest.fixture
def client(tmp_path):
    settings = Settings(_env_file=None, database_path=str(tmp_path / "api.db"))
    manager = SQLiteResultManager(settings.database_path)
    with TestClient(create_app(settings, manager)) as test_client:
        yield test_client


def test_health_and_mock_optimization_history_export(client: TestClient) -> None:
    health_response = client.get("/health").json()
    assert health_response == {"status": "ok", "stage": "Beta", "version": "0.2.0"}

    response = client.post(
        "/api/v1/optimizations",
        json={
            "user_request": "写一条生日祝福，输出一句话。",
            "provider": "mock",
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "completed"
    assert result["request"]["user_request"] == "写一条生日祝福，输出一句话。"

    history = client.get("/api/v1/history").json()
    assert len(history) == 1
    run_id = result["thread_id"]
    detail = client.get(f"/api/v1/history/{run_id}")
    assert detail.status_code == 200
    assert len(detail.json()["versions"]) == 1

    json_export = client.get(f"/api/v1/history/{run_id}/export?format=json")
    markdown_export = client.get(f"/api/v1/history/{run_id}/export?format=markdown")
    assert json.loads(json_export.text)["summary"]["run_id"] == run_id
    assert "Prompt Engineering Agent 运行报告" in markdown_export.text
    assert "attachment" in json_export.headers["content-disposition"]


def test_clarification_cancel_and_missing_routes(client: TestClient) -> None:
    paused = client.post(
        "/api/v1/optimizations",
        json={"user_request": "优化一下"},
    ).json()
    run_id = paused["thread_id"]
    assert paused["status"] == "needs_clarification"

    cancel = client.post(f"/api/v1/optimizations/{run_id}/cancel")
    assert cancel.status_code == 202
    cancelled = client.post(
        f"/api/v1/optimizations/{run_id}/clarifications",
        json={"answers": {"q1": "写一封邮件"}},
    )
    assert cancelled.json()["status"] == "cancelled"

    assert client.get("/api/v1/history/missing").status_code == 404
    assert client.post("/api/v1/optimizations/missing/cancel").status_code == 404
    assert client.post(
        "/api/v1/optimizations/missing/clarifications",
        json={"answers": {"q1": "x"}},
    ).status_code == 404


def test_clarification_resume_completes_and_updates_history(client: TestClient) -> None:
    paused = client.post(
        "/api/v1/optimizations",
        json={"user_request": "优化一下"},
    ).json()

    resumed = client.post(
        f"/api/v1/optimizations/{paused['thread_id']}/clarifications",
        json={"answers": {"q1": "写一封客户回访邮件，输出邮件正文。"}},
    )

    assert resumed.status_code == 200
    assert resumed.json()["status"] == "completed"
    history = client.get("/api/v1/history").json()
    assert len(history) == 1
    assert history[0]["task_type"] == "email_office"


def test_dynamic_mock_evaluation_creates_comparable_versions(client: TestClient) -> None:
    response = client.post(
        "/api/v1/optimizations",
        json={
            "user_request": "生成结果，输出 JSON。",
            "dynamic_evaluation": True,
            "provider": "mock",
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert len(result["iterations"]) == 3
    assert result["final_evaluation"]["passed"] is False
    comparison = client.get(
        f"/api/v1/history/{result['thread_id']}/compare",
        params={"left": 1, "right": 2},
    )
    assert comparison.status_code == 200
    assert "本轮修订重点" in comparison.json()["unified_diff"]


def test_real_provider_is_disabled_by_default(client: TestClient) -> None:
    response = client.post(
        "/api/v1/optimizations",
        json={"user_request": "写一句问候", "provider": "openai"},
    )

    assert response.status_code == 403
    assert "PEA_ENABLE_REAL_PROVIDERS" in response.json()["detail"]


def test_enabled_real_provider_still_requires_safe_configuration(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        database_path=str(tmp_path / "api.db"),
        enable_real_providers=True,
        openai_model="gpt-test",
    )
    manager = SQLiteResultManager(settings.database_path)
    with TestClient(create_app(settings, manager)) as client:
        response = client.post(
            "/api/v1/optimizations",
            json={"user_request": "写一句问候", "provider": "openai"},
        )

    assert response.status_code == 400
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_invalid_input_and_version_return_4xx(client: TestClient) -> None:
    blank = client.post("/api/v1/optimizations", json={"user_request": ""})
    assert blank.status_code == 422

    response = client.post(
        "/api/v1/optimizations",
        json={"user_request": "写一句问候"},
    )
    run_id = response.json()["thread_id"]
    assert client.get(f"/api/v1/history/{run_id}/compare?left=1&right=9").status_code == 404


def test_benchmark_and_public_audit_endpoints(client: TestClient) -> None:
    benchmark = client.get("/api/v1/benchmarks/status")
    audit = client.get("/api/v1/evaluations/public-audit")

    assert benchmark.status_code == 200
    assert benchmark.json()["total"] == 100
    assert benchmark.json()["pending_human_review"] == 100
    assert audit.status_code == 200
    assert audit.json()["public_cases"] == 80
    assert audit.json()["goal_preservation_rate"] == 1.0
    assert audit.json()["semantic_quality_measured"] is False


def test_security_headers_and_trusted_hosts(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert client.get("/health", headers={"host": "untrusted.example"}).status_code == 400


def test_container_host_can_be_allowed_explicitly(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        database_path=str(tmp_path / "api.db"),
        trusted_hosts="127.0.0.1,api",
    )
    manager = SQLiteResultManager(settings.database_path)
    with TestClient(create_app(settings, manager)) as client:
        response = client.get("/health", headers={"host": "api"})

    assert response.status_code == 200


def test_request_body_size_limit_is_enforced_before_model_work(client: TestClient) -> None:
    response = client.post(
        "/api/v1/optimizations",
        content=b"x" * (64 * 1024 + 1),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "request body too large"
    assert client.get("/api/v1/history").json() == []
