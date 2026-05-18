"""FastAPI 앱 통합 테스트 — ``TestClient`` + dependency overrides.

DB 의존성을 직접 mock 하기 어려운 ``register`` / ``login`` 은 별도 integration 단계
(testcontainers 또는 docker-compose)로 검증한다. 본 파일은 ``/health`` 와 라우터
스키마 노출만 smoke 테스트한다.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from src.main import create_app


def test_health_returns_ok() -> None:
    app = create_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] == "development"


def test_request_id_header_attached() -> None:
    app = create_app()
    client = TestClient(app)
    response = client.get("/health")
    assert "x-request-id" in {k.lower() for k in response.headers}


def test_request_id_preserved_when_provided() -> None:
    app = create_app()
    client = TestClient(app)
    response = client.get("/health", headers={"X-Request-Id": "client-abc"})
    assert response.headers["X-Request-Id"] == "client-abc"


def test_openapi_lists_all_v1_routes() -> None:
    app = create_app()
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    paths = set(spec["paths"].keys())
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/auth/register" in paths
    assert "/api/v1/auth/refresh" in paths
    assert "/api/v1/supplements/register" in paths


def test_register_supplement_requires_auth() -> None:
    """Authorization 헤더 없으면 401 — JWT 검증이 의존성으로 묶여 있는지 확인."""
    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/v1/supplements/register",
        files={"image": ("x.jpg", b"x", "image/jpeg")},
    )
    assert response.status_code == 401
