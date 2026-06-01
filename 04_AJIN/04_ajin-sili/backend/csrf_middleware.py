"""Cookie-auth CSRF middleware for FastAPI/Starlette."""

from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse


class CookieCSRFMiddleware(BaseHTTPMiddleware):
    """Require CSRF header for unsafe methods that carry AJIN auth cookies."""

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}

    async def dispatch(self, request: Request, call_next):
        if request.method.upper() not in self.SAFE_METHODS:
            from core.auth.cookies import (
                ACCESS_COOKIE_NAME,
                REFRESH_COOKIE_NAME,
                csrf_matches_request,
            )

            has_auth_cookie = (
                ACCESS_COOKIE_NAME in request.cookies
                or REFRESH_COOKIE_NAME in request.cookies
            )
            if has_auth_cookie and not csrf_matches_request(request):
                return StarletteResponse(
                    content='{"detail":"CSRF token missing or invalid"}',
                    status_code=403,
                    media_type="application/json",
                )
        return await call_next(request)
