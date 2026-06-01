from __future__ import annotations

import base64
import json
import os
from collections.abc import AsyncIterator
from typing import Any, ClassVar

import httpx

from config import ollama_headers
from core.llm_types import (
    LLMMode,
    ProviderResponseError,
    StreamEvent,
    StreamRequest,
)
from core.providers.base import LLMProvider


# Qwen 3.5 / EXAONE Deep 계열은 thinking 모드가 기본 활성화 — content 가 비어 오거나
# <thought>...</thought> 블록 출력이 길어 SSE 응답 지연 → /no_think 토큰 주입 +
# payload think=false 로 강제 비활성화한다.
_THINKING_MODELS: tuple[str, ...] = ("qwen3.5", "qwen3", "exaone-deep")


def _is_thinking_model(model: str) -> bool:
    return any(tag in model for tag in _THINKING_MODELS)


class OllamaProvider(LLMProvider):
    name: ClassVar[str] = "ollama"

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.timeout = float(timeout if timeout is not None else os.getenv("OLLAMA_TIMEOUT", "60"))
        # Plan A 변형: Cloud Run prod 에서는 Caddy reverse proxy 경유 → X-AJIN-Secret 헤더 필요.
        # 로컬 dev (localhost:11434 직접) 에서는 빈 dict 반환 (인증 불요).
        self._headers = ollama_headers()

    async def health_check(self) -> bool:
        # 외장 SSD 경로 이슈로 /api/tags 가 빈 배열이거나 500 을 반환할 수 있어
        # 더 가벼운 /api/version 을 우선 사용한다.
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.base_url}/api/version", headers=self._headers)
                return resp.status_code == 200
        except Exception:
            return False

    async def stream(  # type: ignore[override]
        self,
        req: StreamRequest,
        model: str,
    ) -> AsyncIterator[StreamEvent]:
        prompt: str = req.get("prompt", "")
        image_bytes: bytes | None = req.get("image_bytes")
        history: list[dict[str, Any]] = req.get("history", []) or []
        temperature: float = float(req.get("temperature", 0.3))
        max_tokens: int = int(req.get("max_tokens", 2048))
        response_format = req.get("response_format", "text")

        is_thinking = _is_thinking_model(model)
        actual_prompt = f"/no_think\n{prompt}" if is_thinking else prompt
        if response_format == "json":
            actual_prompt = f"{actual_prompt}\n\n반드시 JSON 형식으로만 응답하세요."

        messages: list[dict[str, Any]] = list(history)
        user_message: dict[str, Any] = {"role": "user", "content": actual_prompt}
        if image_bytes is not None:
            user_message["images"] = [base64.b64encode(image_bytes).decode("utf-8")]
        messages.append(user_message)

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "keep_alive": "24h",
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
                "num_ctx": 8192,
            },
        }
        if is_thinking:
            payload["think"] = False
        if response_format == "json":
            payload["format"] = "json"

        url = f"{self.base_url}/api/chat"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, json=payload, headers=self._headers) as resp:
                    if resp.status_code >= 400:
                        body = await resp.aread()
                        raise ProviderResponseError(
                            f"Ollama HTTP {resp.status_code}: {body.decode('utf-8', errors='replace')[:300]}"
                        )

                    any_token = False
                    # v3.5 — EXAONE Deep 등 <thought> 텍스트 출력 모델은 stripper 적용.
                    # 순환 import 방지 — 함수 호출 시점에 lazy import.
                    stripper = None
                    if _is_thinking_model(model):
                        from core.llm_client import _ThoughtStripper

                        stripper = _ThoughtStripper()

                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        msg = data.get("message", {}) or {}
                        token = msg.get("content", "") or ""
                        # thinking 토큰(API thinking 필드 또는 <thought> 텍스트)은 무시
                        if token:
                            any_token = True
                            if stripper is not None:
                                visible = stripper.process(token)
                                if visible:
                                    yield {
                                        "type": "token",
                                        "content": visible,
                                        "metadata": None,
                                    }
                            else:
                                yield {
                                    "type": "token",
                                    "content": token,
                                    "metadata": None,
                                }

                        if data.get("done"):
                            # 잔여 buffer flush
                            if stripper is not None:
                                tail = stripper.flush()
                                if tail:
                                    yield {
                                        "type": "token",
                                        "content": tail,
                                        "metadata": None,
                                    }
                            if not any_token:
                                # thinking 만 채워져 응답이 비었을 때 — non-stream 폴백
                                async for ev in self._fallback_non_stream(
                                    actual_prompt, model, max_tokens, temperature, image_bytes
                                ):
                                    yield ev
                            break
        except httpx.HTTPError as e:
            raise ProviderResponseError(f"Ollama 연결 실패: {e}") from e

    async def _fallback_non_stream(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        image_bytes: bytes | None,
    ) -> AsyncIterator[StreamEvent]:
        message: dict[str, Any] = {"role": "user", "content": prompt}
        if image_bytes is not None:
            message["images"] = [base64.b64encode(image_bytes).decode("utf-8")]

        payload: dict[str, Any] = {
            "model": model,
            "messages": [message],
            "stream": False,
            "think": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
                "num_ctx": 8192,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload, headers=self._headers)
                if resp.status_code != 200:
                    raise ProviderResponseError(f"Ollama non-stream HTTP {resp.status_code}")
                content = (resp.json().get("message") or {}).get("content") or ""
                if content:
                    yield {"type": "token", "content": content, "metadata": None}
        except httpx.HTTPError as e:
            raise ProviderResponseError(f"Ollama non-stream 폴백 실패: {e}") from e

    async def embed(self, text: str, model: str) -> list[float]:
        url = f"{self.base_url}/api/embeddings"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json={"model": model, "prompt": text}, headers=self._headers)
                if resp.status_code != 200:
                    raise ProviderResponseError(
                        f"Ollama embeddings HTTP {resp.status_code}: {resp.text[:300]}"
                    )
                data = resp.json()
                vec = data.get("embedding") or []
                if not vec:
                    raise ProviderResponseError("Ollama embeddings: 빈 벡터 반환")
                return [float(x) for x in vec]
        except httpx.HTTPError as e:
            raise ProviderResponseError(f"Ollama embeddings 연결 실패: {e}") from e

    def supports_mode(self, mode: LLMMode) -> bool:
        # vision 은 gemma4 계열에서만 가능하지만, 모델이 라우터에서 결정되므로
        # 프로바이더 레벨에서는 모든 모드를 허용. (라우터의 _build_chain 이 모델 선택)
        return True
