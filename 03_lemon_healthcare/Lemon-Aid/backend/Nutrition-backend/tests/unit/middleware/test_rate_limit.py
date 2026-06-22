"""Unit tests for the inference-endpoint rate limit + concurrency middleware."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from src.config import Settings
from src.middleware.rate_limit import RateLimitMiddleware, _is_rate_limited_path


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "environment": "development",
        "auth_mode": "disabled",
        "rate_limit_enabled": True,
        "rate_limit_analyze_per_minute": 60,
        "rate_limit_analyze_burst": 3,
        "inference_max_concurrency": 2,
        "inference_acquire_timeout_sec": 0.1,
    }
    base.update(overrides)
    return Settings(**base)


def _app(settings: Settings) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, settings=settings)

    @app.post("/api/v1/supplements/analyze")
    async def analyze() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/health-unprotected")
    async def unprotected() -> dict[str, str]:
        return {"status": "ok"}

    return app


class TestPathMatching:
    def test_protected_paths(self) -> None:
        assert _is_rate_limited_path("/api/v1/supplements/analyze")
        assert _is_rate_limited_path("/api/v1/meals/analyze-image")
        assert _is_rate_limited_path("/api/v1/supplements/analysis-sessions/abc/images")

    def test_unprotected_paths(self) -> None:
        assert not _is_rate_limited_path("/api/v1/supplements/123/explain")
        assert not _is_rate_limited_path("/health")


class TestRateLimit:
    def test_allows_within_burst_then_429(self) -> None:
        client = TestClient(_app(_settings(rate_limit_analyze_burst=3)))
        # 3-token burst → first 3 succeed, 4th is limited.
        codes = [client.post("/api/v1/supplements/analyze").status_code for _ in range(4)]
        assert codes[:3] == [200, 200, 200]
        assert codes[3] == 429
        body = client.post("/api/v1/supplements/analyze").json()
        assert body["detail"]["code"] == "rate_limited"

    def test_unprotected_path_never_limited(self) -> None:
        client = TestClient(_app(_settings(rate_limit_analyze_burst=1)))
        codes = [client.get("/api/v1/health-unprotected").status_code for _ in range(5)]
        assert codes == [200, 200, 200, 200, 200]

    def test_disabled_bypasses_limit(self) -> None:
        client = TestClient(_app(_settings(rate_limit_enabled=False, rate_limit_analyze_burst=1)))
        codes = [client.post("/api/v1/supplements/analyze").status_code for _ in range(5)]
        assert codes == [200, 200, 200, 200, 200]

    def test_distinct_callers_have_separate_buckets(self) -> None:
        client = TestClient(_app(_settings(rate_limit_analyze_burst=1)))
        a = client.post("/api/v1/supplements/analyze", headers={"Authorization": "Bearer A"})
        b = client.post("/api/v1/supplements/analyze", headers={"Authorization": "Bearer B"})
        # Different tokens → different buckets → both first requests allowed.
        assert a.status_code == 200
        assert b.status_code == 200


class TestConcurrencyCap:
    def test_saturation_returns_503(self) -> None:
        # capacity 1, slow handler, generous rate limit so only concurrency bites.
        settings = _settings(
            inference_max_concurrency=1,
            inference_acquire_timeout_sec=0.1,
            rate_limit_analyze_per_minute=600,
            rate_limit_analyze_burst=50,
        )
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, settings=settings)

        @app.post("/api/v1/supplements/analyze")
        async def analyze() -> dict[str, str]:
            await asyncio.sleep(0.5)
            return {"status": "ok"}

        async def run() -> list[int]:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://t") as client:
                results = await asyncio.gather(
                    client.post("/api/v1/supplements/analyze"),
                    client.post("/api/v1/supplements/analyze"),
                )
                return [r.status_code for r in results]

        codes = asyncio.run(run())
        # One holds the single slot; the other times out acquiring → 503.
        assert 503 in codes
        assert 200 in codes


@pytest.mark.parametrize("burst", [1, 5, 20])
def test_burst_capacity_respected(burst: int) -> None:
    client = TestClient(
        _app(_settings(rate_limit_analyze_per_minute=600, rate_limit_analyze_burst=burst))
    )
    codes = [client.post("/api/v1/supplements/analyze").status_code for _ in range(burst + 1)]
    assert codes[:burst] == [200] * burst
    assert codes[burst] == 429
