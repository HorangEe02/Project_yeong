"""OIDC discovery helper tests."""

from __future__ import annotations

import json
from io import StringIO

import httpx
import pytest
from src.config import Settings
from src.security.oidc import (
    OIDCMetadata,
    OIDCMetadataError,
    fetch_oidc_metadata,
    resolve_oidc_discovery_url,
    validate_oidc_metadata,
)

from scripts import check_oidc_discovery


def _settings() -> Settings:
    """Return settings configured for OIDC metadata validation.

    Returns:
        Settings with issuer and JWKS URL.
    """
    return Settings(
        auth_mode="jwt",
        jwt_issuer="https://auth.example.com/",
        jwt_audience="lemon-api",
        jwt_jwks_url="https://auth.example.com/.well-known/jwks.json",
    )


def test_resolve_oidc_discovery_url_from_issuer() -> None:
    """Verify default discovery URL uses the configured issuer boundary."""
    assert (
        resolve_oidc_discovery_url(_settings())
        == "https://auth.example.com/.well-known/openid-configuration"
    )


def test_validate_oidc_metadata_accepts_matching_issuer_and_jwks() -> None:
    """Verify discovery metadata must match configured issuer and JWKS URL."""
    metadata = validate_oidc_metadata(
        _settings(),
        {
            "issuer": "https://auth.example.com/",
            "jwks_uri": "https://auth.example.com/.well-known/jwks.json",
        },
    )

    assert str(metadata.issuer) == "https://auth.example.com/"
    assert str(metadata.jwks_uri) == "https://auth.example.com/.well-known/jwks.json"


def test_validate_oidc_metadata_preserves_issuer_string_for_exact_match() -> None:
    """Verify issuer comparison does not add a trailing slash during validation."""
    settings = Settings(
        auth_mode="jwt",
        jwt_issuer="https://auth.example.com/oauth2/default",
        jwt_audience="lemon-api",
        jwt_jwks_url="https://auth.example.com/oauth2/default/v1/keys",
    )

    metadata = validate_oidc_metadata(
        settings,
        {
            "issuer": "https://auth.example.com/oauth2/default",
            "jwks_uri": "https://auth.example.com/oauth2/default/v1/keys",
        },
    )

    assert metadata.issuer == "https://auth.example.com/oauth2/default"


def test_validate_oidc_metadata_rejects_untrusted_jwks_uri() -> None:
    """Verify discovery metadata cannot redirect trust to an unexpected JWKS URL."""
    with pytest.raises(OIDCMetadataError, match="jwks_uri"):
        validate_oidc_metadata(
            _settings(),
            {
                "issuer": "https://auth.example.com/",
                "jwks_uri": "https://attacker.example.com/jwks.json",
            },
        )


def test_validate_oidc_metadata_rejects_http_urls_in_production() -> None:
    """Verify production preflight enforces HTTPS issuer and JWKS metadata."""
    settings = _settings().model_copy(
        update={
            "environment": "production",
            "jwt_issuer": "http://auth.example.com/",
            "jwt_jwks_url": "http://auth.example.com/.well-known/jwks.json",
        }
    )

    with pytest.raises(OIDCMetadataError, match="https"):
        validate_oidc_metadata(
            settings,
            {
                "issuer": "http://auth.example.com/",
                "jwks_uri": "http://auth.example.com/.well-known/jwks.json",
            },
        )


@pytest.mark.asyncio
async def test_fetch_oidc_metadata_accepts_valid_discovery_document() -> None:
    """Verify the discovery fetch path validates issuer and JWKS metadata."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://auth.example.com/.well-known/openid-configuration"
        return httpx.Response(
            status_code=200,
            json={
                "issuer": "https://auth.example.com/",
                "jwks_uri": "https://auth.example.com/.well-known/jwks.json",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        metadata = await fetch_oidc_metadata(_settings(), client)

    assert metadata.issuer == "https://auth.example.com/"
    assert metadata.jwks_uri == "https://auth.example.com/.well-known/jwks.json"


@pytest.mark.asyncio
async def test_fetch_oidc_metadata_rejects_http_errors() -> None:
    """Verify discovery preflight fails closed on provider HTTP errors."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OIDCMetadataError, match="could not be fetched"):
            await fetch_oidc_metadata(_settings(), client)


@pytest.mark.asyncio
async def test_fetch_oidc_metadata_rejects_timeout() -> None:
    """Verify discovery preflight fails closed on provider timeouts."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("discovery timed out", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OIDCMetadataError, match="could not be fetched"):
            await fetch_oidc_metadata(_settings(), client)


@pytest.mark.asyncio
async def test_fetch_oidc_metadata_rejects_non_object_json() -> None:
    """Verify discovery metadata must be a JSON object."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, json=["not", "an", "object"])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OIDCMetadataError, match="JSON object"):
            await fetch_oidc_metadata(_settings(), client)


@pytest.mark.asyncio
async def test_oidc_preflight_script_outputs_safe_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the operational preflight emits only safe metadata fields on success."""

    async def fake_fetch_oidc_metadata(_settings_arg: Settings) -> OIDCMetadata:
        return OIDCMetadata(
            issuer="https://auth.example.com/",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
        )

    monkeypatch.setattr(check_oidc_discovery, "fetch_oidc_metadata", fake_fetch_oidc_metadata)
    stdout = StringIO()
    stderr = StringIO()

    exit_code = await check_oidc_discovery.run_preflight(
        _settings(),
        stdout=stdout,
        stderr=stderr,
    )

    payload = json.loads(stdout.getvalue())
    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert payload == {
        "discovery_url": "https://auth.example.com/.well-known/openid-configuration",
        "issuer": "https://auth.example.com/",
        "jwks_uri": "https://auth.example.com/.well-known/jwks.json",
        "status": "ok",
    }


@pytest.mark.asyncio
async def test_oidc_preflight_script_outputs_safe_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the operational preflight reports failures without secret material."""

    async def fake_fetch_oidc_metadata(_settings_arg: Settings) -> OIDCMetadata:
        raise OIDCMetadataError("OIDC metadata could not be fetched.")

    monkeypatch.setattr(check_oidc_discovery, "fetch_oidc_metadata", fake_fetch_oidc_metadata)
    stdout = StringIO()
    stderr = StringIO()

    exit_code = await check_oidc_discovery.run_preflight(
        _settings(),
        stdout=stdout,
        stderr=stderr,
    )

    payload = json.loads(stderr.getvalue())
    assert exit_code == 1
    assert stdout.getvalue() == ""
    assert payload == {
        "discovery_url": "https://auth.example.com/.well-known/openid-configuration",
        "error": "OIDC metadata could not be fetched.",
        "status": "failed",
    }
