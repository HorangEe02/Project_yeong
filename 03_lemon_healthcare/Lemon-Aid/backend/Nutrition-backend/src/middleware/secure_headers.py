"""HTTP security response headers middleware.

Attaches the OWASP Secure Headers Baseline plus a minimal API-server
Content-Security-Policy to every response. HSTS is only emitted in the
production environment so local browsers do not stick the policy in
development caches.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from src.config import Settings

BASELINE_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-site",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), interest-cohort=()",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}
"""Headers attached to every response regardless of environment."""

PRODUCTION_HSTS_HEADER: tuple[str, str] = (
    "Strict-Transport-Security",
    "max-age=63072000; includeSubDomains; preload",
)
"""HSTS header emitted only when ``Settings.environment`` is ``production``."""


class SecureHeadersMiddleware(BaseHTTPMiddleware):
    """Attach baseline security response headers to every HTTP response."""

    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        """Initialize the middleware.

        Args:
            app: Downstream ASGI application.
            settings: Runtime settings used to gate the production-only HSTS header.
        """
        super().__init__(app)
        self._is_production = settings.environment == "production"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Pass the request downstream and stamp security headers on the response.

        Args:
            request: Incoming HTTP request.
            call_next: Downstream middleware/route handler.

        Returns:
            Response with baseline security headers applied via ``setdefault`` so
            downstream handlers can still override individual values when needed.
        """
        response = await call_next(request)
        for header, value in BASELINE_SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        if self._is_production:
            header, value = PRODUCTION_HSTS_HEADER
            response.headers.setdefault(header, value)
        return response
