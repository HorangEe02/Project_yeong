"""Feature C analyzer feature-flag gating tests."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.dependencies import get_current_user
from backend.routers import onboarding as onboarding_router


def _user() -> SimpleNamespace:
    """Build a minimal authenticated user for route dependency overrides.

    Returns:
        SimpleNamespace: Authenticated L1 user context.
    """

    return SimpleNamespace(
        user_id=1,
        employee_id="E001",
        name="tester",
        username="tester",
        department="품질보증팀",
        division="품질본부",
        position="사원",
        role="EMPLOYEE",
        role_level=1,
    )


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(onboarding_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: _user()
    return TestClient(app, raise_server_exceptions=False)


def test_analyzer_flag_off_returns_403(monkeypatch) -> None:
    """Authenticated users still receive 403 when analyzers are sealed."""

    monkeypatch.delenv("FEATURE_C_ANALYZERS_ENABLED", raising=False)
    monkeypatch.setattr("backend.auth_middleware.log_api_access", lambda **_kwargs: None)

    response = _client().post(
        "/api/onboarding/vision/business-card",
        files={"file": ("card.png", b"image", "image/png")},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "analyzer_disabled"


def test_analyzer_flag_on_validates_file_and_returns_source_metadata(monkeypatch) -> None:
    """Enabled analyzers validate upload files before returning trust metadata."""

    monkeypatch.setenv("FEATURE_C_ANALYZERS_ENABLED", "true")
    monkeypatch.setattr("backend.auth_middleware.log_api_access", lambda **_kwargs: None)
    monkeypatch.setattr(
        "core.vision_extractor.invoke_vision_json",
        lambda *_args, **_kwargs: {"name": "홍길동"},
    )

    response = _client().post(
        "/api/onboarding/vision/business-card",
        files={"file": ("card.png", b"image", "image/png")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["citation_status"] == "model_only"
    assert body["sources"][0]["source_type"] == "uploaded_file"


def test_analyzer_flag_on_rejects_unsupported_extension(monkeypatch) -> None:
    """Enabled analyzers reject unsupported file extensions before model calls."""

    monkeypatch.setenv("FEATURE_C_ANALYZERS_ENABLED", "true")
    monkeypatch.setattr("backend.auth_middleware.log_api_access", lambda **_kwargs: None)

    response = _client().post(
        "/api/onboarding/vision/business-card",
        files={"file": ("payload.exe", b"binary", "application/octet-stream")},
    )

    assert response.status_code == 415
    assert response.json()["detail"] == "analyzer_file_type_unsupported"
