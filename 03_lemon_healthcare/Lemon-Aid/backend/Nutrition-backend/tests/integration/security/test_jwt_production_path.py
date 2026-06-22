"""Production-style JWT authentication integration tests."""

from __future__ import annotations

import base64
import json
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Annotated, Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from fastapi import Depends, FastAPI, status
from fastapi.testclient import TestClient
from src.config import Settings, get_settings
from src.security.auth import AuthenticatedUser, get_jwks_client, require_analysis_write

ISSUER = "https://auth.example.com/"
AUDIENCE = "lemon-api"


def _base64url_uint(value: int) -> str:
    """Encode an RSA integer as unpadded base64url.

    Args:
        value: RSA public number.

    Returns:
        Base64url string accepted by JWK consumers.
    """
    byte_length = (value.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(value.to_bytes(byte_length, "big")).rstrip(b"=").decode("ascii")


def _key_pair() -> tuple[RSAPrivateKey, RSAPublicKey]:
    """Generate an RSA key pair for RS256 integration tests.

    Returns:
        Private and public RSA key objects.
    """
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _public_jwk(public_key: RSAPublicKey, key_id: str) -> dict[str, str]:
    """Convert an RSA public key to a minimal signing JWK.

    Args:
        public_key: RSA public key.
        key_id: JWK key ID.

    Returns:
        Public JWK dictionary.
    """
    numbers = public_key.public_numbers()
    return {
        "alg": "RS256",
        "e": _base64url_uint(numbers.e),
        "kid": key_id,
        "kty": "RSA",
        "n": _base64url_uint(numbers.n),
        "use": "sig",
    }


def _claims(**overrides: Any) -> dict[str, Any]:
    """Build default access-token claims.

    Args:
        **overrides: Claim overrides.

    Returns:
        JWT claims dictionary.
    """
    now = datetime.now(UTC)
    claims = {
        "aud": AUDIENCE,
        "exp": now + timedelta(minutes=5),
        "iat": now,
        "iss": ISSUER,
        "scope": "analysis:write profile:read",
        "sub": "user_123",
        "token_use": "access",
    }
    claims.update(overrides)
    return claims


def _access_token(
    private_key: RSAPrivateKey,
    key_id: str,
    *,
    headers: dict[str, Any] | None = None,
    **claim_overrides: Any,
) -> str:
    """Sign an RS256 access token for a configured test key.

    Args:
        private_key: RSA private key.
        key_id: JWT key ID.
        headers: Optional JOSE header overrides.
        **claim_overrides: Claim overrides.

    Returns:
        Compact JWT string.
    """
    return jwt.encode(
        _claims(**claim_overrides),
        private_key,
        algorithm="RS256",
        headers=headers or {"kid": key_id, "typ": "at+jwt"},
    )


class _MutableJwksState:
    """Mutable JWKS response state for PyJWKClient integration tests."""

    def __init__(self) -> None:
        self._keys: list[dict[str, str]] = []
        self.request_count = 0
        self.raise_timeout = False

    def set_keys(self, keys: list[dict[str, str]]) -> None:
        """Replace keys returned by the JWKS endpoint.

        Args:
            keys: Public JWK records.
        """
        self._keys = keys.copy()

    def urlopen(
        self,
        _request: object,
        *,
        timeout: float | None = None,
        context: object | None = None,
    ) -> BytesIO:
        """Return a JWKS response through the same shape used by urllib.

        Args:
            _request: urllib request object from PyJWKClient.
            timeout: Request timeout passed by PyJWKClient.
            context: Optional SSL context passed by PyJWKClient.

        Returns:
            File-like response object containing the current JWKS JSON.

        Raises:
            TimeoutError: If the test configures the endpoint to time out.
        """
        _ = timeout, context
        self.request_count += 1
        if self.raise_timeout:
            raise TimeoutError("JWKS endpoint timed out.")
        return BytesIO(json.dumps({"keys": self._keys.copy()}).encode("utf-8"))


@dataclass(frozen=True)
class _RunningJwksServer:
    """Mutable JWKS fixture endpoint."""

    state: _MutableJwksState
    url: str


@pytest.fixture
def jwks_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[_RunningJwksServer]:
    """Patch PyJWKClient's network fetch with a mutable JWKS endpoint.

    Yields:
        Mutable JWKS endpoint metadata.
    """
    get_jwks_client.cache_clear()
    state = _MutableJwksState()
    monkeypatch.setattr(urllib.request, "urlopen", state.urlopen)
    try:
        yield _RunningJwksServer(
            state=state,
            url="https://auth.example.com/.well-known/jwks.json",
        )
    finally:
        get_jwks_client.cache_clear()


def _jwt_settings(jwks_url: str, *, timeout_seconds: int = 1) -> Settings:
    """Return production-like JWT settings for integration tests.

    Args:
        jwks_url: Local JWKS endpoint URL.
        timeout_seconds: JWKS retrieval timeout.

    Returns:
        JWT-enabled settings.
    """
    return Settings(
        auth_mode="jwt",
        jwt_issuer=ISSUER,
        jwt_audience=AUDIENCE,
        jwt_jwks_url=jwks_url,
        jwt_algorithms=["RS256"],
        jwt_expected_token_type="at+jwt",
        jwt_token_use_claim="token_use",
        jwt_token_use_allowed_values=["access"],
        jwt_jwks_timeout_seconds=timeout_seconds,
    )


def _protected_client(settings: Settings) -> TestClient:
    """Create a FastAPI client with the production auth dependency wired in.

    Args:
        settings: Settings returned by the app dependency override.

    Returns:
        Test client exposing one protected route.
    """
    app = FastAPI()
    app.dependency_overrides[get_settings] = lambda: settings

    @app.get("/protected")
    async def protected(
        user: Annotated[AuthenticatedUser, Depends(require_analysis_write)],
    ) -> dict[str, object]:
        """Return authenticated user data from a protected route.

        Args:
            user: Authenticated and scope-authorized user.

        Returns:
            Route response payload.
        """
        return {"scopes": list(user.scopes), "subject": user.subject}

    return TestClient(app)


def _auth_header(token: str) -> dict[str, str]:
    """Build an HTTP Authorization header.

    Args:
        token: JWT access token.

    Returns:
        Header dictionary.
    """
    return {"Authorization": f"Bearer {token}"}


def test_jwt_auth_accepts_rotated_jwks_key(jwks_server: _RunningJwksServer) -> None:
    """Verify unknown rotated kids trigger JWKS refresh and then authenticate."""
    private_key_a, public_key_a = _key_pair()
    private_key_b, public_key_b = _key_pair()
    jwks_server.state.set_keys([_public_jwk(public_key_a, "kid-a")])
    client = _protected_client(_jwt_settings(jwks_server.url))

    first_response = client.get(
        "/protected", headers=_auth_header(_access_token(private_key_a, "kid-a"))
    )
    assert first_response.status_code == status.HTTP_200_OK
    assert first_response.json()["subject"] == "user_123"

    jwks_server.state.set_keys([_public_jwk(public_key_b, "kid-b")])
    rotated_response = client.get(
        "/protected",
        headers=_auth_header(_access_token(private_key_b, "kid-b")),
    )

    assert rotated_response.status_code == status.HTTP_200_OK
    assert rotated_response.json()["scopes"] == ["analysis:write", "profile:read"]
    assert jwks_server.state.request_count >= 2


def test_jwt_auth_rejects_missing_kid_without_jwks_fetch(
    jwks_server: _RunningJwksServer,
) -> None:
    """Verify missing kid cannot fall back to a cached or first JWKS key."""
    private_key, public_key = _key_pair()
    jwks_server.state.set_keys([_public_jwk(public_key, "kid-a")])
    client = _protected_client(_jwt_settings(jwks_server.url))

    response = client.get(
        "/protected",
        headers=_auth_header(_access_token(private_key, "kid-a", headers={"typ": "at+jwt"})),
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert jwks_server.state.request_count == 0


def test_jwt_auth_rejects_unknown_kid_after_jwks_refresh(
    jwks_server: _RunningJwksServer,
) -> None:
    """Verify unknown kids remain invalid after PyJWKClient refreshes JWKS once."""
    private_key, public_key = _key_pair()
    jwks_server.state.set_keys([_public_jwk(public_key, "kid-a")])
    client = _protected_client(_jwt_settings(jwks_server.url))

    response = client.get(
        "/protected",
        headers=_auth_header(_access_token(private_key, "kid-missing")),
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers["www-authenticate"] == (
        'Bearer realm="lemon-healthcare", error="invalid_token"'
    )


def test_jwt_auth_rejects_invalid_algorithm_without_jwks_fetch(
    jwks_server: _RunningJwksServer,
) -> None:
    """Verify disallowed alg headers are rejected before key lookup."""
    jwks_server.state.set_keys([])
    client = _protected_client(_jwt_settings(jwks_server.url))
    token = jwt.encode(
        _claims(),
        "not-used-for-rs256-but-long-enough-for-hmac",
        algorithm="HS256",
        headers={"kid": "kid-a", "typ": "at+jwt"},
    )

    response = client.get("/protected", headers=_auth_header(token))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert jwks_server.state.request_count == 0


@pytest.mark.parametrize(
    ("headers", "claim_overrides"),
    (
        ({"kid": "kid-a", "typ": "id+jwt"}, {}),
        ({"kid": "kid-a", "typ": "at+jwt"}, {"token_use": "id"}),
    ),
)
def test_jwt_auth_rejects_id_token_confusion(
    jwks_server: _RunningJwksServer,
    headers: dict[str, Any],
    claim_overrides: dict[str, Any],
) -> None:
    """Verify id-token shaped JWTs cannot authenticate as access tokens."""
    private_key, public_key = _key_pair()
    jwks_server.state.set_keys([_public_jwk(public_key, "kid-a")])
    client = _protected_client(_jwt_settings(jwks_server.url))

    response = client.get(
        "/protected",
        headers=_auth_header(
            _access_token(private_key, "kid-a", headers=headers, **claim_overrides)
        ),
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers["www-authenticate"] == (
        'Bearer realm="lemon-healthcare", error="invalid_token"'
    )


def test_jwt_auth_maps_jwks_timeout_to_service_unavailable(
    jwks_server: _RunningJwksServer,
) -> None:
    """Verify JWKS timeout is treated as provider availability, not token validity."""
    private_key, public_key = _key_pair()
    jwks_server.state.set_keys([_public_jwk(public_key, "kid-a")])
    jwks_server.state.raise_timeout = True
    client = _protected_client(_jwt_settings(jwks_server.url, timeout_seconds=1))

    response = client.get(
        "/protected",
        headers=_auth_header(_access_token(private_key, "kid-a")),
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.headers["www-authenticate"] == 'Bearer realm="lemon-healthcare"'
