"""Factory helpers for regulated document OCR intake."""

from __future__ import annotations

from dataclasses import dataclass

from src.config import Settings
from src.ocr.base import OCRAdapter
from src.ocr.factory import OCRConfigurationError, build_supplement_ocr_adapter


@dataclass(frozen=True)
class RegulatedOCRAdapters:
    """Optional adapters for regulated OCR intake.

    Attributes:
        ocr: OCR adapter. When absent, the intake remains memory-only and manual-review only.
    """

    ocr: OCRAdapter | None = None


def build_regulated_ocr_adapters(settings: Settings) -> RegulatedOCRAdapters:
    """Build OCR adapters for regulated document intake.

    Args:
        settings: Runtime settings.

    Returns:
        Adapter bundle for regulated OCR intake.

    Raises:
        OCRConfigurationError: If requested OCR settings are incomplete or unsafe.
    """
    return RegulatedOCRAdapters(ocr=build_supplement_ocr_adapter(settings))


__all__ = ["OCRConfigurationError", "RegulatedOCRAdapters", "build_regulated_ocr_adapters"]
