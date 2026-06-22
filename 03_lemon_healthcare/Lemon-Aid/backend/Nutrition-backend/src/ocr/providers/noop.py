"""No-op OCR provider used when OCR execution is intentionally disabled."""

from __future__ import annotations

from src.ocr.base import OCRAdapter, OCRImageInput, OCRResult


class NoopOCRAdapter(OCRAdapter):
    """OCR adapter that returns no text and performs no provider calls.

    This adapter is useful for intake-only environments where image upload should
    create a review preview but text extraction is not yet enabled.
    """

    async def extract_text(self, image: OCRImageInput) -> OCRResult:
        """Return an empty OCR result without touching external services.

        Args:
            image: Validated image payload. The payload is intentionally ignored.

        Returns:
            Empty OCR result with provider ``noop``.
        """
        _ = image
        return OCRResult(text="", provider="noop", confidence=None)
