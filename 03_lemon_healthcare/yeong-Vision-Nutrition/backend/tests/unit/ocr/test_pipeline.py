"""``OCRPipeline`` 단위 테스트 — primary / secondary / cache 분기 검증.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-01-ocr-pipeline.md Step 6
"""

from __future__ import annotations

import io

import pytest
from fakeredis import FakeAsyncRedis
from PIL import Image
from src.cache.ocr_cache import OCRCache
from src.ocr.base import OCRAdapter, OCRResult
from src.ocr.exceptions import OCRApiError, OCRError
from src.ocr.pipeline import OCRPipeline


class FakeOCRAdapter(OCRAdapter):
    """테스트용 OCR Adapter — 호출 횟수와 응답을 제어한다."""

    def __init__(
        self,
        text: str = "ok",
        confidence: float = 0.95,
        engine: str = "fake",
        raises: Exception | None = None,
    ) -> None:
        self._text = text
        self._confidence = confidence
        self._engine = engine
        self._raises = raises
        self.call_count = 0

    @property
    def engine_name(self) -> str:
        return self._engine

    async def extract_text(self, image_bytes: bytes) -> OCRResult:
        self.call_count += 1
        if self._raises is not None:
            raise self._raises
        return OCRResult(
            text=self._text,
            confidence=self._confidence,
            engine=self._engine,
        )


def _sample_jpeg() -> bytes:
    """전처리를 통과할 수 있는 표준 JPEG."""
    img = Image.new("RGB", (400, 400), color=(10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestPipelinePrimaryOnly:
    @pytest.mark.asyncio
    async def test_primary_high_conf_returns_directly(self) -> None:
        primary = FakeOCRAdapter(text="ok", confidence=0.95)
        pipe = OCRPipeline(primary=primary)
        result = await pipe.extract(_sample_jpeg())
        assert result.text == "ok"
        assert primary.call_count == 1

    @pytest.mark.asyncio
    async def test_primary_low_conf_no_secondary_returns_primary(self) -> None:
        """secondary가 없으면 신뢰도가 낮아도 primary 결과 그대로."""
        primary = FakeOCRAdapter(text="low", confidence=0.4)
        pipe = OCRPipeline(primary=primary)
        result = await pipe.extract(_sample_jpeg())
        assert result.confidence == 0.4
        assert result.text == "low"

    @pytest.mark.asyncio
    async def test_primary_raises_no_secondary_raises_ocr_error(self) -> None:
        primary = FakeOCRAdapter(raises=OCRApiError("fake", "boom"))
        pipe = OCRPipeline(primary=primary)
        with pytest.raises(OCRError):
            await pipe.extract(_sample_jpeg())


class TestPipelineWithSecondary:
    @pytest.mark.asyncio
    async def test_high_conf_skips_secondary(self) -> None:
        primary = FakeOCRAdapter(text="ok", confidence=0.95, engine="p")
        secondary = FakeOCRAdapter(text="never", confidence=0.99, engine="s")
        pipe = OCRPipeline(primary=primary, secondary=secondary)
        await pipe.extract(_sample_jpeg())
        assert secondary.call_count == 0

    @pytest.mark.asyncio
    async def test_low_conf_secondary_higher_wins(self) -> None:
        primary = FakeOCRAdapter(text="low", confidence=0.5, engine="p")
        secondary = FakeOCRAdapter(text="better", confidence=0.9, engine="s")
        pipe = OCRPipeline(primary=primary, secondary=secondary)
        result = await pipe.extract(_sample_jpeg())
        assert result.engine == "s"
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_low_conf_secondary_lower_returns_primary(self) -> None:
        primary = FakeOCRAdapter(text="primary", confidence=0.6, engine="p")
        secondary = FakeOCRAdapter(text="worse", confidence=0.3, engine="s")
        pipe = OCRPipeline(primary=primary, secondary=secondary)
        result = await pipe.extract(_sample_jpeg())
        assert result.engine == "p"

    @pytest.mark.asyncio
    async def test_primary_fails_secondary_recovers(self) -> None:
        primary = FakeOCRAdapter(raises=OCRApiError("p", "boom"))
        secondary = FakeOCRAdapter(text="recovered", confidence=0.9, engine="s")
        pipe = OCRPipeline(primary=primary, secondary=secondary)
        result = await pipe.extract(_sample_jpeg())
        assert result.engine == "s"
        assert result.text == "recovered"

    @pytest.mark.asyncio
    async def test_both_fail_raises(self) -> None:
        primary = FakeOCRAdapter(raises=OCRApiError("p", "boom"))
        secondary = FakeOCRAdapter(raises=OCRApiError("s", "also boom"))
        pipe = OCRPipeline(primary=primary, secondary=secondary)
        with pytest.raises(OCRError):
            await pipe.extract(_sample_jpeg())


class TestPipelineCache:
    @pytest.mark.asyncio
    async def test_cache_hit_skips_primary(self) -> None:
        """동일 이미지 두 번째 호출 시 primary가 호출되지 않는다."""
        redis = FakeAsyncRedis()
        cache = OCRCache(redis, ttl_seconds=60)
        primary = FakeOCRAdapter(text="first", confidence=0.95)
        pipe = OCRPipeline(primary=primary, cache=cache)
        sample = _sample_jpeg()

        first = await pipe.extract(sample)
        second = await pipe.extract(sample)

        assert first.text == second.text == "first"
        assert primary.call_count == 1  # 두 번째는 캐시 hit

    @pytest.mark.asyncio
    async def test_cache_persists_across_pipeline_instances(self) -> None:
        """동일 Redis 인스턴스를 공유하면 다른 파이프라인도 캐시를 본다."""
        redis = FakeAsyncRedis()
        cache_a = OCRCache(redis, ttl_seconds=60)
        cache_b = OCRCache(redis, ttl_seconds=60)
        primary_a = FakeOCRAdapter(text="fresh", confidence=0.92)
        primary_b = FakeOCRAdapter(text="different", confidence=0.5)
        pipe_a = OCRPipeline(primary=primary_a, cache=cache_a)
        pipe_b = OCRPipeline(primary=primary_b, cache=cache_b)
        sample = _sample_jpeg()

        await pipe_a.extract(sample)
        result_b = await pipe_b.extract(sample)

        assert result_b.text == "fresh"  # cache_a가 저장한 것
        assert primary_b.call_count == 0
