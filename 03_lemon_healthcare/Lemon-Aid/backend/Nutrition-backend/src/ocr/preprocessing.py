"""Image preprocessing helpers used before OCR provider calls."""

from __future__ import annotations

from io import BytesIO
from typing import Literal

from PIL import Image, ImageOps, UnidentifiedImageError

from src.utils.image_safety import ImageSafetyError, safe_load_with_bomb_guard

LocalOCRPreprocessMode = Literal["none", "autocontrast", "grayscale_autocontrast"]


class OCRPreprocessingError(ValueError):
    """Raised when an image cannot be normalized for OCR."""


def normalize_image_for_ocr(image_bytes: bytes, *, max_side_px: int = 2048) -> bytes:
    """Normalize an uploaded label image to bounded RGB PNG bytes.

    Args:
        image_bytes: Validated source image bytes.
        max_side_px: Maximum width or height after normalization.

    Returns:
        PNG-encoded RGB image bytes.

    Raises:
        OCRPreprocessingError: If the image cannot be decoded or the size bound is invalid.
    """
    if max_side_px <= 0:
        raise OCRPreprocessingError("max_side_px must be positive.")

    try:
        source = safe_load_with_bomb_guard(image_bytes)
    except ImageSafetyError as exc:
        raise OCRPreprocessingError("Image cannot be decoded for OCR preprocessing.") from exc

    try:
        with source:
            normalized = source.convert("RGB")
            normalized.thumbnail((max_side_px, max_side_px), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            normalized.save(buffer, format="PNG", optimize=True)
            return buffer.getvalue()
    except (OSError, UnidentifiedImageError) as exc:
        raise OCRPreprocessingError("Image cannot be decoded for OCR preprocessing.") from exc


def preprocess_local_ocr_image(
    image_bytes: bytes,
    *,
    mime_type: str,
    mode: LocalOCRPreprocessMode,
    max_side_px: int = 2048,
) -> tuple[bytes, str]:
    """Apply opt-in local OCR preprocessing without persisting derived images.

    Args:
        image_bytes: Validated source image bytes.
        mime_type: Original MIME type used when ``mode`` is ``none``.
        mode: Local preprocessing mode. ``none`` returns input bytes unchanged.
        max_side_px: Maximum width or height after preprocessing.

    Returns:
        Image bytes and MIME type to pass to the local OCR adapter.

    Raises:
        OCRPreprocessingError: If the image cannot be decoded or the mode is unsupported.
    """
    if mode == "none":
        return image_bytes, mime_type
    if max_side_px <= 0:
        raise OCRPreprocessingError("max_side_px must be positive.")

    try:
        source = safe_load_with_bomb_guard(image_bytes)
    except ImageSafetyError as exc:
        raise OCRPreprocessingError("Image cannot be decoded for OCR preprocessing.") from exc

    try:
        with source:
            normalized = ImageOps.exif_transpose(source).convert("RGB")
            if mode == "autocontrast":
                processed = ImageOps.autocontrast(normalized)
            elif mode == "grayscale_autocontrast":
                processed = ImageOps.autocontrast(ImageOps.grayscale(normalized)).convert("RGB")
            else:  # pragma: no cover - Literal typing and Settings validation guard this.
                raise OCRPreprocessingError("Unsupported OCR preprocessing mode.")
            processed.thumbnail((max_side_px, max_side_px), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            processed.save(buffer, format="PNG", optimize=True)
            return buffer.getvalue(), "image/png"
    except (OSError, UnidentifiedImageError) as exc:
        raise OCRPreprocessingError("Image cannot be decoded for OCR preprocessing.") from exc
