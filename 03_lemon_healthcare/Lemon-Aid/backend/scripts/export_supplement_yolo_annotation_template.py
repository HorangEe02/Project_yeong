"""Export local supplement detail-page YOLO annotation templates.

This operator tool converts sanitized ``detail-yolo`` candidate rows into a
human-review JSONL template. It may optionally copy PII-cleared detail-page
images into a private hashed fixture directory so reviewers can draw bbox labels
without exposing the original ``crawling-image`` path or product-folder literal.

The script never writes to the database, never creates final YOLO labels, and
never emits raw OCR text, provider payloads, image bytes, local absolute paths,
or product directory literals.

References:
    https://docs.ultralytics.com/datasets/detect/
    https://docs.ultralytics.com/tasks/detect/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
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

from src.learning.retraining import SUPPLEMENT_SECTION_CLASS_NAMES  # noqa: E402
from src.learning.supplement_section_labels import SNAPSHOT_SCHEMA_VERSION  # noqa: E402

from scripts import audit_supplement_crawling_image_taxonomy as audit  # noqa: E402

SUMMARY_SCHEMA_VERSION = "supplement-yolo-annotation-template-summary-v1"
ROW_SCHEMA_VERSION = "supplement-yolo-annotation-template-row-v1"
CANDIDATE_SCHEMA_VERSION = "supplement-detail-page-yolo-annotation-candidate-v1"
DEFAULT_MAX_ROWS = 500
MAX_ROWS = 5000
MAX_REVIEW_NOTE_LENGTH = 240
SAFE_TOKEN_PATTERN = re.compile(r"^[0-9A-Za-z가-힣_.:-]{1,200}$")
SAFE_MIME_TYPE_PATTERN = re.compile(r"^[a-z0-9.+-]+/[a-z0-9.+-]+$", re.IGNORECASE)
RAW_FORBIDDEN_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "image_bytes",
        "local_path",
        "ocr_text",
        "provider_payload",
        "raw_image",
        "raw_model_response",
        "raw_ocr_text",
        "raw_provider_payload",
        "request_headers",
        "service_key",
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output>.summary.json.",
    )
    parser.add_argument("--source-run-id", default=None)
    parser.add_argument("--limit", type=int, default=DEFAULT_MAX_ROWS)
    parser.add_argument(
        "--source-root",
        type=Path,
        default=None,
        help="Optional crawling-image root used only to materialize private fixtures.",
    )
    parser.add_argument(
        "--materialized-image-dir",
        type=Path,
        default=None,
        help="Optional private directory where source images are copied with hashed names.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write annotation template rows and a redacted summary.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    output_path = args.output.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )
    try:
        rows, summary = export_yolo_annotation_template(
            candidate_manifest=args.candidate_manifest,
            output_path=output_path,
            source_run_id=args.source_run_id,
            limit=args.limit,
            source_root=args.source_root,
            materialized_image_dir=args.materialized_image_dir,
        )
        _reject_unsafe_payload({"rows": rows, "summary": summary})
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
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure = _failure_summary(
            candidate_manifest=args.candidate_manifest,
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


def export_yolo_annotation_template(
    *,
    candidate_manifest: Path,
    output_path: Path | None = None,
    source_run_id: str | None = None,
    limit: int = DEFAULT_MAX_ROWS,
    source_root: Path | None = None,
    materialized_image_dir: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build review templates from sanitized YOLO candidate rows.

    Args:
        candidate_manifest: Detail-page YOLO candidate JSONL.
        output_path: Optional output path used to compute relative fixture image paths.
        source_run_id: Optional operator run id.
        limit: Maximum rows to export.
        source_root: Optional crawling-image root for image materialization.
        materialized_image_dir: Optional private image fixture directory.

    Returns:
        Template rows and a redacted summary.

    Raises:
        ValueError: If inputs are malformed, unsafe, or exceed limits.
    """
    _validate_limit(limit)
    candidates = _read_jsonl(candidate_manifest)
    source_paths = _source_paths_by_image_ref_hash(source_root) if materialized_image_dir else {}
    rows: list[dict[str, Any]] = []
    skip_reasons: Counter[str] = Counter()

    for candidate in candidates:
        if len(rows) >= limit:
            skip_reasons["limit_reached"] += 1
            continue
        _reject_unsafe_payload(candidate)
        if not _candidate_is_annotation_ready(candidate):
            skip_reasons["candidate_not_annotation_ready"] += 1
            continue
        image_path = None
        if materialized_image_dir is not None:
            image_path = _materialize_image_fixture(
                candidate=candidate,
                source_paths=source_paths,
                materialized_image_dir=materialized_image_dir,
                output_path=output_path,
            )
            if image_path is None:
                skip_reasons["source_image_not_found_for_materialization"] += 1
                continue
        rows.append(
            _template_row(
                candidate=candidate,
                source_run_id=source_run_id,
                image_path=image_path,
            )
        )

    summary = _summary(
        candidate_manifest=candidate_manifest,
        source_run_id=source_run_id,
        candidate_count=len(candidates),
        rows=rows,
        skip_reasons=skip_reasons,
        limit=limit,
        image_materialization_requested=materialized_image_dir is not None,
    )
    _reject_unsafe_payload({"rows": rows, "summary": summary})
    return rows, summary


def _template_row(
    *,
    candidate: dict[str, Any],
    source_run_id: str | None,
    image_path: str | None,
) -> dict[str, Any]:
    """Return one annotation template row.

    Args:
        candidate: Sanitized detail-page candidate row.
        source_run_id: Optional operator run id.
        image_path: Optional relative hashed fixture image path.

    Returns:
        JSON-safe template row for human bbox annotation.
    """
    row = {
        "schema_version": ROW_SCHEMA_VERSION,
        "source_run_id": source_run_id,
        "fixture_id": _safe_required_token(candidate.get("fixture_id"), field_name="fixture_id"),
        "source_ref": _safe_required_token(candidate.get("source_ref"), field_name="source_ref"),
        "image_ref_hash": _safe_sha256(
            candidate.get("image_ref_hash"), field_name="image_ref_hash"
        ),
        "image_sha256": _safe_sha256(candidate.get("image_sha256"), field_name="image_sha256"),
        "image_mime_type": _safe_mime_type(
            candidate.get("image_mime_type"),
            field_name="image_mime_type",
        ),
        "category_key": _safe_required_token(
            candidate.get("category_key"), field_name="category_key"
        ),
        "source_kind": "detail_page",
        "annotation_task_type": "supplement_roi_box",
        "annotation_status": "pending_human_bbox_review",
        "coordinate_space": "source_image",
        "allowed_labels": list(SUPPLEMENT_SECTION_CLASS_NAMES),
        "label_snapshot": {
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "candidate_source": "human_annotation_template",
            "coordinate_space": "source_image",
            "human_review_required": True,
            "text_stored": False,
            "training_export_allowed": False,
            "boxes": [],
        },
        "review_checklist": [
            "bbox는 원본 이미지 기준 normalized xywh로 작성",
            "라벨은 allowed_labels 중 하나만 사용",
            "텍스트 원문, OCR 결과, 로컬 경로는 label_snapshot에 기록 금지",
            "훈련 사용 전 training_export_allowed=true와 human_review_required=false로 검수",
        ],
        "review_notes_code": "pending_section_bbox_human_annotation",
        "image_materialization_required": image_path is None,
        "image_materialization_policy": (
            "private_hashed_fixture_copy_materialized"
            if image_path is not None
            else "private_operator_source_required"
        ),
        "db_write_performed": False,
        "training_export_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }
    if image_path is not None:
        row["image_path"] = image_path
    _reject_unsafe_payload(row)
    return row


def _candidate_is_annotation_ready(candidate: dict[str, Any]) -> bool:
    """Return whether a candidate can become a human annotation template.

    Args:
        candidate: Candidate row.

    Returns:
        True when the row is a local-only detail-page YOLO candidate.
    """
    return (
        candidate.get("schema_version") == CANDIDATE_SCHEMA_VERSION
        and candidate.get("candidate_purpose") == "supplement_section_bbox_annotation"
        and candidate.get("source_kind") == "detail_page"
        and candidate.get("annotation_task_type") == "supplement_roi_box"
        and candidate.get("contains_personal_data") is False
        and candidate.get("local_processing_allowed") is True
        and candidate.get("custom_section_model_required") is True
        and candidate.get("coco_pretrained_allowed_for_final_labels") is False
    )


def _summary(
    *,
    candidate_manifest: Path,
    source_run_id: str | None,
    candidate_count: int,
    rows: list[dict[str, Any]],
    skip_reasons: Counter[str],
    limit: int,
    image_materialization_requested: bool,
) -> dict[str, Any]:
    """Return an aggregate redacted summary.

    Args:
        candidate_manifest: Input manifest path.
        source_run_id: Optional operator run id.
        candidate_count: Number of input candidates.
        rows: Exported template rows.
        skip_reasons: Counts by skip reason.
        limit: Requested export limit.
        image_materialization_requested: Whether fixture copies were requested.

    Returns:
        JSON-safe summary.
    """
    category_counts = Counter(str(row["category_key"]) for row in rows)
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "source_run_id": source_run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "candidate_manifest_name": candidate_manifest.name,
        "candidate_count": candidate_count,
        "template_row_count": len(rows),
        "limit": limit,
        "category_counts": dict(sorted(category_counts.items())),
        "skip_reason_counts": dict(sorted(skip_reasons.items())),
        "image_materialization_requested": image_materialization_requested,
        "image_materialized_count": sum(1 for row in rows if "image_path" in row),
        "required_human_review_count": sum(
            1 for row in rows if row["annotation_status"].startswith("pending_")
        ),
        "db_write_performed": False,
        "training_export_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


def _materialize_image_fixture(
    *,
    candidate: dict[str, Any],
    source_paths: dict[str, Path],
    materialized_image_dir: Path,
    output_path: Path | None,
) -> str | None:
    """Copy one source image into a private hashed fixture directory.

    Args:
        candidate: Template source candidate.
        source_paths: Map from image-ref hash to local source image path.
        materialized_image_dir: Destination image directory.
        output_path: Template output path used for relative references.

    Returns:
        Relative image path, or None when source resolution fails.
    """
    image_ref_hash = _safe_sha256(candidate.get("image_ref_hash"), field_name="image_ref_hash")
    source_image = source_paths.get(image_ref_hash)
    if source_image is None or not source_image.is_file():
        return None
    expected_sha256 = _safe_sha256(candidate.get("image_sha256"), field_name="image_sha256")
    if _sha256_file(source_image) != expected_sha256:
        return None
    fixture_id = _safe_required_token(candidate.get("fixture_id"), field_name="fixture_id")
    suffix = source_image.suffix.lower()
    destination = materialized_image_dir.expanduser().resolve() / f"{fixture_id}{suffix}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_image, destination)
    if output_path is not None:
        relative = destination.relative_to(output_path.expanduser().resolve().parent)
        return relative.as_posix()
    return destination.name


def _source_paths_by_image_ref_hash(source_root: Path | None) -> dict[str, Path]:
    """Build an image-ref hash map from the private source tree.

    Args:
        source_root: Optional crawling-image source root.

    Returns:
        Mapping from sanitized image-ref hash to local image path.

    Raises:
        ValueError: If source_root is required but missing.
    """
    if source_root is None:
        raise ValueError("source_root is required when materializing annotation images.")
    resolved_root = source_root.expanduser().resolve()
    if not resolved_root.is_dir():
        raise ValueError("source_root is not a directory.")
    source_paths: dict[str, Path] = {}
    for image_path in sorted(resolved_root.rglob("*")):
        if not image_path.is_file() or not audit._is_image_file(image_path):
            continue
        relative_ref = image_path.relative_to(resolved_root).as_posix()
        source_paths[audit._sha256_text(relative_ref)] = image_path
    return source_paths


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL object rows from disk.

    Args:
        path: JSONL file path.

    Returns:
        Parsed row objects.

    Raises:
        ValueError: If rows are malformed.
    """
    if not path.is_file():
        raise ValueError("candidate manifest file does not exist.")
    rows: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        row = json.loads(raw_line)
        if not isinstance(row, dict):
            raise ValueError(f"Line {line_number} must be a JSON object.")
        rows.append(row)
    return rows


def _validate_limit(limit: int) -> None:
    """Validate requested export limit."""
    if limit < 1 or limit > MAX_ROWS:
        raise ValueError("limit must be between 1 and 5000.")


def _safe_required_token(value: Any, *, field_name: str) -> str:
    """Return a sanitized token field.

    Args:
        value: Candidate value.
        field_name: Field name for redacted errors.

    Returns:
        Safe token string.

    Raises:
        ValueError: If the value is missing or unsafe.
    """
    if not isinstance(value, str) or not SAFE_TOKEN_PATTERN.fullmatch(value.strip()):
        raise ValueError(f"{field_name} must be a safe token.")
    return value.strip()


def _safe_mime_type(value: Any, *, field_name: str) -> str:
    """Return a validated MIME type string.

    Args:
        value: Candidate MIME type.
        field_name: Field name for redacted errors.

    Returns:
        Safe MIME type string.

    Raises:
        ValueError: If the value is missing or malformed.
    """
    if not isinstance(value, str) or not SAFE_MIME_TYPE_PATTERN.fullmatch(value.strip()):
        raise ValueError(f"{field_name} must be a safe MIME type.")
    return value.strip().lower()


def _safe_sha256(value: Any, *, field_name: str) -> str:
    """Return a SHA-256 hex field.

    Args:
        value: Candidate value.
        field_name: Field name for redacted errors.

    Returns:
        SHA-256 hex digest.
    """
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"{field_name} must be a SHA-256 hex string.")
    return value


def _sha256_file(path: Path) -> str:
    """Return a SHA-256 content hash for a local source file."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_unsafe_payload(value: Any) -> None:
    """Reject local path markers and raw provider/OCR keys.

    Args:
        value: Payload candidate.

    Raises:
        ValueError: If unsafe output would be emitted.
    """
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    for marker in LOCAL_PATH_MARKERS:
        if marker in serialized:
            raise ValueError("annotation template contains a local path literal.")
    _reject_raw_keys(value)


def _reject_raw_keys(value: Any) -> None:
    """Recursively reject raw OCR/provider key names."""
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in RAW_FORBIDDEN_KEYS:
                raise ValueError(f"annotation template contains raw key: {key}")
            _reject_raw_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_raw_keys(child)


def _failure_summary(
    *,
    candidate_manifest: Path,
    output_path: Path,
    error: Exception,
) -> dict[str, Any]:
    """Return a redacted failure summary."""
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "candidate_manifest_name": candidate_manifest.name,
        "output_name": output_path.name,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


if __name__ == "__main__":
    main()
