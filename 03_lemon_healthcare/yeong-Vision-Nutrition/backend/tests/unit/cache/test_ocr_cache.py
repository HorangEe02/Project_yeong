"""``OCRCache`` 단위 테스트 — ``fakeredis`` 인메모리 백엔드.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-01-ocr-pipeline.md Step 5
"""

from __future__ import annotations

from typing import Any

import pytest
from fakeredis import FakeAsyncRedis
from src.cache.ocr_cache import CACHE_PREFIX, OCRCache, hash_image
from src.ocr.base import OCRResult


@pytest.fixture
def fake_redis() -> FakeAsyncRedis:
    """인메모리 fakeredis 인스턴스."""
    return FakeAsyncRedis()


@pytest.fixture
def cache(fake_redis: FakeAsyncRedis) -> OCRCache:
    return OCRCache(redis_client=fake_redis, ttl_seconds=3600)


class TestHashImage:
    def test_same_bytes_same_hash(self) -> None:
        assert hash_image(b"abc") == hash_image(b"abc")

    def test_different_bytes_different_hash(self) -> None:
        assert hash_image(b"abc") != hash_image(b"abd")

    def test_empty_bytes_known_sha256(self) -> None:
        """SHA-256 of empty string 알려진 값."""
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert hash_image(b"") == expected

    def test_returns_hex_string_64_chars(self) -> None:
        digest = hash_image(b"any input")
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)


class TestOCRCacheRoundTrip:
    @pytest.mark.asyncio
    async def test_get_returns_none_when_miss(self, cache: OCRCache) -> None:
        assert await cache.get(b"never cached") is None

    @pytest.mark.asyncio
    async def test_set_then_get_returns_equivalent_result(
        self,
        cache: OCRCache,
    ) -> None:
        original = OCRResult(
            text="비타민 C 1000mg",
            confidence=0.91,
            engine="google_vision_v1",
            words=[{"text": "비타민", "confidence": 0.93}],
            elapsed_ms=850.0,
        )
        await cache.set(b"image-bytes", original)
        retrieved = await cache.get(b"image-bytes")
        assert retrieved is not None
        assert retrieved.text == original.text
        assert retrieved.confidence == original.confidence
        assert retrieved.engine == original.engine
        assert retrieved.words == original.words
        assert retrieved.elapsed_ms == original.elapsed_ms

    @pytest.mark.asyncio
    async def test_korean_text_round_trips_intact(self, cache: OCRCache) -> None:
        """한글 텍스트가 ``ensure_ascii=False`` 로 손상 없이 유지되는지."""
        original = OCRResult(
            text="종합 영양제 — 비타민 D₃ 25μg (1000 IU)",
            confidence=0.88,
            engine="google_vision_v1",
        )
        await cache.set(b"korean", original)
        retrieved = await cache.get(b"korean")
        assert retrieved is not None
        assert retrieved.text == original.text


class TestOCRCacheCorruption:
    @pytest.mark.asyncio
    async def test_corrupted_cache_entry_returns_none(
        self,
        cache: OCRCache,
        fake_redis: FakeAsyncRedis,
    ) -> None:
        """JSON 디코드 실패 시 조용히 ``None`` 으로 떨어진다 (재계산 유도)."""
        key = f"{CACHE_PREFIX}{hash_image(b'corrupt-key')}"
        await fake_redis.set(key, b"not-valid-json-at-all")
        assert await cache.get(b"corrupt-key") is None

    @pytest.mark.asyncio
    async def test_missing_required_field_returns_none(
        self,
        cache: OCRCache,
        fake_redis: FakeAsyncRedis,
    ) -> None:
        """필수 필드 누락 JSON 도 ``None`` 처리."""
        import json

        key = f"{CACHE_PREFIX}{hash_image(b'partial')}"
        await fake_redis.set(key, json.dumps({"text": "x"}).encode())
        assert await cache.get(b"partial") is None


class TestOCRCacheConstruction:
    def test_zero_ttl_raises(self, fake_redis: FakeAsyncRedis) -> None:
        with pytest.raises(ValueError):
            OCRCache(redis_client=fake_redis, ttl_seconds=0)

    def test_negative_ttl_raises(self, fake_redis: FakeAsyncRedis) -> None:
        with pytest.raises(ValueError):
            OCRCache(redis_client=fake_redis, ttl_seconds=-1)


class TestOCRCacheTTL:
    @pytest.mark.asyncio
    async def test_ttl_applied_to_key(
        self,
        cache: OCRCache,
        fake_redis: FakeAsyncRedis,
    ) -> None:
        """``setex`` 가 호출돼 키에 TTL 이 붙어야 한다."""
        await cache.set(b"check-ttl", OCRResult(text="x", confidence=0.5, engine="e"))
        key = f"{CACHE_PREFIX}{hash_image(b'check-ttl')}"
        ttl: Any = await fake_redis.ttl(key)
        assert ttl > 0
