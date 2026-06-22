"""Supabase Auth JWT verification regression tests (ADR 39).

The backend verifies Supabase-issued JWTs with configuration only — no new
``/auth/*`` routes. Supabase asymmetric signing keys are RS256 or ES256; the
backend rejects symmetric (HS256) in production, so a deploying project MUST
enable asymmetric JWT signing keys.

Official reference: https://supabase.com/docs/guides/auth/jwts
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi import HTTPException, status
from src.config import Settings
from src.security import auth
from src.security.auth import AuthenticatedUser, JWTVerifier
from src.security.subjects import MAX_OWNER_SUBJECT_LENGTH, build_owner_subject
from src.security.supabase_auth import (
    SUPABASE_ASYMMETRIC_ALGORITHMS,
    SUPABASE_AUTH_AUDIENCE,
    supabase_auth_endpoints,
)

_PROJECT_REF = "abcdefghijklmnopqrst"
_SUPABASE_ISSUER = f"https://{_PROJECT_REF}.supabase.co/auth/v1"
_SUPABASE_JWKS = f"https://{_PROJECT_REF}.supabase.co/auth/v1/.well-known/jwks.json"
_SUPABASE_SUBJECT = "3f1c8e2a-0b7d-4a9e-9c1f-2b6d8e0a1c34"


class _SigningKey:
    """Fake PyJWT signing-key wrapper."""

    def __init__(self, key: object) -> None:
        self.key = key


class _JwksClient:
    """Fake JWKS client returning a fixed public key for any kid."""

    def __init__(self, key: object) -> None:
        self._key = key

    def get_signing_key(self, _key_id: str) -> _SigningKey:
        """Return the configured signing key regardless of kid.

        Args:
            _key_id: JWT key id. The fake does not inspect it.

        Returns:
            Signing key wrapper.
        """
        return _SigningKey(self._key)


# --- helper: canonical Supabase endpoint derivation ---------------------------


def test_supabase_auth_endpoints_derives_official_urls() -> None:
    """Verify the helper derives the documented Supabase issuer and JWKS URLs."""
    endpoints = supabase_auth_endpoints(_PROJECT_REF)

    assert endpoints.issuer == _SUPABASE_ISSUER
    assert endpoints.jwks_url == _SUPABASE_JWKS
    assert endpoints.audience == "authenticated"
    assert endpoints.algorithms == ("RS256", "ES256")


def test_supabase_auth_constants() -> None:
    """Verify the audience and asymmetric-algorithm constants match Supabase."""
    assert SUPABASE_AUTH_AUDIENCE == "authenticated"
    assert SUPABASE_ASYMMETRIC_ALGORITHMS == ("RS256", "ES256")


def test_supabase_auth_endpoints_strips_surrounding_whitespace() -> None:
    """Verify a padded ref is accepted after trimming (common .env copy error)."""
    assert supabase_auth_endpoints(f"  {_PROJECT_REF}  ").issuer == _SUPABASE_ISSUER


@pytest.mark.parametrize(
    "bad_ref",
    [
        "",
        "   ",
        "has space",
        "bad/ref",
        "evil.com",
        "UPPERCASE",
        "ref_underscore",
        "ref.dot",
        "abcdefghijklmnopqrs1",  # 20 chars but contains a digit (official: letters only)
        "abcdefghijklmnopqr",  # 18 letters (too short; official ref is exactly 20)
        "abcdefghijklmnopqrstu",  # 21 letters (too long)
    ],
)
def test_supabase_auth_endpoints_rejects_invalid_ref(bad_ref: str) -> None:
    """Verify non-conforming refs are rejected (official format is ^[a-z]{20}$)."""
    with pytest.raises(ValueError, match="project ref"):
        supabase_auth_endpoints(bad_ref)


# --- verifier: Supabase-shaped tokens ----------------------------------------


def _supabase_settings(algorithms: list[str]) -> Settings:
    """Return JWT settings pointed at a Supabase project.

    Args:
        algorithms: Allowed signing algorithms.

    Returns:
        Settings configured to verify Supabase access tokens.
    """
    endpoints = supabase_auth_endpoints(_PROJECT_REF)
    return Settings(
        auth_mode="jwt",
        jwt_issuer=endpoints.issuer,
        jwt_audience=endpoints.audience,
        jwt_jwks_url=endpoints.jwks_url,
        jwt_algorithms=algorithms,
        jwt_expected_token_type="JWT",
    )


def _supabase_claims(**overrides: Any) -> dict[str, Any]:
    """Build Supabase access-token claims for tests.

    Args:
        **overrides: Claim overrides.

    Returns:
        JWT claims dictionary shaped like a Supabase access token.
    """
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": _SUPABASE_SUBJECT,
        "iss": _SUPABASE_ISSUER,
        "aud": "authenticated",
        "role": "authenticated",
        "exp": now + timedelta(minutes=5),
        "iat": now,
    }
    payload.update(overrides)
    return payload


def test_verifier_accepts_supabase_rs256_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify a Supabase RS256 access token resolves to the expected subject."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(auth, "get_jwks_client", lambda *_a: _JwksClient(private_key.public_key()))
    token = jwt.encode(_supabase_claims(), private_key, algorithm="RS256", headers={"kid": "rs"})

    user = JWTVerifier(_supabase_settings(["RS256", "ES256"])).verify(token)

    assert user.subject == _SUPABASE_SUBJECT
    assert user.issuer == _SUPABASE_ISSUER
    assert user.audience == "authenticated"


def test_verifier_accepts_supabase_es256_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify a Supabase ES256 access token verifies (Supabase's newer default)."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(auth, "get_jwks_client", lambda *_a: _JwksClient(private_key.public_key()))
    token = jwt.encode(_supabase_claims(), private_key, algorithm="ES256", headers={"kid": "es"})

    user = JWTVerifier(_supabase_settings(["RS256", "ES256"])).verify(token)

    assert user.subject == _SUPABASE_SUBJECT
    assert user.issuer == _SUPABASE_ISSUER


def test_verifier_rejects_anon_audience(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify an anonymous Supabase token is rejected when authenticated is required."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(auth, "get_jwks_client", lambda *_a: _JwksClient(private_key.public_key()))
    token = jwt.encode(
        _supabase_claims(aud="anon"), private_key, algorithm="RS256", headers={"kid": "rs"}
    )

    with pytest.raises(HTTPException) as error:
        JWTVerifier(_supabase_settings(["RS256", "ES256"])).verify(token)

    assert error.value.status_code == status.HTTP_401_UNAUTHORIZED


# --- owner-subject mapping (ADR 39 regression) -------------------------------


def test_build_owner_subject_supabase_mapping() -> None:
    """Verify the Supabase issuer + uuid form a stable, bounded owner key."""
    user = AuthenticatedUser(
        subject=_SUPABASE_SUBJECT,
        issuer=_SUPABASE_ISSUER,
        audience="authenticated",
    )

    owner_subject = build_owner_subject(user)

    assert owner_subject == f"{_SUPABASE_ISSUER}::{_SUPABASE_SUBJECT}"
    assert len(owner_subject) <= MAX_OWNER_SUBJECT_LENGTH
