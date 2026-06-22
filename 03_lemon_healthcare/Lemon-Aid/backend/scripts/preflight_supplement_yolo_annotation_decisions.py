"""Preflight supplement YOLO section annotation decisions before promotion.

This operator tool checks whether an edited ``annotation.todo.jsonl`` can be
passed to ``promote_supplement_yolo_annotation_template.py``. Blank bbox stubs
are reported as pending operator work and are never auto-approved for training.

The script does not write to the database, does not call OCR providers or LLMs,
does not train a model, and does not emit local absolute paths, raw OCR text,
provider payloads, product directory literals, or image bytes.

References:
    https://docs.ultralytics.com/datasets/detect/
    https://docs.ultralytics.com/tasks/detect/
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.learning import retraining  # noqa: E402

from scripts import promote_supplement_yolo_annotation_template as promoter  # noqa: E402

SCHEMA_VERSION = "supplement-yolo-annotation-decision-preflight-v1"
SOURCE_DOC_URLS = promoter.SOURCE_DOC_URLS
VALIDATION_CODE_MARKERS = (
    ("unsafe key", "unsafe_raw_field"),
    ("path or url", "unsafe_path_or_url"),
    ("local path", "unsafe_path_or_url"),
    ("unsupported", "unsupported_schema"),
    ("label_snapshot", "missing_label_snapshot"),
    ("requires boxes", "missing_boxes"),
    ("requires at least one box", "missing_boxes"),
    ("section label", "invalid_section_label"),
    ("label is not allowed", "invalid_section_label"),
    ("coordinates", "invalid_box_coordinates"),
    ("normalized", "invalid_box_coordinates"),
    ("positive", "invalid_box_area"),
    ("fixture_id", "invalid_fixture_id"),
    ("duplicate", "duplicate_fixture_id"),
    ("image_path", "invalid_image_path"),
    ("sha256", "image_sha256_mismatch"),
    ("split", "invalid_split"),
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument(
        "--source-map",
        type=Path,
        default=None,
        help="Planned source-map path. Defaults to <template>.source-map.json.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--default-split", choices=sorted(promoter.SUPPORTED_SPLITS), default="train"
    )
    parser.add_argument("--limit", type=int, default=promoter.DEFAULT_MAX_ROWS)
    parser.add_argument("--require-all-reviewed", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write a redacted supplement YOLO annotation preflight summary.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    template_path = args.template.expanduser().resolve()
    source_map_path = (
        args.source_map.expanduser().resolve()
        if args.source_map is not None
        else template_path.with_suffix(template_path.suffix + ".source-map.json")
    )
    output_path = args.output.expanduser().resolve()
    try:
        summary = preflight_yolo_annotation_decisions(
            template_path=template_path,
            source_map_path=source_map_path,
            default_split=args.default_split,
            limit=args.limit,
            require_all_reviewed=args.require_all_reviewed,
        )
        promoter._reject_unsafe_payload(summary)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    except (
        OSError,
        promoter.TemplatePromotionError,
        retraining.RetrainingSecurityError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        failure = _failure_summary(
            template_path=template_path,
            source_map_path=source_map_path,
            output_path=output_path,
            require_all_reviewed=args.require_all_reviewed,
            error=exc,
        )
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None


def preflight_yolo_annotation_decisions(
    *,
    template_path: Path,
    source_map_path: Path,
    default_split: str = "train",
    limit: int = promoter.DEFAULT_MAX_ROWS,
    require_all_reviewed: bool = False,
) -> dict[str, Any]:
    """Return redacted readiness for YOLO template promotion.

    Args:
        template_path: Operator-edited supplement YOLO annotation JSONL.
        source_map_path: Planned source-map path used to validate fixture image
            locality exactly like the promotion script.
        default_split: Split used when rows omit ``split``.
        limit: Planned promotion limit.
        require_all_reviewed: Whether every template row must be accepted before
            the requested promotion step is considered ready.

    Returns:
        Redacted aggregate preflight summary.
    """
    promoter._validate_args(default_split=default_split, limit=limit)
    rows = promoter._read_jsonl(template_path)
    scan = _scan_template_rows(
        rows=rows,
        template_path=template_path,
        source_map_path=source_map_path,
        default_split=default_split,
        limit=limit,
    )
    pending_operator_action_count = (
        scan.pending_review_row_count
        + scan.invalid_row_count
        + scan.unpromotable_accepted_row_count
    )
    ready_for_partial_promotion = (
        scan.valid_accepted_row_count > 0
        and scan.invalid_row_count == 0
        and scan.unpromotable_accepted_row_count == 0
    )
    ready_for_strict_promotion = (
        ready_for_partial_promotion
        and scan.valid_accepted_row_count == scan.template_row_count
        and scan.pending_review_row_count == 0
        and scan.blank_box_row_count == 0
        and scan.limit_reached_count == 0
    )
    ready_for_requested_promotion = (
        ready_for_strict_promotion if require_all_reviewed else ready_for_partial_promotion
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "template_name": template_path.name,
        "source_map_name": source_map_path.name,
        "template_row_count": scan.template_row_count,
        "valid_accepted_row_count": scan.valid_accepted_row_count,
        "pending_review_row_count": scan.pending_review_row_count,
        "reviewed_box_row_count": scan.reviewed_box_row_count,
        "blank_box_row_count": scan.blank_box_row_count,
        "invalid_row_count": scan.invalid_row_count,
        "unpromotable_accepted_row_count": scan.unpromotable_accepted_row_count,
        "image_missing_or_unresolved_count": scan.image_missing_or_unresolved_count,
        "image_sha256_mismatch_count": scan.image_sha256_mismatch_count,
        "duplicate_fixture_id_count": scan.duplicate_fixture_id_count,
        "limit_reached_count": scan.limit_reached_count,
        "split_counts": dict(sorted(scan.split_counts.items())),
        "status_counts": dict(sorted(scan.status_counts.items())),
        "invalid_reason_counts": dict(sorted(scan.invalid_reason_counts.items())),
        "pending_operator_action_count": pending_operator_action_count,
        "require_all_reviewed": require_all_reviewed,
        "ready_for_partial_promotion": ready_for_partial_promotion,
        "ready_for_strict_promotion": ready_for_strict_promotion,
        "ready_for_requested_promotion": ready_for_requested_promotion,
        "next_operator_action": _next_operator_action(
            invalid_count=scan.invalid_row_count,
            unpromotable_accepted_count=scan.unpromotable_accepted_row_count,
            blank_box_count=scan.blank_box_row_count,
            pending_review_count=scan.pending_review_row_count,
            ready_for_requested_promotion=ready_for_requested_promotion,
        ),
        "db_write_performed": False,
        "training_performed": False,
        "export_artifact_written": False,
        "source_map_written": False,
        "source_image_read_performed": True,
        "source_image_read_purpose": "fixture_sha256_integrity_check_only",
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
        "source_ref_printed": False,
        "image_path_printed": False,
        "labels_printed": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    promoter._reject_unsafe_payload(summary)
    return summary


class AnnotationScan:
    """Aggregate state for one YOLO annotation template scan."""

    def __init__(self) -> None:
        """Initialize counters."""
        self.template_row_count = 0
        self.valid_accepted_row_count = 0
        self.pending_review_row_count = 0
        self.reviewed_box_row_count = 0
        self.blank_box_row_count = 0
        self.invalid_row_count = 0
        self.unpromotable_accepted_row_count = 0
        self.image_missing_or_unresolved_count = 0
        self.image_sha256_mismatch_count = 0
        self.duplicate_fixture_id_count = 0
        self.limit_reached_count = 0
        self.seen_fixture_ids: set[str] = set()
        self.split_counts: Counter[str] = Counter()
        self.status_counts: Counter[str] = Counter()
        self.invalid_reason_counts: Counter[str] = Counter()


def _scan_template_rows(
    *,
    rows: list[dict[str, Any]],
    template_path: Path,
    source_map_path: Path,
    default_split: str,
    limit: int,
) -> AnnotationScan:
    """Scan annotation rows without promoting them.

    Args:
        rows: Parsed annotation template rows.
        template_path: Template JSONL path.
        source_map_path: Planned source-map path.
        default_split: Default dataset split.
        limit: Planned promotion limit.

    Returns:
        Aggregate scan counters.
    """
    scan = AnnotationScan()
    for row in rows:
        scan.template_row_count += 1
        try:
            _scan_template_row(
                row=row,
                scan=scan,
                template_path=template_path,
                source_map_path=source_map_path,
                default_split=default_split,
                limit=limit,
            )
        except (
            promoter.TemplatePromotionError,
            retraining.RetrainingSecurityError,
            ValueError,
        ) as exc:
            _mark_invalid(scan, _safe_validation_code(exc))
    return scan


def _scan_template_row(
    *,
    row: dict[str, Any],
    scan: AnnotationScan,
    template_path: Path,
    source_map_path: Path,
    default_split: str,
    limit: int,
) -> None:
    """Scan one parsed annotation template row.

    Args:
        row: Parsed template row.
        scan: Mutable aggregate scan state.
        template_path: Template JSONL path.
        source_map_path: Planned source-map path.
        default_split: Default dataset split.
        limit: Planned promotion limit.

    Raises:
        TemplatePromotionError: If row safety or bbox structure is invalid.
        RetrainingSecurityError: If label snapshot contains unsafe data.
    """
    promoter._reject_unsafe_payload(row, allow_relative_image_paths=True)
    if row.get("schema_version") != promoter.TEMPLATE_ROW_SCHEMA_VERSION:
        _mark_invalid(scan, "unsupported_schema")
        return
    fixture_id = _safe_fixture_id(row)
    if fixture_id in scan.seen_fixture_ids:
        scan.duplicate_fixture_id_count += 1
        raise promoter.TemplatePromotionError("duplicate fixture_id")
    scan.seen_fixture_ids.add(fixture_id)
    if row.get("annotation_task_type") != "supplement_roi_box":
        _mark_invalid(scan, "unsupported_task_type")
        return
    status = row.get("annotation_status")
    status_key = status if isinstance(status, str) and status else "missing"
    scan.status_counts[status_key] += 1
    split = promoter._row_split(row=row, default_split=default_split)
    scan.split_counts[split] += 1
    label_snapshot = promoter._label_snapshot(row)
    boxes = _validated_boxes(label_snapshot)
    if boxes:
        scan.reviewed_box_row_count += 1
    else:
        scan.blank_box_row_count += 1
    if not promoter._row_marked_accepted(row):
        scan.pending_review_row_count += 1
        return
    _scan_accepted_template_row(
        row=row,
        scan=scan,
        template_path=template_path,
        source_map_path=source_map_path,
        label_snapshot=label_snapshot,
        boxes=boxes,
        limit=limit,
    )


def _scan_accepted_template_row(
    *,
    row: dict[str, Any],
    scan: AnnotationScan,
    template_path: Path,
    source_map_path: Path,
    label_snapshot: dict[str, Any],
    boxes: list[dict[str, Any]],
    limit: int,
) -> None:
    """Scan one accepted row for actual promotion readiness.

    Args:
        row: Parsed template row.
        scan: Mutable aggregate scan state.
        template_path: Template JSONL path.
        source_map_path: Planned source-map path.
        label_snapshot: Reviewed label snapshot.
        boxes: Validated section boxes.
        limit: Planned promotion limit.
    """
    if scan.valid_accepted_row_count >= limit:
        scan.limit_reached_count += 1
        return
    if not boxes:
        _mark_unpromotable(scan, "accepted_without_boxes")
        return
    image_path = promoter._resolve_relative_image_path(
        template_path=template_path,
        source_map_path=source_map_path,
        row=row,
    )
    if image_path is None:
        scan.image_missing_or_unresolved_count += 1
        _mark_unpromotable(scan, "image_path_missing_or_unresolved")
        return
    if not promoter._image_hash_matches(row=row, image_path=image_path):
        scan.image_sha256_mismatch_count += 1
        _mark_unpromotable(scan, "image_sha256_mismatch")
        return
    retraining.validate_supplement_section_training_label_snapshot(label_snapshot)
    scan.valid_accepted_row_count += 1


def _safe_fixture_id(row: dict[str, Any]) -> str:
    """Return one safe template fixture id.

    Args:
        row: Template row.

    Returns:
        Safe fixture id.
    """
    fixture_id = row.get("fixture_id")
    if not isinstance(fixture_id, str) or not promoter.SAFE_TOKEN_PATTERN.fullmatch(fixture_id):
        raise promoter.TemplatePromotionError("Template row requires a safe fixture_id.")
    return fixture_id


def _validated_boxes(label_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Return validated section boxes without exposing labels.

    Args:
        label_snapshot: Human annotation label snapshot.

    Returns:
        List of normalized section boxes. Empty means the operator has not drawn
        boxes yet.

    Raises:
        TemplatePromotionError: If boxes are present but invalid.
        RetrainingSecurityError: If unsafe data is embedded in the snapshot.
    """
    retraining.validate_sanitized_label_snapshot(label_snapshot)
    raw_boxes = label_snapshot.get("boxes")
    if raw_boxes in (None, []):
        return []
    boxes = promoter._normalized_section_labels(label_snapshot)
    for box in boxes:
        _validate_positive_box_area(box)
    return boxes


def _validate_positive_box_area(box: dict[str, Any]) -> None:
    """Reject zero-area section boxes before training export.

    Args:
        box: Normalized section box.

    Raises:
        TemplatePromotionError: If width or height is not positive.
    """
    if float(box["width"]) <= 0 or float(box["height"]) <= 0:
        raise promoter.TemplatePromotionError("Reviewed box dimensions must be positive.")


def _mark_invalid(scan: AnnotationScan, reason: str) -> None:
    """Increment invalid counters.

    Args:
        scan: Mutable scan aggregate.
        reason: Safe reason code.
    """
    scan.invalid_row_count += 1
    scan.invalid_reason_counts[reason] += 1


def _mark_unpromotable(scan: AnnotationScan, reason: str) -> None:
    """Increment unpromotable accepted-row counters.

    Args:
        scan: Mutable scan aggregate.
        reason: Safe reason code.
    """
    scan.unpromotable_accepted_row_count += 1
    scan.invalid_reason_counts[reason] += 1


def _safe_validation_code(error: Exception) -> str:
    """Return a bounded non-sensitive validation code.

    Args:
        error: Validation error.

    Returns:
        Safe reason code.
    """
    message = str(error).strip().lower()
    for marker, code in VALIDATION_CODE_MARKERS:
        if marker in message:
            return code
    return "validation_error"


def _next_operator_action(
    *,
    invalid_count: int,
    unpromotable_accepted_count: int,
    blank_box_count: int,
    pending_review_count: int,
    ready_for_requested_promotion: bool,
) -> str:
    """Return the next operator action code.

    Args:
        invalid_count: Invalid row count.
        unpromotable_accepted_count: Accepted rows that promotion would skip.
        blank_box_count: Rows without boxes.
        pending_review_count: Rows not accepted for training.
        ready_for_requested_promotion: Whether the requested promotion mode is ready.

    Returns:
        Stable operator action code.
    """
    if ready_for_requested_promotion:
        return "run_yolo_annotation_template_promotion"
    if invalid_count:
        return "fix_invalid_yolo_annotation_rows"
    if unpromotable_accepted_count:
        return "fix_unpromotable_accepted_yolo_rows"
    if blank_box_count or pending_review_count:
        return "complete_supplement_section_bbox_review"
    return "review_yolo_annotation_preflight"


def _failure_summary(
    *,
    template_path: Path,
    source_map_path: Path,
    output_path: Path,
    require_all_reviewed: bool,
    error: Exception,
) -> dict[str, Any]:
    """Return a redacted CLI failure summary.

    Args:
        template_path: Input template path.
        source_map_path: Planned source-map path.
        output_path: Planned output path.
        require_all_reviewed: Strict review flag.
        error: Raised exception.

    Returns:
        Redacted failure summary.
    """
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "template_name": template_path.name,
        "source_map_name": source_map_path.name,
        "output_name": output_path.name,
        "error_code": _safe_error_code(error),
        "error_message": _safe_error_message(error),
        "require_all_reviewed": require_all_reviewed,
        "ready_for_requested_promotion": False,
        "db_write_performed": False,
        "training_performed": False,
        "export_artifact_written": False,
        "source_map_written": False,
        "source_ref_printed": False,
        "image_path_printed": False,
        "labels_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }
    promoter._reject_unsafe_payload(summary)
    return summary


def _safe_error_code(error: Exception) -> str:
    """Return a public error code.

    Args:
        error: Raised exception.

    Returns:
        Error code.
    """
    if isinstance(error, OSError):
        return "local_file_read_error"
    if isinstance(error, json.JSONDecodeError):
        return "json_decode_error"
    return "validation_error"


def _safe_error_message(error: Exception) -> str:
    """Return a bounded public error message.

    Args:
        error: Raised exception.

    Returns:
        Redacted message.
    """
    if isinstance(error, OSError):
        return "Local file read failed."
    message = str(error).strip()
    if not message:
        return "Validation failed."
    if any(marker in message for marker in promoter.LOCAL_PATH_MARKERS):
        return "Validation failed."
    if "/" in message or "\\" in message:
        return "Validation failed."
    return message[:200]


if __name__ == "__main__":
    main()
