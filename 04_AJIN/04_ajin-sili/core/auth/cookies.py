"""Browser cookie and CSRF helpers for AJIN auth sessions.

The browser session intentionally keeps access and refresh JWTs out of
JavaScript-readable storage. A separate non-HttpOnly CSRF cookie is issued so
the frontend can copy it into ``X-CSRF-Token`` for unsafe methods.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass

from fastapi import Request
from starlette.responses import Response

from core.auth.jwt_handler import JWT_ACCESS_EXPIRE_MINUTES, JWT_REFRESH_EXPIRE_DAYS

ACCESS_COOKIE_NAME = "ajin_access"
REFRESH_COOKIE_NAME = "ajin_refresh"
CSRF_COOKIE_NAME = "ajin_csrf"
CSRF_HEADER_NAME = "x-csrf-token"


def _env_truthy(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _is_production() -> bool:
    app_env = os.environ.get("APP_ENV", "")
    environment = os.environ.get("ENVIRONMENT", "")
    cloud_run = os.environ.get("K_SERVICE", "")
    return any(v.strip().lower() == "production" for v in (app_env, environment)) or bool(cloud_run)


def auth_cookie_secure() -> bool:
    """Return whether auth cookies should use the Secure attribute.

    Returns:
        bool: True in production/Cloud Run by default. Local HTTP development can
        opt out with ``AUTH_COOKIE_SECURE=false``.
    """

    return _env_truthy("AUTH_COOKIE_SECURE", default=_is_production())


@dataclass(frozen=True)
class AuthCookieSettings:
    """Resolved browser cookie settings used by the auth router.

    Args:
        secure: Whether cookies carry the Secure attribute.
        samesite: SameSite policy. AJIN uses Lax for same-site SPA/API flows.
        access_path: Path scope for the short-lived access cookie.
        refresh_path: Path scope for the refresh cookie.
        csrf_path: Path scope for the JS-readable CSRF cookie.
        access_max_age: Access cookie max-age in seconds.
        refresh_max_age: Refresh cookie max-age in seconds.
    """

    secure: bool
    samesite: str
    access_path: str
    refresh_path: str
    csrf_path: str
    access_max_age: int
    refresh_max_age: int


def resolve_auth_cookie_settings() -> AuthCookieSettings:
    """Resolve cookie attributes from release defaults and environment overrides."""

    return AuthCookieSettings(
        secure=auth_cookie_secure(),
        samesite="lax",
        access_path="/api",
        refresh_path="/api/auth",
        csrf_path="/",
        access_max_age=JWT_ACCESS_EXPIRE_MINUTES * 60,
        refresh_max_age=JWT_REFRESH_EXPIRE_DAYS * 24 * 60 * 60,
    )


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> str:
    """Set access, refresh, and CSRF cookies on a response.

    Args:
        response: Starlette/FastAPI response object to mutate.
        access_token: Signed short-lived access JWT.
        refresh_token: Signed refresh JWT stored server-side for rotation.

    Returns:
        str: CSRF token value mirrored in the non-HttpOnly cookie.
    """

    settings = resolve_auth_cookie_settings()
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        ACCESS_COOKIE_NAME,
        access_token,
        max_age=settings.access_max_age,
        httponly=True,
        secure=settings.secure,
        samesite=settings.samesite,
        path=settings.access_path,
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=settings.refresh_max_age,
        httponly=True,
        secure=settings.secure,
        samesite=settings.samesite,
        path=settings.refresh_path,
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        max_age=settings.refresh_max_age,
        httponly=False,
        secure=settings.secure,
        samesite=settings.samesite,
        path=settings.csrf_path,
    )
    return csrf_token


def clear_auth_cookies(response: Response) -> None:
    """Clear AJIN browser auth cookies from their exact path scopes."""

    settings = resolve_auth_cookie_settings()
    for name, path in (
        (ACCESS_COOKIE_NAME, settings.access_path),
        (REFRESH_COOKIE_NAME, settings.refresh_path),
        (CSRF_COOKIE_NAME, settings.csrf_path),
    ):
        response.delete_cookie(
            name,
            path=path,
            secure=settings.secure,
            samesite=settings.samesite,
        )


def access_token_from_request(request: Request) -> str | None:
    """Read the HttpOnly access cookie from a request."""

    return request.cookies.get(ACCESS_COOKIE_NAME) or None


def refresh_token_from_request(request: Request) -> str | None:
    """Read the HttpOnly refresh cookie from a request."""

    return request.cookies.get(REFRESH_COOKIE_NAME) or None


def csrf_matches_request(request: Request) -> bool:
    """Validate that the CSRF header matches the JS-readable CSRF cookie."""

    cookie_value = request.cookies.get(CSRF_COOKIE_NAME)
    header_value = request.headers.get(CSRF_HEADER_NAME)
    return bool(cookie_value and header_value and secrets.compare_digest(cookie_value, header_value))
