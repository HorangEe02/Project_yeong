"""OIDC discovery metadata helpers for operational preflight checks."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from src.config import Settings


class OIDCMetadata(BaseModel):
    """Validated OpenID Provider metadata needed by this resource server.

    Attributes:
        issuer: OpenID Provider issuer identifier.
        jwks_uri: JWKS endpoint used to validate JWT signatures.
    """

    model_config = ConfigDict(extra="allow")

    issuer: str
    jwks_uri: str


class OIDCMetadataError(ValueError):
    """Raised when OIDC discovery metadata is missing or inconsistent."""


def resolve_oidc_discovery_url(settings: Settings) -> str:
    """Resolve the OIDC discovery URL for the configured issuer.

    Args:
        settings: Application settings.

    Returns:
        Explicit discovery URL or a conventional issuer-relative URL.

    Raises:
        OIDCMetadataError: If no issuer is configured.
    """
    if settings.oidc_discovery_url:
        return settings.oidc_discovery_url
    if not settings.jwt_issuer:
        raise OIDCMetadataError("JWT_ISSUER is required to resolve OIDC discovery metadata.")
    return f"{settings.jwt_issuer.rstrip('/')}/.well-known/openid-configuration"


def _is_http_url(value: str) -> bool:
    """Check whether a metadata value is an HTTP(S) URL.

    Args:
        value: Metadata string to inspect.

    Returns:
        True when the value has an HTTP or HTTPS URL scheme.
    """
    return value.startswith(("https://", "http://"))


def validate_oidc_metadata(settings: Settings, metadata: dict[str, Any]) -> OIDCMetadata:
    """Validate issuer and JWKS values from an OIDC discovery document.

    Args:
        settings: Application settings.
        metadata: Raw JSON metadata from discovery.

    Returns:
        Validated OIDC metadata.

    Raises:
        OIDCMetadataError: If metadata does not match the configured trust boundary.
    """
    try:
        parsed_metadata = OIDCMetadata.model_validate(metadata)
    except ValidationError as exc:
        raise OIDCMetadataError("OIDC metadata is missing required issuer or jwks_uri.") from exc

    issuer = parsed_metadata.issuer
    jwks_uri = parsed_metadata.jwks_uri
    if not _is_http_url(issuer) or not _is_http_url(jwks_uri):
        raise OIDCMetadataError("OIDC issuer and jwks_uri must be HTTP URLs.")
    if issuer != settings.jwt_issuer:
        raise OIDCMetadataError("OIDC metadata issuer does not match JWT_ISSUER.")
    if settings.jwt_jwks_url and jwks_uri != settings.jwt_jwks_url:
        raise OIDCMetadataError("OIDC metadata jwks_uri does not match JWT_JWKS_URL.")
    if settings.environment == "production" and (
        not issuer.startswith("https://") or not jwks_uri.startswith("https://")
    ):
        raise OIDCMetadataError("OIDC issuer and jwks_uri must use https in production.")
    return parsed_metadata


async def _request_oidc_metadata(
    client: httpx.AsyncClient,
    discovery_url: str,
) -> dict[str, Any]:
    """Request raw OIDC metadata from a discovery endpoint.

    Args:
        client: HTTP client configured with the caller's timeout and redirect policy.
        discovery_url: OpenID Provider configuration endpoint.

    Returns:
        Raw discovery JSON object.

    Raises:
        OIDCMetadataError: If the endpoint cannot be fetched or returns non-object JSON.
    """
    try:
        response = await client.get(discovery_url, headers={"Accept": "application/json"})
        response.raise_for_status()
        raw_metadata = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OIDCMetadataError("OIDC metadata could not be fetched.") from exc
    if not isinstance(raw_metadata, dict):
        raise OIDCMetadataError("OIDC metadata response must be a JSON object.")
    return raw_metadata


async def fetch_oidc_metadata(
    settings: Settings,
    client: httpx.AsyncClient | None = None,
) -> OIDCMetadata:
    """Fetch and validate OIDC discovery metadata.

    Args:
        settings: Application settings.
        client: Optional HTTP client for tests or managed operational callers.

    Returns:
        Validated OIDC metadata.

    Raises:
        OIDCMetadataError: If retrieval or validation fails.
    """
    discovery_url = resolve_oidc_discovery_url(settings)
    if client is not None:
        return validate_oidc_metadata(settings, await _request_oidc_metadata(client, discovery_url))

    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=settings.jwt_jwks_timeout_seconds,
    ) as owned_client:
        return validate_oidc_metadata(
            settings,
            await _request_oidc_metadata(owned_client, discovery_url),
        )
