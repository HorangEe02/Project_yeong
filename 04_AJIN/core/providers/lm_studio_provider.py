"""LM Studio (OpenAI 호환) 프로바이더.

POST /v1/chat/completions + stream:true 의 SSE 라인 ("data: {...}\\n\\n") 을 직접 파싱.
openai SDK 추가 없이 httpx async 만으로 동작.
임베딩과 비전은 미지원 — 라우터의 _build_chain 에서 LM Studio 슬롯이 비전/임베딩 모드에 매핑되지 않음.
"""
from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any, ClassVar

import httpx

from core.llm_types import (
    LLMMode,
    ProviderResponseError,
    StreamEvent,
    StreamRequest,
    UnsupportedModeError,
)
from core.providers.base import LLMProvider


class LMStudioProvider(LLMProvider):
    name: ClassVar[str] = "lm_studio"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")).rstrip("/")
        self.api_key = api_key or os.getenv("LM_STUDIO_API_KEY", "lm-studio")
        self.timeout = float(timeout if timeout is not None else os.getenv("LM_STUDIO_TIMEOUT", "60"))

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def stream(  # type: ignore[override]
        self,
        req: StreamRequest,
        model: str,
    ) -> AsyncIterator[StreamEvent]:
        prompt: str = req.get("prompt", "")
        history: list[dict[str, Any]] = req.get("history", []) or []
        temperature: float = float(req.get("temperature", 0.3))
        max_tokens: int = int(req.get("max_tokens", 2048))

        # OpenAI 호환 messages: {role: "user"|"assistant"|"system", content: str}
        # 라우터에 들어오는 history 는 {role: "user"|"model", content} 또는 OpenAI 호환 형태일 수 있어
        # "model" → "assistant" 로 변환만 적용.
        messages: list[dict[str, Any]] = []
        for h in history:
            role = h.get("role", "user")
            if role == "model":
                role = "assistant"
            content = h.get("content", "")
            if not content:
                continue
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as resp:
                    if resp.status_code >= 400:
                        body = await resp.aread()
                        raise ProviderResponseError(
                            f"LM Studio HTTP {resp.status_code}: {body.decode('utf-8', errors='replace')[:300]}"
                        )

                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        # OpenAI 호환 SSE: "data: {...}" 또는 "data: [DONE]"
                        if not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        if not data_str:
                            continue
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        choices = data.get("choices") or []
                        if not choices:
                            continue
                        delta = (choices[0] or {}).get("delta") or {}
                        token = delta.get("content") or ""
                        if token:
                            yield {
                                "type": "token",
                                "content": token,
                                "metadata": None,
                            }
        except httpx.HTTPError as e:
            raise ProviderResponseError(f"LM Studio 연결 실패: {e}") from e

    async def embed(self, text: str, model: str) -> list[float]:
        raise UnsupportedModeError("LM Studio 임베딩은 사용하지 않습니다 (bge-m3 단독).")

    def supports_mode(self, mode: LLMMode) -> bool:
        # 임베딩 미지원, 비전은 모델 의존이지만 라우터의 _build_chain 에서 lm_studio 슬롯은 비전 None 으로 매핑됨.
        return mode is not LLMMode.EMBEDDING and mode is not LLMMode.VISION
