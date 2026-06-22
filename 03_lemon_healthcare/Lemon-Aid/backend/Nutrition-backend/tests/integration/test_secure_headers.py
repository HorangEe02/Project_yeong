"""Integration tests for the SecureHeadersMiddleware baseline headers."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from src.config import Settings
from src.main import create_app
from src.middleware.secure_headers import (
    BASELINE_SECURITY_HEADERS,
    PRODUCTION_HSTS_HEADER,
)


def _build_app(settings: Settings) -> TestClient:
    """Return a test client running the app under the given settings."""
    return TestClient(create_app(settings=settings))


def _development_settings() -> Settings:
    """Return development settings with the basic guards relaxed."""
    return Settings(_env_file=None, environment="development")


def _production_settings() -> Settings:
    """Return production settings that pass the production validator.

    The validator requires explicit hosts/origins, JWT plumbing, and
    KDRIs/path overrides. We satisfy the minimal set needed to construct
    the Settings object so the SecureHeaders middleware can be exercised.
    """
    return Settings(
        _env_file=None,
        environment="production",
        database_url="postgresql+asyncpg://lemon_prod:secret@db.example.com:5432/lemon",
        allowed_origins=["https://lemonaid.example.com"],
        allowed_hosts=["api.lemonaid.example.com"],
        auth_mode="jwt",
        jwt_issuer="https://auth.example.com/",
        jwt_audience="lemon-api",
        jwt_jwks_url="https://auth.example.com/.well-known/jwks.json",
        jwt_expected_token_type="at+jwt",
        privacy_hash_secret=SecretStr("prod-privacy-hash-secret-at-least-32"),
        kdris_data_version="2025",
        kdris_data_path="data/nutrition_reference/kdris/kdris_2025.csv",
        allow_sample_kdris=False,
        enable_local_ocr=False,
        ocr_primary_provider="none",
    )


@pytest.mark.parametrize("path", ["/health", "/nonexistent-route"])
def test_secure_headers_apply_to_every_response(path: str) -> None:
    """Verify baseline headers are present on success and 404 responses alike."""
    client = _build_app(_development_settings())

    response = client.get(path)

    for header, expected in BASELINE_SECURITY_HEADERS.items():
        assert response.headers.get(header) == expected, header


def test_hsts_header_emitted_only_in_production() -> None:
    """Verify HSTS appears only when ``environment`` is ``production``."""
    hsts_name, hsts_value = PRODUCTION_HSTS_HEADER

    dev_client = _build_app(_development_settings())
    dev_response = dev_client.get("/health")
    assert dev_response.headers.get(hsts_name) is None

    prod_client = _build_app(_production_settings())
    prod_response = prod_client.get("/health")
    assert prod_response.headers.get(hsts_name) == hsts_value
