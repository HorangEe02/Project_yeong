"""Multilingual OCR adapter that chooses the higher-confidence provider result.

The adapter keeps the current OCR boundary intact: callers pass one validated
``OCRImageInput`` and receive one normalized ``OCRResult``. It does not store raw
images, log OCR text, or expose provider payloads.
"""

from __future__ import annotations

import asyncio
import logging

from src.ocr.base import OCRAdapter, OCRError, OCRImageInput, OCRResult

logger = logging.getLogger(__name__)


class MultilingualOCRAdapter(OCRAdapter):
    """Call two OCR adapters concurrently and return the better result.

    Attributes:
        primary: Preferred adapter when both confidence values are tied.
        secondary: Fallback adapter used for alternate language/model coverage.
    """

    def __init__(self, primary: OCRAdapter, secondary: OCRAdapter) -> None:
        """Initialize the multilingual OCR adapter.

        Args:
            primary: First OCR adapter. Wins confidence ties.
            secondary: Second OCR adapter.
        """
        self._primary = primary
        self._secondary = secondary

    async def extract_text(self, image: OCRImageInput) -> OCRResult:
        """Run both adapters and return the higher-confidence OCR result.

        Args:
            image: Validated image payload shared by both adapters.

        Returns:
            OCR result from the selected adapter. A ``None`` confidence is treated
            as lower than any numeric confidence.

        Raises:
            OCRError: If both adapters fail.
        """
        primary_task = asyncio.create_task(self._primary.extract_text(image))
        secondary_task = asyncio.create_task(self._secondary.extract_text(image))

        primary_result, secondary_result = await asyncio.gather(
            primary_task,
            secondary_task,
            return_exceptions=True,
        )

        primary_ok = isinstance(primary_result, OCRResult)
        secondary_ok = isinstance(secondary_result, OCRResult)

        if primary_ok and secondary_ok:
            chosen = self._pick_higher_confidence(primary_result, secondary_result)
            logger.info(
                "Multilingual OCR completed",
                extra={
                    "chosen_provider": chosen.provider,
                    "primary_provider": primary_result.provider,
                    "secondary_provider": secondary_result.provider,
                    "primary_confidence": primary_result.confidence,
                    "secondary_confidence": secondary_result.confidence,
                },
            )
            return chosen

        if primary_ok and not secondary_ok:
            assert isinstance(secondary_result, BaseException)
            logger.warning(
                "Secondary OCR failed, falling back to primary",
                extra={
                    "primary_provider": primary_result.provider,
                    "secondary_error_type": secondary_result.__class__.__name__,
                },
            )
            return primary_result

        if secondary_ok and not primary_ok:
            assert isinstance(primary_result, BaseException)
            logger.warning(
                "Primary OCR failed, falling back to secondary",
                extra={
                    "primary_error_type": primary_result.__class__.__name__,
                    "secondary_provider": secondary_result.provider,
                },
            )
            return secondary_result

        assert isinstance(primary_result, BaseException)
        assert isinstance(secondary_result, BaseException)
        logger.error(
            "Both OCR adapters failed",
            extra={
                "primary_error_type": primary_result.__class__.__name__,
                "secondary_error_type": secondary_result.__class__.__name__,
            },
        )
        if isinstance(primary_result, OCRError):
            raise primary_result
        raise OCRError("Both multilingual OCR adapters failed.") from primary_result

    @staticmethod
    def _pick_higher_confidence(a: OCRResult, b: OCRResult) -> OCRResult:
        """Return the higher-confidence result, using ``a`` for ties.

        Args:
            a: Primary adapter result.
            b: Secondary adapter result.

        Returns:
            Higher-confidence result, or ``a`` when confidence values tie.
        """
        a_confidence = a.confidence if a.confidence is not None else float("-inf")
        b_confidence = b.confidence if b.confidence is not None else float("-inf")
        if b_confidence > a_confidence:
            return b
        return a
