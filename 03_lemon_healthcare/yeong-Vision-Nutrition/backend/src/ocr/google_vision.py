"""Google Cloud Vision OCR 구현 (Document Text Detection).

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-01-ocr-pipeline.md Step 4
    docs/dev-guides/07-ocr-pipeline.md §4
    docs/09-data-catalog.md §5.1
"""

from __future__ import annotations

import logging
import time
from typing import Any, Final

from google.api_core import exceptions as gapi_exceptions
from google.cloud import vision

from src.ocr.base import OCRAdapter, OCRResult
from src.ocr.exceptions import OCRApiError, OCRTimeoutError

logger = logging.getLogger(__name__)

CLIENT_TIMEOUT_SEC: Final[float] = 10.0
LANGUAGE_HINTS: Final[list[str]] = ["ko", "en"]


class GoogleVisionOCR(OCRAdapter):
    """Google Cloud Vision API 기반 OCR.

    Reference:
        docs/09-data-catalog.md §5.1
    """

    def __init__(self, client: vision.ImageAnnotatorClient | None = None) -> None:
        """클라이언트 초기화.

        Args:
            client: 의존성 주입용 클라이언트. ``None`` 이면 환경변수
                ``GOOGLE_APPLICATION_CREDENTIALS`` 를 사용해 자동 생성된다.
        """
        self._client = client or vision.ImageAnnotatorClient()

    @property
    def engine_name(self) -> str:
        """``"google_vision_v1"``."""
        return "google_vision_v1"

    async def extract_text(self, image_bytes: bytes) -> OCRResult:
        """이미지에서 텍스트 추출 (Document Text Detection).

        Args:
            image_bytes: 전처리된 JPEG 바이트.

        Returns:
            ``OCRResult``.

        Raises:
            OCRApiError: API 호출 실패.
            OCRTimeoutError: 타임아웃.
        """
        start = time.perf_counter()

        image = vision.Image(content=image_bytes)
        ctx = vision.ImageContext(language_hints=LANGUAGE_HINTS)

        try:
            response = self._client.document_text_detection(
                image=image,
                image_context=ctx,
                timeout=CLIENT_TIMEOUT_SEC,
            )
        except gapi_exceptions.DeadlineExceeded as exc:
            raise OCRTimeoutError(f"Cloud Vision timeout: {exc}") from exc
        except gapi_exceptions.GoogleAPIError as exc:
            raise OCRApiError(self.engine_name, str(exc)) from exc

        if response.error.message:
            raise OCRApiError(self.engine_name, response.error.message)

        elapsed_ms = (time.perf_counter() - start) * 1000
        full = response.full_text_annotation

        if not full or not getattr(full, "pages", None):
            return OCRResult(
                text="",
                confidence=0.0,
                engine=self.engine_name,
                elapsed_ms=elapsed_ms,
            )

        page_confs = [p.confidence for p in full.pages if p.confidence > 0]
        avg_conf = sum(page_confs) / len(page_confs) if page_confs else 0.0

        words: list[dict[str, Any]] = []
        for page in full.pages:
            for block in page.blocks:
                for paragraph in block.paragraphs:
                    for word in paragraph.words:
                        text_value = "".join(s.text for s in word.symbols)
                        words.append({"text": text_value, "confidence": word.confidence})

        logger.info(
            "Cloud Vision OCR completed",
            extra={
                "elapsed_ms": elapsed_ms,
                "confidence": avg_conf,
                "word_count": len(words),
            },
        )

        return OCRResult(
            text=full.text,
            confidence=avg_conf,
            engine=self.engine_name,
            words=words,
            elapsed_ms=elapsed_ms,
        )
