"""Vision preprocessing helpers for supplement label ROI handling."""

from __future__ import annotations

from io import BytesIO

from PIL import UnidentifiedImageError

from src.utils.image_safety import ImageSafetyError, safe_load_with_bomb_guard
from src.vision.base import BoundingBox
from src.vision.taxonomy import label_priority


class VisionPreprocessingError(ValueError):
    """Raised when a detected label region cannot be applied to an image."""


def clamp_bounding_box(box: BoundingBox, *, image_width: int, image_height: int) -> BoundingBox:
    """Clamp a detected bounding box to decoded image boundaries.

    Args:
        box: Candidate detector output in input-image pixel coordinates.
        image_width: Decoded source image width in pixels.
        image_height: Decoded source image height in pixels.

    Returns:
        Bounding box clipped to the image extent.

    Raises:
        VisionPreprocessingError: If the image or clamped region is invalid.
    """
    if image_width <= 0 or image_height <= 0:
        raise VisionPreprocessingError("Image dimensions must be positive.")

    left = max(0, min(round(box.x), image_width))
    top = max(0, min(round(box.y), image_height))
    right = max(0, min(round(box.x + box.width), image_width))
    lower = max(0, min(round(box.y + box.height), image_height))

    if right <= left or lower <= top:
        raise VisionPreprocessingError("Bounding box does not overlap the image.")

    return BoundingBox(
        x=left,
        y=top,
        width=right - left,
        height=lower - top,
        confidence=box.confidence,
        label=box.label,
        model=box.model,
    )


def select_best_label_region(regions: list[BoundingBox]) -> BoundingBox:
    """Select the best OCR ROI without treating confidence as product identity.

    Args:
        regions: Allowed detector regions.

    Returns:
        Highest-priority ROI. Label regions outrank bottles and blister packs;
        confidence only breaks ties within the same ROI class.

    Raises:
        VisionPreprocessingError: If no regions are available.
    """
    if not regions:
        raise VisionPreprocessingError("No candidate label regions were detected.")
    return min(regions, key=lambda region: (label_priority(region.label), -region.confidence))


def crop_image_to_bounding_box(
    image_bytes: bytes,
    box: BoundingBox,
    *,
    output_format: str = "PNG",
    padding_ratio: float = 0.0,
    min_padding_px: int = 0,
    max_padding_px: int | None = None,
) -> bytes:
    """Crop image bytes to a validated bounding box.

    Args:
        image_bytes: Validated source image bytes.
        box: Pixel-based bounding box produced by a vision adapter.
        output_format: Pillow output format, normally ``PNG``.
        padding_ratio: Fractional padding relative to the box width/height.
        min_padding_px: Minimum padding pixels on each side when padding is enabled.
        max_padding_px: Optional maximum padding pixels on each side.

    Returns:
        Cropped image bytes.

    Raises:
        VisionPreprocessingError: If the image or bounding box is invalid.
    """
    if box.width <= 0 or box.height <= 0:
        raise VisionPreprocessingError("Bounding box dimensions must be positive.")
    if box.x < 0 or box.y < 0:
        raise VisionPreprocessingError("Bounding box origin must be non-negative.")

    try:
        decoded = safe_load_with_bomb_guard(image_bytes)
    except ImageSafetyError as exc:
        raise VisionPreprocessingError("Image cannot be decoded for vision preprocessing.") from exc

    try:
        with decoded as source:
            image_width, image_height = source.size
            right = box.x + box.width
            lower = box.y + box.height
            if right > image_width or lower > image_height:
                raise VisionPreprocessingError("Bounding box exceeds image dimensions.")

            crop_box = expand_bounding_box(
                box,
                image_width=image_width,
                image_height=image_height,
                padding_ratio=padding_ratio,
                min_padding_px=min_padding_px,
                max_padding_px=max_padding_px,
            )
            crop_right = crop_box.x + crop_box.width
            crop_lower = crop_box.y + crop_box.height
            cropped = source.crop((crop_box.x, crop_box.y, crop_right, crop_lower)).convert("RGB")
            buffer = BytesIO()
            cropped.save(buffer, format=output_format)
            return buffer.getvalue()
    except VisionPreprocessingError:
        raise
    except (OSError, UnidentifiedImageError) as exc:
        raise VisionPreprocessingError("Image cannot be decoded for vision preprocessing.") from exc


def expand_bounding_box(
    box: BoundingBox,
    *,
    image_width: int,
    image_height: int,
    padding_ratio: float,
    min_padding_px: int = 0,
    max_padding_px: int | None = None,
) -> BoundingBox:
    """Expand a detected OCR ROI before cropping, then clamp to image bounds.

    OCR is sensitive to clipping text ascenders, descenders, and adjacent table
    columns. This helper keeps the detector's semantic box as the source of
    truth but adds bounded context around it so ROI-scoped OCR does not lose
    visible ingredient names or amount units at the edges.

    Args:
        box: Pixel-based detector box already validated to overlap the image.
        image_width: Source image width in pixels.
        image_height: Source image height in pixels.
        padding_ratio: Fractional padding relative to the box width/height.
        min_padding_px: Minimum padding on each side when padding is non-zero.
        max_padding_px: Optional maximum padding on each side.

    Returns:
        Expanded, clamped bounding box.

    Raises:
        VisionPreprocessingError: If dimensions or padding values are invalid.
    """
    if (
        padding_ratio < 0
        or min_padding_px < 0
        or (max_padding_px is not None and max_padding_px < 0)
    ):
        raise VisionPreprocessingError("Bounding box padding values must be non-negative.")
    if max_padding_px is not None and max_padding_px < min_padding_px:
        raise VisionPreprocessingError("Maximum padding must be greater than minimum padding.")

    horizontal_padding = round(box.width * padding_ratio)
    vertical_padding = round(box.height * padding_ratio)
    if padding_ratio > 0:
        horizontal_padding = max(horizontal_padding, min_padding_px)
        vertical_padding = max(vertical_padding, min_padding_px)
    if max_padding_px is not None:
        horizontal_padding = min(horizontal_padding, max_padding_px)
        vertical_padding = min(vertical_padding, max_padding_px)

    expanded = BoundingBox(
        x=box.x - horizontal_padding,
        y=box.y - vertical_padding,
        width=box.width + (horizontal_padding * 2),
        height=box.height + (vertical_padding * 2),
        confidence=box.confidence,
        label=box.label,
        model=box.model,
    )
    return clamp_bounding_box(expanded, image_width=image_width, image_height=image_height)
