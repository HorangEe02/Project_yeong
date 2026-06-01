"""P8 — Phase B Vertex AI Gemini 라우팅 (LLM_PROVIDER toggle).

config.LLM_PROVIDER + VERTEX_PROJECT_ID 조합으로 Ollama ↔ Vertex 분기.
Vertex 미연결 시 Ollama 자동 폴백 (Stage 1 호환). _call_llm dispatcher 가
provider 에 따라 _call_ollama / _call_vertex 정확히 호출.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# ─────────────────────────────────────────────────────────────
# 케이스 1 — Vertex tier 활성 시 resolve_llm_route 가 vertex provider 반환
# ─────────────────────────────────────────────────────────────


def test_resolve_route_returns_vertex_when_tier_and_project_set(monkeypatch):
    import config
    monkeypatch.setattr(config, "VERTEX_PROJECT_ID", "test-proj", raising=False)
    monkeypatch.setitem(config.LLM_FEATURE_ROUTES, "rag_answer",
                        ("vertex", "gemini-2.0-flash"))

    provider, base_or_proj, model = config.resolve_llm_route("rag_answer")
    assert provider == "vertex"
    assert base_or_proj == "test-proj"
    assert model == "gemini-2.0-flash"


# ─────────────────────────────────────────────────────────────
# 케이스 2 — Vertex tier 인데 VERTEX_PROJECT_ID 미설정 → Ollama 폴백
# ─────────────────────────────────────────────────────────────


def test_resolve_route_falls_back_to_ollama_when_vertex_project_unset(monkeypatch):
    import config
    monkeypatch.setattr(config, "VERTEX_PROJECT_ID", "", raising=False)
    monkeypatch.setitem(config.LLM_FEATURE_ROUTES, "rag_answer",
                        ("vertex", "gemini-2.0-flash"))

    provider, base, model = config.resolve_llm_route("rag_answer")
    assert provider == "ollama", "VERTEX_PROJECT_ID 미설정 시 ollama 폴백"
    assert model == config.LLM_MODEL


# ─────────────────────────────────────────────────────────────
# 케이스 3 — _call_llm dispatcher 가 vertex tier 시 _call_vertex 호출
# ─────────────────────────────────────────────────────────────


def test_call_llm_dispatches_to_vertex_for_vertex_tier(monkeypatch):
    import config
    monkeypatch.setattr(config, "VERTEX_PROJECT_ID", "test-proj", raising=False)
    monkeypatch.setitem(config.LLM_FEATURE_ROUTES, "rag_answer",
                        ("vertex", "gemini-2.0-flash"))

    from features.compliance import regulation_qa
    calls = {"vertex": 0, "ollama": 0}
    monkeypatch.setattr(regulation_qa, "_call_vertex",
                        lambda *a, **kw: (calls.__setitem__("vertex", calls["vertex"] + 1), "VERTEX_RESP")[1])
    monkeypatch.setattr(regulation_qa, "_call_ollama",
                        lambda *a, **kw: (calls.__setitem__("ollama", calls["ollama"] + 1), "OLLAMA_RESP")[1])

    out = regulation_qa._call_llm("p", feature="rag_answer")
    assert out == "VERTEX_RESP"
    assert calls["vertex"] == 1
    assert calls["ollama"] == 0


# ─────────────────────────────────────────────────────────────
# 케이스 4 — _call_llm dispatcher 가 ollama tier (기본) 시 _call_ollama 호출
# ─────────────────────────────────────────────────────────────


def test_call_llm_dispatches_to_ollama_for_default_tier(monkeypatch):
    """LLM_PROVIDER 미변경 (default ollama) → _call_ollama 사용."""
    from features.compliance import regulation_qa
    calls = {"vertex": 0, "ollama": 0}
    monkeypatch.setattr(regulation_qa, "_call_vertex",
                        lambda *a, **kw: (calls.__setitem__("vertex", calls["vertex"] + 1), "VERTEX_RESP")[1])
    monkeypatch.setattr(regulation_qa, "_call_ollama",
                        lambda *a, **kw: (calls.__setitem__("ollama", calls["ollama"] + 1), "OLLAMA_RESP")[1])

    out = regulation_qa._call_llm("p", feature="rag_answer")  # default routes 의 tier=fast
    assert out == "OLLAMA_RESP"
    assert calls["ollama"] == 1
    assert calls["vertex"] == 0


# ─────────────────────────────────────────────────────────────
# 케이스 5 — _call_vertex payload — format="json" 시 response_mime_type 적용
# ─────────────────────────────────────────────────────────────


def test_vertex_call_sets_response_mime_type_for_json(monkeypatch):
    import config
    monkeypatch.setattr(config, "VERTEX_PROJECT_ID", "test-proj", raising=False)
    monkeypatch.setattr(config, "VERTEX_LOCATION", "asia-northeast3", raising=False)
    monkeypatch.setitem(config.LLM_FEATURE_ROUTES, "whatif_nl_route",
                        ("vertex", "gemini-2.0-flash"))

    captured: dict = {}

    class FakeGenConfig:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class FakeClient:
        def __init__(self, *, vertexai=False, project=None, location=None):
            captured["client_init"] = dict(vertexai=vertexai, project=project, location=location)
            self.models = self

        def generate_content(self, *, model=None, contents=None, config=None):
            captured["generate"] = dict(model=model, contents=contents)
            r = MagicMock()
            r.text = '{"scenario_type":"tariff"}'
            return r

    # google-genai SDK 의 genai.Client + types.GenerateContentConfig patch
    from google import genai
    from google.genai import types as genai_types
    monkeypatch.setattr(genai, "Client", FakeClient, raising=True)
    monkeypatch.setattr(genai_types, "GenerateContentConfig", FakeGenConfig, raising=True)

    from features.compliance import regulation_qa
    out = regulation_qa._call_vertex("자연어 질문", feature="whatif_nl_route", format="json")

    assert out == '{"scenario_type":"tariff"}'
    assert captured["client_init"]["vertexai"] is True
    assert captured["client_init"]["project"] == "test-proj"
    assert captured["client_init"]["location"] == "asia-northeast3"
    assert captured["generate"]["model"] == "gemini-2.0-flash"
    assert captured.get("response_mime_type") == "application/json"
    assert captured.get("temperature") == 0.2
    assert captured.get("max_output_tokens") == 600


# ─────────────────────────────────────────────────────────────
# 케이스 6 — Vertex 호출 예외 발생 시 graceful skip (None)
# ─────────────────────────────────────────────────────────────


def test_vertex_call_graceful_skip_on_exception(monkeypatch):
    import config
    monkeypatch.setattr(config, "VERTEX_PROJECT_ID", "test-proj", raising=False)
    monkeypatch.setitem(config.LLM_FEATURE_ROUTES, "rag_answer",
                        ("vertex", "gemini-2.0-flash"))

    class BoomClient:
        def __init__(self, **kwargs):
            raise RuntimeError("simulated network error")

    from google import genai
    monkeypatch.setattr(genai, "Client", BoomClient, raising=True)

    from features.compliance import regulation_qa
    out = regulation_qa._call_vertex("test", feature="rag_answer")
    assert out is None, "Vertex 예외 시 None 반환 (룰 폴백 보장)"


# ─────────────────────────────────────────────────────────────
# 케이스 7 — _call_vertex provider != vertex 시 즉시 None
# ─────────────────────────────────────────────────────────────


def test_vertex_call_returns_none_when_provider_not_vertex():
    """기본 ollama provider 상태에서 _call_vertex 직접 호출 시 None."""
    from features.compliance import regulation_qa
    out = regulation_qa._call_vertex("test", feature="rag_answer")
    assert out is None
