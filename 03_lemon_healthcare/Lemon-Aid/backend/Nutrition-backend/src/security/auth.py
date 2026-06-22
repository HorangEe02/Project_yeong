"""OAuth/OIDC JWT authentication helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from functools import lru_cache
from typing import Annotated, Any, cast

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from pydantic import BaseModel, Field

from src.config import Settings, get_settings
from src.security.scopes import ALL_API_SCOPES, ApiScope, scope_values

ANALYSIS_READ_SCOPE = ApiScope.ANALYSIS_READ.value
ANALYSIS_WRITE_SCOPE = ApiScope.ANALYSIS_WRITE.value
ANALYSIS_DELETE_SCOPE = ApiScope.ANALYSIS_DELETE.value
PRIVACY_READ_SCOPE = ApiScope.PRIVACY_READ.value
PRIVACY_WRITE_SCOPE = ApiScope.PRIVACY_WRITE.value
PRIVACY_DELETE_SCOPE = ApiScope.PRIVACY_DELETE.value
SUPPLEMENT_READ_SCOPE = ApiScope.SUPPLEMENT_READ.value
SUPPLEMENT_WRITE_SCOPE = ApiScope.SUPPLEMENT_WRITE.value
SUPPLEMENT_DELETE_SCOPE = ApiScope.SUPPLEMENT_DELETE.value
MEAL_READ_SCOPE = ApiScope.MEAL_READ.value
MEAL_WRITE_SCOPE = ApiScope.MEAL_WRITE.value
HEALTH_READ_SCOPE = ApiScope.HEALTH_READ.value
HEALTH_WRITE_SCOPE = ApiScope.HEALTH_WRITE.value
MEDICAL_READ_SCOPE = ApiScope.MEDICAL_READ.value
MEDICAL_WRITE_SCOPE = ApiScope.MEDICAL_WRITE.value
REGULATED_INPUT_WRITE_SCOPE = ApiScope.REGULATED_INPUT_WRITE.value
DASHBOARD_READ_SCOPE = ApiScope.DASHBOARD_READ.value
DEVELOPMENT_AUTH_SCOPES = ALL_API_SCOPES

bearer_scheme = HTTPBearer(
    auto_error=False,
    bearerFormat="JWT",
    scheme_name="BearerAuth",
    description=(
        "OAuth/OIDC Bearer access token. Protected APIs require route-specific "
        "analysis:*, privacy:*, supplement:*, meal:*, health:*, medical:*, "
        "or dashboard:* scopes."
    ),
)


class AuthenticatedUser(BaseModel):
    """Authenticated principal resolved from the bearer token.

    Attributes:
        subject: Stable user or service subject from the JWT sub claim.
        issuer: Token issuer claim.
        audience: Token audience claim.
        scopes: OAuth scopes extracted from scope or scp claims.
        claims: Full validated JWT claims for downstream audit records.
    """

    subject: str
    issuer: str | None = None
    audience: str | list[str] | None = None
    scopes: tuple[str, ...] = ()
    claims: dict[str, Any] = Field(default_factory=dict)


@lru_cache(maxsize=8)
def get_jwks_client(
    jwks_url: str,
    cache_ttl_seconds: int,
    timeout_seconds: int,
) -> PyJWKClient:
    """Return a cached JWKS client for an issuer.

    Args:
        jwks_url: HTTPS JWKS endpoint URL from the OAuth/OIDC provider.
        cache_ttl_seconds: JWKS cache lifespan in seconds.
        timeout_seconds: JWKS retrieval timeout in seconds.

    Returns:
        Cached PyJWT JWKS client.
    """
    return PyJWKClient(
        jwks_url,
        cache_jwk_set=True,
        lifespan=cache_ttl_seconds,
        timeout=timeout_seconds,
    )


def _auth_error(
    status_code: int,
    detail: str,
    *,
    error: str | None = None,
    scope: str | None = None,
) -> HTTPException:
    """Build a Bearer authentication error.

    Args:
        status_code: HTTP status code to return.
        detail: Safe error detail for clients.
        error: Optional RFC 6750 Bearer error code.
        scope: Optional RFC 6750 required scope string.

    Returns:
        HTTP exception with a Bearer challenge header.
    """
    challenge_values = ['realm="lemon-healthcare"']
    if error:
        challenge_values.append(f'error="{error}"')
    if scope:
        challenge_values.append(f'scope="{scope}"')
    return HTTPException(
        status_code=status_code,
        detail=detail,
        headers={"WWW-Authenticate": f"Bearer {', '.join(challenge_values)}"},
    )


def _extract_scopes(claims: dict[str, Any], scope_claims: Sequence[str]) -> tuple[str, ...]:
    """Extract OAuth scopes from common JWT claim shapes.

    Args:
        claims: Validated JWT claims.
        scope_claims: Claim names to inspect for OAuth scopes.

    Returns:
        Tuple of scope strings.
    """
    for claim_name in scope_claims:
        scope_claim = claims.get(claim_name)
        if isinstance(scope_claim, str):
            return tuple(scope for scope in scope_claim.split() if scope)
        if isinstance(scope_claim, list):
            return tuple(scope for scope in scope_claim if isinstance(scope, str) and scope)
    return ()


def _normalize_token_type(value: str) -> str:
    """Normalize a JOSE typ header value for access-token comparisons.

    Args:
        value: Raw typ header value.

    Returns:
        Lowercase token type with an optional application/ prefix removed.
    """
    normalized = value.strip().lower()
    if normalized.startswith("application/"):
        return normalized.removeprefix("application/")
    return normalized


def _validate_token_type(header: dict[str, Any], settings: Settings) -> None:
    """Validate an optional JOSE typ header against settings.

    Args:
        header: Unverified JWT header.
        settings: Application settings.

    Raises:
        HTTPException: If the configured token type does not match.
    """
    if not settings.jwt_expected_token_type:
        return

    token_type = header.get("typ")
    if not isinstance(token_type, str) or _normalize_token_type(
        token_type
    ) != _normalize_token_type(settings.jwt_expected_token_type):
        raise _auth_error(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid authentication credentials.",
            error="invalid_token",
        )


def _validate_token_use(claims: dict[str, Any], settings: Settings) -> None:
    """Validate a provider-specific token-use claim when configured.

    Args:
        claims: Validated JWT claims.
        settings: Application settings.

    Raises:
        HTTPException: If the token-use claim is missing or disallowed.
    """
    if not settings.jwt_token_use_claim:
        return

    token_use = claims.get(settings.jwt_token_use_claim)
    if not isinstance(token_use, str) or token_use not in settings.jwt_token_use_allowed_values:
        raise _auth_error(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid authentication credentials.",
            error="invalid_token",
        )


def _validate_jwt_header(header: dict[str, Any], settings: Settings) -> str:
    """Validate JOSE header fields required for production JWKS verification.

    Args:
        header: Unverified JWT header.
        settings: Application settings.

    Returns:
        JWT key ID used to resolve the signing key from JWKS.

    Raises:
        jwt.PyJWTError: If the header is malformed or not allowed by settings.
        HTTPException: If the configured token type does not match.
    """
    algorithm = header.get("alg")
    if not isinstance(algorithm, str) or algorithm not in settings.jwt_algorithms:
        raise jwt.InvalidAlgorithmError("Unsupported JWT algorithm.")
    _validate_token_type(header, settings)

    key_id = header.get("kid")
    if not isinstance(key_id, str) or not key_id:
        raise jwt.InvalidTokenError("JWT kid header is required for JWKS verification.")
    return key_id


class JWTVerifier:
    """Validate OAuth/OIDC JWT access tokens with issuer JWKS keys.

    Args:
        settings: Application settings containing issuer, audience, JWKS URL, and algorithms.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def verify(self, token: str) -> AuthenticatedUser:
        """Validate a bearer token and return the authenticated principal.

        Args:
            token: Compact JWT string from an Authorization header.

        Returns:
            Authenticated user principal.

        Raises:
            HTTPException: If auth is misconfigured or token validation fails.
        """
        if (
            self._settings.jwt_issuer is None
            or self._settings.jwt_audience is None
            or self._settings.jwt_jwks_url is None
        ):
            raise _auth_error(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Authentication backend is not configured.",
            )

        try:
            header = jwt.get_unverified_header(token)
            key_id = _validate_jwt_header(header, self._settings)

            signing_key = get_jwks_client(
                self._settings.jwt_jwks_url,
                self._settings.jwt_jwks_cache_ttl_seconds,
                self._settings.jwt_jwks_timeout_seconds,
            ).get_signing_key(key_id)
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=self._settings.jwt_algorithms,
                audience=self._settings.jwt_audience,
                issuer=self._settings.jwt_issuer,
                leeway=self._settings.jwt_leeway_seconds,
                options={"require": self._settings.jwt_required_claims},
            )
        except jwt.PyJWKClientConnectionError as exc:
            raise _auth_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Authentication provider unavailable.",
            ) from exc
        except jwt.PyJWTError as exc:
            raise _auth_error(
                status.HTTP_401_UNAUTHORIZED,
                "Invalid authentication credentials.",
                error="invalid_token",
            ) from exc

        _validate_token_use(claims, self._settings)
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise _auth_error(
                status.HTTP_401_UNAUTHORIZED,
                "Invalid authentication credentials.",
                error="invalid_token",
            )

        audience_claim = claims.get("aud")
        audience: str | list[str] | None
        if isinstance(audience_claim, str) or (
            isinstance(audience_claim, list)
            and all(isinstance(value, str) for value in audience_claim)
        ):
            audience = cast(str | list[str], audience_claim)
        else:
            audience = None

        return AuthenticatedUser(
            subject=subject,
            issuer=claims.get("iss") if isinstance(claims.get("iss"), str) else None,
            audience=audience,
            scopes=_extract_scopes(claims, self._settings.jwt_scope_claims),
            claims=claims,
        )


def _ensure_scopes(
    current_user: AuthenticatedUser,
    required_scopes: tuple[str, ...],
) -> AuthenticatedUser:
    """Ensure the authenticated user has all required OAuth scopes.

    Args:
        current_user: Authenticated principal.
        required_scopes: Scopes required by the route.

    Returns:
        The same authenticated principal when authorization succeeds.

    Raises:
        HTTPException: If one or more scopes are missing.
    """
    granted_scopes = set(current_user.scopes)
    missing_scopes = [scope for scope in required_scopes if scope not in granted_scopes]
    if missing_scopes:
        raise _auth_error(
            status.HTTP_403_FORBIDDEN,
            "Not enough permissions.",
            error="insufficient_scope",
            scope=" ".join(required_scopes),
        )
    return current_user


def require_scopes(*required_scopes: ApiScope) -> Callable[..., Awaitable[AuthenticatedUser]]:
    """Build a FastAPI dependency that requires registered OAuth scopes.

    Args:
        required_scopes: Registered API scopes required by the route.

    Returns:
        Dependency callable that validates the current user's scopes.
    """
    required_scope_values = scope_values(*required_scopes)

    async def _require_scoped_user(
        current_user: Annotated[AuthenticatedUser, Depends(require_current_user)],
    ) -> AuthenticatedUser:
        """Require the configured scope set for one route.

        Args:
            current_user: Authenticated principal.

        Returns:
            Authorized principal.
        """
        return _ensure_scopes(current_user, required_scope_values)

    return _require_scoped_user


async def require_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedUser:
    """Resolve the authenticated user for protected API routes.

    Args:
        credentials: Optional HTTP Bearer credentials from FastAPI.
        settings: Loaded application settings.

    Returns:
        Authenticated user principal. Development mode with AUTH_MODE=disabled returns
        a deterministic local principal for API development.

    Raises:
        HTTPException: If JWT auth is enabled and the request is unauthenticated or invalid.
    """
    if settings.auth_mode == "disabled":
        return AuthenticatedUser(
            subject="local-dev-user",
            issuer="local-development",
            scopes=DEVELOPMENT_AUTH_SCOPES,
            claims={"auth_mode": "disabled"},
        )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _auth_error(status.HTTP_401_UNAUTHORIZED, "Not authenticated.")

    return JWTVerifier(settings).verify(credentials.credentials)


require_analysis_read = require_scopes(ApiScope.ANALYSIS_READ)
require_analysis_write = require_scopes(ApiScope.ANALYSIS_WRITE)
require_analysis_delete = require_scopes(ApiScope.ANALYSIS_DELETE)
require_privacy_read = require_scopes(ApiScope.PRIVACY_READ)
require_privacy_write = require_scopes(ApiScope.PRIVACY_WRITE)
require_privacy_delete = require_scopes(ApiScope.PRIVACY_DELETE)
require_supplement_read = require_scopes(ApiScope.SUPPLEMENT_READ)
require_supplement_write = require_scopes(ApiScope.SUPPLEMENT_WRITE)
require_supplement_delete = require_scopes(ApiScope.SUPPLEMENT_DELETE)
require_meal_read = require_scopes(ApiScope.MEAL_READ)
require_meal_write = require_scopes(ApiScope.MEAL_WRITE)
require_health_read = require_scopes(ApiScope.HEALTH_READ)
require_health_write = require_scopes(ApiScope.HEALTH_WRITE)
require_medical_read = require_scopes(ApiScope.MEDICAL_READ)
require_medical_write = require_scopes(ApiScope.MEDICAL_WRITE)
require_regulated_input_write = require_scopes(ApiScope.REGULATED_INPUT_WRITE)
require_dashboard_read = require_scopes(ApiScope.DASHBOARD_READ)
