from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from typing import Any, ClassVar

from core.llm_types import (
    LLMMode,
    ProviderResponseError,
    StreamEvent,
    StreamRequest,
    UnsupportedModeError,
)
from core.providers.base import LLMProvider


# google-genai SDK 는 import 비용이 상대적으로 크므로 lazy import.
# 또한 Client 인스턴스화 시 API 키가 없으면 동작 안 하므로 health_check 에서도 검증.


class GeminiProvider(LLMProvider):
    name: ClassVar[str] = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.timeout = float(timeout if timeout is not None else os.getenv("GEMINI_TIMEOUT", "60"))
        self._client: Any | None = None
        self._client_async: Any | None = None

    def _get_client(self) -> Any:
        if not self.api_key:
            raise ProviderResponseError("GEMINI_API_KEY 가 설정되지 않았습니다.")
        if self._client is None:
            from google import genai  # type: ignore[import-not-found]

            self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            client = self._get_client()
            # 가벼운 모델 리스트 호출 — 실패 시 False
            await asyncio.wait_for(
                asyncio.to_thread(lambda: list(client.models.list())),
                timeout=3.0,
            )
            return True
        except Exception:
            return False

    async def stream(  # type: ignore[override]
        self,
        req: StreamRequest,
        model: str,
    ) -> AsyncIterator[StreamEvent]:
        from google.genai import types  # type: ignore[import-not-found]

        prompt: str = req.get("prompt", "")
        image_bytes: bytes | None = req.get("image_bytes")
        history: list[dict[str, Any]] = req.get("history", []) or []
        temperature: float = float(req.get("temperature", 0.3))
        max_tokens: int = int(req.get("max_tokens", 2048))
        response_format = req.get("response_format", "text")

        client = self._get_client()

        contents: list[Any] = []
        # history 는 {role: "user"|"model", content: str} 포맷을 가정
        for h in history:
            role = h.get("role", "user")
            text = h.get("content", "")
            if not text:
                continue
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=text)]))

        user_parts: list[Any] = []
        if image_bytes is not None:
            user_parts.append(
                types.Part.from_bytes(data=image_bytes, mime_type="image/png")
            )
        if prompt:
            user_parts.append(types.Part.from_text(text=prompt))
        if user_parts:
            contents.append(types.Content(role="user", parts=user_parts))

        config_kwargs: dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if response_format == "json":
            config_kwargs["response_mime_type"] = "application/json"

        # P3 — Gemini 2.5 thinking 모드 최소화 (첫 토큰 latency 단축).
        # Pro: thinking 비활성 불가 → 최소 budget(128) 로 reasoning 시간 단축.
        # Flash: thinking_budget=0 으로 완전 비활성 (즉시 streaming 시작).
        # 실패 시 silently skip — 구버전 SDK 호환.
        try:
            model_lower = model.lower()
            if "2.5-flash" in model_lower or "flash" in model_lower:
                config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
            elif "2.5-pro" in model_lower or "2.5" in model_lower:
                config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=128)
        except Exception:
            pass

        config = types.GenerateContentConfig(**config_kwargs)

        try:
            stream = await client.aio.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
            )
            async for chunk in stream:
                text = getattr(chunk, "text", None)
                if text:
                    yield {"type": "token", "content": text, "metadata": None}
        except Exception as e:
            raise ProviderResponseError(f"Gemini 스트리밍 실패: {e}") from e

    async def embed(self, text: str, model: str) -> list[float]:
        # 본 라우터는 임베딩을 Ollama bge-m3 단독으로 라우팅한다 (PLAN 4-2).
        # Gemini text-embedding-004 는 차원이 달라 ChromaDB 호환을 위해 사용 안 함.
        raise UnsupportedModeError("Gemini 임베딩은 사용하지 않습니다 (bge-m3 단독).")

    def supports_mode(self, mode: LLMMode) -> bool:
        # 임베딩은 미지원, 그 외 모든 모드 지원 (vision 포함)
        return mode is not LLMMode.EMBEDDING
