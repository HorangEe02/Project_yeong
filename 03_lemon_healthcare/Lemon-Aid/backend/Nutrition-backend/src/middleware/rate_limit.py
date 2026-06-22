"""Abuse controls for the expensive OCR + LLM inference endpoints.

The OCR → Ollama pipeline is the cheapest denial-of-service surface in the app:
a single ``/analyze`` request triggers image decode + OCR + an LLM inference, and
the mobile client fans out across multiple OCR providers per image. Without a
guard, an authenticated caller (or, when ``AUTH_MODE=disabled`` in a tunnelled
dev/demo, anyone) can saturate CPU/GPU/Ollama at near-zero cost.

This middleware applies two layered, in-process controls to a fixed set of
expensive path prefixes only (everything else passes straight through):

1. **Per-caller token-bucket rate limit** — sheds floods early with HTTP 429.
2. **Global concurrency cap** — an :class:`asyncio.Semaphore` bounds how many of
   these requests run in parallel, so a burst that passes the rate limit still
   cannot exhaust the inference backend; excess waits up to a short timeout then
   gets HTTP 503.

It deliberately uses no external dependency (no slowapi/redis): the limiter is a
process-local dict, which is correct for the single-process uvicorn deployment.
Behind multiple replicas this becomes per-replica limiting — acceptable as a
floor; a shared store would be a later enhancement.

Middleware runs *before* FastAPI dependency injection, so the authenticated
subject is not yet on ``request.state``. The limiter therefore keys on a stable
proxy available at this layer: a salted hash of the ``Authorization`` header when
present, else the client host. Same token → same bucket; unauthenticated dev
traffic → per-IP bucket.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from src.config import Settings

# Expensive OCR + LLM inference endpoints (exact paths from the mounted router).
RATE_LIMITED_PATHS: tuple[str, ...] = (
    "/api/v1/supplements/analyze",
    "/api/v1/supplements/analyze-comprehensive",
    "/api/v1/meals/analyze-image",
)
# Path *prefixes* (multi-image session upload uses a templated suffix).
RATE_LIMITED_PREFIXES: tuple[str, ...] = ("/api/v1/supplements/analysis-sessions",)

# Bounded key table so a flood of distinct keys cannot grow memory without limit.
_MAX_TRACKED_KEYS = 10_000


def _is_rate_limited_path(path: str) -> bool:
    """Return whether a request path is one of the protected expensive endpoints.

    Args:
        path: Request URL path.

    Returns:
        True if the path should be rate limited and concurrency capped.
    """
    if path in RATE_LIMITED_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in RATE_LIMITED_PREFIXES)


class _TokenBucket:
    """Monotonic-clock token bucket (burst capacity refilled at a steady rate)."""

    __slots__ = ("tokens", "updated_at")

    def __init__(self, tokens: float, updated_at: float) -> None:
        self.tokens = tokens
        self.updated_at = updated_at


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-caller rate limit + global concurrency cap on inference endpoints.

    Attributes:
        _enabled: Whether limiting is active.
        _capacity: Burst capacity (max tokens) per caller bucket.
        _refill_per_sec: Steady-state token refill rate per second.
        _semaphore: Global concurrency limiter for protected requests.
        _acquire_timeout: Max seconds to wait for a concurrency slot before 503.
    """

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        """Initialize middleware from settings.

        Args:
            app: Wrapped ASGI application.
            settings: Loaded application settings.
        """
        super().__init__(app)
        self._enabled = settings.rate_limit_enabled
        self._capacity = float(settings.rate_limit_analyze_burst)
        self._refill_per_sec = settings.rate_limit_analyze_per_minute / 60.0
        self._acquire_timeout = settings.inference_acquire_timeout_sec
        self._semaphore = asyncio.Semaphore(settings.inference_max_concurrency)
        self._buckets: dict[str, _TokenBucket] = {}
        # Per-process salt so Authorization-header hashes are not correlatable to
        # known token values from the logs/keys (defense in depth, not the bucket
        # identity which only needs stability within the process).
        self._salt = hashlib.sha256(str(id(self)).encode()).hexdigest()

    def _caller_key(self, request: Request) -> str:
        """Derive a stable per-caller bucket key available at middleware time.

        Args:
            request: Incoming request.

        Returns:
            Salted hash of the Authorization header, else the client host.
        """
        auth = request.headers.get("authorization")
        if auth:
            digest = hashlib.sha256(f"{self._salt}:{auth}".encode()).hexdigest()
            return f"tok:{digest}"
        client = request.client
        return f"ip:{client.host}" if client else "ip:unknown"

    def _check_rate(self, key: str) -> bool:
        """Consume one token for ``key``; return False when the bucket is empty.

        Args:
            key: Caller bucket key.

        Returns:
            True when a token was available (request allowed).
        """
        now = time.monotonic()
        bucket = self._buckets.get(key)
        if bucket is None:
            if len(self._buckets) >= _MAX_TRACKED_KEYS:
                self._evict_stale(now)
            self._buckets[key] = _TokenBucket(tokens=self._capacity - 1.0, updated_at=now)
            return True
        elapsed = now - bucket.updated_at
        bucket.tokens = min(self._capacity, bucket.tokens + elapsed * self._refill_per_sec)
        bucket.updated_at = now
        if bucket.tokens < 1.0:
            return False
        bucket.tokens -= 1.0
        return True

    def _evict_stale(self, now: float) -> None:
        """Drop buckets that have fully refilled (idle) to bound memory.

        Args:
            now: Current monotonic timestamp.
        """
        idle_after = self._capacity / self._refill_per_sec if self._refill_per_sec else 60.0
        stale = [
            key for key, bucket in self._buckets.items() if (now - bucket.updated_at) > idle_after
        ]
        for key in stale:
            del self._buckets[key]
        # If still saturated (all active), clear the oldest half as a hard backstop.
        if len(self._buckets) >= _MAX_TRACKED_KEYS:
            oldest = sorted(self._buckets.items(), key=lambda kv: kv[1].updated_at)
            for key, _ in oldest[: _MAX_TRACKED_KEYS // 2]:
                del self._buckets[key]

    @staticmethod
    def _too_many_requests() -> JSONResponse:
        """Build the structured 429 response matching the API error contract."""
        retry_after = 60
        return JSONResponse(
            status_code=429,
            content={
                "detail": {
                    "code": "rate_limited",
                    "message": "Rate limit exceeded. Please retry after a short delay.",
                    "retry_after_seconds": retry_after,
                }
            },
            headers={"Retry-After": str(retry_after)},
        )

    @staticmethod
    def _service_unavailable() -> JSONResponse:
        """Build the structured 503 response when the inference pool is saturated."""
        retry_after = 10
        return JSONResponse(
            status_code=503,
            content={
                "detail": {
                    "code": "inference_capacity_exceeded",
                    "message": "Analysis capacity is temporarily saturated. Please retry shortly.",
                    "retry_after_seconds": retry_after,
                }
            },
            headers={"Retry-After": str(retry_after)},
        )

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Apply rate limit + concurrency cap to protected paths only.

        Args:
            request: Incoming HTTP request.
            call_next: Downstream handler producing the response.

        Returns:
            Downstream response, or a 429/503 when a limit is exceeded.
        """
        if not self._enabled or not _is_rate_limited_path(request.url.path):
            return await call_next(request)

        if not self._check_rate(self._caller_key(request)):
            return self._too_many_requests()

        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=self._acquire_timeout)
        except TimeoutError:
            return self._service_unavailable()
        try:
            return await call_next(request)
        finally:
            self._semaphore.release()
