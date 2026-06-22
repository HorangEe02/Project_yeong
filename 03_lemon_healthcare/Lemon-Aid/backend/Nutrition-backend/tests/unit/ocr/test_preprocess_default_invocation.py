"""Tests that the default ``autocontrast`` OCR preprocessing actually transforms.

Task #3 flips the ``local_ocr_preprocess_mode`` default from ``none`` to a
conservative ``autocontrast`` pass to reduce truncated/garbled fragments on
dense, low-contrast Korean labels. The default value itself is asserted in
``tests/unit/test_config.py``; these tests confirm the preprocessing function
invoked for that default genuinely enhances image bytes while remaining a
pass-through for ``none``.
"""

from __future__ import annotations

from io import BytesIO

from PIL import Image
from src.ocr.preprocessing import preprocess_local_ocr_image


def _low_contrast_png() -> bytes:
    """Return a low-contrast PNG that autocontrast should visibly stretch.

    Returns:
        PNG bytes whose pixel values occupy only a narrow mid-tone band so the
        autocontrast pass produces output that differs from the input.
    """
    image = Image.new("RGB", (8, 8), color=(120, 120, 120))
    image.putpixel((0, 0), (110, 110, 110))
    image.putpixel((7, 7), (130, 130, 130))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_autocontrast_mode_transforms_low_contrast_image() -> None:
    """The default ``autocontrast`` mode runs the enhancement and returns PNG bytes.

    Confirms the preprocessing branch is actually invoked for the new default
    (rather than the ``none`` pass-through) by checking the output is decodable
    PNG bytes that differ from a low-contrast input.
    """
    source = _low_contrast_png()

    processed_bytes, mime_type = preprocess_local_ocr_image(
        source, mime_type="image/png", mode="autocontrast"
    )

    assert mime_type == "image/png"
    assert processed_bytes != source
    # The result must still be a valid, decodable image.
    Image.open(BytesIO(processed_bytes)).load()


def test_none_mode_is_pass_through() -> None:
    """The ``none`` mode returns the input bytes and MIME type unchanged."""
    source = _low_contrast_png()

    processed_bytes, mime_type = preprocess_local_ocr_image(
        source, mime_type="image/png", mode="none"
    )

    assert processed_bytes == source
    assert mime_type == "image/png"
