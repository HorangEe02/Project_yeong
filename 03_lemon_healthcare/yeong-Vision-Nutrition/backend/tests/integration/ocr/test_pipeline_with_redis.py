"""``OCRPipeline`` + 실제 Redis 통합 — testcontainers Redis 7 컨테이너 사용.

Docker daemon이 필요하다. ``pytest -m "not integration"`` 으로 건너뛸 수 있다.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-01-ocr-pipeline.md Step 8
"""

from __future__ import annotations

import io

import pytest
import redis.asyncio as redis_async
from PIL import Image
from src.cache.ocr_cache import OCRCache
from src.ocr.base import OCRAdapter, OCRResult
from src.ocr.pipeline import OCRPipeline

pytestmark = pytest.mark.integration


class _CountingAdapter(OCRAdapter):
    """호출 횟수 추적용 미니 Adapter."""

    def __init__(self) -> None:
        self.call_count = 0

    @property
    def engine_name(self) -> str:
        return "counting"

    async def extract_text(self, image_bytes: bytes) -> OCRResult:
        self.call_count += 1
        return OCRResult(
            text=f"call-{self.call_count}",
            confidence=0.95,
            engine=self.engine_name,
        )


def _sample_jpeg() -> bytes:
    img = Image.new("RGB", (400, 400), color=(120, 60, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_pipeline_caches_to_real_redis() -> None:
    """실 Redis (testcontainers) 백엔드에서 OCR 결과가 round-trip 된다."""
    from testcontainers.redis import RedisContainer

    with RedisContainer("redis:7-alpine") as container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        client = redis_async.from_url(
            f"redis://{host}:{port}/0",
            decode_responses=False,
        )
        try:
            cache = OCRCache(client, ttl_seconds=60)
            adapter = _CountingAdapter()
            pipe = OCRPipeline(primary=adapter, cache=cache)

            sample = _sample_jpeg()
            first = await pipe.extract(sample)
            second = await pipe.extract(sample)

            assert first.text == second.text == "call-1"
            assert adapter.call_count == 1
        finally:
            await client.aclose()
