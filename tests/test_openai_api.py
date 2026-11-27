import pytest
from fastapi.testclient import TestClient

from pea.api import create_app
from pea.config import Settings
from pea.storage import SQLiteResultManager


@pytest.fixture
def client(tmp_path):
    settings = Settings(_env_file=None, database_path=str(tmp_path / "openai-api.db"))
    manager = SQLiteResultManager(settings.database_path)
    with TestClient(create_app(settings, manager)) as test_client:
        yield test_client


def test_openai_chat_completions_returns_optimized_prompt(client: TestClient) -> None:
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "pea-optimizer",
            "messages": [
                {
                    "role": "user",
                    "content": "写一封客户延期邮件，包含原因、日期和补救措施。",
                }
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "chat.completion"
    assert data["model"] == "pea-optimizer"
    assert data["system_fingerprint"] == "pea-0.2.0"
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert "## 任务目标" in data["choices"][0]["message"]["content"]
    assert data["choices"][0]["finish_reason"] == "stop"
    assert "usage" not in data


def test_openai_chat_completions_preserves_conversation_context(client: TestClient) -> None:
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "pea-optimizer",
            "messages": [
                {"role": "system", "content": "Always answer in French."},
                {"role": "user", "content": "Write a product summary."},
            ],
        },
    )

    content = response.json()["choices"][0]["message"]["content"]
    assert "Always answer in French." in content
    assert "Write a product summary." in content


def test_openai_chat_completions_rejects_streaming_and_empty_user(client: TestClient) -> None:
    streaming = client.post(
        "/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "Write a summary"}],
            "stream": True,
        },
    )
    no_user = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "system", "content": "Be concise"}]},
    )

    assert streaming.status_code == 400
    assert no_user.status_code == 422
