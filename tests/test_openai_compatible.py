from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from threading import Thread
import time

from pydantic import SecretStr

from pea.config import ProviderConfig
from pea.gateway import LiteLLMBackend
from pea.models import ChatMessage, CompletionRequest, Provider


class OpenAICompatibleHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        payload = json.loads(self.rfile.read(length))
        self.server.captured = {
            "path": self.path,
            "authorization": self.headers.get("Authorization"),
            "payload": payload,
        }
        body = json.dumps(
            {
                "id": "chatcmpl-local-compatible",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "compatible-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "local-openai-compatible-response",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 4,
                    "completion_tokens": 3,
                    "total_tokens": 7,
                },
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def test_litellm_uses_openai_compatible_local_http_api() -> None:
    server = HTTPServer(("127.0.0.1", 0), OpenAICompatibleHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}/v1"
        config = ProviderConfig(
            provider=Provider.OPENAI,
            model="compatible-model",
            api_key=SecretStr("test-local-key"),
            api_base=base_url,
            timeout_seconds=10.0,
        )
        request = CompletionRequest(
            provider=Provider.OPENAI,
            messages=[ChatMessage(role="user", content="local format check")],
        )

        result = LiteLLMBackend(local_model_cost_map=True).complete(request, config)

        assert result.content == "local-openai-compatible-response"
        assert result.usage.total_tokens == 7
        assert server.captured["path"] == "/v1/chat/completions"
        assert server.captured["authorization"] == "Bearer test-local-key"
        assert server.captured["payload"]["model"] == "compatible-model"
        assert server.captured["payload"]["messages"] == [
            {"role": "user", "content": "local format check"}
        ]
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
