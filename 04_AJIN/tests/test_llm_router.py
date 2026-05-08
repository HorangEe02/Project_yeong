"""LLM 멀티 라우터 단위 테스트 — Phase 3 마무리.

PLAN Section 11-2 의 10 통합 시나리오 + 추가 유닛 (체인 매트릭스, Circuit Breaker
상태 전환, 메트릭 카운터, SSE 이벤트 시퀀스) 을 모두 mock 으로 커버한다.

사용자 정책:
- Gemini: gemini-2.5-pro 단일
- Ollama: qwen3.5:9b/4b, gemma4:e4b/e2b, bge-m3
- EXAONE 미사용 — 한국어 모드도 Gemini 1순위
- 모든 외부 호출 (Gemini SDK, Ollama HTTP) 은 mock — 실 비용/연결 없음
"""
from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterable
from typing import Any

import pytest

from core.llm_health import CircuitState, HealthRegistry
from core.llm_metrics import MetricsRecorder
from core.llm_router import LLMRouter
from core.llm_types import (
    LLMMode,
    ProviderResponseError,
    StreamEvent,
    StreamRequest,
)
from core.providers.base import LLMProvider


# ============================================================
# MockProvider — 실 SDK/HTTP 호출 없이 라우터 로직만 검증
# ============================================================
class MockProvider(LLMProvider):
    """LLMProvider ABC 의 인메모리 구현. 호출 카운트와 실패 모드를 외부에서 제어 가능."""

    def __init__(
        self,
        name: str,
        *,
        fail: bool = False,
        tokens: Iterable[str] = ("hi",),
        exc_factory: Any = None,
        embed_dim: int = 1024,
        supports: set[LLMMode] | None = None,
    ) -> None:
        # ABC 의 ClassVar `name` 을 instance attribute 로 덮어씀 — type checker 우회
        self.name = name  # type: ignore[misc]
        self._fail = fail
        self._tokens = list(tokens)
        self._exc_factory = exc_factory or RuntimeError
        self._embed_dim = embed_dim
        self._supports = supports
        self.call_count = 0
        self.embed_call_count = 0

    async def health_check(self) -> bool:
        return not self._fail

    async def stream(  # type: ignore[override]
        self,
        req: StreamRequest,
        model: str,
    ) -> AsyncIterator[StreamEvent]:
        self.call_count += 1
        if self._fail:
            raise self._exc_factory(f"{self.name} simulated failure")
        for tok in self._tokens:
            yield {"type": "token", "content": tok, "metadata": None}

    async def embed(self, text: str, model: str) -> list[float]:
        self.embed_call_count += 1
        if self._fail:
            raise self._exc_factory(f"{self.name} embed failed")
        return [0.1] * self._embed_dim

    def supports_mode(self, mode: LLMMode) -> bool:
        if self._supports is None:
            return True
        return mode in self._supports


# ============================================================
# 공용 fixture
# ============================================================
@pytest.fixture(autouse=True)
def _isolate_metrics(monkeypatch, tmp_path):
    """각 테스트는 격리된 메트릭 로그 경로 + 격리된 logger 를 사용 — 핸들러 중복 방지."""
    monkeypatch.setenv("LLM_METRICS_LOG_PATH", str(tmp_path / "llm_metrics.log"))
    # MetricsRecorder 의 모듈-스코프 logger 가 누적되지 않도록 매번 핸들러 클리어
    import logging
    lg = logging.getLogger("ajin.llm_metrics")
    for h in list(lg.handlers):
        lg.removeHandler(h)
    yield


@pytest.fixture
def router_with_mocks() -> LLMRouter:
    """Gemini + Ollama 가 모두 정상인 기본 라우터."""
    r = LLMRouter(providers={
        "gemini": MockProvider("gemini", tokens=("g1", "g2")),
        "ollama": MockProvider("ollama", tokens=("o1", "o2")),
    })
    return r


@pytest.fixture
def failing_gemini_router() -> LLMRouter:
    """Gemini 는 실패, Ollama 는 정상 — 폴백 검증용."""
    r = LLMRouter(providers={
        "gemini": MockProvider("gemini", fail=True),
        "ollama": MockProvider("ollama", tokens=("fallback-ok",)),
    })
    return r


@pytest.fixture
def failing_ollama_router() -> LLMRouter:
    """Ollama 는 실패, Gemini 는 정상 — 역방향 검증."""
    r = LLMRouter(providers={
        "gemini": MockProvider("gemini", tokens=("only-gemini",)),
        "ollama": MockProvider("ollama", fail=True),
    })
    return r


@pytest.fixture
def all_failing_router() -> LLMRouter:
    """Gemini, Ollama 모두 실패 — error 이벤트 종착 확인."""
    r = LLMRouter(providers={
        "gemini": MockProvider("gemini", fail=True),
        "ollama": MockProvider("ollama", fail=True),
    })
    return r


@pytest.fixture
def router_with_lm_studio() -> LLMRouter:
    """3-tier 풀세트 — gemini/ollama 실패 시 lm_studio 로 폴백."""
    r = LLMRouter(providers={
        "gemini": MockProvider("gemini", fail=True),
        "ollama": MockProvider("ollama", fail=True),
        "lm_studio": MockProvider("lm_studio", tokens=("lms-1",)),
    })
    return r


@pytest.fixture
def embedding_router() -> LLMRouter:
    """임베딩 전용 — Ollama bge-m3 1024 차원."""
    r = LLMRouter(providers={
        "gemini": MockProvider("gemini"),
        "ollama": MockProvider("ollama", embed_dim=1024),
    })
    return r


@pytest.fixture
def fast_circuit_router() -> LLMRouter:
    """recovery_sec=0.5 로 빠른 HALF_OPEN 검증."""
    r = LLMRouter(providers={
        "gemini": MockProvider("gemini", fail=True),
        "ollama": MockProvider("ollama", tokens=("o",)),
    })
    r.health = HealthRegistry(threshold=3, recovery_sec=0.5)
    return r


# ============================================================
# 헬퍼 — async generator 를 list 로 수집
# ============================================================
async def _collect(stream_iter: AsyncIterator[StreamEvent]) -> list[StreamEvent]:
    return [ev async for ev in stream_iter]


# ============================================================
# 시나리오 #1 — Gemini 정상 호출
# ============================================================
@pytest.mark.asyncio
async def test_scenario_1_gemini_primary_success(router_with_mocks: LLMRouter) -> None:
    """LLMMode.CHAT 호출 시 첫 metadata 의 provider="gemini", token 들이 yield, done 으로 종료."""
    events = await _collect(router_with_mocks.stream("hello", mode=LLMMode.CHAT))

    metas = [e for e in events if e["type"] == "metadata"]
    tokens = [e for e in events if e["type"] == "token"]
    dones = [e for e in events if e["type"] == "done"]
    errors = [e for e in events if e["type"] == "error"]

    assert len(metas) >= 1, "최소 1개의 metadata 이벤트 필요"
    assert metas[0]["metadata"]["provider"] == "gemini"
    assert metas[0]["metadata"]["model"] == "gemini-2.5-pro"
    assert metas[0]["metadata"]["fallback_from"] is None
    assert [t["content"] for t in tokens] == ["g1", "g2"]
    assert len(dones) == 1
    assert dones[0]["metadata"]["final_provider"] == "gemini"
    assert not errors


# ============================================================
# 시나리오 #2 — Gemini 실패 → Ollama 자동 폴백
# ============================================================
@pytest.mark.asyncio
async def test_scenario_2_gemini_failure_falls_back_to_ollama(
    failing_gemini_router: LLMRouter,
) -> None:
    """Gemini 가 실패하면 Ollama 로 자동 폴백되어 fallback_from='gemini' 또는 provider='ollama' 의 metadata 가 등장."""
    events = await _collect(failing_gemini_router.stream("test", mode=LLMMode.CHAT))

    metas = [e for e in events if e["type"] == "metadata"]
    dones = [e for e in events if e["type"] == "done"]

    # 최소 2개의 metadata (gemini 시도 → ollama 시도)
    assert len(metas) >= 2
    providers = [m["metadata"]["provider"] for m in metas]
    assert "gemini" in providers
    assert "ollama" in providers

    # ollama metadata 의 fallback_from 은 "gemini"
    ollama_meta = next(m for m in metas if m["metadata"]["provider"] == "ollama")
    assert ollama_meta["metadata"]["fallback_from"] == "gemini"

    # 최종 응답은 ollama
    assert len(dones) == 1
    assert dones[0]["metadata"]["final_provider"] == "ollama"


# ============================================================
# 시나리오 #3 — Ollama 종료 → Gemini 만 응답
# ============================================================
@pytest.mark.asyncio
async def test_scenario_3_ollama_down_gemini_serves(
    failing_ollama_router: LLMRouter,
) -> None:
    """기본 체인은 Gemini → Ollama 이므로 Ollama 가 죽어도 Gemini 단독으로 응답."""
    events = await _collect(failing_ollama_router.stream("query", mode=LLMMode.CHAT))

    tokens = [e for e in events if e["type"] == "token"]
    dones = [e for e in events if e["type"] == "done"]

    assert [t["content"] for t in tokens] == ["only-gemini"]
    assert dones[0]["metadata"]["final_provider"] == "gemini"


# ============================================================
# 시나리오 #4 — 둘 다 실패 → error / LM Studio 등록 시 fallback
# ============================================================
@pytest.mark.asyncio
async def test_scenario_4a_all_fail_yields_error(all_failing_router: LLMRouter) -> None:
    """Gemini + Ollama 모두 실패 시 마지막에 error 이벤트가 yield 되고 done 은 없다."""
    events = await _collect(all_failing_router.stream("q", mode=LLMMode.CHAT))

    errors = [e for e in events if e["type"] == "error"]
    dones = [e for e in events if e["type"] == "done"]

    assert len(errors) == 1
    assert "모든 LLM 프로바이더 실패" in (errors[0]["content"] or "")
    assert errors[0]["metadata"]["attempted"]
    assert "gemini" in errors[0]["metadata"]["attempted"]
    assert not dones


@pytest.mark.asyncio
async def test_scenario_4b_lm_studio_third_tier_fallback(
    router_with_lm_studio: LLMRouter,
) -> None:
    """Gemini + Ollama 모두 실패해도 LM Studio 가 등록되어 있으면 마지막에 응답."""
    events = await _collect(router_with_lm_studio.stream("q", mode=LLMMode.CHAT))

    tokens = [e for e in events if e["type"] == "token"]
    dones = [e for e in events if e["type"] == "done"]

    assert [t["content"] for t in tokens] == ["lms-1"]
    assert dones[0]["metadata"]["final_provider"] == "lm_studio"


# ============================================================
# 시나리오 #5 — 한국어 모드도 Gemini 1순위 (사용자 정책: EXAONE 아님)
# ============================================================
@pytest.mark.asyncio
async def test_scenario_5_korean_mode_routes_to_gemini_first(
    router_with_mocks: LLMRouter,
) -> None:
    """LLMMode.CHAT_KOREAN 도 Gemini 1순위 — EXAONE 라우팅은 사용자 정책상 없음."""
    events = await _collect(
        router_with_mocks.stream("안녕하세요", mode=LLMMode.CHAT_KOREAN)
    )

    metas = [e for e in events if e["type"] == "metadata"]
    dones = [e for e in events if e["type"] == "done"]

    # 1순위는 gemini-2.5-pro
    assert metas[0]["metadata"]["provider"] == "gemini"
    assert metas[0]["metadata"]["model"] == "gemini-2.5-pro"
    assert metas[0]["metadata"]["mode"] == "chat_korean"
    assert dones[0]["metadata"]["final_provider"] == "gemini"


@pytest.mark.asyncio
async def test_scenario_5b_korean_fallback_to_qwen35_9b() -> None:
    """한국어 모드에서 Gemini 가 죽으면 폴백은 qwen3.5:9b (chat_large)."""
    r = LLMRouter(providers={
        "gemini": MockProvider("gemini", fail=True),
        "ollama": MockProvider("ollama", tokens=("ko",)),
    })
    events = await _collect(r.stream("안녕", mode=LLMMode.CHAT_KOREAN))

    metas = [e for e in events if e["type"] == "metadata"]
    ollama_meta = next(m for m in metas if m["metadata"]["provider"] == "ollama")
    assert ollama_meta["metadata"]["model"] == "qwen3.5:9b"


# ============================================================
# 시나리오 #6 — 비전 모드 + 이미지 입력
# ============================================================
@pytest.mark.asyncio
async def test_scenario_6_vision_mode_uses_gemini(router_with_mocks: LLMRouter) -> None:
    """VISION 모드 + image_bytes 가 있으면 Gemini Vision 호출, ollama 는 gemma 만."""
    events = await _collect(
        router_with_mocks.stream(
            "이 이미지를 설명",
            mode=LLMMode.VISION,
            image_bytes=b"fake-png-bytes",
        )
    )

    metas = [e for e in events if e["type"] == "metadata"]
    dones = [e for e in events if e["type"] == "done"]

    assert metas[0]["metadata"]["provider"] == "gemini"
    assert metas[0]["metadata"]["mode"] == "vision"
    assert dones[0]["metadata"]["final_provider"] == "gemini"


@pytest.mark.asyncio
async def test_scenario_6b_vision_falls_back_to_gemma_not_qwen() -> None:
    """비전 폴백 시 ollama 모델은 gemma4 만 — qwen3.5 는 비전 미지원이므로 호출되면 안 됨."""
    r = LLMRouter(providers={
        "gemini": MockProvider("gemini", fail=True),
        "ollama": MockProvider("ollama", tokens=("vision-ok",)),
    })
    events = await _collect(
        r.stream("img?", mode=LLMMode.VISION, image_bytes=b"fake")
    )

    metas = [e for e in events if e["type"] == "metadata"]
    ollama_meta = next(
        (m for m in metas if m["metadata"]["provider"] == "ollama"), None
    )
    # 비전 슬롯의 ollama 는 gemma4:e4b 만 매핑 — qwen 이 model 에 들어가면 안 됨
    assert ollama_meta is not None
    assert "gemma" in ollama_meta["metadata"]["model"]
    assert "qwen" not in ollama_meta["metadata"]["model"]


# ============================================================
# 시나리오 #7 — 임베딩 1024 차원
# ============================================================
@pytest.mark.asyncio
async def test_scenario_7_embedding_returns_1024_dim(
    embedding_router: LLMRouter,
) -> None:
    """LLMRouter.embed 는 ollama bge-m3 호출, 1024 차원 벡터 반환."""
    vec = await embedding_router.embed("아진산업 품질관리")

    assert isinstance(vec, list)
    assert len(vec) == 1024
    assert all(isinstance(x, float) for x in vec)
    # ollama 만 호출되어야 함 (gemini.embed 는 호출 안 됨)
    ollama_mock: MockProvider = embedding_router.providers["ollama"]  # type: ignore[assignment]
    gemini_mock: MockProvider = embedding_router.providers["gemini"]  # type: ignore[assignment]
    assert ollama_mock.embed_call_count == 1
    assert gemini_mock.embed_call_count == 0


# ============================================================
# 시나리오 #8 — Circuit Breaker 3 실패 후 OPEN
# ============================================================
@pytest.mark.asyncio
async def test_scenario_8_circuit_breaker_opens_after_threshold() -> None:
    """3 회 연속 실패 후 4번째 호출에서 Gemini 는 즉시 스킵, Ollama 가 곧바로 호출."""
    gemini_mock = MockProvider("gemini", fail=True)
    ollama_mock = MockProvider("ollama", tokens=("ok",))
    r = LLMRouter(providers={"gemini": gemini_mock, "ollama": ollama_mock})

    # 3 회 호출 — 매번 Gemini 가 실패 후 Ollama 폴백
    for _ in range(3):
        await _collect(r.stream("q", mode=LLMMode.CHAT))

    # threshold (3) 도달 후 Gemini 는 OPEN
    snap = r.health.snapshot()
    assert snap["gemini"]["state"] == "open"
    assert snap["gemini"]["failure_count"] >= 3

    # 4번째 호출 — Gemini 호출 카운트 증가 안 함 (스킵)
    gemini_call_count_before = gemini_mock.call_count
    events = await _collect(r.stream("q4", mode=LLMMode.CHAT))
    assert gemini_mock.call_count == gemini_call_count_before  # 스킵됨

    # 첫 metadata 가 곧바로 ollama
    metas = [e for e in events if e["type"] == "metadata"]
    assert metas[0]["metadata"]["provider"] == "ollama"


# ============================================================
# 시나리오 #9 — recovery_sec 후 HALF_OPEN, 1회 성공 시 CLOSED
# ============================================================
@pytest.mark.asyncio
async def test_scenario_9_circuit_breaker_recovery() -> None:
    """OPEN 후 recovery_sec 경과 → HALF_OPEN → 성공 시 CLOSED 로 복귀."""
    gemini_mock = MockProvider("gemini", fail=True)
    ollama_mock = MockProvider("ollama", tokens=("ok",))
    r = LLMRouter(providers={"gemini": gemini_mock, "ollama": ollama_mock})
    r.health = HealthRegistry(threshold=3, recovery_sec=0.5)

    # 3회 실패로 OPEN 만들기
    for _ in range(3):
        await _collect(r.stream("q", mode=LLMMode.CHAT))
    assert r.health.snapshot()["gemini"]["state"] == "open"

    # recovery_sec 경과 대기
    await asyncio.sleep(0.6)

    # 다음 is_available 호출 시 HALF_OPEN 으로 전이
    assert r.health.is_available("gemini") is True
    assert r.health._states["gemini"].state is CircuitState.HALF_OPEN

    # Gemini 를 성공으로 전환하고 호출 → CLOSED
    gemini_mock._fail = False
    gemini_mock._tokens = ["recovered"]
    await _collect(r.stream("recover", mode=LLMMode.CHAT))
    assert r.health._states["gemini"].state is CircuitState.CLOSED
    assert r.health._states["gemini"].failure_count == 0


# ============================================================
# 시나리오 #10 — SSE 이벤트 시퀀스 (metadata → token+ → done)
# ============================================================
@pytest.mark.asyncio
async def test_scenario_10_event_sequence_order(router_with_mocks: LLMRouter) -> None:
    """단일 성공 호출에서 이벤트 순서는 metadata → token... → done 순으로 보장."""
    events = await _collect(router_with_mocks.stream("seq", mode=LLMMode.CHAT))
    types_seq = [e["type"] for e in events]

    # 첫 이벤트는 metadata, 마지막은 done
    assert types_seq[0] == "metadata"
    assert types_seq[-1] == "done"
    # token 들은 metadata 이후, done 이전
    first_token_idx = types_seq.index("token")
    last_token_idx = len(types_seq) - 1 - types_seq[::-1].index("token")
    assert first_token_idx > 0
    assert last_token_idx < len(types_seq) - 1


@pytest.mark.asyncio
async def test_scenario_10b_event_sequence_with_fallback(
    failing_gemini_router: LLMRouter,
) -> None:
    """폴백 시 이벤트 순서: metadata(gemini) → metadata(ollama) → token+ → done."""
    events = await _collect(
        failing_gemini_router.stream("seq", mode=LLMMode.CHAT)
    )
    types_seq = [e["type"] for e in events]

    # 최소 2개 metadata, 최소 1개 token, 마지막은 done
    assert types_seq.count("metadata") >= 2
    assert "token" in types_seq
    assert types_seq[-1] == "done"


# ============================================================
# 추가 유닛 — _build_chain 8 모드 × 이미지 매트릭스
# ============================================================
@pytest.mark.asyncio
async def test_build_chain_chat_no_image(router_with_mocks: LLMRouter) -> None:
    chain = router_with_mocks._build_chain(LLMMode.CHAT, has_image=False)
    # gemini → ollama (qwen3.5:9b) → ollama (gemma4:e4b)
    providers_in_chain = [p for p, _ in chain]
    assert providers_in_chain[0] == "gemini"
    assert "ollama" in providers_in_chain
    # 모델 검증
    models_in_chain = [m for _, m in chain]
    assert "gemini-2.5-pro" in models_in_chain
    assert "qwen3.5:9b" in models_in_chain


@pytest.mark.asyncio
async def test_build_chain_summary_uses_smaller_models(
    router_with_mocks: LLMRouter,
) -> None:
    """SUMMARY 모드는 chat_small (qwen3.5:4b) 사용 — 빠른 응답 우선."""
    chain = router_with_mocks._build_chain(LLMMode.SUMMARY, has_image=False)
    models = [m for _, m in chain]
    assert "qwen3.5:4b" in models
    assert "qwen3.5:9b" not in models  # large 는 SUMMARY 에 안 들어가야 함


@pytest.mark.asyncio
async def test_build_chain_draft_prefers_local_first(
    router_with_mocks: LLMRouter,
) -> None:
    """DRAFT 모드는 사내 보안 우선 — ollama 가 gemini 보다 먼저 와야 함."""
    chain = router_with_mocks._build_chain(LLMMode.DRAFT, has_image=False)
    providers_in_order = [p for p, _ in chain]
    ollama_idx = providers_in_order.index("ollama")
    gemini_idx = providers_in_order.index("gemini")
    assert ollama_idx < gemini_idx, "DRAFT 는 사내 ollama 가 gemini 보다 우선"


@pytest.mark.asyncio
async def test_build_chain_intent_short_chain(router_with_mocks: LLMRouter) -> None:
    """INTENT 모드는 단순화된 체인 — gemini → ollama (chat_small)."""
    chain = router_with_mocks._build_chain(LLMMode.INTENT, has_image=False)
    assert len(chain) == 2
    assert chain[0][0] == "gemini"
    assert chain[1][0] == "ollama"
    assert chain[1][1] == "qwen3.5:4b"


@pytest.mark.asyncio
async def test_build_chain_embedding_single_ollama(
    router_with_mocks: LLMRouter,
) -> None:
    """EMBEDDING 모드는 폴백 없음 — ollama bge-m3 단독."""
    chain = router_with_mocks._build_chain(LLMMode.EMBEDDING, has_image=False)
    assert chain == [("ollama", "bge-m3")]


@pytest.mark.asyncio
async def test_build_chain_vision_filters_qwen(router_with_mocks: LLMRouter) -> None:
    """VISION 모드는 ollama 의 gemma4 만 — qwen 은 비전 미지원이라 체인에서 제외."""
    chain = router_with_mocks._build_chain(LLMMode.VISION, has_image=True)
    for prov, model in chain:
        if prov == "ollama":
            assert "gemma" in (model or "")
            assert "qwen" not in (model or "")


@pytest.mark.asyncio
async def test_build_chain_chat_with_image_routes_vision(
    router_with_mocks: LLMRouter,
) -> None:
    """CHAT 모드인데 이미지가 들어오면 비전 슬롯의 gemma4 로 폴백."""
    chain = router_with_mocks._build_chain(LLMMode.CHAT, has_image=True)
    providers = [p for p, _ in chain]
    assert "gemini" in providers
    # ollama 가 있다면 gemma4 모델
    for prov, model in chain:
        if prov == "ollama":
            assert "gemma" in (model or "")


@pytest.mark.asyncio
async def test_build_chain_json_mode(router_with_mocks: LLMRouter) -> None:
    """JSON 모드 체인 — gemini → ollama (chat_large) → ollama (gemma_large), lm_studio 슬롯은 None."""
    chain = router_with_mocks._build_chain(LLMMode.JSON, has_image=False)
    providers = [p for p, _ in chain]
    assert "gemini" in providers
    assert "ollama" in providers


# ============================================================
# 추가 유닛 — LLMMode Enum 8개
# ============================================================
def test_llm_mode_enum_has_eight_values() -> None:
    expected = {
        "chat", "chat_korean", "vision", "draft",
        "summary", "intent", "embedding", "json",
    }
    actual = {m.value for m in LLMMode}
    assert actual == expected


# ============================================================
# 추가 유닛 — MetricsRecorder 카운터
# ============================================================
@pytest.mark.asyncio
async def test_metrics_recorder_counts_success_and_failure(
    failing_gemini_router: LLMRouter,
) -> None:
    """성공/실패 호출 후 MetricsRecorder.snapshot 의 카운터가 정확히 증가."""
    await _collect(failing_gemini_router.stream("q", mode=LLMMode.CHAT))

    snap = failing_gemini_router.metrics.snapshot()
    counters = snap["counters"]
    # gemini 는 실패 1회, ollama 는 성공 1회 기대
    assert counters.get("gemini:chat", {}).get("failure", 0) == 1
    assert counters.get("ollama:chat", {}).get("success", 0) == 1


def test_metrics_snapshot_structure() -> None:
    rec = MetricsRecorder(enabled=False)  # 디스크 IO 없이
    rec.record_success("gemini", "chat", ttft_ms=100.5, latency_ms=500.7)
    rec.record_failure("ollama", "chat", "connection refused")
    snap = rec.snapshot()
    assert "counters" in snap
    assert "latency" in snap
    assert snap["counters"]["gemini:chat"]["success"] == 1
    assert snap["counters"]["ollama:chat"]["failure"] == 1
    assert snap["latency"]["gemini:chat"]["count"] == 1


# ============================================================
# 추가 유닛 — HealthRegistry 401 즉시 OPEN
# ============================================================
def test_health_registry_auth_error_immediately_opens() -> None:
    """HTTP 401 류 인증 실패는 1회만으로도 즉시 OPEN — 폴백 도배 방지."""
    reg = HealthRegistry(threshold=3, recovery_sec=60)
    reg.record_failure("gemini", ProviderResponseError("Gemini HTTP 401: invalid API key"))
    snap = reg.snapshot()
    assert snap["gemini"]["state"] == "open"
    assert snap["gemini"]["last_error_kind"] == "auth"


def test_health_registry_normal_failures_need_threshold() -> None:
    """일반 실패는 threshold 누적 후에 OPEN 으로 전이."""
    reg = HealthRegistry(threshold=3, recovery_sec=60)
    reg.record_failure("ollama", ProviderResponseError("connection refused"))
    assert reg.snapshot()["ollama"]["state"] == "closed"
    reg.record_failure("ollama", ProviderResponseError("connection refused"))
    assert reg.snapshot()["ollama"]["state"] == "closed"
    reg.record_failure("ollama", ProviderResponseError("connection refused"))
    assert reg.snapshot()["ollama"]["state"] == "open"


def test_health_registry_success_resets_state() -> None:
    """성공 1회로 CLOSED 복귀 + failure_count 리셋."""
    reg = HealthRegistry(threshold=3, recovery_sec=60)
    reg.record_failure("ollama", ProviderResponseError("timeout"))
    reg.record_failure("ollama", ProviderResponseError("timeout"))
    assert reg.snapshot()["ollama"]["failure_count"] == 2
    reg.record_success("ollama")
    assert reg.snapshot()["ollama"]["state"] == "closed"
    assert reg.snapshot()["ollama"]["failure_count"] == 0


# ============================================================
# 추가 유닛 — 빈 응답 = 실패 → 폴백
# ============================================================
@pytest.mark.asyncio
async def test_empty_response_treated_as_failure_triggers_fallback() -> None:
    """provider 가 토큰을 한 개도 안 yield 하면 ProviderResponseError 발생 → 다음 provider 폴백."""
    r = LLMRouter(providers={
        "gemini": MockProvider("gemini", tokens=()),  # 빈 응답
        "ollama": MockProvider("ollama", tokens=("recovered",)),
    })
    events = await _collect(r.stream("q", mode=LLMMode.CHAT))
    dones = [e for e in events if e["type"] == "done"]
    tokens = [e for e in events if e["type"] == "token"]

    assert dones[0]["metadata"]["final_provider"] == "ollama"
    assert any(t["content"] == "recovered" for t in tokens)


# ============================================================
# 추가 유닛 — fallback_enabled=False 시 단일 시도로 끝
# ============================================================
@pytest.mark.asyncio
async def test_fallback_disabled_does_not_try_next_provider() -> None:
    """LLM_ROUTER_FALLBACK_ENABLED=false 시 첫 provider 실패하면 폴백 안 함."""
    r = LLMRouter(providers={
        "gemini": MockProvider("gemini", fail=True),
        "ollama": MockProvider("ollama", tokens=("o",)),
    })
    r.fallback_enabled = False

    events = await _collect(r.stream("q", mode=LLMMode.CHAT))
    errors = [e for e in events if e["type"] == "error"]
    dones = [e for e in events if e["type"] == "done"]
    ollama_mock: MockProvider = r.providers["ollama"]  # type: ignore[assignment]

    assert len(errors) == 1  # 폴백 안 했으므로 에러로 종료
    assert not dones
    assert ollama_mock.call_count == 0  # ollama 호출 안 됨
