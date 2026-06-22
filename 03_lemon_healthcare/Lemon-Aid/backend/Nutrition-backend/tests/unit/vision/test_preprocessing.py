"""Vision preprocessing helper tests."""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image
from src.vision.base import BoundingBox
from src.vision.preprocessing import (
    VisionPreprocessingError,
    clamp_bounding_box,
    crop_image_to_bounding_box,
    expand_bounding_box,
    select_best_label_region,
)


def _png_bytes(width: int = 10, height: int = 8) -> bytes:
    """Return a PNG fixture.

    Args:
        width: Image width.
        height: Image height.

    Returns:
        Encoded PNG bytes.
    """
    buffer = BytesIO()
    Image.new("RGB", (width, height), color=(255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_clamp_bounding_box_limits_region_to_image_bounds() -> None:
    """Verify detector boxes are clipped to decoded image dimensions."""
    clamped = clamp_bounding_box(
        BoundingBox(
            x=-2,
            y=1,
            width=20,
            height=10,
            confidence=0.82,
            label="supplement_label",
            model="test-yolo",
        ),
        image_width=10,
        image_height=8,
    )

    assert clamped == BoundingBox(
        x=0,
        y=1,
        width=10,
        height=7,
        confidence=0.82,
        label="supplement_label",
        model="test-yolo",
    )


def test_clamp_bounding_box_rejects_non_overlapping_region() -> None:
    """Verify boxes outside the image do not become zero-size crops."""
    with pytest.raises(VisionPreprocessingError):
        clamp_bounding_box(
            BoundingBox(x=20, y=20, width=5, height=5, confidence=0.8),
            image_width=10,
            image_height=8,
        )


def test_select_best_label_region_prefers_label_over_higher_confidence_bottle() -> None:
    """Verify label ROI wins because YOLO confidence is not product identity confidence."""
    selected = select_best_label_region(
        [
            BoundingBox(
                x=0,
                y=0,
                width=10,
                height=8,
                confidence=0.99,
                label="supplement_bottle",
            ),
            BoundingBox(
                x=1,
                y=1,
                width=6,
                height=4,
                confidence=0.60,
                label="supplement_label",
            ),
        ]
    )

    assert selected.label == "supplement_label"
    assert selected.confidence == 0.60


def test_crop_image_to_bounding_box_returns_cropped_image() -> None:
    """Verify a valid ROI crop produces a decodable image."""
    cropped = crop_image_to_bounding_box(
        _png_bytes(),
        BoundingBox(x=2, y=1, width=4, height=3, confidence=0.9),
    )

    with Image.open(BytesIO(cropped)) as image:
        assert image.size == (4, 3)


def test_crop_image_to_bounding_box_applies_bounded_padding() -> None:
    """Verify OCR ROI padding adds context while staying inside the source image."""
    cropped = crop_image_to_bounding_box(
        _png_bytes(),
        BoundingBox(x=2, y=1, width=4, height=3, confidence=0.9),
        padding_ratio=0.25,
        min_padding_px=1,
        max_padding_px=2,
    )

    with Image.open(BytesIO(cropped)) as image:
        assert image.size == (6, 5)


def test_expand_bounding_box_clamps_padding_to_image_bounds() -> None:
    """Verify padded detector boxes are clipped instead of losing OCR edge text."""
    expanded = expand_bounding_box(
        BoundingBox(x=1, y=1, width=4, height=3, confidence=0.9, label="ingredient_amounts"),
        image_width=10,
        image_height=8,
        padding_ratio=0.5,
        min_padding_px=2,
        max_padding_px=4,
    )

    assert expanded == BoundingBox(
        x=0,
        y=0,
        width=7,
        height=6,
        confidence=0.9,
        label="ingredient_amounts",
    )


def test_crop_image_to_bounding_box_rejects_out_of_bounds_region() -> None:
    """Verify invalid crops fail before downstream OCR or vision assist calls."""
    with pytest.raises(VisionPreprocessingError):
        crop_image_to_bounding_box(
            _png_bytes(),
            BoundingBox(x=8, y=1, width=4, height=3, confidence=0.9),
        )
