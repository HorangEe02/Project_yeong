"""v3.3 Phase H — 통합 LLM 상태 엔드포인트 테스트.

GET /api/health/llm-status 가 시연 환경(Cloudflare Tunnel) 활성 시
모든 기능(A~F) 에 OLLAMA_BASE_URL 이 적용되었는지 한 번에 검증한다.

검증 항목:
1. 응답 스키마 — status / summary / ollama / gemini / features / circuit_breakers / feature_flags
2. 6 기능 매핑 (A~F) 모두 반환
3. Tunnel 감지 (`is_tunnel`, `tunnel_active`)
4. Gemini API 키 / FEATURE_B_BLOCK_GEMINI 토글 반영
5. LLMRouter circuit breaker 스냅샷 노출
6. 피처 플래그 8종 노출 (Phase 0)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.routers.health import router

    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


# ════════════════════════════════════════════════════════════
# 1. 응답 스키마 + 200
# ════════════════════════════════════════════════════════════


def test_llm_status_returns_200(client):
    r = client.get("/api/health/llm-status")
    assert r.status_code == 200


def test_llm_status_response_schema(client):
    r = client.get("/api/health/llm-status")
    body = r.json()
    expected_top_keys = {
        "status", "summary", "ollama", "gemini", "features",
        "circuit_breakers", "feature_flags", "tunnel_active",
    }
    assert expected_top_keys.issubset(set(body.keys()))


def test_llm_status_overall_status_enum(client):
    r = client.get("/api/health/llm-status")
    assert r.json()["status"] in ("ok", "degraded", "error")


# ════════════════════════════════════════════════════════════
# 2. 6 기능 매핑
# ════════════════════════════════════════════════════════════


def test_llm_status_returns_6_features(client):
    r = client.get("/api/health/llm-status")
    features = r.json()["features"]
    assert len(features) == 6


def test_llm_status_feature_ids(client):
    r = client.get("/api/health/llm-status")
    ids = {f["id"] for f in r.json()["features"]}
    assert ids == {"A", "B", "C", "D", "E", "F"}


def test_llm_status_feature_required_fields(client):
    r = client.get("/api/health/llm-status")
    for f in r.json()["features"]:
        for key in ("id", "name", "endpoint", "uses", "via", "notes", "ok"):
            assert key in f, f"Feature {f.get('id')} 누락 필드: {key}"


def test_llm_status_feature_C_uses_ollama_and_gemini(client):
    """Feature C 는 LLMRouter 폴백 — Ollama + Gemini 둘 다 사용."""
    r = client.get("/api/health/llm-status")
    feat_c = next(f for f in r.json()["features"] if f["id"] == "C")
    assert "ollama" in feat_c["uses"]
    assert "gemini" in feat_c["uses"]


def test_llm_status_feature_F_no_llm(client):
    """Feature F 는 ML 검색만 — LLM 무관."""
    r = client.get("/api/health/llm-status")
    feat_f = next(f for f in r.json()["features"] if f["id"] == "F")
    assert feat_f["uses"] == []


def test_llm_status_feature_E_uses_only_ollama(client):
    """Feature E 는 BGE-M3 임베딩만 — Ollama 단독."""
    r = client.get("/api/health/llm-status")
    feat_e = next(f for f in r.json()["features"] if f["id"] == "E")
    assert feat_e["uses"] == ["ollama"]


# ════════════════════════════════════════════════════════════
# 3. Tunnel 감지
# ════════════════════════════════════════════════════════════


def test_llm_status_local_ollama_not_tunnel(client):
    """기본 localhost:11434 → tunnel_active=False."""
    r = client.get("/api/health/llm-status")
    body = r.json()
    if body["ollama"]["base_url"].startswith("http://localhost"):
        assert body["tunnel_active"] is False
        assert body["ollama"]["is_tunnel"] is False


def test_llm_status_detects_trycloudflare_url(monkeypatch):
    """OLLAMA_BASE_URL 이 trycloudflare.com 이면 is_tunnel=True."""
    from backend.routers import health as health_mod

    monkeypatch.setattr(
        health_mod,
        "OLLAMA_BASE_URL",
        "https://electrical-beginners-roman-science.trycloudflare.com",
    )
    result = health_mod._check_ollama()
    assert result.is_tunnel is True
    assert "trycloudflare" in result.base_url


def test_llm_status_empty_ollama_url():
    """OLLAMA_BASE_URL='' (Gemini 단독 모드) → ok=False + 안내."""
    from backend.routers import health as health_mod

    with patch.object(health_mod, "OLLAMA_BASE_URL", ""):
        result = health_mod._check_ollama()
        assert result.ok is False
        assert "Gemini 단독" in result.error


# ════════════════════════════════════════════════════════════
# 4. Gemini 키 + FEATURE_B_BLOCK_GEMINI
# ════════════════════════════════════════════════════════════


def test_gemini_key_present(client):
    """GEMINI_API_KEY 환경변수 → api_key_present=true."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
        r = client.get("/api/health/llm-status")
        assert r.json()["gemini"]["api_key_present"] is True


def test_gemini_key_absent(client):
    """GEMINI_API_KEY 미설정 → false."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("GEMINI_API_KEY", None)
        r = client.get("/api/health/llm-status")
        assert r.json()["gemini"]["api_key_present"] is False


def test_feature_b_block_default_true(client):
    """FEATURE_B_BLOCK_GEMINI 기본값 true (보수적)."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("FEATURE_B_BLOCK_GEMINI", None)
        r = client.get("/api/health/llm-status")
        assert r.json()["gemini"]["feature_b_blocked"] is True


def test_feature_b_block_can_be_false(client):
    """FEATURE_B_BLOCK_GEMINI=false (시연 환경) → 반영."""
    with patch.dict(os.environ, {"FEATURE_B_BLOCK_GEMINI": "false"}):
        r = client.get("/api/health/llm-status")
        assert r.json()["gemini"]["feature_b_blocked"] is False


# ════════════════════════════════════════════════════════════
# 5. Circuit Breaker
# ════════════════════════════════════════════════════════════


def test_circuit_breakers_exposed(client):
    r = client.get("/api/health/llm-status")
    breakers = r.json()["circuit_breakers"]
    # LLMRouter 가 정상 import 되면 ollama/gemini 2 breaker
    providers = {b["provider"] for b in breakers}
    # 최소 ollama 는 등록되어야 함
    assert "ollama" in providers


def test_circuit_breaker_state_enum(client):
    r = client.get("/api/health/llm-status")
    for b in r.json()["circuit_breakers"]:
        assert b["state"] in ("closed", "open", "half_open")


# ════════════════════════════════════════════════════════════
# 6. 피처 플래그 노출
# ════════════════════════════════════════════════════════════


def test_feature_flags_8_keys(client):
    r = client.get("/api/health/llm-status")
    flags = r.json()["feature_flags"]
    expected = {
        "multi_llm", "compare_mode", "dept_lock", "division_boundary",
        "work_fullscreen", "quick_questions_v2", "inline_actions", "cad_upload",
    }
    assert set(flags.keys()) == expected


def test_feature_flags_reflect_env(client):
    """env 토글이 응답에 반영."""
    with patch.dict(os.environ, {"FEATURE_C_INLINE_ACTIONS": "true"}):
        r = client.get("/api/health/llm-status")
        assert r.json()["feature_flags"]["inline_actions"] is True


# ════════════════════════════════════════════════════════════
# 7. summary 텍스트
# ════════════════════════════════════════════════════════════


def test_summary_contains_models_count(client):
    r = client.get("/api/health/llm-status")
    body = r.json()
    if body["ollama"]["ok"]:
        # Ollama 가동 시 "모델 N개" 표기
        assert "모델" in body["summary"] or "Ollama" in body["summary"]


def test_summary_contains_feature_counter(client):
    """summary 에 '기능 A~F 매핑: N/6' 형태 포함."""
    r = client.get("/api/health/llm-status")
    body = r.json()
    assert "/6" in body["summary"] or "6/6" in body["summary"]


# ════════════════════════════════════════════════════════════
# 8. 통합 — Tunnel 시뮬레이션 시나리오
# ════════════════════════════════════════════════════════════


def test_tunnel_simulation_status_all_features_ok(monkeypatch, client):
    """Tunnel + Gemini 키 모두 있으면 모든 기능 ok."""
    from backend.routers import health as health_mod

    fake_url = "https://electrical-beginners-roman-science.trycloudflare.com"
    monkeypatch.setattr(health_mod, "OLLAMA_BASE_URL", fake_url)

    # Ollama 응답을 mock
    class FakeResp:
        status_code = 200
        def json(self):
            return {"models": [{"name": "qwen3.5:9b"}, {"name": "exaone3.5:latest"}]}

    monkeypatch.setattr(health_mod.requests, "get", lambda *a, **kw: FakeResp())

    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
        r = client.get("/api/health/llm-status")
        body = r.json()

    assert body["ollama"]["is_tunnel"] is True
    assert body["tunnel_active"] is True
    assert body["ollama"]["ok"] is True
    assert body["gemini"]["api_key_present"] is True
    # 모든 기능 ok
    assert all(f["ok"] for f in body["features"])
    assert body["status"] == "ok"
