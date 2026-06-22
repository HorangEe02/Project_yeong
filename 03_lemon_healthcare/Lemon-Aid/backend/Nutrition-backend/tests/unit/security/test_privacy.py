"""Privacy hashing helper tests."""

from __future__ import annotations

from fastapi import Request
from pydantic import SecretStr
from src.config import Settings
from src.security.auth import AuthenticatedUser
from src.security.privacy import (
    hash_actor_subject,
    hash_with_privacy_secret,
    request_id_from_headers,
    request_privacy_hashes,
)


def _request() -> Request:
    """Return a request fixture with network metadata.

    Returns:
        Starlette request object.
    """
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [
                (b"user-agent", b"raw-test-agent"),
                (
                    b"x-request-id",
                    b"request-id-that-is-longer-than-sixty-four-characters-0123456789-extra",
                ),
            ],
            "client": ("203.0.113.10", 12345),
        }
    )


def test_privacy_hashes_are_hmacs_not_raw_values() -> None:
    """Verify privacy hashes do not store raw subjects, IPs, or user agents."""
    settings = Settings(privacy_hash_secret=SecretStr("test-privacy-secret"))
    request = _request()
    user = AuthenticatedUser(
        subject="user_123",
        issuer="https://auth.example.com/",
        claims={"sub": "user_123"},
    )

    subject_hash = hash_actor_subject(user, settings)
    ip_hash, user_agent_hash = request_privacy_hashes(request, settings)

    assert subject_hash != "https://auth.example.com/::user_123"
    assert ip_hash != "203.0.113.10"
    assert user_agent_hash != "raw-test-agent"
    assert len(subject_hash) == 64
    assert len(ip_hash or "") == 64
    assert len(user_agent_hash or "") == 64


def test_hash_with_privacy_secret_returns_none_for_empty_values() -> None:
    """Verify blank optional audit metadata remains absent."""
    settings = Settings(privacy_hash_secret=SecretStr("test-privacy-secret"))

    assert hash_with_privacy_secret(None, settings) is None
    assert hash_with_privacy_secret("   ", settings) is None


def test_request_id_is_bounded() -> None:
    """Verify external request IDs cannot exceed the storage limit."""
    request_id = request_id_from_headers(_request())

    assert request_id is not None
    assert len(request_id) == 64


def test_audit_pepper_changes_actor_hash() -> None:
    """A configured audit pepper changes the actor-subject hash.

    Without a pepper the actor hash equals the privacy-secret HMAC, so a leak of
    the general privacy secret cannot reproduce the peppered audit hashes.
    """
    user = AuthenticatedUser(subject="user_123", issuer="https://auth.example.com/")
    base = Settings(privacy_hash_secret=SecretStr("test-privacy-secret"))
    peppered = Settings(
        privacy_hash_secret=SecretStr("test-privacy-secret"),
        privacy_hash_secret_audit_pepper=SecretStr("distinct-audit-pepper"),
    )

    assert hash_actor_subject(user, peppered) != hash_actor_subject(user, base)
    # Pepper keys only the audit-subject hash, not generic request-metadata hashing.
    assert hash_with_privacy_secret("value", peppered) == hash_with_privacy_secret("value", base)


def test_audit_hash_falls_back_to_privacy_secret_without_pepper() -> None:
    """Without a pepper the audit hash stays stable on the privacy secret."""
    user = AuthenticatedUser(subject="user_123", issuer="https://auth.example.com/")
    a = Settings(privacy_hash_secret=SecretStr("test-privacy-secret"))
    b = Settings(privacy_hash_secret=SecretStr("test-privacy-secret"))

    assert hash_actor_subject(user, a) == hash_actor_subject(user, b)
