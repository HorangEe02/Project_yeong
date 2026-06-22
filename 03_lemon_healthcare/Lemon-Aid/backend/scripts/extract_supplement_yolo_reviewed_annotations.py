"""Extract reviewed supplement YOLO annotations from a mixed operator queue.

Operator batch reconciliation can produce a queue-level annotation JSONL that
still contains untouched blank bbox stubs for batches that have not been
reviewed. This tool writes a reviewed-only JSONL copy so partial YOLO dataset
previews can run without weakening the strict section dataset training gate.
Blank stubs are counted and ignored; non-blank incomplete or invalid rows fail
closed.

Reviewed-only output must be written next to the original annotation template
so its private relative image fixture references continue to resolve during
template promotion.

The script does not write to the database, does not train a model, and does not
run OCR. CLI output and summaries never emit local absolute paths, source refs,
raw OCR text, provider payloads, labels, or image bytes. The reviewed-only JSONL
keeps private relative fixture refs and reviewed label snapshots because the
downstream template promotion step must still validate image integrity and
materialize YOLO labels.

References:
    https://docs.ultralytics.com/datasets/detect/
    https://docs.ultralytics.com/tasks/detect/
    https://docs.python.org/3/library/argparse.html
    https://docs.python.org/3/library/json.html
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

from scripts import preflight_supplement_yolo_annotation_decisions as preflight  # noqa: E402
from scripts import promote_supplement_yolo_annotation_template as promoter  # noqa: E402

SCHEMA_VERSION = "supplement-yolo-reviewed-annotation-extract-v1"
SOURCE_DOC_URLS = (
    "https://docs.ultralytics.com/datasets/detect/",
    "https://docs.ultralytics.com/tasks/detect/",
)
MAX_SAFE_ERROR_LENGTH = 200


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--source-map",
        type=Path,
        default=None,
        help="Planned source-map path. Defaults to <output>.source-map.json.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output>.summary.json.",
    )
    parser.add_argument(
        "--default-split", choices=sorted(promoter.SUPPORTED_SPLITS), default="train"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write reviewed-only YOLO annotation rows and a redacted summary.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    output_path = args.output.expanduser().resolve()
    source_map_path = (
        args.source_map.expanduser().resolve()
        if args.source_map is not None
        else output_path.with_suffix(output_path.suffix + ".source-map.json")
    )
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )
    try:
        rows, summary = extract_reviewed_yolo_annotations(
            template_path=args.template,
            annotations_path=args.annotations,
            output_path=output_path,
            source_map_path=source_map_path,
            default_split=args.default_split,
        )
        _reject_unsafe_output(rows=rows, summary=summary)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError, promoter.TemplatePromotionError) as exc:
        failure = _failure_summary(
            template_path=args.template,
            annotations_path=args.annotations,
            output_path=output_path,
            error=exc,
        )
        try:
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(
                json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None


def extract_reviewed_yolo_annotations(
    *,
    template_path: Path,
    annotations_path: Path,
    output_path: Path,
    source_map_path: Path,
    default_split: str = "train",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return accepted annotation rows from a mixed YOLO operator queue.

    Args:
        template_path: Original annotation template JSONL with fixture refs.
        annotations_path: Mixed operator annotation JSONL that may include blanks.
        output_path: Reviewed-only JSONL destination.
        source_map_path: Planned source-map path for later template promotion.
        default_split: Split used when rows omit ``split``.

    Returns:
        Reviewed annotation rows and redacted summary.

    Raises:
        ValueError: If non-blank rows are invalid, duplicated, stale, or the
            output path would break relative fixture references.
        TemplatePromotionError: If YOLO row validation fails.
    """
    template_path = template_path.expanduser().resolve()
    annotations_path = annotations_path.expanduser().resolve()
    output_path = output_path.expanduser().resolve()
    source_map_path = source_map_path.expanduser().resolve()
    _validate_output_location(template_path=template_path, output_path=output_path)
    promoter._validate_args(default_split=default_split, limit=promoter.MAX_ROWS)

    template_ids = _template_fixture_ids(template_path)
    seen_fixture_ids: set[str] = set()
    rows: list[dict[str, Any]] = []
    split_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    blank_count = 0
    pending_without_boxes_count = 0
    reviewed_box_unaccepted_count = 0
    unmatched_count = 0

    for row in promoter._read_jsonl(annotations_path):
        promoter._reject_unsafe_payload(row, allow_relative_image_paths=True)
        fixture_id = _fixture_id(row)
        if fixture_id in seen_fixture_ids:
            raise ValueError("Duplicate supplement YOLO annotation fixture_id.")
        seen_fixture_ids.add(fixture_id)
        if fixture_id not in template_ids:
            unmatched_count += 1
            raise ValueError("YOLO annotation fixture_id is not in the source template.")
        if row.get("schema_version") != promoter.TEMPLATE_ROW_SCHEMA_VERSION:
            raise ValueError("YOLO annotation row uses an unsupported schema.")
        if row.get("annotation_task_type") != "supplement_roi_box":
            raise ValueError("YOLO annotation row uses an unsupported task type.")

        status = row.get("annotation_status")
        status_counts[status if isinstance(status, str) and status else "missing"] += 1
        split_counts[promoter._row_split(row=row, default_split=default_split)] += 1
        label_snapshot = promoter._label_snapshot(row)
        boxes = preflight._validated_boxes(label_snapshot)
        if not promoter._row_marked_accepted(row):
            if boxes:
                reviewed_box_unaccepted_count += 1
                raise ValueError("YOLO annotation row has boxes but is not accepted for training.")
            blank_count += 1
            pending_without_boxes_count += 1
            continue

        _validate_accepted_row(
            row=row,
            template_path=template_path,
            source_map_path=source_map_path,
            label_snapshot=label_snapshot,
            boxes=boxes,
        )
        rows.append(dict(row))

    missing_annotation_count = len(template_ids - seen_fixture_ids)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "template_name": template_path.name,
        "template_hash": promoter._sha256_file(template_path),
        "annotations_name": annotations_path.name,
        "annotations_hash": promoter._sha256_file(annotations_path),
        "output_name": output_path.name,
        "source_map_name": source_map_path.name,
        "template_row_count": len(template_ids),
        "input_annotation_row_count": len(seen_fixture_ids),
        "reviewed_annotation_count": len(rows),
        "blank_annotation_ignored_count": blank_count,
        "pending_without_boxes_ignored_count": pending_without_boxes_count,
        "reviewed_box_unaccepted_count": reviewed_box_unaccepted_count,
        "missing_annotation_count": missing_annotation_count,
        "unmatched_annotation_count": unmatched_count,
        "split_counts": dict(sorted(split_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "ready_for_partial_promotion": bool(rows) and unmatched_count == 0,
        "ready_for_strict_promotion": (
            bool(rows)
            and blank_count == 0
            and missing_annotation_count == 0
            and len(rows) == len(template_ids)
        ),
        "output_rows_written": len(rows),
        "db_write_performed": False,
        "training_performed": False,
        "training_execution_performed_by_script": False,
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
    _reject_unsafe_output(rows=rows, summary=summary)
    return rows, summary


def _template_fixture_ids(template_path: Path) -> set[str]:
    """Return source template fixture ids.

    Args:
        template_path: Original template JSONL path.

    Returns:
        Fixture id set.
    """
    fixture_ids: set[str] = set()
    for row in promoter._read_jsonl(template_path):
        promoter._reject_unsafe_payload(row, allow_relative_image_paths=True)
        if row.get("schema_version") != promoter.TEMPLATE_ROW_SCHEMA_VERSION:
            raise ValueError("Source YOLO template row uses an unsupported schema.")
        fixture_id = _fixture_id(row)
        if fixture_id in fixture_ids:
            raise ValueError("Duplicate source YOLO template fixture_id.")
        fixture_ids.add(fixture_id)
    return fixture_ids


def _validate_output_location(*, template_path: Path, output_path: Path) -> None:
    """Validate output stays next to the original template.

    Args:
        template_path: Original template path.
        output_path: Reviewed-only output path.

    Raises:
        ValueError: If relative fixture refs would stop resolving.
    """
    if output_path.parent.resolve() != template_path.parent.resolve():
        raise ValueError("Reviewed-only YOLO annotation output must stay beside the template.")


def _validate_accepted_row(
    *,
    row: dict[str, Any],
    template_path: Path,
    source_map_path: Path,
    label_snapshot: dict[str, Any],
    boxes: list[dict[str, Any]],
) -> None:
    """Validate one accepted row can later be promoted.

    Args:
        row: Annotation row.
        template_path: Original template path.
        source_map_path: Planned source-map path.
        label_snapshot: Reviewed label snapshot.
        boxes: Validated boxes.

    Raises:
        TemplatePromotionError: If image or label validation fails.
        RetrainingSecurityError: If label snapshot contains unsafe data.
    """
    if not boxes:
        raise promoter.TemplatePromotionError("Accepted YOLO annotation row requires boxes.")
    image_path = promoter._resolve_relative_image_path(
        template_path=template_path,
        source_map_path=source_map_path,
        row=row,
    )
    if image_path is None:
        raise promoter.TemplatePromotionError("YOLO annotation image fixture is missing.")
    if not promoter._image_hash_matches(row=row, image_path=image_path):
        raise promoter.TemplatePromotionError("YOLO annotation image hash does not match.")
    retraining.validate_supplement_section_training_label_snapshot(label_snapshot)


def _fixture_id(row: dict[str, Any]) -> str:
    """Return a safe fixture id.

    Args:
        row: Annotation row.

    Returns:
        Safe fixture id.
    """
    fixture_id = row.get("fixture_id")
    if not isinstance(fixture_id, str) or not promoter.SAFE_TOKEN_PATTERN.fullmatch(fixture_id):
        raise ValueError("YOLO annotation row requires a safe fixture_id.")
    return fixture_id


def _reject_unsafe_output(*, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    """Reject unsafe row and summary payloads except explicit doc citations.

    Args:
        rows: Reviewed annotation rows.
        summary: Redacted summary payload.
    """
    checked_summary = {key: value for key, value in summary.items() if key != "source_doc_urls"}
    promoter._reject_unsafe_payload({"rows": rows}, allow_relative_image_paths=True)
    promoter._reject_unsafe_payload({"summary": checked_summary})


def _failure_summary(
    *,
    template_path: Path,
    annotations_path: Path,
    output_path: Path,
    error: Exception,
) -> dict[str, Any]:
    """Return a redacted CLI failure summary.

    Args:
        template_path: Source template path.
        annotations_path: Mixed annotation path.
        output_path: Planned output path.
        error: Raised exception.

    Returns:
        Redacted failure summary.
    """
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "template_name": template_path.name,
        "annotations_name": annotations_path.name,
        "output_name": output_path.name,
        "error_code": _safe_error_code(error),
        "error_message": _safe_error_message(error),
        "reviewed_annotation_count": 0,
        "output_rows_written": 0,
        "db_write_performed": False,
        "training_performed": False,
        "training_execution_performed_by_script": False,
        "source_image_read_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
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
    return message[:MAX_SAFE_ERROR_LENGTH]


if __name__ == "__main__":
    main()
