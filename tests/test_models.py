import pytest
from pydantic import ValidationError

from pea.models import ChatMessage, CompletionRequest, Provider


def test_completion_request_accepts_typed_messages() -> None:
    request = CompletionRequest(
        provider=Provider.OPENAI,
        messages=[ChatMessage(role="user", content="Hello")],
        temperature=0.2,
        max_tokens=100,
    )

    assert request.messages[0].role.value == "user"
    assert request.provider == Provider.OPENAI


@pytest.mark.parametrize("content", ["", "   "])
def test_message_rejects_blank_content(content: str) -> None:
    with pytest.raises(ValidationError):
        ChatMessage(role="user", content=content)


def test_request_rejects_empty_message_list() -> None:
    with pytest.raises(ValidationError):
        CompletionRequest(messages=[])


@pytest.mark.parametrize("temperature", [-0.1, 2.1])
def test_request_rejects_invalid_temperature(temperature: float) -> None:
    with pytest.raises(ValidationError):
        CompletionRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            temperature=temperature,
        )
