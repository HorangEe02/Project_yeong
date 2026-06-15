"""v4.7 Sprint 2 P0 (축 ④) — Vision OCR + 검색 통합 테스트.

외부 의존성 (GEMINI_API_KEY) 미설정 환경에서도 테스트가 통과되도록
Gemini API 호출을 monkeypatch 로 모킹.

검증:
  1. GEMINI_API_KEY 미설정 시 vision_search 가 RuntimeError("vision_disabled") 발생.
  2. 키 설정 + Gemini mock → OCR 텍스트 추출 + searcher 호출 → 결과 합쳐 반환.
  3. capability endpoint 가 환경 변수 상태를 반영.
"""

from __future__ import annotations

import io
from typing import Any

import pytest


class _FakeRRFResult:
    """SearchResult dataclass 호환 stub."""

    def __init__(
        self,
        doc_id: str = "doc-1",
        title: str = "Drawing KOR-2024-001",
        doc_type: str = "drawing",
        score: float = 0.91,
    ) -> None:
        self.doc_id = doc_id
        self.title = title
        self.doc_type = doc_type
        self.part_name = ""
        self.content = "도면 KOR-2024-001 — 부품 사양"
        self.score = score
        self.metadata = {"source": "vision"}


class _FakeSearcher:
    def search(self, query: str, k: int = 8) -> list[Any]:  # noqa: ARG002
        return [_FakeRRFResult()]


def test_vision_search_without_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    # 캐시 비우기 — 다른 테스트에서 채워졌을 수 있음.
    import features.search.vision_query as mod

    mod._OCR_CACHE.clear()

    with pytest.raises(RuntimeError) as exc:
        mod.vision_search(b"fake-image-bytes", searcher=_FakeSearcher())
    assert str(exc.value) == "vision_disabled"


def test_vision_search_with_api_key_uses_ocr_and_searcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    import features.search.vision_query as mod

    mod._OCR_CACHE.clear()

    captured: dict[str, Any] = {}

    def fake_ocr(image_bytes: bytes) -> str:
        captured["bytes_len"] = len(image_bytes)
        return "KOR-2024-001 도면 정보"

    monkeypatch.setattr(mod, "_gemini_ocr", fake_ocr)

    ocr, results = mod.vision_search(b"binary-image-data", searcher=_FakeSearcher())
    assert ocr == "KOR-2024-001 도면 정보"
    assert captured["bytes_len"] == len(b"binary-image-data")
    assert len(results) == 1
    assert results[0]["doc_id"] == "doc-1"
    assert results[0]["title"] == "Drawing KOR-2024-001"
    assert results[0]["score"] == pytest.approx(0.91)


def test_vision_search_empty_bytes_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    from features.search import vision_query as mod

    mod._OCR_CACHE.clear()
    ocr, results = mod.vision_search(b"", searcher=_FakeSearcher())
    assert ocr == ""
    assert results == []


def test_vision_search_caches_repeated_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    import features.search.vision_query as mod

    mod._OCR_CACHE.clear()

    call_count = {"n": 0}

    def fake_ocr(image_bytes: bytes) -> str:
        call_count["n"] += 1
        return "cached-text"

    monkeypatch.setattr(mod, "_gemini_ocr", fake_ocr)

    payload = b"identical-bytes"
    mod.vision_search(payload, searcher=_FakeSearcher())
    mod.vision_search(payload, searcher=_FakeSearcher())
    mod.vision_search(payload, searcher=_FakeSearcher())
    # 동일 이미지는 OCR 1회만 호출.
    assert call_count["n"] == 1


def test_capabilities_endpoint_reflects_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """`/search/capabilities` 는 GEMINI_API_KEY 환경 변수 상태를 반영한다."""
    from fastapi.testclient import TestClient

    # capabilities endpoint 만 검증 — 전체 앱 부트는 무거우므로 직접 함수 호출로 단순화.
    from backend.routers.search import get_search_capabilities

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    caps = get_search_capabilities()
    assert caps.vision_enabled is False

    monkeypatch.setenv("GEMINI_API_KEY", "present")
    caps2 = get_search_capabilities()
    assert caps2.vision_enabled is True
    assert caps2.intent_classifier is True


def test_intent_endpoint_request_response_shape() -> None:
    """`/search/intent` 핸들러 직접 호출 — pydantic 모델 변환 검증."""
    from backend.routers.search import classify_palette_intent, IntentRequest

    resp = classify_palette_intent(IntentRequest(query="REACH 규제 현황"))
    assert resp.suggested_category == "regulation"
    assert resp.confidence >= 0.7
    assert isinstance(resp.alternatives, list)
