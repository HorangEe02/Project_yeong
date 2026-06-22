"""Tests for OCR-layout-derived supplement section YOLO label candidates."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from src.learning.retraining import (
    DatasetExportCandidate,
    RetrainingSecurityError,
    build_dataset_export_manifest,
    build_supplement_section_yolo_detection_export,
    validate_sanitized_label_snapshot,
)
from src.learning.supplement_section_labels import (
    SUPPLEMENT_SECTION_ANNOTATION_ASSIGNEE_ROLE,
    SUPPLEMENT_SECTION_ANNOTATION_REVIEW_NOTES_CODE,
    SUPPLEMENT_SECTION_ANNOTATION_TASK_TYPE,
    SupplementSectionLabelCandidateError,
    build_supplement_section_annotation_task,
    build_supplement_section_yolo_label_snapshot,
    page_dimensions_from_ocr_result,
)
from src.models.db.retraining import LearningDatasetVersion
from src.models.schemas.label_layout import LabelBox, LabelCell, LabelLayout, LabelSection
from src.ocr.base import OCRBlock, OCRPage, OCRResult


def _box(left: float, top: float, right: float, bottom: float, *, page_index: int = 0) -> LabelBox:
    """Build a label box fixture."""
    return LabelBox(
        page_index=page_index,
        left=left,
        top=top,
        right=right,
        bottom=bottom,
    )


def _cell(
    text: str,
    left: float,
    top: float,
    right: float,
    bottom: float,
    *,
    row_index: int = 0,
    column_index: int = 0,
) -> LabelCell:
    """Build a layout cell fixture."""
    return LabelCell(
        row_index=row_index,
        column_index=column_index,
        text=text,
        bounding_box=_box(left, top, right, bottom),
        confidence=0.93,
        word_count=1,
    )


def _dataset() -> LearningDatasetVersion:
    """Build an exportable dataset version fixture."""
    return LearningDatasetVersion(
        id=uuid4(),
        dataset_key="supplement_section_yolo",
        version="2026-06-02.1",
        status="frozen",
        train_count=1,
        val_count=0,
        test_count=0,
        privacy_review_status="approved",
    )


def test_build_supplement_section_snapshot_omits_ocr_text_and_normalizes_boxes() -> None:
    """Verify OCR layout can become sanitized normalized section boxes."""
    layout = LabelLayout(
        provider="unit-ocr",
        page_count=1,
        sections=[
            LabelSection(
                section_type="nutrition_function_info",
                anchor_text="Supplement Facts",
                anchor_box=_box(100, 200, 300, 240),
                rows=[
                    [
                        _cell("Vitamin C", 100, 260, 300, 300),
                        _cell("90 mg", 700, 260, 820, 300, column_index=1),
                    ]
                ],
            ),
            LabelSection(
                section_type="precautions",
                anchor_text="Warning",
                anchor_box=_box(120, 1500, 300, 1540),
                rows=[[_cell("Contains soy and milk", 120, 1550, 850, 1600)]],
            ),
        ],
    )

    snapshot = build_supplement_section_yolo_label_snapshot(
        layout,
        page_dimensions={0: (1000, 2000)},
    )

    assert snapshot["schema_version"] == "supplement-section-yolo-label-candidates-v1"
    assert snapshot["candidate_source"] == "ocr_layout"
    assert snapshot["coordinate_space"] == "ocr_page"
    assert snapshot["human_review_required"] is True
    assert snapshot["text_stored"] is False
    assert snapshot["training_export_allowed"] is False
    assert snapshot["boxes"] == [
        {
            "label": "supplement_facts",
            "x_center": 0.46,
            "y_center": 0.125,
            "width": 0.72,
            "height": 0.05,
        },
        {
            "label": "precautions",
            "x_center": 0.485,
            "y_center": 0.775,
            "width": 0.73,
            "height": 0.05,
        },
    ]
    serialized = json.dumps(snapshot, ensure_ascii=False)
    assert "Vitamin C" not in serialized
    assert "Contains soy" not in serialized
    validate_sanitized_label_snapshot(snapshot)


def test_supplement_section_snapshot_requires_review_before_export() -> None:
    """Verify OCR-derived candidate snapshots cannot bypass human review."""
    dataset = _dataset()
    snapshot = build_supplement_section_yolo_label_snapshot(
        LabelLayout(
            provider="unit-ocr",
            page_count=1,
            sections=[
                LabelSection(
                    section_type="intake_method",
                    anchor_text="Suggested Use",
                    anchor_box=_box(100, 800, 280, 840),
                    rows=[[_cell("Take one capsule daily", 100, 850, 740, 900)]],
                )
            ],
        ),
        page_dimensions={0: (1000, 1000)},
    )

    manifest = build_dataset_export_manifest(
        dataset,
        [
            DatasetExportCandidate(
                item_id=uuid4(),
                split="train",
                source_domain="supplement",
                task_type="yolo_detection",
                label_status="human_reviewed",
                source_ref=f"media:{uuid4()}",
                label_snapshot=snapshot,
                label_hash="b" * 64,
            )
        ],
    )

    with pytest.raises(RetrainingSecurityError, match="training export approval"):
        build_supplement_section_yolo_detection_export(manifest)


def test_reviewed_supplement_section_snapshot_feeds_export_contract() -> None:
    """Verify reviewer-approved snapshots connect to the section YOLO export bridge."""
    dataset = _dataset()
    snapshot = build_supplement_section_yolo_label_snapshot(
        LabelLayout(
            provider="unit-ocr",
            page_count=1,
            sections=[
                LabelSection(
                    section_type="intake_method",
                    anchor_text="Suggested Use",
                    anchor_box=_box(100, 800, 280, 840),
                    rows=[[_cell("Take one capsule daily", 100, 850, 740, 900)]],
                )
            ],
        ),
        page_dimensions={0: (1000, 1000)},
    )
    reviewed_snapshot = {
        **snapshot,
        "coordinate_space": "source_image",
        "human_review_required": False,
        "training_export_allowed": True,
    }
    candidate = DatasetExportCandidate(
        item_id=uuid4(),
        split="train",
        source_domain="supplement",
        task_type="yolo_detection",
        label_status="human_reviewed",
        source_ref=f"media:{uuid4()}",
        label_snapshot=reviewed_snapshot,
        label_hash="b" * 64,
    )

    manifest = build_dataset_export_manifest(dataset, [candidate])
    export = build_supplement_section_yolo_detection_export(manifest)

    assert export["schema_version"] == "supplement-section-yolo-detect-export-v1"
    assert export["items"][0]["labels"] == [
        {
            "class_id": 5,
            "label": "intake_method",
            "x_center": 0.42,
            "y_center": 0.85,
            "width": 0.64,
            "height": 0.1,
        }
    ]


def test_build_supplement_section_annotation_task_stores_pending_review_contract() -> None:
    """Verify OCR layout candidates become sanitized pending annotation tasks."""
    media_object_id = uuid4()
    task = build_supplement_section_annotation_task(
        owner_subject_hash="a" * 64,
        media_object_id=media_object_id,
        layout=LabelLayout(
            provider="unit-ocr",
            page_count=1,
            sections=[
                LabelSection(
                    section_type="precautions",
                    anchor_text="Warning",
                    anchor_box=_box(100, 800, 280, 840),
                    rows=[[_cell("Contains soy and milk", 100, 850, 740, 900)]],
                )
            ],
        ),
        page_dimensions={0: (1000, 1000)},
    )

    assert task.owner_subject_hash == "a" * 64
    assert task.media_object_id == media_object_id
    assert task.learning_image_object_id is None
    assert task.task_type == SUPPLEMENT_SECTION_ANNOTATION_TASK_TYPE
    assert task.status == "pending"
    assert task.assignee_role == SUPPLEMENT_SECTION_ANNOTATION_ASSIGNEE_ROLE
    assert task.review_notes_code == SUPPLEMENT_SECTION_ANNOTATION_REVIEW_NOTES_CODE
    assert task.reviewer_hash is None
    assert task.completed_at is None
    assert task.label_snapshot["candidate_source"] == "ocr_layout"
    assert task.label_snapshot["human_review_required"] is True
    assert task.label_snapshot["training_export_allowed"] is False
    assert task.label_snapshot["boxes"][0]["label"] == "precautions"
    serialized = json.dumps(task.label_snapshot, ensure_ascii=False)
    assert "Contains soy" not in serialized
    assert str(media_object_id) not in serialized
    assert "a" * 64 not in serialized


def test_build_supplement_section_annotation_task_maps_allergen_warning() -> None:
    """Verify allergen warnings remain separate section candidates for YOLO."""
    task = build_supplement_section_annotation_task(
        owner_subject_hash="a" * 64,
        media_object_id=uuid4(),
        layout=LabelLayout(
            provider="unit-ocr",
            page_count=1,
            sections=[
                LabelSection(
                    section_type="allergen_warning",
                    anchor_text="Allergen Warning",
                    anchor_box=_box(100, 800, 300, 840),
                    rows=[[_cell("Contains milk and soy", 100, 850, 740, 900)]],
                )
            ],
        ),
        page_dimensions={0: (1000, 1000)},
    )

    assert task.label_snapshot["boxes"][0]["label"] == "allergen_warning"
    serialized = json.dumps(task.label_snapshot, ensure_ascii=False)
    assert "Contains milk" not in serialized


def test_build_supplement_section_annotation_task_accepts_learning_image_source() -> None:
    """Verify consent-retained learning images can be the source for review tasks."""
    learning_image_object_id = uuid4()
    task = build_supplement_section_annotation_task(
        owner_subject_hash="b" * 64,
        learning_image_object_id=learning_image_object_id,
        layout=LabelLayout(
            provider="unit-ocr",
            page_count=1,
            sections=[
                LabelSection(
                    section_type="intake_method",
                    anchor_text="Suggested Use",
                    anchor_box=_box(100, 700, 320, 740),
                    rows=[[_cell("Take 1 softgel daily", 100, 750, 650, 790)]],
                )
            ],
        ),
        page_dimensions={0: (1000, 1000)},
    )

    assert task.media_object_id is None
    assert task.learning_image_object_id == learning_image_object_id
    serialized = json.dumps(task.label_snapshot, ensure_ascii=False)
    assert "Take 1 softgel" not in serialized
    assert str(learning_image_object_id) not in serialized


def test_build_supplement_section_annotation_task_rejects_missing_or_ambiguous_source() -> None:
    """Verify annotation tasks cannot be created without one clear image source."""
    layout = LabelLayout(
        provider="unit-ocr",
        page_count=1,
        sections=[
            LabelSection(
                section_type="precautions",
                anchor_text="Warning",
                anchor_box=_box(100, 800, 280, 840),
                rows=[],
            )
        ],
    )

    with pytest.raises(SupplementSectionLabelCandidateError, match="Exactly one"):
        build_supplement_section_annotation_task(
            owner_subject_hash="c" * 64,
            layout=layout,
            page_dimensions={0: (1000, 1000)},
        )

    with pytest.raises(SupplementSectionLabelCandidateError, match="Exactly one"):
        build_supplement_section_annotation_task(
            owner_subject_hash="c" * 64,
            media_object_id=uuid4(),
            learning_image_object_id=uuid4(),
            layout=layout,
            page_dimensions={0: (1000, 1000)},
        )


def test_build_supplement_section_annotation_task_rejects_raw_owner_subject() -> None:
    """Verify raw owner subjects cannot be passed as annotation task owner ids."""
    with pytest.raises(SupplementSectionLabelCandidateError, match="SHA-256"):
        build_supplement_section_annotation_task(
            owner_subject_hash="issuer::user-123",
            media_object_id=uuid4(),
            layout=LabelLayout(
                provider="unit-ocr",
                page_count=1,
                sections=[
                    LabelSection(
                        section_type="precautions",
                        anchor_text="Warning",
                        anchor_box=_box(100, 800, 280, 840),
                        rows=[],
                    )
                ],
            ),
            page_dimensions={0: (1000, 1000)},
        )


def test_build_supplement_section_snapshot_requires_page_dimensions() -> None:
    """Verify training labels fail closed when page size is unavailable."""
    layout = LabelLayout(
        provider="unit-ocr",
        page_count=1,
        sections=[
            LabelSection(
                section_type="precautions",
                anchor_text="Warning",
                anchor_box=_box(100, 100, 200, 160),
                rows=[],
            )
        ],
    )

    with pytest.raises(SupplementSectionLabelCandidateError, match="dimensions are required"):
        build_supplement_section_yolo_label_snapshot(layout, page_dimensions={})


def test_build_supplement_section_snapshot_rejects_non_trainable_layout() -> None:
    """Verify unsupported layout sections are not silently exported."""
    layout = LabelLayout(
        provider="unit-ocr",
        page_count=1,
        sections=[
            LabelSection(
                section_type="storage_method",
                anchor_text="Storage",
                anchor_box=_box(100, 100, 200, 160),
                rows=[],
            )
        ],
    )

    with pytest.raises(SupplementSectionLabelCandidateError, match="no trainable section"):
        build_supplement_section_yolo_label_snapshot(layout, page_dimensions={0: (1000, 1000)})


def test_page_dimensions_from_ocr_result_omits_missing_page_sizes() -> None:
    """Verify page dimension extraction never guesses missing OCR page sizes."""
    ocr_result = OCRResult(
        text="",
        provider="unit-ocr",
        confidence=None,
        pages=(
            OCRPage(width=640, height=480, confidence=None, blocks=()),
            OCRPage(width=None, height=480, confidence=None, blocks=()),
            OCRPage(
                width=320,
                height=240,
                confidence=None,
                blocks=(
                    OCRBlock(
                        text="not used",
                        confidence=None,
                        bounding_box=None,
                        block_type="TEXT",
                        paragraphs=(),
                    ),
                ),
            ),
        ),
    )

    dimensions = page_dimensions_from_ocr_result(ocr_result)

    assert dimensions[0].width == 640
    assert dimensions[0].height == 480
    assert 1 not in dimensions
    assert dimensions[2].width == 320
