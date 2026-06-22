"""Promote reviewed supplement YOLO annotation templates to export artifacts.

This operator-only bridge consumes rows produced by
``export_supplement_yolo_annotation_template.py`` after a human reviewer has
filled section boxes and approved them for training. It writes two local
artifacts:

* ``supplement-section-yolo-detect-export-v1`` for YOLO materialization
* an operator-private source map that resolves template source refs to hashed
  fixture images

The script does not write to the database, does not train a model, and never
prints source refs, image paths, raw OCR text, provider payloads, or labels in
the CLI summary.

References:
    https://docs.ultralytics.com/datasets/detect/
    https://docs.ultralytics.com/tasks/detect/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.learning.retraining import (  # noqa: E402
    SUPPLEMENT_SECTION_CLASS_NAMES,
    SUPPLEMENT_SECTION_YOLO_EXPORT_SCHEMA_VERSION,
    RetrainingSecurityError,
    validate_supplement_section_training_label_snapshot,
)
from src.learning.supplement_section_labels import SNAPSHOT_SCHEMA_VERSION  # noqa: E402
from src.vision.taxonomy import normalize_vision_label  # noqa: E402

SUMMARY_SCHEMA_VERSION = "supplement-yolo-template-promotion-summary-v1"
SOURCE_MAP_SCHEMA_VERSION = "supplement-yolo-template-source-map-v1"
TEMPLATE_ROW_SCHEMA_VERSION = "supplement-yolo-annotation-template-row-v1"
DEFAULT_MAX_ROWS = 500
MAX_ROWS = 5000
SUPPORTED_SPLITS = frozenset({"train", "val", "test"})
ACCEPTED_STATUSES = frozenset(
    {
        "accepted",
        "accepted_for_training",
        "human_reviewed",
        "reviewed_source_image_boxes",
    }
)
SAFE_TOKEN_PATTERN = re.compile(r"^[0-9A-Za-z가-힣_.:-]{1,200}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
RAW_FORBIDDEN_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "credential",
        "credentials",
        "diagnosis",
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
        "raw_model_response",
        "raw_ocr_text",
        "raw_payload",
        "raw_provider_payload",
        "request_headers",
        "secret",
        "service_key",
        "signed_url",
        "url",
    }
)
LOCAL_PATH_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    "file://",
    "\\Users\\",
    "\\Volumes\\",
)
SOURCE_DOC_URLS = (
    "https://docs.ultralytics.com/datasets/detect/",
    "https://docs.ultralytics.com/tasks/detect/",
)


class TemplatePromotionError(ValueError):
    """Raised when reviewed annotation templates cannot be promoted safely."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--source-map",
        type=Path,
        default=None,
        help="Defaults to <output>.source-map.json.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Defaults to <output>.summary.json.",
    )
    parser.add_argument("--default-split", choices=sorted(SUPPORTED_SPLITS), default="train")
    parser.add_argument("--limit", type=int, default=DEFAULT_MAX_ROWS)
    parser.add_argument("--source-run-id", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Run the template promotion CLI.

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
        export, source_map, summary = promote_reviewed_templates(
            template_path=args.template,
            source_map_path=source_map_path,
            default_split=args.default_split,
            limit=args.limit,
            source_run_id=args.source_run_id,
        )
        _reject_unsafe_payload(export, allow_private_source_refs=True)
        _reject_unsafe_payload(source_map, allow_relative_image_paths=True)
        _write_json(output_path, export)
        _write_json(source_map_path, source_map)
        _write_json(summary_path, summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, TemplatePromotionError, RetrainingSecurityError, json.JSONDecodeError) as exc:
        failure = _failure_summary(
            template_path=args.template,
            output_path=output_path,
            error=exc,
        )
        with suppress(OSError):
            _write_json(summary_path, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None


def promote_reviewed_templates(
    *,
    template_path: Path,
    source_map_path: Path,
    default_split: str = "train",
    limit: int = DEFAULT_MAX_ROWS,
    source_run_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Promote reviewed template rows into YOLO export/source-map artifacts.

    Args:
        template_path: Human-reviewed annotation template JSONL.
        output_path: Destination export artifact path.
        source_map_path: Destination private source map path.
        default_split: Split used when a row has no explicit split.
        limit: Maximum accepted rows to promote.
        source_run_id: Optional operator run id.

    Returns:
        Export artifact, source map, and redacted summary.

    Raises:
        TemplatePromotionError: If inputs are malformed or unsafe.
        RetrainingSecurityError: If label snapshots contain unsafe data.
    """
    _validate_args(default_split=default_split, limit=limit)
    rows = _read_jsonl(template_path)
    export_items: list[dict[str, Any]] = []
    source_rows: list[dict[str, str]] = []
    skip_reasons: Counter[str] = Counter()
    split_counts = {"train": 0, "val": 0, "test": 0, "holdout": 0}
    seen_source_refs: set[str] = set()

    for row in rows:
        if len(export_items) >= limit:
            skip_reasons["limit_reached"] += 1
            continue
        _reject_unsafe_payload(row, allow_relative_image_paths=True)
        if row.get("schema_version") != TEMPLATE_ROW_SCHEMA_VERSION:
            skip_reasons["unsupported_template_schema"] += 1
            continue
        if not _row_marked_accepted(row):
            skip_reasons["not_accepted_for_training"] += 1
            continue
        image_path = _resolve_relative_image_path(
            template_path=template_path,
            source_map_path=source_map_path,
            row=row,
        )
        if image_path is None:
            skip_reasons["image_path_missing_or_unresolved"] += 1
            continue
        if not _image_hash_matches(row=row, image_path=image_path):
            skip_reasons["image_sha256_mismatch"] += 1
            continue
        label_snapshot = _label_snapshot(row)
        validate_supplement_section_training_label_snapshot(label_snapshot)
        labels = _normalized_section_labels(label_snapshot)
        source_ref = _template_source_ref(row)
        if source_ref in seen_source_refs:
            skip_reasons["duplicate_source_ref"] += 1
            continue
        seen_source_refs.add(source_ref)
        split = _row_split(row=row, default_split=default_split)
        split_counts[split] += 1
        export_items.append({"source_ref": source_ref, "split": split, "labels": labels})
        source_rows.append(
            {
                "source_ref": source_ref,
                "image_path": _relative_path_for_source_map(
                    image_path=image_path,
                    source_map_path=source_map_path,
                ),
            }
        )

    export = {
        "schema_version": SUPPLEMENT_SECTION_YOLO_EXPORT_SCHEMA_VERSION,
        "class_names": list(SUPPLEMENT_SECTION_CLASS_NAMES),
        "item_count": len(export_items),
        "split_counts": split_counts,
        "items": export_items,
    }
    source_map = {
        "schema_version": SOURCE_MAP_SCHEMA_VERSION,
        "source_run_id": source_run_id,
        "source": "reviewed_supplement_yolo_annotation_template",
        "sources": source_rows,
    }
    summary = _summary(
        template_path=template_path,
        source_run_id=source_run_id,
        row_count=len(rows),
        export_items=export_items,
        split_counts=split_counts,
        skip_reasons=skip_reasons,
        limit=limit,
    )
    _reject_unsafe_payload(summary)
    return export, source_map, summary


def _validate_args(*, default_split: str, limit: int) -> None:
    """Validate promotion arguments.

    Args:
        default_split: Default split.
        limit: Promotion limit.

    Raises:
        TemplatePromotionError: If values are invalid.
    """
    if default_split not in SUPPORTED_SPLITS:
        raise TemplatePromotionError("Default split must be train, val, or test.")
    if limit < 1 or limit > MAX_ROWS:
        raise TemplatePromotionError("Promotion limit must be between 1 and 5000.")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL rows from disk.

    Args:
        path: JSONL file path.

    Returns:
        List of object rows.

    Raises:
        TemplatePromotionError: If the file is missing or a row is malformed.
    """
    if not path.is_file():
        raise TemplatePromotionError("Template JSONL file does not exist.")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise TemplatePromotionError(f"Template row {line_number} must be an object.")
        rows.append(value)
    return rows


def _row_marked_accepted(row: dict[str, Any]) -> bool:
    """Return whether a row is explicitly approved for training.

    Args:
        row: Template row.

    Returns:
        True when status and label snapshot flags both indicate human approval.
    """
    status = row.get("annotation_status")
    if status not in ACCEPTED_STATUSES:
        return False
    label_snapshot = row.get("label_snapshot")
    return (
        isinstance(label_snapshot, dict)
        and label_snapshot.get("training_export_allowed") is True
        and label_snapshot.get("human_review_required") is False
    )


def _resolve_relative_image_path(
    *,
    template_path: Path,
    source_map_path: Path,
    row: dict[str, Any],
) -> Path | None:
    """Resolve one row's relative fixture image path.

    Args:
        template_path: Input template path.
        source_map_path: Output source-map path.
        row: Template row.

    Returns:
        Resolved image path, or None if missing/unusable.

    Raises:
        TemplatePromotionError: If a row contains an absolute or path-traversal image path.
    """
    raw_image_path = row.get("image_path")
    if not isinstance(raw_image_path, str) or not raw_image_path.strip():
        return None
    if raw_image_path.startswith("/") or "://" in raw_image_path or ".." in raw_image_path:
        raise TemplatePromotionError("Template image_path must be a safe relative fixture path.")
    if any(marker in raw_image_path for marker in LOCAL_PATH_MARKERS):
        raise TemplatePromotionError("Template image_path must not contain a local path literal.")
    resolved = (template_path.expanduser().resolve().parent / raw_image_path).resolve()
    try:
        resolved.relative_to(source_map_path.expanduser().resolve().parent)
    except ValueError as exc:
        raise TemplatePromotionError(
            "Template image fixture must be under the source-map output directory."
        ) from exc
    if not resolved.is_file():
        return None
    return resolved


def _image_hash_matches(*, row: dict[str, Any], image_path: Path) -> bool:
    """Return whether the fixture image matches the row image digest.

    Args:
        row: Template row.
        image_path: Resolved fixture image.

    Returns:
        True when the fixture bytes match ``image_sha256``.
    """
    expected = row.get("image_sha256")
    if not isinstance(expected, str) or not SHA256_PATTERN.fullmatch(expected):
        return False
    return _sha256_file(image_path) == expected


def _label_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    """Return a reviewed label snapshot.

    Args:
        row: Template row.

    Returns:
        Label snapshot.

    Raises:
        TemplatePromotionError: If the snapshot is missing.
    """
    value = row.get("label_snapshot")
    if not isinstance(value, dict):
        raise TemplatePromotionError("Template row requires label_snapshot.")
    schema = value.get("schema_version")
    if schema is not None and schema != SNAPSHOT_SCHEMA_VERSION:
        raise TemplatePromotionError("Unsupported supplement section label snapshot schema.")
    return value


def _normalized_section_labels(label_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize reviewed boxes into YOLO class rows.

    Args:
        label_snapshot: Human-reviewed label snapshot.

    Returns:
        Supplement section labels with class ids.
    """
    raw_boxes = label_snapshot.get("boxes")
    if not isinstance(raw_boxes, list) or not raw_boxes:
        raise TemplatePromotionError("Reviewed label snapshot requires boxes.")
    labels: list[dict[str, Any]] = []
    for raw_box in raw_boxes:
        if not isinstance(raw_box, dict):
            raise TemplatePromotionError("Reviewed boxes must be objects.")
        label = _canonical_section_label(raw_box)
        labels.append(
            {
                "class_id": SUPPLEMENT_SECTION_CLASS_NAMES.index(label),
                "label": label,
                "x_center": _coordinate(raw_box, "x_center"),
                "y_center": _coordinate(raw_box, "y_center"),
                "width": _coordinate(raw_box, "width"),
                "height": _coordinate(raw_box, "height"),
            }
        )
    return labels


def _canonical_section_label(raw_box: dict[str, Any]) -> str:
    """Return the canonical supplement section label for one reviewed box.

    Args:
        raw_box: Reviewed box.

    Returns:
        Canonical section class name.
    """
    raw_label = raw_box.get("label") or raw_box.get("class_name") or raw_box.get("section_type")
    if not isinstance(raw_label, str) or not raw_label.strip():
        raise TemplatePromotionError("Reviewed boxes require a section label.")
    label = normalize_vision_label(raw_label)
    if label not in SUPPLEMENT_SECTION_CLASS_NAMES:
        raise TemplatePromotionError("Reviewed box section label is not allowed.")
    return label


def _coordinate(raw_box: dict[str, Any], key: str) -> float:
    """Return one normalized coordinate from a reviewed box.

    Args:
        raw_box: Reviewed box.
        key: Coordinate key.

    Returns:
        Coordinate as a finite float in [0, 1].
    """
    value = raw_box.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TemplatePromotionError("Reviewed box coordinates must be numbers.")
    coordinate = float(value)
    if not math.isfinite(coordinate) or not 0 <= coordinate <= 1:
        raise TemplatePromotionError("Reviewed box coordinates must be normalized.")
    return coordinate


def _template_source_ref(row: dict[str, Any]) -> str:
    """Return an opaque template source ref for one reviewed row.

    Args:
        row: Template row.

    Returns:
        Private source ref.
    """
    fixture_id = row.get("fixture_id")
    if not isinstance(fixture_id, str) or not SAFE_TOKEN_PATTERN.fullmatch(fixture_id):
        raise TemplatePromotionError("Template row requires a safe fixture_id.")
    return f"template:{fixture_id}"


def _row_split(*, row: dict[str, Any], default_split: str) -> str:
    """Return the dataset split for one row.

    Args:
        row: Template row.
        default_split: Fallback split.

    Returns:
        Split name.
    """
    value = row.get("split", default_split)
    if value not in SUPPORTED_SPLITS:
        raise TemplatePromotionError("Template row split must be train, val, or test.")
    return str(value)


def _relative_path_for_source_map(*, image_path: Path, source_map_path: Path) -> str:
    """Return an image path relative to the source-map file directory.

    Args:
        image_path: Resolved image path.
        source_map_path: Source map path.

    Returns:
        Safe relative path string.
    """
    relative = image_path.relative_to(source_map_path.expanduser().resolve().parent).as_posix()
    if relative.startswith("/") or ".." in relative:
        raise TemplatePromotionError("Source-map image path must stay inside output directory.")
    return relative


def _summary(
    *,
    template_path: Path,
    source_run_id: str | None,
    row_count: int,
    export_items: list[dict[str, Any]],
    split_counts: dict[str, int],
    skip_reasons: Counter[str],
    limit: int,
) -> dict[str, Any]:
    """Return a redacted promotion summary.

    Args:
        template_path: Input template path.
        source_run_id: Optional operator run id.
        row_count: Input row count.
        export_items: Promoted export items.
        split_counts: Counts by split.
        skip_reasons: Skipped-row counts.
        limit: Promotion limit.

    Returns:
        Safe aggregate summary.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "source_run_id": source_run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "template_name": template_path.name,
        "template_row_count": row_count,
        "promoted_item_count": len(export_items),
        "limit": limit,
        "split_counts": split_counts,
        "skip_reason_counts": dict(sorted(skip_reasons.items())),
        "db_write_performed": False,
        "training_performed": False,
        "source_map_written": True,
        "export_artifact_written": True,
        "source_ref_printed": False,
        "image_path_printed": False,
        "labels_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


def _failure_summary(
    *, template_path: Path, output_path: Path, error: BaseException
) -> dict[str, Any]:
    """Return a safe failure summary.

    Args:
        template_path: Input path.
        output_path: Output path.
        error: Raised exception.

    Returns:
        Redacted failure summary.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "failed",
        "error_type": error.__class__.__name__,
        "template_path_hash": _sha256_text(str(template_path.expanduser())),
        "output_path_hash": _sha256_text(str(output_path.expanduser())),
        "db_write_performed": False,
        "training_performed": False,
        "source_ref_printed": False,
        "image_path_printed": False,
        "labels_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


def _reject_unsafe_payload(
    value: Any,
    *,
    allow_private_source_refs: bool = False,
    allow_relative_image_paths: bool = False,
) -> None:
    """Reject raw text, provider payloads, paths, URLs, or secrets.

    Args:
        value: JSON-like value.
        allow_private_source_refs: Whether ``source_ref`` private tokens are allowed.
        allow_relative_image_paths: Whether relative ``image_path`` values are allowed.

    Raises:
        TemplatePromotionError: If unsafe content is found.
    """
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in RAW_FORBIDDEN_KEYS:
                raise TemplatePromotionError(f"Unsafe key in template promotion payload: {key}")
            if key == "source_ref" and allow_private_source_refs:
                _validate_private_token(nested, field_name=key)
                continue
            if key == "image_path" and allow_relative_image_paths:
                _validate_relative_path_value(nested)
                continue
            if key == "source_doc_urls":
                _validate_source_doc_urls(nested)
                continue
            _reject_unsafe_payload(
                nested,
                allow_private_source_refs=allow_private_source_refs,
                allow_relative_image_paths=allow_relative_image_paths,
            )
    elif isinstance(value, list):
        for nested in value:
            _reject_unsafe_payload(
                nested,
                allow_private_source_refs=allow_private_source_refs,
                allow_relative_image_paths=allow_relative_image_paths,
            )
    elif isinstance(value, str):
        if "://" in value or value.startswith("/"):
            raise TemplatePromotionError("Template promotion payload contains a path or URL.")
        if any(marker in value for marker in LOCAL_PATH_MARKERS):
            raise TemplatePromotionError(
                "Template promotion payload contains a local path literal."
            )


def _validate_private_token(value: object, *, field_name: str) -> None:
    """Validate a private source token.

    Args:
        value: Candidate token.
        field_name: Field name for errors.
    """
    if not isinstance(value, str) or not SAFE_TOKEN_PATTERN.fullmatch(value):
        raise TemplatePromotionError(f"{field_name} must be an opaque private token.")
    if "://" in value or value.startswith("/") or ".." in value:
        raise TemplatePromotionError(f"{field_name} must not be a path or URL.")


def _validate_relative_path_value(value: object) -> None:
    """Validate a relative fixture path string.

    Args:
        value: Candidate relative path.
    """
    if not isinstance(value, str) or not value.strip():
        raise TemplatePromotionError("image_path must be a relative fixture path.")
    if value.startswith("/") or "://" in value or ".." in value:
        raise TemplatePromotionError("image_path must not be absolute or path-traversing.")
    if any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise TemplatePromotionError("image_path must not contain a local path literal.")


def _validate_source_doc_urls(value: object) -> None:
    """Validate official documentation URLs carried in summaries.

    Args:
        value: Candidate documentation URL list.
    """
    if not isinstance(value, list):
        raise TemplatePromotionError("source_doc_urls must be a list.")
    if list(value) != list(SOURCE_DOC_URLS):
        raise TemplatePromotionError("source_doc_urls must match the official reference allowlist.")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write one JSON object.

    Args:
        path: Output path.
        payload: JSON object.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _sha256_file(path: Path) -> str:
    """Return a SHA-256 digest for a local file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    """Return a SHA-256 digest for text."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
