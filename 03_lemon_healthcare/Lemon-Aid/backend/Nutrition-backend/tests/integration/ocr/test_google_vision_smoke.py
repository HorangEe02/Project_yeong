"""Opt-in Google Vision OCR smoke test.

This test is skipped unless RUN_GOOGLE_VISION_SMOKE=1 and a local sample image path
are provided. Credentials and sample images must not be committed to the repository.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from src.config import Settings
from src.ocr.base import OCRImageInput
from src.ocr.factory import build_supplement_ocr_adapter
from src.ocr.providers.google_vision import GoogleVisionOCRAdapter

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_GOOGLE_VISION_SMOKE") != "1",
    reason="Google Vision smoke test requires RUN_GOOGLE_VISION_SMOKE=1.",
)


@pytest.mark.asyncio
async def test_google_vision_smoke_returns_non_empty_text() -> None:
    """Verify a real opt-in Google Vision call returns text for a local sample image."""
    image_path_value = os.getenv("GOOGLE_VISION_SMOKE_IMAGE_PATH")
    assert image_path_value, "GOOGLE_VISION_SMOKE_IMAGE_PATH is required."
    image_path = Path(image_path_value)
    image_bytes = image_path.read_bytes()
    mime_type = _mime_type_for_path(image_path)
    settings = Settings(_env_file=None)
    adapter = build_supplement_ocr_adapter(settings)

    assert isinstance(adapter, GoogleVisionOCRAdapter)
    result = await adapter.extract_text(
        OCRImageInput(
            image_bytes=image_bytes,
            mime_type=mime_type,
            width=1,
            height=1,
        )
    )

    assert result.text.strip()
    assert result.provider == "google_vision_document"


def _mime_type_for_path(path: Path) -> str:
    """Infer an accepted image MIME type from a smoke image path.

    Args:
        path: Local smoke image path.

    Returns:
        Image MIME type.
    """
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"
