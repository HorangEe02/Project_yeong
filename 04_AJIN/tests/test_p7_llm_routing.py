"""P7 — LLM 풀 모델별 라우팅 (Phase 2).

config.LLM_FEATURE_ROUTES 매핑이 _call_ollama 호출 시 정확히
base URL + 모델로 변환되는지, 미설정/미등록 폴백이 Phase 1 동작을
유지하는지, Ollama 미연결 시 graceful skip 이 보장되는지 검증.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import httpx
import pytest


# ─────────────────────────────────────────────────────────────
# 헬퍼 — config 의 라우팅 변수를 monkeypatch 로 강제 후 _call_ollama 호출
# ─────────────────────────────────────────────────────────────


def _setup_routing(monkeypatch, *, large: str, fast: str, base: str | None = None):
    """config 의 Phase 2 라우팅 변수를 강제."""
    import config
    if base is not None:
        monkeypatch.setattr(config, "OLLAMA_BASE_URL", base, raising=False)
    monkeypatch.setattr(config, "OLLAMA_BASE_URL_LARGE", large, raising=False)
    monkeypatch.setattr(config, "OLLAMA_BASE_URL_FAST",  fast,  raising=False)


def _mock_post_response(payload_response: str = "OK"):
    """httpx.post 가 반환할 mock response 객체."""
    m = MagicMock()
    m.raise_for_status = lambda: None
    m.json = lambda: {"response": payload_response}
    return m


# ─────────────────────────────────────────────────────────────
# 케이스 1 — rag_answer → FAST URL + qwen3.5:4b
# ─────────────────────────────────────────────────────────────


def test_routing_rag_answer_uses_fast_url_and_small_model(monkeypatch):
    _setup_routing(monkeypatch,
                   large="http://large-host:11434",
                   fast="http://fast-host:11434")
    from features.compliance import regulation_qa

    with patch.object(regulation_qa.httpx, "post",
                      return_value=_mock_post_response("rag-답변")) as mp:
        out = regulation_qa._call_ollama("질문", feature="rag_answer")

    assert out == "rag-답변"
    args, kwargs = mp.call_args
    url = args[0] if args else kwargs.get("url")
    assert "fast-host" in url, f"FAST URL 사용 기대, 실제 url={url}"
    assert kwargs["json"]["model"] == "qwen3.5:4b"


# ─────────────────────────────────────────────────────────────
# 케이스 2 — whatif_nl_route → LARGE URL + qwen3.5:9b + format=json
# ─────────────────────────────────────────────────────────────


def test_routing_whatif_nl_route_uses_large_url_and_format_json(monkeypatch):
    _setup_routing(monkeypatch,
                   large="http://large-host:11434",
                   fast="http://fast-host:11434")
    from features.compliance import regulation_qa

    with patch.object(regulation_qa.httpx, "post",
                      return_value=_mock_post_response('{"scenario_type":"tariff"}')) as mp:
        out = regulation_qa._call_ollama(
            "관세 25% 시나리오",
            feature="whatif_nl_route",
            format="json",
            temperature=0.1,
            num_predict=200,
        )

    assert out == '{"scenario_type":"tariff"}'
    args, kwargs = mp.call_args
    url = args[0] if args else kwargs.get("url")
    assert "large-host" in url, f"LARGE URL 사용 기대, 실제 url={url}"
    assert kwargs["json"]["model"] == "qwen3.5:9b"
    assert kwargs["json"]["format"] == "json"
    assert kwargs["json"]["options"]["temperature"] == 0.1
    assert kwargs["json"]["options"]["num_predict"] == 200


# ─────────────────────────────────────────────────────────────
# 케이스 3 — quiz_gen → FAST URL + gemma4:e2b
# ─────────────────────────────────────────────────────────────


def test_routing_quiz_gen_uses_fast_url_and_gemma(monkeypatch):
    _setup_routing(monkeypatch,
                   large="http://large-host:11434",
                   fast="http://fast-host:11434")
    from features.compliance import regulation_qa

    with patch.object(regulation_qa.httpx, "post",
                      return_value=_mock_post_response("퀴즈 JSON")) as mp:
        out = regulation_qa._call_ollama("퀴즈 프롬프트", feature="quiz_gen")

    assert out == "퀴즈 JSON"
    args, kwargs = mp.call_args
    url = args[0] if args else kwargs.get("url")
    assert "fast-host" in url
    assert kwargs["json"]["model"] == "gemma4:e2b"


# ─────────────────────────────────────────────────────────────
# 케이스 4 — feature 미지정 → 기본 OLLAMA_BASE_URL + LLM_MODEL (Phase 1 동작)
# ─────────────────────────────────────────────────────────────


def test_routing_default_falls_back_to_base_url_and_default_model(monkeypatch):
    import config
    _setup_routing(monkeypatch,
                   large="http://large-host:11434",
                   fast="http://fast-host:11434",
                   base="http://default-host:11434")
    from features.compliance import regulation_qa

    with patch.object(regulation_qa.httpx, "post",
                      return_value=_mock_post_response("기본 답변")) as mp:
        # feature 인자 없이 호출 → "default" → Phase 1 폴백
        out = regulation_qa._call_ollama("질문")

    assert out == "기본 답변"
    args, kwargs = mp.call_args
    url = args[0] if args else kwargs.get("url")
    assert "default-host" in url
    assert kwargs["json"]["model"] == config.LLM_MODEL


# ─────────────────────────────────────────────────────────────
# 케이스 5 — LARGE/FAST 미설정 (단일 endpoint) → 모든 feature 가 동일 호스트
# ─────────────────────────────────────────────────────────────


def test_routing_when_large_fast_unset_all_features_share_host(monkeypatch):
    """Phase 1 환경 (LARGE/FAST 미설정) — config.py 기본값으로 OLLAMA_BASE_URL 폴백."""
    same = "http://only-host:11434"
    _setup_routing(monkeypatch, large=same, fast=same, base=same)
    from features.compliance import regulation_qa

    seen_urls: list[str] = []
    seen_models: list[str] = []

    def _capture(url, **kwargs):
        seen_urls.append(url)
        seen_models.append(kwargs["json"]["model"])
        return _mock_post_response("ok")

    with patch.object(regulation_qa.httpx, "post", side_effect=_capture):
        regulation_qa._call_ollama("p", feature="rag_answer")
        regulation_qa._call_ollama("p", feature="quiz_gen")
        regulation_qa._call_ollama("p", feature="whatif_nl_route")
        regulation_qa._call_ollama("p", feature="short_answer_grade")

    # 모든 호출이 동일 호스트를 사용
    assert all("only-host" in u for u in seen_urls), seen_urls
    # 모델은 feature 별로 다름 (URL 만 공유)
    assert "qwen3.5:4b" in seen_models
    assert "gemma4:e2b" in seen_models
    assert "qwen3.5:9b" in seen_models


# ─────────────────────────────────────────────────────────────
# 케이스 6 — Ollama 미연결 시 graceful skip (None 반환)
# ─────────────────────────────────────────────────────────────


def test_routing_graceful_skip_on_connect_error(monkeypatch):
    _setup_routing(monkeypatch,
                   large="http://nonexistent-large:11434",
                   fast="http://nonexistent-fast:11434")
    from features.compliance import regulation_qa

    def _raise(*a, **kw):
        raise httpx.ConnectError("연결 실패")

    with patch.object(regulation_qa.httpx, "post", side_effect=_raise):
        out = regulation_qa._call_ollama("질문", feature="rag_answer")

    assert out is None, "Ollama 미연결 시 None 반환해야 (룰 폴백 보장)"


# ─────────────────────────────────────────────────────────────
# 케이스 7 — whatif_engine._llm_extract 가 _call_ollama 를 올바른 feature 로 호출
# ─────────────────────────────────────────────────────────────


def test_whatif_llm_extract_delegates_to_call_llm_with_feature(monkeypatch):
    """_llm_extract 리팩토 검증 — Phase B dispatcher (_call_llm) 위임."""
    from features.compliance import whatif_engine

    captured: dict = {}

    def _fake_call(prompt, timeout=15.0, *, feature="default",
                   format=None, temperature=0.2, num_predict=600, think=False):
        captured["feature"] = feature
        captured["format"] = format
        captured["temperature"] = temperature
        captured["num_predict"] = num_predict
        return '{"scenario_type":"tariff","params":{"rate_pct":25}}'

    monkeypatch.setattr(
        "features.compliance.regulation_qa._call_llm",
        _fake_call,
        raising=True,
    )

    out = whatif_engine._llm_extract("관세 25% 시나리오")
    assert out == {"scenario_type": "tariff", "params": {"rate_pct": 25}}
    assert captured["feature"] == "whatif_nl_route"
    assert captured["format"] == "json"
    assert captured["temperature"] == 0.1
    assert captured["num_predict"] == 200


# ─────────────────────────────────────────────────────────────
# 케이스 8 — config.resolve_llm_route 단위 검증
# ─────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────
# 케이스 9 — think kwarg payload 직렬화 (default=False, opt-in=True)
# ─────────────────────────────────────────────────────────────


def test_routing_think_default_false_and_optin_true(monkeypatch):
    """qwen3 류 thinking 모델의 chain-of-thought 차단 — payload 최상위 think 필드."""
    _setup_routing(monkeypatch,
                   large="http://h:11434", fast="http://h:11434", base="http://h:11434")
    from features.compliance import regulation_qa

    # default 호출 → think=False
    with patch.object(regulation_qa.httpx, "post",
                      return_value=_mock_post_response("answer")) as mp:
        regulation_qa._call_ollama("p", feature="rag_answer")
    args, kwargs = mp.call_args
    assert kwargs["json"]["think"] is False, "default 는 think=False 여야"

    # opt-in think=True
    with patch.object(regulation_qa.httpx, "post",
                      return_value=_mock_post_response("reasoned")) as mp:
        regulation_qa._call_ollama("p", feature="rag_answer", think=True)
    args, kwargs = mp.call_args
    assert kwargs["json"]["think"] is True, "think=True 명시 시 활성화"


def test_resolve_llm_route_feature_mapping(monkeypatch):
    """Phase B 호환: 3-tuple (provider, base_or_project, model) 반환."""
    import config
    monkeypatch.setattr(config, "OLLAMA_BASE_URL_LARGE", "http://L:11434", raising=False)
    monkeypatch.setattr(config, "OLLAMA_BASE_URL_FAST",  "http://F:11434", raising=False)
    monkeypatch.setattr(config, "OLLAMA_BASE_URL",       "http://D:11434", raising=False)

    assert config.resolve_llm_route("rag_answer")         == ("ollama", "http://F:11434", "qwen3.5:4b")
    assert config.resolve_llm_route("quiz_gen")           == ("ollama", "http://F:11434", "gemma4:e2b")
    assert config.resolve_llm_route("short_answer_grade") == ("ollama", "http://F:11434", "qwen3.5:4b")
    assert config.resolve_llm_route("whatif_nl_route")    == ("ollama", "http://L:11434", "qwen3.5:9b")
    assert config.resolve_llm_route("default")            == ("ollama", "http://D:11434", config.LLM_MODEL)
    assert config.resolve_llm_route("unknown_feature_x")  == ("ollama", "http://D:11434", config.LLM_MODEL)
