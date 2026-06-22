"""Fail-closed retraining dataset export and model promotion gates."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.models.db.retraining import (
    LearningDatasetItem,
    LearningDatasetVersion,
    ModelEvalResult,
    ModelRegistryEntry,
    ModelTrainingRun,
)
from src.vision.taxonomy import VISION_SECTION_LABELS, normalize_vision_label

DATASET_EXPORT_SCHEMA_VERSION = "learning-dataset-export-v1"
YOLO_EXPORT_SCHEMA_VERSION = "learning-yolo-detect-export-v1"
SUPPLEMENT_SECTION_YOLO_EXPORT_SCHEMA_VERSION = "supplement-section-yolo-detect-export-v1"
PADDLEOCR_DETECTION_EXPORT_SCHEMA_VERSION = "learning-paddleocr-det-export-v1"
PADDLEOCR_RECOGNITION_EXPORT_SCHEMA_VERSION = "learning-paddleocr-rec-export-v1"
MODEL_PROMOTION_GATE_SCHEMA_VERSION = "learning-model-promotion-gate-v1"
HUMAN_REVIEWED_STATUS = "human_reviewed"
SHA256_HEX_LENGTH = 64
MAX_RECOGNITION_TEXT_LABEL_LENGTH = 512
SUPPLEMENT_SECTION_CLASS_NAMES = (
    "product_identity",
    "supplement_facts",
    "ingredient_amounts",
    "precautions",
    "allergen_warning",
    "intake_method",
    "other_ingredients",
    "functional_claims",
)
SKIPPED_LABEL_STATUSES = frozenset({"rejected", "revoked"})
PRIVATE_SOURCE_REF_PREFIXES = ("media:", "learning_image:")
RAW_FORBIDDEN_LABEL_KEYS = frozenset(
    {
        "access_token",
        "authorization",
        "credential",
        "credentials",
        "diagnosis",
        "diagnosis_text",
        "file_path",
        "image_base64",
        "image_bytes",
        "local_path",
        "object_uri",
        "object_url",
        "ocr_text",
        "owner_subject",
        "owner_subject_hash",
        "provider_payload",
        "provider_raw_payload",
        "public_url",
        "raw_document",
        "raw_image",
        "raw_image_bytes",
        "raw_ocr_text",
        "raw_payload",
        "raw_provider_payload",
        "request_headers",
        "secret",
        "signed_url",
        "treatment_instruction",
        "treatment_instructions",
        "url",
    }
)
NORMALIZED_FORBIDDEN_LABEL_KEYS = frozenset(
    "".join(character for character in key.casefold() if character.isalnum())
    for key in RAW_FORBIDDEN_LABEL_KEYS
)
SECRET_LIKE_VALUE_MARKERS = (
    "bearer ",
    "ngrok-free.dev",
    "sb_secret_",
    "service_role",
    "aws_secret_access_key",
    "-----begin",
)
PII_LIKE_TEXT_PATTERN = re.compile(
    r"(?P<email>[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})|" r"(?P<phone>\+?\d[\d\s().-]{7,}\d)",
    re.IGNORECASE,
)


class RetrainingSecurityError(ValueError):
    """Raised when a retraining artifact could expose raw data or secrets."""


class DatasetFreezeError(ValueError):
    """Raised when a dataset version is not safe to freeze or export."""


class ModelPromotionGateError(ValueError):
    """Raised when model promotion gate input is invalid."""


@dataclass(frozen=True)
class DatasetExportCandidate:
    """Sanitized candidate row used to build learning export manifests.

    Attributes:
        item_id: Source learning dataset item id.
        split: Dataset split key.
        source_domain: Source domain such as supplement or food.
        task_type: Learning task type.
        label_status: Human-review label lifecycle status.
        source_ref: Backend-only private source token, not a URL or path.
        label_snapshot: Sanitized structured label payload.
        label_hash: Optional SHA-256 hash of the sanitized label snapshot.
    """

    item_id: UUID
    split: str
    source_domain: str
    task_type: str
    label_status: str
    source_ref: str
    label_snapshot: Mapping[str, Any]
    label_hash: str | None


@dataclass(frozen=True)
class MetricGateRule:
    """One model promotion metric threshold.

    Attributes:
        metric_name: Eval metric key that must exist in model eval results.
        comparator: One of >=, >, <=, <.
        threshold: Required threshold value.
    """

    metric_name: str
    comparator: str
    threshold: Decimal


def candidate_from_dataset_item(item: LearningDatasetItem) -> DatasetExportCandidate | None:
    """Convert a dataset item into a private export candidate.

    Args:
        item: Persisted learning dataset item.

    Returns:
        Export candidate, or None when the item is rejected/revoked.

    Raises:
        DatasetFreezeError: If a trainable item has no private source token.
    """
    if item.label_status in SKIPPED_LABEL_STATUSES:
        return None
    if item.media_object_id is not None:
        source_ref = f"media:{item.media_object_id}"
    elif item.learning_image_object_id is not None:
        source_ref = f"learning_image:{item.learning_image_object_id}"
    else:
        raise DatasetFreezeError("Trainable dataset item is missing a private source ref.")
    return DatasetExportCandidate(
        item_id=item.id,
        split=item.split,
        source_domain=item.source_domain,
        task_type=item.task_type,
        label_status=item.label_status,
        source_ref=source_ref,
        label_snapshot=item.label_snapshot,
        label_hash=item.label_hash,
    )


def build_dataset_export_manifest(
    dataset_version: LearningDatasetVersion,
    candidates: Sequence[DatasetExportCandidate | None],
) -> dict[str, Any]:
    """Build a deterministic sanitized dataset export manifest.

    Args:
        dataset_version: Dataset version being frozen/exported.
        candidates: Candidate rows already resolved to private source refs.

    Returns:
        JSON-serializable manifest without raw OCR, image bytes, URLs, paths, or secrets.

    Raises:
        DatasetFreezeError: If the dataset version is not privacy-approved.
        RetrainingSecurityError: If any candidate contains unsafe fields.
    """
    _validate_dataset_version_exportable(dataset_version)
    rows: list[dict[str, Any]] = []
    counts = {"train": 0, "val": 0, "test": 0, "holdout": 0}
    for candidate in sorted(
        (candidate for candidate in candidates if candidate is not None),
        key=lambda row: (row.split, str(row.item_id)),
    ):
        if candidate.label_status in SKIPPED_LABEL_STATUSES:
            continue
        _validate_export_candidate(candidate)
        if candidate.label_status != HUMAN_REVIEWED_STATUS:
            continue
        label_snapshot = _normalize_json_object(candidate.label_snapshot)
        row = {
            "item_id": str(candidate.item_id),
            "split": candidate.split,
            "source_domain": candidate.source_domain,
            "task_type": candidate.task_type,
            "source_ref": candidate.source_ref,
            "label_snapshot": label_snapshot,
            "label_hash": candidate.label_hash,
        }
        rows.append(row)
        counts[candidate.split] += 1

    manifest_hash = _sha256_json(rows)
    return {
        "schema_version": DATASET_EXPORT_SCHEMA_VERSION,
        "dataset_version_id": str(dataset_version.id),
        "dataset_key": dataset_version.dataset_key,
        "version": dataset_version.version,
        "manifest_hash": manifest_hash,
        "counts": counts,
        "items": rows,
    }


def build_yolo_detection_export(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Build a sanitized YOLO detection export contract.

    The output intentionally uses backend-only source refs instead of filesystem
    paths. A trusted training worker may resolve those refs to temporary files.

    Args:
        manifest: Output from ``build_dataset_export_manifest``.

    Returns:
        YOLO detection export rows with normalized boxes.

    Raises:
        RetrainingSecurityError: If a label row is malformed or unsafe.
    """
    rows = []
    for row in _manifest_items_for_task(manifest, "yolo_detection"):
        boxes = _normalize_box_labels(row["label_snapshot"].get("boxes"))
        rows.append(
            {
                "source_ref": row["source_ref"],
                "split": row["split"],
                "labels": boxes,
            }
        )
    return {
        "schema_version": YOLO_EXPORT_SCHEMA_VERSION,
        "item_count": len(rows),
        "items": rows,
    }


def build_supplement_section_yolo_detection_export(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Build a sanitized supplement-section YOLO detection export contract.

    This export is stricter than the generic YOLO export. Each box must carry a
    semantic section label so the class id is derived from the fixed supplement
    section contract instead of trusting upstream numeric ids.

    Args:
        manifest: Output from ``build_dataset_export_manifest``.

    Returns:
        YOLO detection export rows for supplement OCR section training.

    Raises:
        RetrainingSecurityError: If a row is not a supplement section ROI label.
    """
    rows = []
    split_counts = {"train": 0, "val": 0, "test": 0, "holdout": 0}
    for row in _manifest_items_for_task(manifest, "yolo_detection"):
        if row.get("source_domain") != "supplement":
            raise RetrainingSecurityError(
                "Supplement section YOLO export only accepts supplement source rows."
            )
        label_snapshot = row["label_snapshot"]
        _validate_supplement_section_training_approval(label_snapshot)
        labels = _normalize_supplement_section_box_labels(label_snapshot.get("boxes"))
        rows.append(
            {
                "source_ref": row["source_ref"],
                "split": row["split"],
                "labels": labels,
            }
        )
        split_counts[row["split"]] += 1
    return {
        "schema_version": SUPPLEMENT_SECTION_YOLO_EXPORT_SCHEMA_VERSION,
        "class_names": list(SUPPLEMENT_SECTION_CLASS_NAMES),
        "item_count": len(rows),
        "split_counts": split_counts,
        "items": rows,
    }


def build_paddleocr_detection_export(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Build a sanitized PaddleOCR text detection export contract.

    Args:
        manifest: Output from ``build_dataset_export_manifest``.

    Returns:
        PaddleOCR detection rows with normalized text-line boxes.

    Raises:
        RetrainingSecurityError: If a label row is malformed or unsafe.
    """
    rows = []
    for row in _manifest_items_for_task(manifest, "paddleocr_detection"):
        boxes = _normalize_box_labels(row["label_snapshot"].get("textline_boxes"))
        rows.append(
            {
                "source_ref": row["source_ref"],
                "split": row["split"],
                "textline_boxes": boxes,
            }
        )
    return {
        "schema_version": PADDLEOCR_DETECTION_EXPORT_SCHEMA_VERSION,
        "item_count": len(rows),
        "items": rows,
    }


def build_paddleocr_recognition_export(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Build a sanitized PaddleOCR recognition export contract.

    Args:
        manifest: Output from ``build_dataset_export_manifest``.

    Returns:
        PaddleOCR recognition rows with confirmed text labels.

    Raises:
        RetrainingSecurityError: If a confirmed text label is unsafe.
    """
    rows = []
    for row in _manifest_items_for_task(manifest, "paddleocr_recognition"):
        label_snapshot = row["label_snapshot"]
        export_row = {
            "source_ref": row["source_ref"],
            "split": row["split"],
            "text_label": _confirmed_text_label(label_snapshot.get("text_label")),
        }
        crop_box = _optional_crop_box(label_snapshot.get("crop_box"))
        if crop_box is not None:
            export_row["crop_box"] = crop_box
            export_row["recognition_source"] = "source_image_crop"
        else:
            export_row["recognition_source"] = "pre_cropped_image"
        rows.append(export_row)
    return {
        "schema_version": PADDLEOCR_RECOGNITION_EXPORT_SCHEMA_VERSION,
        "item_count": len(rows),
        "items": rows,
    }


def evaluate_model_promotion_gate(
    *,
    training_run: ModelTrainingRun,
    model: ModelRegistryEntry,
    eval_results: Sequence[ModelEvalResult],
    required_metrics: Sequence[MetricGateRule],
) -> dict[str, Any]:
    """Evaluate whether a model may move from candidate to staging.

    Args:
        training_run: Training run that produced the candidate model.
        model: Candidate model registry entry.
        eval_results: Persisted holdout/eval metric rows.
        required_metrics: Metric thresholds required for promotion.

    Returns:
        Sanitized promotion gate snapshot with metric values and pass/fail flags.

    Raises:
        ModelPromotionGateError: If lineage or gate configuration is invalid.
    """
    if model.training_run_id != training_run.id:
        raise ModelPromotionGateError("Model registry entry does not match training run.")
    if not required_metrics:
        raise ModelPromotionGateError("At least one metric gate rule is required.")

    metric_values = _metric_values_by_name(eval_results)
    rule_snapshots = []
    allowed = training_run.status == "succeeded" and model.deployment_status == "candidate"
    reason = "passed"
    if training_run.status != "succeeded":
        allowed = False
        reason = "training_run_not_succeeded"
    elif model.deployment_status != "candidate":
        allowed = False
        reason = "model_not_candidate"

    for rule in required_metrics:
        _validate_metric_gate_rule(rule)
        value = metric_values.get(rule.metric_name)
        if value is None:
            passed = False
            if reason == "passed":
                reason = f"missing_metric:{rule.metric_name}"
        else:
            passed = _compare_metric(value, rule.comparator, rule.threshold)
            if not passed and reason == "passed":
                reason = f"metric_gate_failed:{rule.metric_name}"
        allowed = allowed and passed
        rule_snapshots.append(
            {
                "metric_name": rule.metric_name,
                "comparator": rule.comparator,
                "threshold": _decimal_to_string(rule.threshold),
                "value": _decimal_to_string(value) if value is not None else None,
                "passed": passed,
            }
        )

    return {
        "schema_version": MODEL_PROMOTION_GATE_SCHEMA_VERSION,
        "allowed": allowed,
        "reason": reason,
        "model_id": str(model.id),
        "training_run_id": str(training_run.id),
        "rules": rule_snapshots,
    }


def _validate_dataset_version_exportable(dataset_version: LearningDatasetVersion) -> None:
    """Reject dataset versions that have not passed privacy review."""
    if dataset_version.privacy_review_status != "approved":
        raise DatasetFreezeError("Dataset privacy review must be approved before export.")
    if dataset_version.status not in {"frozen", "training", "evaluated", "approved"}:
        raise DatasetFreezeError("Dataset must be frozen before export.")


def _validate_export_candidate(candidate: DatasetExportCandidate) -> None:
    """Validate one dataset export candidate before manifest inclusion."""
    if candidate.split not in {"train", "val", "test", "holdout"}:
        raise RetrainingSecurityError("Dataset split is not allowed.")
    if candidate.source_domain not in {"supplement", "food"}:
        raise RetrainingSecurityError("Dataset source domain is not allowed.")
    if candidate.task_type not in {
        "yolo_detection",
        "paddleocr_detection",
        "paddleocr_recognition",
        "food_classification",
        "embedding",
    }:
        raise RetrainingSecurityError("Dataset task type is not allowed.")
    if candidate.label_status not in {HUMAN_REVIEWED_STATUS, "auto_labeled"}:
        raise RetrainingSecurityError("Dataset label status is not exportable.")
    _validate_private_source_ref(candidate.source_ref)
    if candidate.label_hash is not None and len(candidate.label_hash) != SHA256_HEX_LENGTH:
        raise RetrainingSecurityError("Dataset label hash must be a SHA-256 hex string.")
    validate_sanitized_label_snapshot(candidate.label_snapshot)


def validate_sanitized_label_snapshot(label_snapshot: Mapping[str, Any]) -> None:
    """Reject label snapshots with raw data, object URLs, paths, or secrets.

    Args:
        label_snapshot: Candidate structured label payload.

    Raises:
        RetrainingSecurityError: If the payload contains unsafe keys or values.
    """
    _validate_json_value(label_snapshot)


def validate_supplement_section_training_label_snapshot(
    label_snapshot: Mapping[str, Any],
) -> None:
    """Validate one reviewed supplement section YOLO training label snapshot.

    Args:
        label_snapshot: Human-reviewed supplement section label payload.

    Raises:
        RetrainingSecurityError: If the payload contains unsafe data, has not
            passed human training approval, uses non-source-image coordinates,
            or lacks valid supplement section boxes.
    """
    validate_sanitized_label_snapshot(label_snapshot)
    _validate_supplement_section_training_approval(label_snapshot)
    _normalize_supplement_section_box_labels(label_snapshot.get("boxes"))


def _validate_json_value(value: Any, *, key_path: str = "") -> None:
    """Validate a JSON-like label value recursively."""
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            if not isinstance(key, str):
                raise RetrainingSecurityError("Label snapshot keys must be strings.")
            normalized_key = "".join(
                character for character in key.casefold() if character.isalnum()
            )
            if normalized_key in NORMALIZED_FORBIDDEN_LABEL_KEYS:
                raise RetrainingSecurityError(f"Forbidden label snapshot key: {key_path}{key}")
            _validate_json_value(nested_value, key_path=f"{key_path}{key}.")
    elif isinstance(value, list):
        for nested_value in value:
            _validate_json_value(nested_value, key_path=key_path)
    elif isinstance(value, str):
        _validate_safe_string(value)
    elif isinstance(value, bool) or value is None:
        return
    elif isinstance(value, int | float):
        if not math.isfinite(float(value)):
            raise RetrainingSecurityError("Label snapshot contains a non-finite number.")
    else:
        raise RetrainingSecurityError("Label snapshot contains a non-JSON value.")


def _validate_safe_string(value: str) -> None:
    """Reject string values that look like paths, URLs, secrets, or PII."""
    folded = value.casefold()
    if "://" in value or value.startswith("/") or ".." in value:
        raise RetrainingSecurityError("Label snapshot contains a path or URL-like value.")
    if any(marker in folded for marker in SECRET_LIKE_VALUE_MARKERS):
        raise RetrainingSecurityError("Label snapshot contains a secret-like value.")
    if PII_LIKE_TEXT_PATTERN.search(value):
        raise RetrainingSecurityError("Label snapshot contains PII-like text.")


def _validate_private_source_ref(source_ref: str) -> None:
    """Validate backend-only source refs such as media:<uuid>."""
    if "://" in source_ref or source_ref.startswith("/") or ".." in source_ref:
        raise RetrainingSecurityError("Dataset source ref must not be a URL or filesystem path.")
    for prefix in PRIVATE_SOURCE_REF_PREFIXES:
        if source_ref.startswith(prefix):
            UUID(source_ref.removeprefix(prefix))
            return
    raise RetrainingSecurityError("Dataset source ref must use a backend-only private token.")


def _normalize_json_object(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return a JSON round-tripped dict for deterministic output."""
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _sha256_json(value: object) -> str:
    """Return a SHA-256 digest for deterministic JSON payloads."""
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _manifest_items_for_task(manifest: Mapping[str, Any], task_type: str) -> list[dict[str, Any]]:
    """Return validated manifest rows for one task type."""
    if manifest.get("schema_version") != DATASET_EXPORT_SCHEMA_VERSION:
        raise RetrainingSecurityError("Unsupported dataset export manifest schema.")
    items = manifest.get("items")
    if not isinstance(items, list):
        raise RetrainingSecurityError("Dataset export manifest items must be a list.")
    selected: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise RetrainingSecurityError("Dataset export manifest item must be an object.")
        if item.get("task_type") != task_type:
            continue
        source_ref = item.get("source_ref")
        split = item.get("split")
        label_snapshot = item.get("label_snapshot")
        if not isinstance(source_ref, str) or not isinstance(split, str):
            raise RetrainingSecurityError("Dataset export manifest item is missing metadata.")
        if not isinstance(label_snapshot, dict):
            raise RetrainingSecurityError("Dataset export manifest label snapshot must be object.")
        _validate_private_source_ref(source_ref)
        validate_sanitized_label_snapshot(label_snapshot)
        selected.append(item)
    return selected


def _normalize_box_labels(raw_boxes: object) -> list[dict[str, Any]]:
    """Validate normalized box labels used by YOLO/PaddleOCR detection exports."""
    if not isinstance(raw_boxes, list) or not raw_boxes:
        raise RetrainingSecurityError("Detection export requires at least one normalized box.")
    boxes = []
    for raw_box in raw_boxes:
        if not isinstance(raw_box, Mapping):
            raise RetrainingSecurityError("Detection box must be an object.")
        class_id = raw_box.get("class_id", 0)
        if isinstance(class_id, bool) or not isinstance(class_id, int) or class_id < 0:
            raise RetrainingSecurityError("Detection box class_id must be a nonnegative integer.")
        normalized = {"class_id": class_id}
        for key in ("x_center", "y_center", "width", "height"):
            value = raw_box.get(key)
            if (
                isinstance(value, bool)
                or not isinstance(value, int | float)
                or not 0 <= float(value) <= 1
            ):
                raise RetrainingSecurityError("Detection box coordinates must be normalized.")
            normalized[key] = float(value)
        boxes.append(normalized)
    return boxes


def _normalize_supplement_section_box_labels(raw_boxes: object) -> list[dict[str, Any]]:
    """Validate and map supplement section box labels to fixed YOLO class ids.

    Args:
        raw_boxes: Raw label snapshot boxes.

    Returns:
        Normalized YOLO boxes with canonical section labels.

    Raises:
        RetrainingSecurityError: If a box has no supported section label.
    """
    if not isinstance(raw_boxes, list) or not raw_boxes:
        raise RetrainingSecurityError("Supplement section export requires at least one box.")
    boxes = []
    for raw_box in raw_boxes:
        if not isinstance(raw_box, Mapping):
            raise RetrainingSecurityError("Supplement section box must be an object.")
        label = _canonical_supplement_section_label(raw_box)
        normalized = {
            "class_id": SUPPLEMENT_SECTION_CLASS_NAMES.index(label),
            "label": label,
        }
        normalized.update(_normalized_detection_coordinates(raw_box))
        boxes.append(normalized)
    return boxes


def _validate_supplement_section_training_approval(
    label_snapshot: Mapping[str, Any],
) -> None:
    """Reject OCR-derived section candidates before human training approval."""
    if label_snapshot.get("training_export_allowed") is False:
        raise RetrainingSecurityError(
            "Supplement section label snapshot requires training export approval."
        )
    if label_snapshot.get("human_review_required") is True:
        raise RetrainingSecurityError("Supplement section label snapshot still requires review.")
    coordinate_space = label_snapshot.get("coordinate_space")
    if coordinate_space is not None and coordinate_space != "source_image":
        raise RetrainingSecurityError(
            "Supplement section label snapshot must use source_image coordinates."
        )


def _canonical_supplement_section_label(raw_box: Mapping[str, Any]) -> str:
    """Return the canonical supplement section label for one box.

    Args:
        raw_box: Raw box mapping.

    Returns:
        Canonical section label.

    Raises:
        RetrainingSecurityError: If the label is missing or not a section label.
    """
    raw_label = raw_box.get("label") or raw_box.get("class_name") or raw_box.get("section_type")
    if not isinstance(raw_label, str) or not raw_label.strip():
        raise RetrainingSecurityError("Supplement section boxes require a semantic label.")
    label = normalize_vision_label(raw_label)
    if label not in VISION_SECTION_LABELS:
        raise RetrainingSecurityError("Supplement section box label is not allowed.")
    return label


def _normalized_detection_coordinates(raw_box: Mapping[str, Any]) -> dict[str, float]:
    """Validate normalized YOLO coordinates for one box.

    Args:
        raw_box: Raw box mapping.

    Returns:
        Normalized coordinate mapping.

    Raises:
        RetrainingSecurityError: If any coordinate is missing or out of range.
    """
    coordinates: dict[str, float] = {}
    for key in ("x_center", "y_center", "width", "height"):
        value = raw_box.get(key)
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not 0 <= float(value) <= 1
        ):
            raise RetrainingSecurityError("Detection box coordinates must be normalized.")
        coordinates[key] = float(value)
    return coordinates


def _confirmed_text_label(raw_label: object) -> str:
    """Validate a confirmed PaddleOCR recognition label."""
    if not isinstance(raw_label, str) or not raw_label.strip():
        raise RetrainingSecurityError("PaddleOCR recognition export requires a text label.")
    label = raw_label.strip()
    if len(label) > MAX_RECOGNITION_TEXT_LABEL_LENGTH:
        raise RetrainingSecurityError("PaddleOCR recognition text label is too long.")
    _validate_safe_string(label)
    return label


def _optional_crop_box(raw_box: object) -> dict[str, float] | None:
    """Validate an optional normalized crop box for recognition training.

    Args:
        raw_box: Optional crop box mapping in source-image coordinates.

    Returns:
        Normalized crop box, or None when the recognition source is already a
        cropped text image.

    Raises:
        RetrainingSecurityError: If the crop box shape is invalid.
    """
    if raw_box is None:
        return None
    if not isinstance(raw_box, Mapping):
        raise RetrainingSecurityError("PaddleOCR recognition crop_box must be an object.")
    normalized: dict[str, float] = {}
    for key in ("x_center", "y_center", "width", "height"):
        value = raw_box.get(key)
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not 0 <= float(value) <= 1
        ):
            raise RetrainingSecurityError("PaddleOCR recognition crop_box must be normalized.")
        normalized[key] = float(value)
    if normalized["width"] <= 0 or normalized["height"] <= 0:
        raise RetrainingSecurityError("PaddleOCR recognition crop_box dimensions must be positive.")
    return normalized


def _metric_values_by_name(eval_results: Sequence[ModelEvalResult]) -> dict[str, Decimal]:
    """Return one metric value per metric name from persisted eval rows."""
    metric_values: dict[str, Decimal] = {}
    for result in eval_results:
        if result.metric_name not in metric_values:
            metric_values[result.metric_name] = Decimal(result.metric_value)
    return metric_values


def _validate_metric_gate_rule(rule: MetricGateRule) -> None:
    """Validate one metric gate rule."""
    if not rule.metric_name.strip():
        raise ModelPromotionGateError("Metric name is required.")
    if rule.comparator not in {">=", ">", "<=", "<"}:
        raise ModelPromotionGateError("Unsupported metric gate comparator.")
    if not math.isfinite(float(rule.threshold)) or rule.threshold < 0:
        raise ModelPromotionGateError("Metric gate threshold must be nonnegative and finite.")


def _compare_metric(value: Decimal, comparator: str, threshold: Decimal) -> bool:
    """Compare a metric value against a threshold."""
    if comparator == ">=":
        return value >= threshold
    if comparator == ">":
        return value > threshold
    if comparator == "<=":
        return value <= threshold
    if comparator == "<":
        return value < threshold
    raise ModelPromotionGateError("Unsupported metric gate comparator.")


def _decimal_to_string(value: Decimal) -> str:
    """Serialize a Decimal without scientific notation for audit snapshots."""
    return format(value.normalize(), "f")
