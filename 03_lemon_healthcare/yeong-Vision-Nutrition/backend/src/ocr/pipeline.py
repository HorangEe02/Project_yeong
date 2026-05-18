"""OCR 통합 파이프라인 — 전처리 + 캐싱 + (옵션) 보조 엔진 슬롯.

트랙 B는 ``primary`` 단일 채널만 운영한다. ``secondary`` 슬롯은 인터페이스를
보존하기 위해 키워드 인자로 유지하되 기본값 ``None`` 이며, 호출되지 않는다.
트랙 C에서 CLOVA 같은 보조 어댑터를 주입하는 경로로 사용한다.

동작:
    1. ``preprocessor.preprocess_image`` 로 전처리 (보안 게이트 + 정규화).
    2. ``cache`` 가 있으면 처리된 이미지 해시로 조회.
    3. 캐시 미스 → ``primary.extract_text`` 호출.
    4. (트랙 C 경로) 신뢰도가 임계 미만이거나 primary 실패 시 ``secondary`` 호출
       — 더 높은 신뢰도 결과를 선택.
    5. 성공 결과를 캐시에 저장.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-01-ocr-pipeline.md Step 6
    docs/dev-guides/07-ocr-pipeline.md §7
"""

from __future__ import annotations

import logging

from src.cache.ocr_cache import OCRCache
from src.ocr.base import CONFIDENCE_HIGH_THRESHOLD, OCRAdapter, OCRResult
from src.ocr.exceptions import OCRApiError, OCRError
from src.ocr.preprocessor import preprocess_image

logger = logging.getLogger(__name__)


class OCRPipeline:
    """전처리 + 캐싱 + (옵션) 보조 엔진을 묶는 파이프라인."""

    def __init__(
        self,
        primary: OCRAdapter,
        secondary: OCRAdapter | None = None,
        cache: OCRCache | None = None,
    ) -> None:
        """파이프라인 초기화.

        Args:
            primary: 주력 OCR Adapter (트랙 B: Google Cloud Vision).
            secondary: 트랙 B는 ``None``. 인터페이스 보존용 슬롯.
            cache: ``OCRCache`` 또는 ``None`` (캐시 비활성).
        """
        self._primary = primary
        self._secondary = secondary
        self._cache = cache

    async def extract(self, image_bytes: bytes) -> OCRResult:
        """파이프라인 실행.

        Args:
            image_bytes: 원본 이미지 바이트.

        Returns:
            ``OCRResult`` — 캐시 hit, primary, 또는 secondary 결과.

        Raises:
            OCRError: 모든 엔진이 실패한 경우.
            OCRSecurityError: 전처리 단계의 보안 게이트 위반.
            OCRImageError: 전처리 단계의 이미지 검증 실패.
        """
        processed = preprocess_image(image_bytes)

        if self._cache is not None:
            hit = await self._cache.get(processed)
            if hit is not None:
                logger.info("OCR cache hit", extra={"engine": hit.engine})
                return hit

        primary_result: OCRResult | None
        try:
            primary_result = await self._primary.extract_text(processed)
            logger.info(
                "Primary OCR completed",
                extra={
                    "engine": primary_result.engine,
                    "confidence": primary_result.confidence,
                },
            )
        except OCRApiError as exc:
            logger.warning("Primary OCR failed: %s", exc)
            primary_result = None

        result = await self._maybe_consult_secondary(processed, primary_result)

        if self._cache is not None:
            await self._cache.set(processed, result)

        return result

    async def _maybe_consult_secondary(
        self,
        processed: bytes,
        primary_result: OCRResult | None,
    ) -> OCRResult:
        """보조 엔진 호출 여부를 판단해 최종 결과를 결정한다.

        Args:
            processed: 전처리된 이미지 바이트.
            primary_result: ``primary`` 호출 결과 (실패 시 ``None``).

        Returns:
            최종 ``OCRResult``.

        Raises:
            OCRError: 둘 다 실패한 경우.
        """
        should_consult = primary_result is None or (
            primary_result.confidence < CONFIDENCE_HIGH_THRESHOLD
        )

        if not should_consult:
            assert primary_result is not None  # for mypy
            return primary_result

        if self._secondary is None:
            if primary_result is None:
                raise OCRError("Primary OCR failed and no secondary configured")
            return primary_result

        try:
            secondary_result = await self._secondary.extract_text(processed)
            logger.info(
                "Secondary OCR completed",
                extra={
                    "engine": secondary_result.engine,
                    "confidence": secondary_result.confidence,
                },
            )
        except OCRApiError as exc:
            logger.warning("Secondary OCR failed: %s", exc)
            if primary_result is None:
                raise OCRError("All OCR engines failed") from exc
            return primary_result

        if primary_result is None or secondary_result.confidence > primary_result.confidence:
            return secondary_result
        return primary_result
