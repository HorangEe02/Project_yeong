from __future__ import annotations

import json
import urllib.error
import urllib.request

from lemon_ai_agent.llm.base import LLMRequest, LLMResponse


class OllamaClient:
    """Local Ollama chat client for development runtime checks."""

    def __init__(
        self,
        model: str = "qwen2.5:7b-instruct",
        endpoint: str = "http://127.0.0.1:11434",
        timeout: float = 30,
    ) -> None:
        self.provider = "ollama"
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout

    def generate(self, request: LLMRequest) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": [
                {"role": message.role, "content": message.content} for message in request.messages
            ],
            "stream": False,
            "think": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        http_request = urllib.request.Request(
            f"{self.endpoint}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc

        text = data.get("message", {}).get("content", "")
        return LLMResponse(text=text, provider=self.provider, model=self.model)
