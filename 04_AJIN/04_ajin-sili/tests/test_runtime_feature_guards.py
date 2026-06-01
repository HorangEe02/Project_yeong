"""Runtime guard regressions for deployed Cloud Run feature gates."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from types import SimpleNamespace

from backend.main import OllamaHealthMiddleware
from backend.routers import search as search_router


def test_search_documents_returns_503_when_searcher_disabled() -> None:
    """Document search reports a disabled feature instead of raising 500."""

    app = FastAPI()
    app.include_router(search_router.router, prefix="/api")
    app.dependency_overrides[search_router.get_current_user] = lambda: SimpleNamespace(
        user_id=1,
        employee_id="E001",
        name="tester",
        department="품질보증팀",
        division="품질본부",
        position="사원",
        role="EMPLOYEE",
        role_level=1,
    )
    app.dependency_overrides[search_router.get_searcher] = lambda: None

    response = TestClient(app).post(
        "/api/search/documents",
        json={"query": "품질", "k": 3},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "feature_disabled"


def test_ollama_guard_excludes_non_llm_metadata_routes() -> None:
    """Cheap metadata routes must not be blocked by Mac Ollama availability."""

    assert OllamaHealthMiddleware._requires_ollama("/api/draft/doc-types") is False
    assert OllamaHealthMiddleware._requires_ollama("/api/draft/diagnose") is False
    assert OllamaHealthMiddleware._requires_ollama("/api/onboarding/health") is False
    assert OllamaHealthMiddleware._requires_ollama("/api/onboarding/quick-questions") is False


def test_ollama_guard_still_blocks_generation_routes() -> None:
    """LLM generation routes remain guarded when Mac Ollama is unavailable."""

    assert OllamaHealthMiddleware._requires_ollama("/api/draft/generate") is True
    assert OllamaHealthMiddleware._requires_ollama("/api/draft/stream-v2") is True
    assert OllamaHealthMiddleware._requires_ollama("/api/onboarding/chat") is True
    assert OllamaHealthMiddleware._requires_ollama("/api/onboarding/vision/po") is True
