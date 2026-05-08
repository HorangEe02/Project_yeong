from __future__ import annotations

import os
from collections.abc import AsyncIterator
from time import monotonic
from typing import Any

from dotenv import load_dotenv

from core.llm_health import HealthRegistry
from core.llm_metrics import MetricsRecorder
from core.llm_types import (
    LLMMode,
    ProviderResponseError,
    StreamEvent,
    UnsupportedModeError,
)
from core.providers import GeminiProvider, LLMProvider, OllamaProvider


load_dotenv()


def _build_model_map() -> dict[LLMMode, dict[str, str | None]]:
    """환경변수로부터 모델맵을 동적으로 구성. PLAN Section 7-2 매핑."""
    chat_large = os.getenv("OLLAMA_MODEL_CHAT_LARGE", "qwen3.5:9b")
    chat_small = os.getenv("OLLAMA_MODEL_CHAT_SMALL", "qwen3.5:4b")
    gemma_large = os.getenv("OLLAMA_MODEL_GEMMA_LARGE", "gemma4:e4b")
    gemma_small = os.getenv("OLLAMA_MODEL_GEMMA_SMALL", "gemma4:e2b")
    embedding = os.getenv("OLLAMA_MODEL_EMBEDDING", "bge-m3")
    gemini = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")

    return {
        LLMMode.CHAT:        {"gemini": gemini, "ollama": chat_large, "ollama_alt": gemma_large, "lm_studio": "default"},
        LLMMode.CHAT_KOREAN: {"gemini": gemini, "ollama": chat_large, "ollama_alt": gemma_large, "lm_studio": "default"},
        LLMMode.VISION:      {"gemini": gemini, "ollama": gemma_large, "ollama_alt": None,        "lm_studio": None},
        LLMMode.DRAFT:       {"gemini": gemini, "ollama": chat_large, "ollama_alt": gemma_large, "lm_studio": "default"},
        LLMMode.SUMMARY:     {"gemini": gemini, "ollama": chat_small, "ollama_alt": gemma_small, "lm_studio": "default"},
        LLMMode.JSON:        {"gemini": gemini, "ollama": chat_large, "ollama_alt": gemma_large, "lm_studio": None},
        LLMMode.INTENT:      {"gemini": gemini, "ollama": chat_small, "ollama_alt": None,        "lm_studio": None},
        LLMMode.EMBEDDING:   {"gemini": None,   "ollama": embedding,  "ollama_alt": None,        "lm_studio": None},
    }


class LLMRouter:
    """Gemini → Ollama → (Phase 2: LM Studio) 폴백 체인을 갖는 비동기 LLM 라우터."""

    def __init__(
        self,
        providers: dict[str, LLMProvider] | None = None,
    ) -> None:
        if providers is None:
            providers = {
                "gemini": GeminiProvider(),
                "ollama": OllamaProvider(),
            }
            # LM Studio 는 환경변수 토글로만 등록 — 미설치 환경에서 health_check 실패 도배 방지
            if os.getenv("LM_STUDIO_ENABLED", "false").lower() == "true":
                from core.providers.lm_studio_provider import LMStudioProvider
                providers["lm_studio"] = LMStudioProvider()
        self.providers: dict[str, LLMProvider] = providers
        self.model_map = _build_model_map()
        self.fallback_enabled = os.getenv("LLM_ROUTER_FALLBACK_ENABLED", "true").lower() == "true"

        self.health = HealthRegistry(
            threshold=int(os.getenv("LLM_ROUTER_CIRCUIT_BREAKER_THRESHOLD", "3")),
            recovery_sec=int(os.getenv("LLM_ROUTER_CIRCUIT_RECOVERY_SEC", "60")),
        )
        self.metrics = MetricsRecorder(
            log_path=os.getenv("LLM_METRICS_LOG_PATH", "logs/llm_metrics.log"),
        )

    async def stream(
        self,
        prompt: str,
        mode: LLMMode = LLMMode.CHAT,
        image_bytes: bytes | None = None,
        history: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.3,
        response_format: str = "text",
        force_provider: tuple[str, str] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        # Day 5 Phase 5 사전 준비 — 단일 (provider, model) 강제. UI 는 Phase 5 에서 부착.
        chain: list[tuple[str, str | None]]
        if force_provider is not None:
            chain = [(force_provider[0], force_provider[1])]
        else:
            chain = self._build_chain(mode, has_image=image_bytes is not None)
        if not chain:
            yield {
                "type": "error",
                "content": f"모드 '{mode}' 에 대한 라우팅 체인이 비어 있습니다.",
                "metadata": None,
            }
            return

        req: dict[str, Any] = {
            "prompt": prompt,
            "mode": mode,
            "image_bytes": image_bytes,
            "history": history or [],
            "temperature": temperature,
            "response_format": response_format,
        }
        if max_tokens is not None:
            req["max_tokens"] = max_tokens

        last_error: Exception | None = None
        attempted: list[str] = []

        for provider_name, model in chain:
            provider = self.providers.get(provider_name)
            if provider is None or model is None:
                continue
            if not provider.supports_mode(mode):
                continue
            # Circuit Breaker — OPEN 상태면 폴백 체인에서 스킵
            if not self.health.is_available(provider_name):
                continue

            start_ts = monotonic()
            first_token_ts: float | None = None

            try:
                yield {
                    "type": "metadata",
                    "content": None,
                    "metadata": {
                        "provider": provider_name,
                        "model": model,
                        "mode": mode.value,
                        "fallback_from": attempted[-1] if attempted else None,
                    },
                }
                got_token = False
                async for ev in provider.stream(req, model=model):
                    if ev.get("type") == "token":
                        if first_token_ts is None:
                            first_token_ts = monotonic()
                        got_token = True
                    yield ev

                if not got_token:
                    # 빈 응답은 실패로 간주하고 다음 프로바이더 시도
                    raise ProviderResponseError(f"{provider_name}/{model}: 빈 응답")

                ttft_ms = (first_token_ts - start_ts) * 1000 if first_token_ts else None
                latency_ms = (monotonic() - start_ts) * 1000
                self.health.record_success(provider_name)
                self.metrics.record_success(provider_name, mode.value, ttft_ms, latency_ms)

                yield {
                    "type": "done",
                    "content": None,
                    "metadata": {"final_provider": provider_name, "final_model": model},
                }
                return
            except Exception as e:
                last_error = e
                attempted.append(provider_name)
                self.health.record_failure(provider_name, e)
                self.metrics.record_failure(provider_name, mode.value, str(e))
                if not self.fallback_enabled:
                    break
                continue

        yield {
            "type": "error",
            "content": f"모든 LLM 프로바이더 실패 (시도: {attempted}): {last_error}",
            "metadata": {"attempted": attempted},
        }

    async def embed(self, text: str) -> list[float]:
        """텍스트를 벡터로 임베딩한다.

        OLLAMA_BASE_URL 비어있거나 EMBEDDING_BACKEND=gemini 설정 시 Gemini API 사용.
        그 외엔 Ollama (bge-m3) 사용.
        """
        import os
        from config import OLLAMA_BASE_URL

        explicit = os.environ.get("EMBEDDING_BACKEND", "").strip().lower()
        use_gemini = (explicit == "gemini") or (
            explicit != "ollama" and not (OLLAMA_BASE_URL or "").strip()
        )

        if use_gemini:
            from core.embedding_client import GeminiEmbeddings
            client = GeminiEmbeddings()
            # 동기 메서드를 async 컨텍스트에서 안전하게 실행
            import asyncio
            return await asyncio.to_thread(client.embed_query, text)

        ollama = self.providers.get("ollama")
        if ollama is None:
            raise UnsupportedModeError("임베딩 프로바이더 (ollama) 가 등록되지 않았습니다.")
        model = self.model_map[LLMMode.EMBEDDING]["ollama"] or "bge-m3"
        return await ollama.embed(text, model=model)

    def _build_chain(self, mode: LLMMode, has_image: bool) -> list[tuple[str, str | None]]:
        """모드별 (provider, model) 폴백 체인 구성."""
        slot = self.model_map.get(mode)
        if slot is None:
            return []

        # 임베딩은 단일 — 폴백 없음. 이미지 입력은 무시 (벡터화에 의미 없음).
        if mode is LLMMode.EMBEDDING:
            return [("ollama", slot["ollama"])] if slot.get("ollama") else []

        # 비전은 이미지 입력 시 Gemini 1순위 + gemma4 만 (qwen 비전 X)
        if mode is LLMMode.VISION or has_image:
            chain: list[tuple[str, str | None]] = []
            if slot.get("gemini"):
                chain.append(("gemini", slot["gemini"]))
            # 비전 시 ollama 모델은 gemma4 만 사용 (image_bytes 가 있을 때 qwen 호출 금지)
            ollama_model = slot.get("ollama")
            if ollama_model and "gemma" in ollama_model:
                chain.append(("ollama", ollama_model))
            elif has_image:
                # CHAT 모드인데 이미지가 들어온 경우 — VISION 슬롯의 gemma4 로 강제
                vision_slot = self.model_map.get(LLMMode.VISION) or {}
                if vision_slot.get("ollama"):
                    chain.append(("ollama", vision_slot["ollama"]))
            return chain

        # draft 는 사내 보안 우선: ollama → ollama_alt → gemini → lm_studio
        if mode is LLMMode.DRAFT:
            order: list[tuple[str, str | None]] = [
                ("ollama", slot.get("ollama")),
                ("ollama", slot.get("ollama_alt")),
                ("gemini", slot.get("gemini")),
                ("lm_studio", slot.get("lm_studio")),
            ]
            return [(p, m) for p, m in order if m]

        # intent: Phase 1 에서는 단순화 — Gemini → Ollama (TF-IDF 는 Phase 2)
        if mode is LLMMode.INTENT:
            order = [
                ("gemini", slot.get("gemini")),
                ("ollama", slot.get("ollama")),
            ]
            return [(p, m) for p, m in order if m]

        # 기본 체인 — LLM_ROUTER_PRIMARY 환경변수로 1순위 토글 (Plan A 변형 v3.7).
        #   LLM_ROUTER_PRIMARY=ollama → ollama → ollama_alt → gemini → lm_studio
        #   LLM_ROUTER_PRIMARY=gemini (또는 미설정) → gemini → ollama → ollama_alt → lm_studio
        # 자가 호스팅 모드(Mac 또는 사내 GPU 서버) 운영 시 ollama, Gemini 폴백 운영 시 gemini.
        # 사고 시 Cloud Run env 만 변경해 즉시 전환 가능.
        primary = os.getenv("LLM_ROUTER_PRIMARY", "gemini").lower()
        if primary == "ollama":
            order = [
                ("ollama", slot.get("ollama")),
                ("ollama", slot.get("ollama_alt")),
                ("gemini", slot.get("gemini")),
                ("lm_studio", slot.get("lm_studio")),
            ]
        else:
            # default — 기존 동작 보존 (Gemini 1순위)
            order = [
                ("gemini", slot.get("gemini")),
                ("ollama", slot.get("ollama")),
                ("ollama", slot.get("ollama_alt")),
                ("lm_studio", slot.get("lm_studio")),
            ]
        return [(p, m) for p, m in order if m]
