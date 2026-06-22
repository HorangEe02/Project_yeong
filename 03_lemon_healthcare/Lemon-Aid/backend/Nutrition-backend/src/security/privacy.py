"""Privacy-preserving request and actor helpers."""

from __future__ import annotations

import hashlib
import hmac

from fastapi import Request

from src.config import Settings
from src.security.auth import AuthenticatedUser
from src.security.subjects import build_owner_subject

MAX_REQUEST_ID_LENGTH = 64


def hash_with_privacy_secret(
    value: str | None, settings: Settings, *, secret_override: str | None = None
) -> str | None:
    """Hash a value with the configured privacy HMAC secret.

    Args:
        value: Sensitive value to hash.
        settings: Application settings containing the privacy hash secret.
        secret_override: Optional explicit HMAC secret. When provided (and
            non-empty) it is used instead of ``privacy_hash_secret`` — used for
            the audit pepper so an audit-subject hash is keyed independently.

    Returns:
        Hex-encoded SHA-256 HMAC, or None for empty input.
    """
    if value is None:
        return None

    normalized_value = value.strip()
    if not normalized_value:
        return None

    secret = secret_override or settings.privacy_hash_secret.get_secret_value()
    return hmac.new(
        secret.encode("utf-8"),
        normalized_value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _audit_secret(settings: Settings) -> str | None:
    """Return the dedicated audit pepper when configured, else ``None``.

    Using a separate pepper for audit actor-subject hashes means a leak of the
    general ``privacy_hash_secret`` cannot also be used to correlate audit
    owner-subject hashes back to known subjects. When unset, callers fall back to
    the privacy hash secret, keeping existing audit-hash values stable (no
    migration required).

    Args:
        settings: Application settings.

    Returns:
        The audit pepper string, or ``None`` to use the privacy hash secret.
    """
    pepper = settings.privacy_hash_secret_audit_pepper
    if pepper is not None and pepper.get_secret_value().strip():
        return pepper.get_secret_value()
    return None


def hash_actor_subject(user: AuthenticatedUser, settings: Settings) -> str:
    """Hash the issuer-qualified authenticated subject for audit storage.

    Args:
        user: Authenticated actor.
        settings: Application settings containing the privacy hash secret.

    Returns:
        Hex-encoded subject HMAC.

    Raises:
        ValueError: If the authenticated subject is invalid.
    """
    subject_hash = hash_with_privacy_secret(
        build_owner_subject(user), settings, secret_override=_audit_secret(settings)
    )
    if subject_hash is None:
        raise ValueError("Authenticated owner subject is invalid.")
    return subject_hash


def request_id_from_headers(request: Request) -> str | None:
    """Extract a bounded request identifier from HTTP headers.

    Args:
        request: Current FastAPI request.

    Returns:
        Header value truncated to the storage limit, or None when absent.
    """
    request_id = request.headers.get("x-request-id")
    if request_id is None:
        return None
    normalized_request_id = request_id.strip()
    if not normalized_request_id:
        return None
    return normalized_request_id[:MAX_REQUEST_ID_LENGTH]


def request_privacy_hashes(request: Request, settings: Settings) -> tuple[str | None, str | None]:
    """Hash request network metadata for audit storage.

    Args:
        request: Current FastAPI request.
        settings: Application settings containing the privacy hash secret.

    Returns:
        Pair of IP hash and user-agent hash.
    """
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return (
        hash_with_privacy_secret(client_ip, settings),
        hash_with_privacy_secret(user_agent, settings),
    )
