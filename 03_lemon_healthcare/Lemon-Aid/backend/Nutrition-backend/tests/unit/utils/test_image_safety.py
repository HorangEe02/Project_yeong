"""Unit tests for ``src.utils.image_safety``."""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image
from src.utils.image_safety import (
    ImageSafetyError,
    configure_pillow_limits,
    safe_load_with_bomb_guard,
    strip_image_metadata,
)

GPSINFO_TAG = 0x8825
ORIENTATION_TAG = 0x0112
SOFTWARE_TAG = 0x0131
MAKE_TAG = 0x010F


def _jpeg_with_identifying_exif() -> bytes:
    """Build a small JPEG embedding identifying EXIF tags + a GPS sub-IFD.

    The GPS sub-IFD uses ``get_ifd`` so Pillow writes the offset cleanly,
    and the Make/Software fields stand in for device/app fingerprints that
    the sanitizer must drop.

    Returns:
        Bytes of a 16x12 JPEG carrying GPS, Software, and Make EXIF entries.
    """
    base = Image.new("RGB", (16, 12), color=(220, 30, 30))
    buf = BytesIO()
    exif = base.getexif()
    exif[SOFTWARE_TAG] = "lemon-test-suite"
    exif[MAKE_TAG] = "TestPhone"
    gps_ifd = exif.get_ifd(GPSINFO_TAG)
    gps_ifd[1] = "N"
    gps_ifd[3] = "E"
    base.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


def _jpeg_with_orientation(orientation: int) -> bytes:
    """Build a small JPEG with the requested EXIF orientation tag.

    Args:
        orientation: EXIF orientation value.

    Returns:
        Bytes of a 100x50 JPEG carrying the orientation tag.
    """
    base = Image.new("RGB", (100, 50), color=(0, 200, 0))
    buf = BytesIO()
    exif = base.getexif()
    exif[ORIENTATION_TAG] = orientation
    base.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


def _normal_png() -> bytes:
    """Return a small in-bounds PNG used for the bomb-guard happy path."""
    buf = BytesIO()
    Image.new("RGB", (100, 100), color=(10, 10, 10)).save(buf, format="PNG")
    return buf.getvalue()


def _oversized_png() -> bytes:
    """Return a PNG decoding to 36 Mpx so the bomb guard rejects it."""
    buf = BytesIO()
    Image.new("L", (6000, 6000), color=0).save(buf, format="PNG", optimize=False)
    return buf.getvalue()


def test_strip_removes_identifying_exif_and_xmp() -> None:
    """Verify GPS IFD, Make, Software, and XMP payloads are absent after stripping."""
    source = _jpeg_with_identifying_exif()
    with Image.open(BytesIO(source)) as before:
        before_exif = before.getexif()
        assert before_exif.get(SOFTWARE_TAG) == "lemon-test-suite"
        assert before_exif.get(MAKE_TAG) == "TestPhone"
        assert before_exif.get_ifd(GPSINFO_TAG).get(1) == "N"

    sanitized = strip_image_metadata(source, "image/jpeg")
    with Image.open(BytesIO(sanitized)) as after:
        after_exif = after.getexif()
        assert after_exif.get(SOFTWARE_TAG) is None
        assert after_exif.get(MAKE_TAG) is None
        assert after_exif.get_ifd(GPSINFO_TAG) == {}
        assert "xmp" not in after.info


def test_strip_preserves_visible_orientation() -> None:
    """Verify EXIF orientation is baked into pixels and tag is removed."""
    sanitized = strip_image_metadata(_jpeg_with_orientation(6), "image/jpeg")
    with Image.open(BytesIO(sanitized)) as image:
        assert image.size == (50, 100)
        assert image.getexif().get(ORIENTATION_TAG) in (None, 1)


def test_strip_rejects_unsupported_mime() -> None:
    """Verify unsupported MIME types raise ``ImageSafetyError`` immediately."""
    with pytest.raises(ImageSafetyError, match="unsupported_mime"):
        strip_image_metadata(b"\x00\x01", "image/gif")


def test_strip_rejects_corrupt_bytes() -> None:
    """Verify malformed bytes raise ``ImageSafetyError`` instead of leaking PIL errors."""
    with pytest.raises(ImageSafetyError, match="strip_failed"):
        strip_image_metadata(b"not-a-real-jpeg", "image/jpeg")


def test_safe_load_accepts_normal_image() -> None:
    """Verify the bomb guard loads a normal image to completion."""
    configure_pillow_limits(12_000_000)
    image = safe_load_with_bomb_guard(_normal_png())
    try:
        assert image.size == (100, 100)
    finally:
        image.close()


def test_safe_load_rejects_oversized_image() -> None:
    """Verify the bomb guard rejects images exceeding the configured pixel cap."""
    configure_pillow_limits(12_000_000)
    with pytest.raises(ImageSafetyError, match="bomb_or_decode_failure"):
        safe_load_with_bomb_guard(_oversized_png())


def test_safe_load_rejects_corrupt_bytes() -> None:
    """Verify the bomb guard converts decode failure into ``ImageSafetyError``."""
    configure_pillow_limits(12_000_000)
    with pytest.raises(ImageSafetyError, match="bomb_or_decode_failure"):
        safe_load_with_bomb_guard(b"not-an-image")


def test_configure_pillow_limits_rejects_nonpositive() -> None:
    """Verify the safety limit configuration refuses zero or negative caps."""
    with pytest.raises(ValueError, match="positive"):
        configure_pillow_limits(0)
    with pytest.raises(ValueError, match="positive"):
        configure_pillow_limits(-1)
