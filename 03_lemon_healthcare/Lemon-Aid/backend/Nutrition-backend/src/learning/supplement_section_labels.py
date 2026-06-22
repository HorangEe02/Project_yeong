"""Build sanitized supplement section YOLO label candidates from OCR layout."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.learning.retraining import validate_sanitized_label_snapshot
from src.models.db.retraining import AnnotationTask
from src.models.schemas.label_layout import LabelBox, LabelLayout, LabelSection, SectionType
from src.ocr.base import OCRResult
from src.vision.taxonomy import VisionLabel

LAYOUT_TO_SECTION_LABEL: dict[SectionType, str] = {
    "daily_intake": VisionLabel.SUPPLEMENT_FACTS.value,
    "nutrition_function_info": VisionLabel.SUPPLEMENT_FACTS.value,
    "intake_method": VisionLabel.INTAKE_METHOD.value,
    "precautions": VisionLabel.PRECAUTIONS.value,
    "allergen_warning": VisionLabel.ALLERGEN_WARNING.value,
    "ingredients": VisionLabel.INGREDIENT_AMOUNTS.value,
}
SNAPSHOT_SCHEMA_VERSION = "supplement-section-yolo-label-candidates-v1"
SUPPLEMENT_SECTION_ANNOTATION_TASK_TYPE = "supplement_roi_box"
SUPPLEMENT_SECTION_ANNOTATION_ASSIGNEE_ROLE = "data_reviewer"
SUPPLEMENT_SECTION_ANNOTATION_REVIEW_NOTES_CODE = "ocr_layout_section_candidate"
SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)


class SupplementSectionLabelCandidateError(ValueError):
    """Raised when OCR layout cannot produce safe YOLO section candidates."""


@dataclass(frozen=True)
class PageDimensions:
    """Image/page dimensions used to normalize OCR layout boxes.

    Args:
        width: Page width in provider units, normally image pixels.
        height: Page height in provider units, normally image pixels.
    """

    width: int
    height: int

    def validate(self, page_index: int) -> None:
        """Validate positive page dimensions.

        Args:
            page_index: Page index used in error context.

        Raises:
            SupplementSectionLabelCandidateError: If dimensions are missing or invalid.
        """
        if self.width <= 0 or self.height <= 0:
            raise SupplementSectionLabelCandidateError(
                f"OCR page {page_index} has invalid dimensions."
            )


def page_dimensions_from_ocr_result(ocr_result: OCRResult) -> dict[int, PageDimensions]:
    """Return safe OCR page dimensions for layout box normalization.

    Args:
        ocr_result: OCR result that produced the layout.

    Returns:
        Mapping from zero-based page index to dimensions. Pages with missing dimensions are
        omitted so callers fail closed instead of guessing a training canvas.
    """
    dimensions: dict[int, PageDimensions] = {}
    for page_index, page in enumerate(ocr_result.pages):
        if page.width is None or page.height is None:
            continue
        dimensions[page_index] = PageDimensions(width=page.width, height=page.height)
    return dimensions


def build_supplement_section_yolo_label_snapshot(
    layout: LabelLayout,
    *,
    page_dimensions: Mapping[int, PageDimensions | tuple[int, int]],
) -> dict[str, Any]:
    """Build a sanitized YOLO label snapshot from deterministic OCR layout.

    The returned payload is intentionally limited to section labels and normalized
    boxes. It does not include OCR text, provider payloads, image paths, source
    refs, or user identifiers. A human-review workflow must still approve the
    resulting labels before they can be exported for model training.

    Args:
        layout: Parsed OCR layout with semantic sections and absolute boxes.
        page_dimensions: Page dimensions keyed by ``LabelBox.page_index``.

    Returns:
        Sanitized label snapshot compatible with supplement section YOLO exports.

    Raises:
        SupplementSectionLabelCandidateError: If no section boxes can be produced or
            required page dimensions are missing.
    """
    normalized_dimensions = _normalize_page_dimensions(page_dimensions)
    boxes: list[dict[str, Any]] = []
    for section in layout.sections:
        label = LAYOUT_TO_SECTION_LABEL.get(section.section_type)
        if label is None:
            continue
        for section_box in _section_boxes_by_page(section):
            dimensions = normalized_dimensions.get(section_box.page_index)
            if dimensions is None:
                raise SupplementSectionLabelCandidateError(
                    f"OCR page {section_box.page_index} dimensions are required."
                )
            boxes.append(_normalized_section_box(section_box, label=label, dimensions=dimensions))

    if not boxes:
        raise SupplementSectionLabelCandidateError("OCR layout has no trainable section boxes.")
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "candidate_source": "ocr_layout",
        "coordinate_space": "ocr_page",
        "human_review_required": True,
        "text_stored": False,
        "training_export_allowed": False,
        "boxes": boxes,
    }


def build_supplement_section_annotation_task(
    *,
    owner_subject_hash: str,
    media_object_id: UUID | None = None,
    learning_image_object_id: UUID | None = None,
    layout: LabelLayout,
    page_dimensions: Mapping[int, PageDimensions | tuple[int, int]],
) -> AnnotationTask:
    """Build a sanitized human-review task for OCR-derived section boxes.

    Args:
        owner_subject_hash: HMAC-SHA256 hash for the source owner. The raw owner
            subject must not be passed into this function.
        media_object_id: Optional source media object id stored as a model column,
            not in the label snapshot.
        learning_image_object_id: Optional source learning image object id stored as
            a model column, not in the label snapshot.
        layout: Parsed OCR layout with candidate section boxes.
        page_dimensions: Page dimensions keyed by ``LabelBox.page_index``.

    Returns:
        Pending annotation task that requires data reviewer approval before any
        training export can use its labels.

    Raises:
        SupplementSectionLabelCandidateError: If owner hash or layout candidates
            are invalid.
    """
    _validate_owner_subject_hash(owner_subject_hash)
    _validate_annotation_source(media_object_id, learning_image_object_id)
    label_snapshot = build_supplement_section_yolo_label_snapshot(
        layout,
        page_dimensions=page_dimensions,
    )
    validate_sanitized_label_snapshot(label_snapshot)
    return AnnotationTask(
        owner_subject_hash=owner_subject_hash,
        media_object_id=media_object_id,
        learning_image_object_id=learning_image_object_id,
        task_type=SUPPLEMENT_SECTION_ANNOTATION_TASK_TYPE,
        status="pending",
        assignee_role=SUPPLEMENT_SECTION_ANNOTATION_ASSIGNEE_ROLE,
        label_snapshot=label_snapshot,
        review_notes_code=SUPPLEMENT_SECTION_ANNOTATION_REVIEW_NOTES_CODE,
        reviewer_hash=None,
        completed_at=None,
    )


def _normalize_page_dimensions(
    page_dimensions: Mapping[int, PageDimensions | tuple[int, int]],
) -> dict[int, PageDimensions]:
    """Normalize tuple dimensions into ``PageDimensions`` objects."""
    normalized: dict[int, PageDimensions] = {}
    for page_index, dimensions in page_dimensions.items():
        if isinstance(dimensions, PageDimensions):
            page_dimensions_value = dimensions
        else:
            width, height = dimensions
            page_dimensions_value = PageDimensions(width=width, height=height)
        page_dimensions_value.validate(page_index)
        normalized[page_index] = page_dimensions_value
    return normalized


def _validate_owner_subject_hash(owner_subject_hash: str) -> None:
    """Validate a privacy-preserving owner hash without accepting raw subjects."""
    if not SHA256_HEX_PATTERN.fullmatch(owner_subject_hash):
        raise SupplementSectionLabelCandidateError("Owner subject hash must be SHA-256 hex.")


def _validate_annotation_source(
    media_object_id: UUID | None,
    learning_image_object_id: UUID | None,
) -> None:
    """Require one unambiguous retained image source for human review."""
    source_count = int(media_object_id is not None) + int(learning_image_object_id is not None)
    if source_count != 1:
        raise SupplementSectionLabelCandidateError("Exactly one annotation source id is required.")


def _section_boxes_by_page(section: LabelSection) -> list[LabelBox]:
    """Return one union box per page represented by a label section."""
    boxes_by_page: dict[int, list[LabelBox]] = {}
    for box in _iter_section_boxes(section):
        boxes_by_page.setdefault(box.page_index, []).append(box)
    return [
        _merge_boxes(page_boxes)
        for _page_index, page_boxes in sorted(boxes_by_page.items(), key=lambda item: item[0])
    ]


def _iter_section_boxes(section: LabelSection) -> Iterable[LabelBox]:
    """Yield all non-text layout boxes represented by a section."""
    if section.anchor_box is not None:
        yield section.anchor_box
    for row in section.rows:
        for cell in row:
            yield cell.bounding_box


def _merge_boxes(boxes: list[LabelBox]) -> LabelBox:
    """Return an axis-aligned union box for boxes on the same page.

    Args:
        boxes: Non-empty list of boxes that share a page.

    Returns:
        Union box.

    Raises:
        SupplementSectionLabelCandidateError: If boxes span multiple pages.
    """
    page_indexes = {box.page_index for box in boxes}
    if len(page_indexes) != 1:
        raise SupplementSectionLabelCandidateError("Cannot merge boxes across OCR pages.")
    return LabelBox(
        page_index=boxes[0].page_index,
        left=min(box.left for box in boxes),
        top=min(box.top for box in boxes),
        right=max(box.right for box in boxes),
        bottom=max(box.bottom for box in boxes),
    )


def _normalized_section_box(
    box: LabelBox,
    *,
    label: str,
    dimensions: PageDimensions,
) -> dict[str, Any]:
    """Convert one absolute OCR section box to normalized YOLO xywh."""
    left = _clamp(box.left, 0.0, float(dimensions.width))
    right = _clamp(box.right, 0.0, float(dimensions.width))
    top = _clamp(box.top, 0.0, float(dimensions.height))
    bottom = _clamp(box.bottom, 0.0, float(dimensions.height))
    if right <= left or bottom <= top:
        raise SupplementSectionLabelCandidateError("OCR section box is outside the page.")

    width = (right - left) / dimensions.width
    height = (bottom - top) / dimensions.height
    x_center = ((left + right) / 2) / dimensions.width
    y_center = ((top + bottom) / 2) / dimensions.height
    return {
        "label": label,
        "x_center": x_center,
        "y_center": y_center,
        "width": width,
        "height": height,
    }


def _clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp a numeric coordinate to the page boundary."""
    return max(minimum, min(value, maximum))


__all__ = [
    "SNAPSHOT_SCHEMA_VERSION",
    "SUPPLEMENT_SECTION_ANNOTATION_ASSIGNEE_ROLE",
    "SUPPLEMENT_SECTION_ANNOTATION_REVIEW_NOTES_CODE",
    "SUPPLEMENT_SECTION_ANNOTATION_TASK_TYPE",
    "PageDimensions",
    "SupplementSectionLabelCandidateError",
    "build_supplement_section_annotation_task",
    "build_supplement_section_yolo_label_snapshot",
    "page_dimensions_from_ocr_result",
]
