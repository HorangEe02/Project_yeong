"""Image safety utilities: metadata strip + decompression-bomb guard.

Two complementary defenses for user-uploaded images:

1. ``strip_image_metadata`` removes EXIF/XMP/IPTC/ICC payloads before any
   downstream consumer (OCR, learning storage, audit logs) sees the bytes,
   while preserving visible pixel orientation.
2. ``configure_pillow_limits`` + ``safe_load_with_bomb_guard`` cap pixel
   counts process-wide and escalate :class:`PIL.Image.DecompressionBombWarning`
   to an error so a small-on-disk image that decodes to hundreds of
   megapixels is rejected before the worker is OOM'd.

The utilities are framework-free; they intentionally avoid importing any
service or settings module to prevent circular imports.
"""

from __future__ import annotations

import warnings
from io import BytesIO
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError


class ImageSafetyError(Exception):
    """Raised when image bytes cannot be safely normalized or loaded."""


_FORMAT_BY_MIME: dict[str, str] = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}
"""MIME → Pillow format identifier for supported supplement-label inputs."""


def configure_pillow_limits(max_pixels: int) -> None:
    """Apply process-wide Pillow safety limits at application startup.

    Call once during ``lifespan`` startup. Affects every ``PIL.Image``
    consumer in the process, including downstream Vision/OCR decoders.

    Args:
        max_pixels: Inclusive upper bound on decoded pixel count.

    Raises:
        ValueError: If ``max_pixels`` is not a positive integer.
    """
    if max_pixels <= 0:
        raise ValueError(f"max_pixels must be positive, got {max_pixels}")
    Image.MAX_IMAGE_PIXELS = max_pixels


def strip_image_metadata(data: bytes, mime: str) -> bytes:
    """Return image bytes with EXIF, XMP, and IPTC metadata removed.

    Pixel orientation is applied to the bitmap *before* the EXIF orientation
    tag is dropped, so the visible rotation matches the original file.

    Args:
        data: Source image bytes (JPEG/PNG/WebP).
        mime: Declared MIME type — used to choose the re-encode format.

    Returns:
        Sanitized image bytes with metadata removed.

    Raises:
        ImageSafetyError: If the MIME is unsupported or the image cannot be
            decoded or re-encoded.
    """
    fmt = _FORMAT_BY_MIME.get(mime)
    if fmt is None:
        raise ImageSafetyError(f"unsupported_mime: {mime}")

    try:
        with Image.open(BytesIO(data)) as source:
            oriented = ImageOps.exif_transpose(source) or source
            buf = BytesIO()
            save_kwargs: dict[str, Any] = {
                "format": fmt,
                "exif": b"",
                "xmp": b"",
            }
            if fmt == "JPEG":
                save_kwargs["icc_profile"] = b""
                save_kwargs["optimize"] = True
            oriented.save(buf, **save_kwargs)
            return buf.getvalue()
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        raise ImageSafetyError("strip_failed") from exc


def safe_load_with_bomb_guard(data: bytes) -> Image.Image:
    """Open image bytes while escalating ``DecompressionBombWarning`` to error.

    Pillow raises :class:`PIL.Image.DecompressionBombError` for images with
    pixel counts greater than 2x the configured ``MAX_IMAGE_PIXELS`` and emits
    a :class:`PIL.Image.DecompressionBombWarning` for images between the limit
    and the 2x threshold. This helper escalates the warning to an error so the
    intermediate range is also blocked, then forces a full decode with
    ``Image.load()`` to surface late-stage decode failures up front.

    Args:
        data: Image bytes to decode.

    Returns:
        A fully-loaded :class:`PIL.Image.Image`. The caller owns the returned
        instance and must close it (use ``with`` or ``image.close()``).

    Raises:
        ImageSafetyError: On decompression bomb, decode failure, or
            ``DecompressionBombWarning`` escalation.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(BytesIO(data))
            image.load()
            return image
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
        UnidentifiedImageError,
    ) as exc:
        raise ImageSafetyError("bomb_or_decode_failure") from exc
