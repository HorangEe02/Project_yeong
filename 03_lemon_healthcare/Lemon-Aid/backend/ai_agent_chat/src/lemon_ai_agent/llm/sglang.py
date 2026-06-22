from __future__ import annotations

from lemon_ai_agent.llm.openai_compatible import OpenAICompatibleClient


class SGLangClient(OpenAICompatibleClient):
    """SGLang OpenAI-compatible chat completions client."""

    def __init__(
        self,
        model: str,
        endpoint: str = "http://127.0.0.1:30000/v1",
        api_key: str | None = None,
        timeout: float = 30,
    ) -> None:
        super().__init__(
            model=model,
            endpoint=endpoint,
            api_key=api_key,
            timeout=timeout,
            provider="sglang",
        )
