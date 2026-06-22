"""SGLang OpenAI-compatible client tests."""

from __future__ import annotations

import json
import urllib.request
from typing import Any

from lemon_ai_agent.llm import LLMMessage, LLMRequest, SGLangClient


class _FakeResponse:
    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps({"choices": [{"message": {"content": "structured ok"}}]}).encode("utf-8")


def test_sglang_client_posts_openai_chat_completion_with_json_schema(
    monkeypatch: Any,
) -> None:
    """Verify SGLang payload uses /v1/chat/completions and JSON Schema response_format."""
    captured: dict[str, Any] = {}

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> _FakeResponse:
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    client = SGLangClient(model="qwen-test", timeout=12)
    response = client.generate(
        LLMRequest(
            messages=[LLMMessage(role="user", content="Return JSON.")],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "CoachingSummary",
                    "schema": {
                        "type": "object",
                        "properties": {"summary": {"type": "string"}},
                        "required": ["summary"],
                    },
                },
            },
        )
    )

    assert captured["url"] == "http://127.0.0.1:30000/v1/chat/completions"
    assert captured["timeout"] == 12
    assert captured["payload"]["model"] == "qwen-test"
    assert captured["payload"]["response_format"]["type"] == "json_schema"
    assert response.provider == "sglang"
    assert response.text == "structured ok"
