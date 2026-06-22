from __future__ import annotations

import json
import urllib.error
import urllib.request

from lemon_ai_agent.llm.base import LLMRequest, LLMResponse


class OpenAICompatibleClient:
    """Client for an OpenAI-compatible chat completions server."""

    def __init__(
        self,
        model: str,
        endpoint: str = "http://127.0.0.1:8000/v1",
        api_key: str | None = None,
        timeout: float = 30,
        provider: str = "openai-compatible",
    ) -> None:
        self.provider = provider
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key or "EMPTY"
        self.timeout = timeout

    def generate(self, request: LLMRequest) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": [
                {"role": message.role, "content": message.content} for message in request.messages
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.response_format is not None:
            payload["response_format"] = request.response_format
        http_request = urllib.request.Request(
            f"{self.endpoint}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"OpenAI-compatible request failed: {exc}") from exc

        choices = data.get("choices", [])
        text = ""
        if choices:
            text = choices[0].get("message", {}).get("content", "")
        return LLMResponse(
            text=text,
            provider=self.provider,
            model=self.model,
        )
