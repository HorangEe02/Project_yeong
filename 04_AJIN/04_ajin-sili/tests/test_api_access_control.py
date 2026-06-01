"""API access-control regressions for public, authenticated, and admin routes."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.dependencies import get_current_user
from backend.routers import draft as draft_router
from backend.routers import employee as employee_router
from backend.routers import health as health_router
from backend.routers import models as models_router
from backend.routers import onboarding as onboarding_router
from backend.routers import search as search_router


def _user(level: int = 1, role: str = "EMPLOYEE") -> SimpleNamespace:
    """Build a minimal user context for FastAPI dependency overrides.

    Args:
        level: RBAC numeric level to expose as ``role_level``.
        role: RBAC role name to expose as ``role``.

    Returns:
        A namespace with the UserContext fields used by route dependencies.
    """
    return SimpleNamespace(
        user_id=1,
        employee_id="E001",
        name="tester",
        username="tester",
        department="품질보증팀",
        division="품질본부",
        position="사원",
        role=role,
        role_level=level,
    )


def _client_for(routers: Iterable[APIRouter], user: SimpleNamespace | None = None) -> TestClient:
    """Create an isolated test app with optional authenticated user override.

    Args:
        routers: FastAPI routers to include below ``/api``.
        user: Optional user object returned by ``get_current_user``.

    Returns:
        A TestClient with server exceptions converted to HTTP 500 responses.
    """
    app = FastAPI()
    for router in routers:
        app.include_router(router, prefix="/api")
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("get", "/api/search/capabilities", {}),
        ("post", "/api/search/documents", {"json": {"query": "품질", "k": 3}}),
        ("get", "/api/search/drawings", {}),
        ("get", "/api/onboarding/health", {}),
        ("get", "/api/onboarding/sop/list", {}),
        ("post", "/api/onboarding/upload", {"files": {"file": ("x.txt", b"x", "text/plain")}}),
        ("post", "/api/onboarding/vision/business-card", {"files": {"file": ("x.png", b"x", "image/png")}}),
        ("post", "/api/onboarding/document/contract", {"files": {"file": ("x.pdf", b"x", "application/pdf")}}),
        ("get", "/api/models/catalog", {}),
    ],
)
def test_selected_routes_require_login(method: str, path: str, kwargs: dict) -> None:
    """Search, onboarding, and model UI routes reject anonymous requests."""
    client = _client_for([search_router.router, onboarding_router.router, models_router.router])

    response = getattr(client, method)(path, **kwargs)

    assert response.status_code == 401


def test_health_check_remains_public() -> None:
    """Only ``GET /api/health`` stays public."""
    client = _client_for([health_router.router])

    response = client.get("/api/health")

    assert response.status_code == 200


def test_authenticated_read_routes_stay_available() -> None:
    """Authenticated users can still reach read-only feature metadata routes."""
    client = _client_for(
        [search_router.router, onboarding_router.router, models_router.router],
        user=_user(),
    )

    assert client.get("/api/search/capabilities").status_code == 200
    assert client.get("/api/onboarding/health").status_code == 200
    assert client.get("/api/onboarding/sop/list").status_code == 200
    assert client.get("/api/models/catalog").status_code == 200


def test_authenticated_search_documents_returns_feature_error_when_disabled() -> None:
    """Auth succeeds before the disabled searcher path returns the existing 503."""
    client = _client_for([search_router.router], user=_user())
    client.app.dependency_overrides[search_router.get_searcher] = lambda: None

    response = client.post("/api/search/documents", json={"query": "품질", "k": 3})

    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "feature_disabled"


def test_employee_extras_uses_role_level_before_role_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """Employee extras authorization uses role_level from UserContext/JWT first."""
    monkeypatch.setattr(employee_router, "log_api_access", lambda **_kwargs: None)
    user = _user(level=5, role="EMPLOYEE")
    user.employee_id = "E001"
    user.department = "품질보증팀"
    client = _client_for([employee_router.router], user=user)

    response = client.get("/api/employee/HR-001/extras")

    assert response.status_code == 200
    assert response.json()["permission"] == "FULL"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/health/llm-status"),
        ("get", "/api/draft/diagnose"),
        ("post", "/api/models/invalidate-cache"),
    ],
)
def test_admin_routes_reject_normal_users(method: str, path: str) -> None:
    """Admin-only diagnostics and cache mutation require SYS_ADMIN L5."""
    client = _client_for(
        [health_router.router, draft_router.router, models_router.router],
        user=_user(level=1, role="EMPLOYEE"),
    )

    response = getattr(client, method)(path)

    assert response.status_code == 403


def test_admin_routes_allow_l5_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """SYS_ADMIN L5 can reach all admin-only routes."""

    class _FakeOllamaResponse:
        status_code = 200

        def json(self) -> dict:
            return {"models": [{"name": "qwen3.5:4b"}]}

    monkeypatch.setattr(
        health_router,
        "_check_ollama",
        lambda: health_router.OllamaStatus(
            ok=True,
            base_url="http://localhost:11434",
            is_tunnel=False,
            model_count=1,
            models=["qwen3.5:4b"],
        ),
    )
    monkeypatch.setattr(
        health_router,
        "_check_gemini",
        lambda: health_router.GeminiStatus(
            api_key_present=False,
            model="gemini-2.5-pro",
            feature_b_blocked=True,
        ),
    )
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: _FakeOllamaResponse())

    client = _client_for(
        [health_router.router, draft_router.router, models_router.router],
        user=_user(level=5, role="SYS_ADMIN"),
    )
    client.app.state.draft_pipeline = object()

    assert client.get("/api/health/llm-status").status_code == 200
    assert client.get("/api/draft/diagnose").status_code == 200
    assert client.post("/api/models/invalidate-cache").status_code == 200


def test_admin_diagnostics_redact_runtime_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Admin diagnostics expose posture labels, not secret values or raw endpoints."""

    class _FakeOllamaResponse:
        status_code = 200

        def json(self) -> dict:
            return {"models": [{"name": "qwen3.5:4b"}]}

    raw_ollama_url = "https://secret-ollama.internal.example:11434/private"
    raw_gemini_key = "gemini-secret-value-not-for-response"
    monkeypatch.setattr(health_router, "OLLAMA_BASE_URL", raw_ollama_url)
    monkeypatch.setattr("config.OLLAMA_BASE_URL", raw_ollama_url)
    monkeypatch.setenv("GEMINI_API_KEY", raw_gemini_key)
    monkeypatch.setattr(health_router.requests, "get", lambda *args, **kwargs: _FakeOllamaResponse())

    client = _client_for(
        [health_router.router, draft_router.router],
        user=_user(level=5, role="SYS_ADMIN"),
    )
    client.app.state.draft_pipeline = object()

    llm_status = client.get("/api/health/llm-status")
    diagnose = client.get("/api/draft/diagnose")
    rendered = json.dumps(
        {"llm_status": llm_status.json(), "diagnose": diagnose.json()},
        ensure_ascii=False,
    )

    assert llm_status.status_code == 200
    assert diagnose.status_code == 200
    assert raw_ollama_url not in rendered
    assert "secret-ollama.internal.example" not in rendered
    assert raw_gemini_key not in rendered
    assert "/Users/" not in rendered
    assert "configured:" in rendered


def test_extract_user_from_token_preserves_role_level(monkeypatch: pytest.MonkeyPatch) -> None:
    """JWT payload ``role_level`` is preserved in the restored UserContext."""

    class _EmptyConn:
        def execute(self, *_args, **_kwargs):
            return self

        def fetchone(self):
            return None

        def close(self) -> None:
            return None

    from backend.auth_middleware import extract_user_from_token
    from core.auth import database, jwt_handler

    monkeypatch.setattr(
        jwt_handler,
        "verify_token",
        lambda _token: {
            "type": "access",
            "sub": "E001",
            "username": "tester",
            "role": "SYS_ADMIN",
            "role_level": 5,
        },
    )
    monkeypatch.setattr(database, "get_auth_db", lambda: _EmptyConn())

    user = extract_user_from_token("token")

    assert user is not None
    assert user.role == "SYS_ADMIN"
    assert user.role_level == 5


def test_extract_user_from_token_falls_back_to_role_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """JWTs without ``role_level`` keep admin authorization through role mapping."""

    class _EmptyConn:
        def execute(self, *_args, **_kwargs):
            return self

        def fetchone(self):
            return None

        def close(self) -> None:
            return None

    from backend.auth_middleware import extract_user_from_token
    from core.auth import database, jwt_handler

    monkeypatch.setattr(
        jwt_handler,
        "verify_token",
        lambda _token: {
            "type": "access",
            "sub": "E001",
            "username": "tester",
            "role": "SYS_ADMIN",
        },
    )
    monkeypatch.setattr(database, "get_auth_db", lambda: _EmptyConn())

    user = extract_user_from_token("token")

    assert user is not None
    assert user.role_level == 5
