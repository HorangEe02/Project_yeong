"""Gate supplement-section YOLO dataset readiness before training.

This script reads only redacted summaries from the supplement section bbox
pipeline:

* strict annotation decision preflight,
* reviewed template promotion summary,
* materialized Ultralytics YOLO dataset summary,
* optional dataset validation summary.

It never reads source rows, source images, OCR text, provider payloads, LLM
outputs, image bytes, or database records. YOLO training is allowed only after
strict human bbox review, successful promotion, and a non-empty train/val
dataset with one label file per image.

References:
    https://docs.ultralytics.com/datasets/detect/
    https://docs.ultralytics.com/tasks/detect/
    https://docs.python.org/3/library/argparse.html
    https://docs.python.org/3/library/json.html
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import (  # noqa: E402
    materialize_supplement_section_yolo_dataset as materializer,
)
from scripts import (  # noqa: E402
    preflight_supplement_yolo_annotation_decisions as annotation_preflight,
)
from scripts import (  # noqa: E402
    promote_supplement_yolo_annotation_template as promotion,
)

SCHEMA_VERSION = "supplement-yolo-section-dataset-gate-v1"
ANNOTATION_PREFLIGHT_SCHEMA = annotation_preflight.SCHEMA_VERSION
PROMOTION_SCHEMA = promotion.SUMMARY_SCHEMA_VERSION
MATERIALIZE_SCHEMA = materializer.SUMMARY_SCHEMA_VERSION
STATUS_READY = "ready_for_section_yolo_training_dataset"
STATUS_BLOCKED_ANNOTATION = "blocked_by_annotation_review"
STATUS_BLOCKED_PROMOTION = "blocked_by_template_promotion"
STATUS_BLOCKED_DATASET = "blocked_by_dataset_materialization"
STATUS_BLOCKED_VALIDATION = "blocked_by_dataset_validation"
STATUS_ERROR = "error"
SOURCE_DOC_URLS = (
    "https://docs.ultralytics.com/datasets/detect/",
    "https://docs.ultralytics.com/tasks/detect/",
    "https://docs.python.org/3/library/argparse.html",
    "https://docs.python.org/3/library/json.html",
)
ALLOWED_SOURCE_DOC_URLS = frozenset(SOURCE_DOC_URLS)
MAX_SAFE_TEXT_LENGTH = 160
READY_NEXT_STEPS = (
    "run_yolo26_section_training_with_materialized_dataset",
    "evaluate_section_bbox_model_on_holdout_or_val_split",
    "keep_model_promotion_blocked_until_metric_gate_passes",
)
NEXT_STEPS_BY_STATUS = {
    STATUS_BLOCKED_ANNOTATION: (
        "complete_supplement_section_bbox_review",
        "rerun_yolo_annotation_preflight_require_all_reviewed",
        "rerun_yolo_section_dataset_gate",
    ),
    STATUS_BLOCKED_PROMOTION: (
        "run_yolo_annotation_template_promotion_after_strict_preflight",
        "rerun_yolo_section_dataset_gate",
    ),
    STATUS_BLOCKED_DATASET: (
        "materialize_section_yolo_dataset_from_promoted_export",
        "validate_yolo_dataset_with_require_files",
        "rerun_yolo_section_dataset_gate",
    ),
    STATUS_BLOCKED_VALIDATION: (
        "run_validate_supplement_section_yolo_dataset_require_files",
        "rerun_yolo_section_dataset_gate",
    ),
    STATUS_READY: READY_NEXT_STEPS,
}
TRAINING_POLICY_FLAGS = {
    "official_yolo26_detect_reference_verified": True,
    "yolo26_pretrained_checkpoint_allowed_for_initialization": True,
    "coco_pretrained_allowed_for_final_section_labels": False,
    "custom_supplement_section_dataset_required": True,
    "require_files_dataset_validation_required": True,
    "section_predictions_review_required_until_metric_gate": True,
    "model_promotion_requires_separate_metric_gate": True,
}
REQUIRED_SECTION_LABELS = (
    "product_identity",
    "supplement_facts",
    "ingredient_amounts",
    "precautions",
    "allergen_warning",
    "intake_method",
    "other_ingredients",
    "functional_claims",
)


class YoloSectionDatasetGateError(ValueError):
    """Raised when YOLO section dataset gate inputs cannot be trusted."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotation-preflight", type=Path, required=True)
    parser.add_argument("--template-promotion-summary", type=Path, default=None)
    parser.add_argument("--dataset-materialize-summary", type=Path, default=None)
    parser.add_argument("--dataset-validation-summary", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write YOLO section dataset gate JSON and optional Markdown.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    output_path = args.output.expanduser().resolve()
    markdown_output = (
        args.markdown_output.expanduser().resolve() if args.markdown_output is not None else None
    )
    try:
        summary = build_yolo_section_dataset_gate(
            annotation_preflight_path=args.annotation_preflight.expanduser().resolve(),
            template_promotion_summary_path=(
                args.template_promotion_summary.expanduser().resolve()
                if args.template_promotion_summary is not None
                else None
            ),
            dataset_materialize_summary_path=(
                args.dataset_materialize_summary.expanduser().resolve()
                if args.dataset_materialize_summary is not None
                else None
            ),
            dataset_validation_summary_path=(
                args.dataset_validation_summary.expanduser().resolve()
                if args.dataset_validation_summary is not None
                else None
            ),
        )
        _write_json(output_path, summary)
        if markdown_output is not None:
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            markdown_output.write_text(build_markdown(summary), encoding="utf-8")
        print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    except (OSError, json.JSONDecodeError, YoloSectionDatasetGateError, ValueError) as exc:
        failure = _failure_summary(output_path=output_path, error=exc)
        _write_json(output_path, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None


def build_yolo_section_dataset_gate(
    *,
    annotation_preflight_path: Path,
    template_promotion_summary_path: Path | None = None,
    dataset_materialize_summary_path: Path | None = None,
    dataset_validation_summary_path: Path | None = None,
) -> dict[str, Any]:
    """Build a redacted YOLO section dataset readiness gate.

    Args:
        annotation_preflight_path: Strict bbox decision preflight summary.
        template_promotion_summary_path: Optional reviewed template promotion summary.
        dataset_materialize_summary_path: Optional materialized YOLO dataset summary.
        dataset_validation_summary_path: Optional validator CLI summary.

    Returns:
        Redacted readiness gate summary.

    Raises:
        YoloSectionDatasetGateError: If an input is unsafe or unsupported.
    """
    annotation = _load_summary(
        annotation_preflight_path, expected_schema=ANNOTATION_PREFLIGHT_SCHEMA
    )
    promotion_payload = (
        _load_summary(template_promotion_summary_path, expected_schema=PROMOTION_SCHEMA)
        if template_promotion_summary_path is not None
        else None
    )
    materialized = (
        _load_summary(dataset_materialize_summary_path, expected_schema=MATERIALIZE_SCHEMA)
        if dataset_materialize_summary_path is not None
        else None
    )
    validation = (
        _load_validation_summary(dataset_validation_summary_path)
        if dataset_validation_summary_path is not None
        else None
    )

    counts = _counts(
        annotation=annotation, promotion_payload=promotion_payload, materialized=materialized
    )
    strict_annotation_ready = _strict_annotation_ready(annotation, counts=counts)
    promotion_ready = _promotion_ready(
        annotation=annotation,
        promotion_payload=promotion_payload,
        counts=counts,
    )
    dataset_ready = _dataset_ready(
        promotion_payload=promotion_payload,
        materialized=materialized,
        counts=counts,
    )
    validation_ready = _validation_ready(
        materialized=materialized,
        validation=validation,
        counts=counts,
    )

    status = _status(
        strict_annotation_ready=strict_annotation_ready,
        promotion_ready=promotion_ready,
        dataset_ready=dataset_ready,
        validation_ready=validation_ready,
    )
    allowed = status == STATUS_READY
    input_paths = {
        "annotation_preflight": annotation_preflight_path,
        "template_promotion_summary": template_promotion_summary_path,
        "dataset_materialize_summary": dataset_materialize_summary_path,
        "dataset_validation_summary": dataset_validation_summary_path,
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {
            key: path.name if path is not None else None
            for key, path in sorted(input_paths.items())
        },
        "input_path_hashes": {
            key: _fingerprint_text(str(path.expanduser())) if path is not None else None
            for key, path in sorted(input_paths.items())
        },
        **counts,
        "strict_annotation_review_requested": annotation.get("require_all_reviewed") is True,
        "annotation_ready_for_strict_promotion": annotation.get("ready_for_strict_promotion")
        is True,
        "annotation_ready_for_requested_promotion": annotation.get("ready_for_requested_promotion")
        is True,
        "strict_annotation_ready": strict_annotation_ready,
        "template_promotion_ready": promotion_ready,
        "dataset_materialization_ready": dataset_ready,
        "dataset_validation_ready": validation_ready,
        "required_section_labels": list(REQUIRED_SECTION_LABELS),
        "missing_required_section_labels": _missing_required_section_labels(validation),
        "validation_summary_provided": validation is not None,
        "section_yolo_training_allowed_now": allowed,
        "section_yolo_training_gate_required": True,
        "model_promotion_allowed_now": False,
        **TRAINING_POLICY_FLAGS,
        "next_steps": list(NEXT_STEPS_BY_STATUS[status]),
        "db_write_performed": False,
        "database_connection_opened": False,
        "source_rows_read": False,
        "source_image_read_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    _reject_unsafe_payload(summary)
    return summary


def build_markdown(summary: Mapping[str, Any]) -> str:
    """Build a redacted YOLO section dataset gate report.

    Args:
        summary: Gate summary.

    Returns:
        Markdown report text.
    """
    _reject_unsafe_payload(summary)
    next_steps = "\n".join(f"- `{_safe_token(str(step))}`" for step in summary["next_steps"])
    markdown = "\n".join(
        [
            "# Supplement YOLO Section Dataset Gate",
            "",
            f"Schema: `{SCHEMA_VERSION}`",
            "",
            "이 문서는 supplement label bbox annotation이 YOLO26 학습 데이터셋으로 넘어갈 수 있는지 aggregate summary만으로 판단합니다. 이미지 경로, source ref, 라벨 row, OCR 원문은 포함하지 않습니다.",
            "",
            f"- Status: `{_safe_token(str(summary.get('status') or 'unknown'))}`",
            f"- Training allowed now: `{_bool_text(summary.get('section_yolo_training_allowed_now'))}`",
            f"- Model promotion allowed now: `{_bool_text(summary.get('model_promotion_allowed_now'))}`",
            "",
            "## YOLO26 Policy",
            "",
            f"- Official YOLO26 Detect reference verified: `{_bool_text(summary.get('official_yolo26_detect_reference_verified'))}`",
            f"- Pretrained checkpoint allowed for initialization: `{_bool_text(summary.get('yolo26_pretrained_checkpoint_allowed_for_initialization'))}`",
            f"- COCO pretrained allowed for final section labels: `{_bool_text(summary.get('coco_pretrained_allowed_for_final_section_labels'))}`",
            f"- Custom supplement section dataset required: `{_bool_text(summary.get('custom_supplement_section_dataset_required'))}`",
            f"- Require-files dataset validation required: `{_bool_text(summary.get('require_files_dataset_validation_required'))}`",
            f"- Section predictions require review until metric gate: `{_bool_text(summary.get('section_predictions_review_required_until_metric_gate'))}`",
            f"- Model promotion requires separate metric gate: `{_bool_text(summary.get('model_promotion_requires_separate_metric_gate'))}`",
            "",
            "## Counts",
            "",
            f"- Template rows: `{_non_negative_int(summary.get('template_row_count'))}`",
            f"- Valid accepted rows: `{_non_negative_int(summary.get('valid_accepted_row_count'))}`",
            f"- Pending annotation actions: `{_non_negative_int(summary.get('pending_operator_action_count'))}`",
            f"- Promoted items: `{_non_negative_int(summary.get('promoted_item_count'))}`",
            f"- Materialized items: `{_non_negative_int(summary.get('materialized_item_count'))}`",
            f"- Images: `{_non_negative_int(summary.get('image_count'))}`",
            f"- Labels: `{_non_negative_int(summary.get('label_count'))}`",
            f"- Train split: `{_non_negative_int(summary.get('train_split_count'))}`",
            f"- Val split: `{_non_negative_int(summary.get('val_split_count'))}`",
            f"- Test split: `{_non_negative_int(summary.get('test_split_count'))}`",
            "",
            "## Gate Checks",
            "",
            f"- Strict annotation ready: `{_bool_text(summary.get('strict_annotation_ready'))}`",
            f"- Template promotion ready: `{_bool_text(summary.get('template_promotion_ready'))}`",
            f"- Dataset materialization ready: `{_bool_text(summary.get('dataset_materialization_ready'))}`",
            f"- Dataset validation ready: `{_bool_text(summary.get('dataset_validation_ready'))}`",
            f"- Missing required section labels: `{', '.join(summary.get('missing_required_section_labels') or []) or 'none'}`",
            "",
            "## Next Steps",
            "",
            next_steps,
            "",
            "## Rule",
            "",
            "YOLO26 COCO pretrained checkpoint는 초기화 또는 smoke test에는 사용할 수 있지만 supplement section label의 최종 정답지나 자동 승인 근거로 사용할 수 없습니다. YOLO26 학습은 strict bbox review, reviewed template promotion, train/val이 모두 있는 materialized dataset, product identity/facts/ingredient/intake/precaution/allergen section class contract, require-files validation이 통과한 뒤에만 허용합니다. 모델 promotion은 별도 metric gate 전까지 계속 차단합니다.",
            "",
        ]
    )
    _reject_unsafe_payload(markdown)
    return markdown


def _counts(
    *,
    annotation: Mapping[str, Any],
    promotion_payload: Mapping[str, Any] | None,
    materialized: Mapping[str, Any] | None,
) -> dict[str, int]:
    """Return aggregate counts for the gate.

    Args:
        annotation: Annotation preflight summary.
        promotion_payload: Optional promotion summary.
        materialized: Optional materialization summary.

    Returns:
        Count mapping.
    """
    promotion_split_counts = _split_counts(promotion_payload)
    materialized_split_counts = _split_counts(materialized)
    return {
        "template_row_count": _non_negative_int(annotation.get("template_row_count")),
        "valid_accepted_row_count": _non_negative_int(annotation.get("valid_accepted_row_count")),
        "pending_operator_action_count": _non_negative_int(
            annotation.get("pending_operator_action_count")
        ),
        "pending_review_row_count": _non_negative_int(annotation.get("pending_review_row_count")),
        "blank_box_row_count": _non_negative_int(annotation.get("blank_box_row_count")),
        "invalid_row_count": _non_negative_int(annotation.get("invalid_row_count")),
        "unpromotable_accepted_row_count": _non_negative_int(
            annotation.get("unpromotable_accepted_row_count")
        ),
        "promoted_item_count": _non_negative_int(
            promotion_payload.get("promoted_item_count") if promotion_payload else 0
        ),
        "promotion_skip_count": sum(
            _non_negative_int(value)
            for value in _mapping(
                promotion_payload.get("skip_reason_counts") if promotion_payload else {}
            ).values()
        ),
        "promotion_train_split_count": promotion_split_counts["train"],
        "promotion_val_split_count": promotion_split_counts["val"],
        "promotion_test_split_count": promotion_split_counts["test"],
        "materialized_item_count": _non_negative_int(
            materialized.get("item_count") if materialized else 0
        ),
        "image_count": _non_negative_int(materialized.get("image_count") if materialized else 0),
        "label_count": _non_negative_int(materialized.get("label_count") if materialized else 0),
        "train_split_count": materialized_split_counts["train"],
        "val_split_count": materialized_split_counts["val"],
        "test_split_count": materialized_split_counts["test"],
    }


def _strict_annotation_ready(annotation: Mapping[str, Any], *, counts: Mapping[str, int]) -> bool:
    """Return whether strict bbox review is ready.

    Args:
        annotation: Annotation preflight summary.
        counts: Count mapping.

    Returns:
        True when every row was reviewed and at least one row is exportable.
    """
    return (
        annotation.get("require_all_reviewed") is True
        and annotation.get("ready_for_strict_promotion") is True
        and annotation.get("ready_for_requested_promotion") is True
        and counts["valid_accepted_row_count"] > 0
        and counts["pending_operator_action_count"] == 0
        and counts["pending_review_row_count"] == 0
        and counts["blank_box_row_count"] == 0
        and counts["invalid_row_count"] == 0
        and counts["unpromotable_accepted_row_count"] == 0
    )


def _promotion_ready(
    *,
    annotation: Mapping[str, Any],
    promotion_payload: Mapping[str, Any] | None,
    counts: Mapping[str, int],
) -> bool:
    """Return whether template promotion summary is ready.

    Args:
        annotation: Annotation preflight summary.
        promotion_payload: Optional promotion summary.
        counts: Count mapping.

    Returns:
        True when promotion produced one item per valid accepted annotation.
    """
    if promotion_payload is None:
        return False
    return (
        promotion_payload.get("export_artifact_written") is True
        and promotion_payload.get("source_map_written") is True
        and promotion_payload.get("training_performed") is False
        and counts["promoted_item_count"] > 0
        and counts["promoted_item_count"] == counts["valid_accepted_row_count"]
        and _non_negative_int(promotion_payload.get("template_row_count"))
        == _non_negative_int(annotation.get("template_row_count"))
        and counts["promotion_skip_count"] == 0
        and counts["promotion_train_split_count"] > 0
        and counts["promotion_val_split_count"] > 0
    )


def _dataset_ready(
    *,
    promotion_payload: Mapping[str, Any] | None,
    materialized: Mapping[str, Any] | None,
    counts: Mapping[str, int],
) -> bool:
    """Return whether materialized YOLO files are ready.

    Args:
        promotion_payload: Optional promotion summary.
        materialized: Optional materialization summary.
        counts: Count mapping.

    Returns:
        True when materialization produced non-empty train/val image-label pairs.
    """
    if promotion_payload is None or materialized is None:
        return False
    return (
        materialized.get("status") == "ok"
        and counts["materialized_item_count"] == counts["promoted_item_count"]
        and counts["image_count"] == counts["materialized_item_count"]
        and counts["label_count"] == counts["materialized_item_count"]
        and counts["train_split_count"] > 0
        and counts["val_split_count"] > 0
        and counts["train_split_count"] == counts["promotion_train_split_count"]
        and counts["val_split_count"] == counts["promotion_val_split_count"]
        and counts["test_split_count"] == counts["promotion_test_split_count"]
        and materialized.get("source_ref_printed") is False
        and materialized.get("source_path_printed") is False
        and materialized.get("raw_ocr_text_stored") is False
        and materialized.get("raw_provider_payload_stored") is False
    )


def _validation_ready(
    *,
    materialized: Mapping[str, Any] | None,
    validation: Mapping[str, Any] | None,
    counts: Mapping[str, int],
) -> bool:
    """Return whether optional dataset validation summary is ready.

    Args:
        materialized: Optional materialization summary.
        validation: Optional validation CLI summary.
        counts: Count mapping.

    Returns:
        True when require-files validation is provided and matches the
        materialized image-label counts.
    """
    if validation is None:
        return False
    if materialized is None:
        return False
    return (
        validation.get("ok") is True
        and validation.get("require_files") is True
        and _missing_required_section_labels(validation) == []
        and _non_negative_int(validation.get("image_count")) == counts["image_count"]
        and _non_negative_int(validation.get("label_count")) == counts["label_count"]
        and validation.get("dataset_yaml") == materialized.get("dataset_yaml")
    )


def _missing_required_section_labels(validation: Mapping[str, Any] | None) -> list[str]:
    """Return required section labels missing from validation output.

    Args:
        validation: Optional validation summary.

    Returns:
        Sorted missing required labels. All labels are missing when validation
        was not provided, because YOLO training must be gated by require-files
        validation.
    """
    if validation is None:
        return list(REQUIRED_SECTION_LABELS)
    required_sections = set(_safe_string_list(validation.get("required_sections")))
    names = set(_safe_string_list(validation.get("names")))
    observed = required_sections & names if required_sections else names
    return sorted(set(REQUIRED_SECTION_LABELS) - observed)


def _status(
    *,
    strict_annotation_ready: bool,
    promotion_ready: bool,
    dataset_ready: bool,
    validation_ready: bool,
) -> str:
    """Return the gate status.

    Args:
        strict_annotation_ready: Strict annotation readiness.
        promotion_ready: Promotion readiness.
        dataset_ready: Materialization readiness.
        validation_ready: Validation readiness.

    Returns:
        Stable status token.
    """
    if not strict_annotation_ready:
        return STATUS_BLOCKED_ANNOTATION
    if not promotion_ready:
        return STATUS_BLOCKED_PROMOTION
    if not dataset_ready:
        return STATUS_BLOCKED_DATASET
    if not validation_ready:
        return STATUS_BLOCKED_VALIDATION
    return STATUS_READY


def _load_summary(path: Path | None, *, expected_schema: str) -> dict[str, Any]:
    """Load and validate one JSON summary.

    Args:
        path: Summary path.
        expected_schema: Required schema version.

    Returns:
        Parsed summary.

    Raises:
        YoloSectionDatasetGateError: If the summary is missing, unsafe, or unsupported.
    """
    if path is None:
        raise YoloSectionDatasetGateError("Required YOLO section dataset gate input is missing.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise YoloSectionDatasetGateError("YOLO section dataset gate input must be a JSON object.")
    _reject_unsafe_payload(payload)
    if payload.get("schema_version") != expected_schema:
        raise YoloSectionDatasetGateError("YOLO section dataset gate input schema is unsupported.")
    return payload


def _load_validation_summary(path: Path | None) -> dict[str, Any]:
    """Load optional validator CLI output.

    Args:
        path: Validation summary path.

    Returns:
        Parsed validator summary.

    Raises:
        YoloSectionDatasetGateError: If the validation summary is unsafe.
    """
    if path is None:
        raise YoloSectionDatasetGateError("Dataset validation summary path is missing.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise YoloSectionDatasetGateError("Dataset validation summary must be a JSON object.")
    _reject_unsafe_payload(payload)
    return payload


def _split_counts(payload: Mapping[str, Any] | None) -> dict[str, int]:
    """Return train/val/test split counts.

    Args:
        payload: Optional summary with split_counts.

    Returns:
        Split counts with missing values as zero.
    """
    raw = _mapping(payload.get("split_counts") if payload is not None else {})
    return {
        "train": _non_negative_int(raw.get("train", 0)),
        "val": _non_negative_int(raw.get("val", 0)),
        "test": _non_negative_int(raw.get("test", 0)),
    }


def _mapping(value: object) -> Mapping[str, Any]:
    """Return a string-key mapping.

    Args:
        value: Candidate mapping.

    Returns:
        Mapping value.

    Raises:
        YoloSectionDatasetGateError: If the value is not a mapping.
    """
    if not isinstance(value, Mapping):
        raise YoloSectionDatasetGateError("Expected a JSON object mapping.")
    if not all(isinstance(key, str) for key in value):
        raise YoloSectionDatasetGateError("JSON object keys must be strings.")
    return value


def _safe_string_list(value: object) -> list[str]:
    """Return a safe list of short string tokens.

    Args:
        value: Candidate list value.

    Returns:
        Safe string list.

    Raises:
        YoloSectionDatasetGateError: If the value is not a safe token list.
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise YoloSectionDatasetGateError("Expected a JSON string list.")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise YoloSectionDatasetGateError("Expected a JSON string list.")
        token = _safe_token(item)
        if token != item.strip():
            raise YoloSectionDatasetGateError("Expected a safe string token list.")
        result.append(token)
    return result


def _non_negative_int(value: Any) -> int:
    """Return a non-negative integer.

    Args:
        value: Candidate value.

    Returns:
        Non-negative integer.

    Raises:
        YoloSectionDatasetGateError: If the value is not a non-negative integer.
    """
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise YoloSectionDatasetGateError("Expected a non-negative integer.")
    return value


def _safe_token(value: str) -> str:
    """Return a safe token for Markdown/JSON output."""
    cleaned = value.strip()
    if not cleaned:
        return "unknown"
    if len(cleaned) > MAX_SAFE_TEXT_LENGTH:
        return "truncated_token"
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789가-힣_.:-")
    return cleaned if all(character in allowed for character in cleaned) else "unsafe_token"


def _bool_text(value: object) -> str:
    """Return stable lower-case boolean text."""
    return "true" if value is True else "false"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write one JSON object.

    Args:
        path: Destination path.
        payload: JSON payload.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _cli_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Return stdout-safe gate summary.

    Args:
        summary: Full gate summary.

    Returns:
        Minimal safe stdout payload.
    """
    return {
        "schema_version": summary.get("schema_version"),
        "status": summary.get("status"),
        "template_row_count": summary.get("template_row_count"),
        "valid_accepted_row_count": summary.get("valid_accepted_row_count"),
        "promoted_item_count": summary.get("promoted_item_count"),
        "materialized_item_count": summary.get("materialized_item_count"),
        "image_count": summary.get("image_count"),
        "label_count": summary.get("label_count"),
        "section_yolo_training_allowed_now": summary.get("section_yolo_training_allowed_now"),
        "dataset_validation_ready": summary.get("dataset_validation_ready"),
        "missing_required_section_labels": summary.get("missing_required_section_labels"),
        "coco_pretrained_allowed_for_final_section_labels": summary.get(
            "coco_pretrained_allowed_for_final_section_labels"
        ),
        "custom_supplement_section_dataset_required": summary.get(
            "custom_supplement_section_dataset_required"
        ),
        "model_promotion_requires_separate_metric_gate": summary.get(
            "model_promotion_requires_separate_metric_gate"
        ),
        "next_steps": summary.get("next_steps"),
    }


def _failure_summary(*, output_path: Path, error: Exception) -> dict[str, Any]:
    """Return a redacted failure summary.

    Args:
        output_path: Requested output path.
        error: Raised exception.

    Returns:
        Safe failure payload.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS_ERROR,
        "output_name": output_path.name,
        "error_type": type(error).__name__,
        "error": _safe_error(error),
        "db_write_performed": False,
        "database_connection_opened": False,
        "source_rows_read": False,
        "source_image_read_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
        **TRAINING_POLICY_FLAGS,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


def _safe_error(error: Exception) -> str:
    """Return a non-sensitive error message."""
    text = str(error)
    if "/" in text or "\\" in text or "://" in text:
        return "redacted_path_error"
    if len(text) > MAX_SAFE_TEXT_LENGTH:
        return "redacted_long_error"
    return text or type(error).__name__


def _sha256_file(path: Path) -> str:
    """Return file SHA-256 digest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(value: str) -> str:
    """Return SHA-256 digest for text."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fingerprint_text(value: str) -> str:
    """Return a short non-secret fingerprint for operator artifacts."""
    return f"fp-{_sha256_text(value)[:12]}"


FORBIDDEN_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "credential",
        "credentials",
        "diagnosis",
        "file_path",
        "image_base64",
        "image_bytes",
        "image_path",
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
        "raw_model_response",
        "raw_ocr_text",
        "raw_payload",
        "raw_provider_payload",
        "request_headers",
        "secret",
        "service_key",
        "signed_url",
        "source_ref",
        "url",
    }
)
FORBIDDEN_TEXT_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    "file://",
    "http://",
    "https://",
    "\\Users\\",
    "\\Volumes\\",
)


def _reject_unsafe_payload(value: object, *, key_path: tuple[str, ...] = ()) -> None:
    """Reject payloads containing unsafe keys or local path/source literals.

    Args:
        value: Payload value.
        key_path: Current key path for recursive checks.

    Raises:
        YoloSectionDatasetGateError: If unsafe content is found.
    """
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise YoloSectionDatasetGateError("Payload contains a non-string key.")
            nested_path = (*key_path, key)
            if key == "source_doc_urls":
                _validate_source_doc_urls(nested)
                continue
            if key in FORBIDDEN_KEYS:
                raise YoloSectionDatasetGateError("Payload contains an unsafe raw key.")
            _reject_unsafe_payload(nested, key_path=nested_path)
        return
    if isinstance(value, list | tuple):
        for nested in value:
            _reject_unsafe_payload(nested, key_path=key_path)
        return
    if isinstance(value, str) and any(marker in value for marker in FORBIDDEN_TEXT_MARKERS):
        raise YoloSectionDatasetGateError("Payload contains a path or URL literal.")


def _validate_source_doc_urls(value: object) -> None:
    """Validate official reference URLs.

    Args:
        value: Candidate source_doc_urls value.

    Raises:
        YoloSectionDatasetGateError: If the value is not the official allowlist.
    """
    if not isinstance(value, list):
        raise YoloSectionDatasetGateError("source_doc_urls must be a list.")
    if not set(value).issubset(ALLOWED_SOURCE_DOC_URLS):
        raise YoloSectionDatasetGateError("source_doc_urls must match the official allowlist.")


if __name__ == "__main__":
    main()
