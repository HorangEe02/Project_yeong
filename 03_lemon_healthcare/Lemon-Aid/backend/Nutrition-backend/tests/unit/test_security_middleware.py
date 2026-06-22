"""HTTP security middleware tests."""

from __future__ import annotations

from fastapi import status
from fastapi.testclient import TestClient
from src.config import Settings
from src.main import create_app


def test_trusted_host_allows_configured_host() -> None:
    """Verify configured hosts can access the app."""
    app = create_app(settings=Settings(allowed_hosts=["testserver"]))
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == status.HTTP_200_OK


def test_trusted_host_default_allows_android_emulator_host() -> None:
    """Verify local defaults allow Android emulator host-loopback requests."""
    app = create_app(settings=Settings(_env_file=None))
    client = TestClient(app)

    response = client.get("/health", headers={"host": "10.0.2.2:8000"})

    assert response.status_code == status.HTTP_200_OK


def test_trusted_host_blocks_unconfigured_host() -> None:
    """Verify unknown Host headers are rejected."""
    app = create_app(settings=Settings(allowed_hosts=["api.example.com"]))
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_cors_preflight_allows_configured_origin() -> None:
    """Verify CORS preflight succeeds for an explicitly allowed origin."""
    app = create_app(
        settings=Settings(
            allowed_origins=["http://localhost:3000"],
            allowed_hosts=["testserver"],
        )
    )
    client = TestClient(app)

    response = client.options(
        "/api/v1/nutrition/kdris",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_preflight_rejects_unconfigured_origin() -> None:
    """Verify CORS preflight rejects an unconfigured origin."""
    app = create_app(
        settings=Settings(
            allowed_origins=["http://localhost:3000"],
            allowed_hosts=["testserver"],
        )
    )
    client = TestClient(app)

    response = client.options(
        "/api/v1/nutrition/kdris",
        headers={
            "Origin": "https://attacker.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
