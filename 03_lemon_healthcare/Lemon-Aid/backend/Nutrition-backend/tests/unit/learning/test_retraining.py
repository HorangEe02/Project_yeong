"""Retraining dataset export and model promotion gate tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from src.learning.retraining import (
    DatasetExportCandidate,
    DatasetFreezeError,
    MetricGateRule,
    RetrainingSecurityError,
    build_dataset_export_manifest,
    build_paddleocr_detection_export,
    build_paddleocr_recognition_export,
    build_supplement_section_yolo_detection_export,
    build_yolo_detection_export,
    candidate_from_dataset_item,
    evaluate_model_promotion_gate,
)
from src.models.db.retraining import (
    LearningDatasetItem,
    LearningDatasetVersion,
    ModelEvalResult,
    ModelRegistryEntry,
    ModelTrainingRun,
)


def _dataset(
    *,
    status: str = "frozen",
    privacy_review_status: str = "approved",
) -> LearningDatasetVersion:
    """Build a dataset version fixture.

    Args:
        status: Dataset lifecycle status.
        privacy_review_status: Dataset privacy review status.

    Returns:
        Learning dataset version fixture.
    """
    return LearningDatasetVersion(
        id=uuid4(),
        dataset_key="supplement_roi_detection",
        version="2026-05-27.1",
        status=status,
        train_count=1,
        val_count=0,
        test_count=0,
        privacy_review_status=privacy_review_status,
    )


def _candidate(
    *,
    item_id: UUID | None = None,
    task_type: str = "yolo_detection",
    label_status: str = "human_reviewed",
    source_ref: str | None = None,
    label_snapshot: dict[str, object] | None = None,
    split: str = "train",
) -> DatasetExportCandidate:
    """Build a safe dataset export candidate.

    Args:
        item_id: Optional item id.
        task_type: Learning task type.
        label_status: Label lifecycle status.
        source_ref: Backend-only source ref.
        label_snapshot: Sanitized label snapshot.
        split: Dataset split.

    Returns:
        Dataset export candidate fixture.
    """
    resolved_item_id = item_id or uuid4()
    return DatasetExportCandidate(
        item_id=resolved_item_id,
        split=split,
        source_domain="supplement",
        task_type=task_type,
        label_status=label_status,
        source_ref=source_ref or f"media:{uuid4()}",
        label_snapshot=label_snapshot
        or {
            "boxes": [
                {
                    "class_id": 0,
                    "x_center": 0.5,
                    "y_center": 0.5,
                    "width": 0.6,
                    "height": 0.4,
                }
            ]
        },
        label_hash="a" * 64,
    )


def test_dataset_export_requires_privacy_review_approval() -> None:
    """Verify dataset export fails before privacy review approval."""
    with pytest.raises(DatasetFreezeError, match="privacy review"):
        build_dataset_export_manifest(_dataset(privacy_review_status="pending"), [_candidate()])


def test_dataset_export_uses_private_refs_and_skips_unreviewed_or_revoked_items() -> None:
    """Verify export manifests contain only reviewed rows and no raw owner fields."""
    reviewed = _candidate(split="train")
    auto_labeled = _candidate(label_status="auto_labeled", split="val")
    revoked = _candidate(label_status="revoked", split="test")

    manifest = build_dataset_export_manifest(_dataset(), [auto_labeled, revoked, reviewed])

    assert manifest["counts"] == {"train": 1, "val": 0, "test": 0, "holdout": 0}
    assert manifest["items"] == [
        {
            "item_id": str(reviewed.item_id),
            "split": "train",
            "source_domain": "supplement",
            "task_type": "yolo_detection",
            "source_ref": reviewed.source_ref,
            "label_snapshot": reviewed.label_snapshot,
            "label_hash": "a" * 64,
        }
    ]
    serialized = str(manifest).casefold()
    assert "owner_subject" not in serialized
    assert "raw_ocr_text" not in serialized
    assert "provider_payload" not in serialized
    assert "signed_url" not in serialized
    assert "public_url" not in serialized


def test_candidate_from_dataset_item_uses_tokenized_private_source_refs() -> None:
    """Verify ORM dataset items become backend-only private source tokens."""
    media_object_id = uuid4()
    item = LearningDatasetItem(
        id=uuid4(),
        dataset_version_id=uuid4(),
        owner_subject_hash="b" * 64,
        media_object_id=media_object_id,
        source_domain="supplement",
        task_type="paddleocr_recognition",
        label_status="human_reviewed",
        split="train",
        label_snapshot={"text_label": "Vitamin C 500 mg"},
        label_hash="c" * 64,
        consent_snapshot={"consent_type": "image_learning_dataset"},
        retained_until=datetime(2026, 6, 27, tzinfo=UTC),
    )

    candidate = candidate_from_dataset_item(item)

    assert candidate is not None
    assert candidate.source_ref == f"media:{media_object_id}"


def test_dataset_export_rejects_raw_payload_keys_and_public_urls() -> None:
    """Verify raw OCR/provider/url fields cannot enter retraining exports."""
    unsafe_candidate = _candidate(
        label_snapshot={
            "raw_ocr_text": "unreviewed text",
            "public_url": "https://example.com/object",
        }
    )

    with pytest.raises(RetrainingSecurityError, match="Forbidden label snapshot key"):
        build_dataset_export_manifest(_dataset(), [unsafe_candidate])


def test_yolo_export_uses_normalized_labels_without_paths() -> None:
    """Verify YOLO export emits normalized labels keyed by private refs."""
    candidate = _candidate()
    manifest = build_dataset_export_manifest(_dataset(), [candidate])

    export = build_yolo_detection_export(manifest)

    assert export == {
        "schema_version": "learning-yolo-detect-export-v1",
        "item_count": 1,
        "items": [
            {
                "source_ref": candidate.source_ref,
                "split": "train",
                "labels": [
                    {
                        "class_id": 0,
                        "x_center": 0.5,
                        "y_center": 0.5,
                        "width": 0.6,
                        "height": 0.4,
                    }
                ],
            }
        ],
    }


def test_supplement_section_yolo_export_maps_semantic_labels_to_class_ids() -> None:
    """Verify supplement section export derives class ids from section labels."""
    candidate = _candidate(
        label_snapshot={
            "boxes": [
                {
                    "label": "supplement_facts",
                    "x_center": 0.5,
                    "y_center": 0.4,
                    "width": 0.7,
                    "height": 0.3,
                },
                {
                    "label": "allergy_warning",
                    "x_center": 0.5,
                    "y_center": 0.8,
                    "width": 0.7,
                    "height": 0.2,
                },
            ]
        },
    )
    manifest = build_dataset_export_manifest(_dataset(), [candidate])

    export = build_supplement_section_yolo_detection_export(manifest)

    assert export["schema_version"] == "supplement-section-yolo-detect-export-v1"
    assert export["class_names"] == [
        "product_identity",
        "supplement_facts",
        "ingredient_amounts",
        "precautions",
        "allergen_warning",
        "intake_method",
        "other_ingredients",
        "functional_claims",
    ]
    assert export["split_counts"]["train"] == 1
    assert export["items"] == [
        {
            "source_ref": candidate.source_ref,
            "split": "train",
            "labels": [
                {
                    "class_id": 1,
                    "label": "supplement_facts",
                    "x_center": 0.5,
                    "y_center": 0.4,
                    "width": 0.7,
                    "height": 0.3,
                },
                {
                    "class_id": 4,
                    "label": "allergen_warning",
                    "x_center": 0.5,
                    "y_center": 0.8,
                    "width": 0.7,
                    "height": 0.2,
                },
            ],
        }
    ]


def test_supplement_section_yolo_export_rejects_numeric_only_boxes() -> None:
    """Verify section training exports require semantic bbox labels."""
    candidate = _candidate()
    manifest = build_dataset_export_manifest(_dataset(), [candidate])

    with pytest.raises(RetrainingSecurityError, match="semantic label"):
        build_supplement_section_yolo_detection_export(manifest)


def test_supplement_section_yolo_export_rejects_label_only_regions() -> None:
    """Verify whole-label boxes cannot be used as section detector labels."""
    candidate = _candidate(
        label_snapshot={
            "boxes": [
                {
                    "label": "supplement_label",
                    "x_center": 0.5,
                    "y_center": 0.5,
                    "width": 0.7,
                    "height": 0.8,
                }
            ]
        },
    )
    manifest = build_dataset_export_manifest(_dataset(), [candidate])

    with pytest.raises(RetrainingSecurityError, match="not allowed"):
        build_supplement_section_yolo_detection_export(manifest)


def test_supplement_section_yolo_export_rejects_unapproved_candidate_snapshot() -> None:
    """Verify OCR-derived candidate snapshots cannot be exported before review approval."""
    candidate = _candidate(
        label_snapshot={
            "schema_version": "supplement-section-yolo-label-candidates-v1",
            "candidate_source": "ocr_layout",
            "coordinate_space": "ocr_page",
            "human_review_required": True,
            "text_stored": False,
            "training_export_allowed": False,
            "boxes": [
                {
                    "label": "precautions",
                    "x_center": 0.5,
                    "y_center": 0.8,
                    "width": 0.7,
                    "height": 0.2,
                }
            ],
        },
    )
    manifest = build_dataset_export_manifest(_dataset(), [candidate])

    with pytest.raises(RetrainingSecurityError, match="training export approval"):
        build_supplement_section_yolo_detection_export(manifest)


def test_supplement_section_yolo_export_rejects_non_source_coordinates() -> None:
    """Verify section detector labels must be reviewed into source-image coordinates."""
    candidate = _candidate(
        label_snapshot={
            "coordinate_space": "ocr_page",
            "human_review_required": False,
            "training_export_allowed": True,
            "boxes": [
                {
                    "label": "precautions",
                    "x_center": 0.5,
                    "y_center": 0.8,
                    "width": 0.7,
                    "height": 0.2,
                }
            ],
        },
    )
    manifest = build_dataset_export_manifest(_dataset(), [candidate])

    with pytest.raises(RetrainingSecurityError, match="source_image"):
        build_supplement_section_yolo_detection_export(manifest)


def test_paddleocr_exports_require_confirmed_text_and_detection_boxes() -> None:
    """Verify PaddleOCR exports require reviewed labels in task-specific shape."""
    rec_candidate = _candidate(
        task_type="paddleocr_recognition",
        label_snapshot={"text_label": "Magnesium 135 mg"},
    )
    det_candidate = _candidate(
        task_type="paddleocr_detection",
        label_snapshot={
            "textline_boxes": [
                {
                    "class_id": 0,
                    "x_center": 0.4,
                    "y_center": 0.3,
                    "width": 0.5,
                    "height": 0.2,
                }
            ]
        },
        split="val",
    )
    manifest = build_dataset_export_manifest(_dataset(), [rec_candidate, det_candidate])

    rec_export = build_paddleocr_recognition_export(manifest)
    det_export = build_paddleocr_detection_export(manifest)

    assert rec_export["items"] == [
        {
            "source_ref": rec_candidate.source_ref,
            "split": "train",
            "text_label": "Magnesium 135 mg",
            "recognition_source": "pre_cropped_image",
        }
    ]
    assert det_export["items"][0]["source_ref"] == det_candidate.source_ref
    assert det_export["items"][0]["split"] == "val"


def test_paddleocr_recognition_export_rejects_pii_like_labels() -> None:
    """Verify text labels cannot smuggle emails or phone numbers into training rows."""
    candidate = _candidate(
        task_type="paddleocr_recognition",
        label_snapshot={"text_label": "Contact user@example.com"},
    )

    with pytest.raises(RetrainingSecurityError, match="PII-like"):
        build_dataset_export_manifest(_dataset(), [candidate])


def test_model_promotion_gate_requires_persisted_eval_metrics() -> None:
    """Verify model promotion fails when required metric rows are absent."""
    training_run_id = uuid4()
    training_run = ModelTrainingRun(
        id=training_run_id,
        model_family="yolo",
        base_model="yolov8n",
        dataset_version_id=uuid4(),
        hyperparam_snapshot={"epochs": 10},
        metrics_snapshot={},
        status="succeeded",
    )
    model = ModelRegistryEntry(
        id=uuid4(),
        task_type="supplement_roi_detection",
        model_version="roi-2026-05-27.1",
        training_run_id=training_run_id,
        artifact_ref="models/supplement-roi/2026-05-27",
        deployment_status="candidate",
        metric_gate_snapshot={},
    )

    snapshot = evaluate_model_promotion_gate(
        training_run=training_run,
        model=model,
        eval_results=[],
        required_metrics=[MetricGateRule("mAP50", ">=", Decimal("0.85"))],
    )

    assert snapshot["allowed"] is False
    assert snapshot["reason"] == "missing_metric:mAP50"
    assert "artifact_ref" not in snapshot


def test_model_promotion_gate_passes_only_when_metric_rules_pass() -> None:
    """Verify successful promotion snapshots are based on eval result rows only."""
    training_run_id = uuid4()
    dataset_version_id = uuid4()
    model_id = uuid4()
    training_run = ModelTrainingRun(
        id=training_run_id,
        model_family="paddleocr_rec",
        base_model="PP-OCRv5-rec",
        dataset_version_id=dataset_version_id,
        hyperparam_snapshot={"epochs": 5},
        metrics_snapshot={},
        status="succeeded",
    )
    model = ModelRegistryEntry(
        id=model_id,
        task_type="supplement_ocr_recognition",
        model_version="ocr-rec-2026-05-27.1",
        training_run_id=training_run_id,
        artifact_ref="models/supplement-ocr-rec/2026-05-27",
        deployment_status="candidate",
        metric_gate_snapshot={},
    )
    eval_result = ModelEvalResult(
        id=uuid4(),
        model_id=model_id,
        eval_dataset_version_id=dataset_version_id,
        metric_name="cer",
        metric_value=Decimal("0.081"),
    )

    snapshot = evaluate_model_promotion_gate(
        training_run=training_run,
        model=model,
        eval_results=[eval_result],
        required_metrics=[MetricGateRule("cer", "<=", Decimal("0.10"))],
    )

    assert snapshot["allowed"] is True
    assert snapshot["reason"] == "passed"
    assert snapshot["rules"] == [
        {
            "metric_name": "cer",
            "comparator": "<=",
            "threshold": "0.1",
            "value": "0.081",
            "passed": True,
        }
    ]
