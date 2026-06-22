"""Build OCR ground-truth and YOLO annotation candidate manifests.

This tool scans the local ``data/nutrition_reference/crawling-image`` tree and
splits images into two review-gated artifacts:

* review images -> OCR ground-truth candidates, blocked by PII screening
* detail-page images -> supplement-section YOLO bbox annotation candidates

It does not run OCR, does not create YOLO labels, does not write to the
database, and does not emit local absolute paths, product directory literals,
raw OCR text, or provider payloads.

References:
    https://docs.ultralytics.com/datasets/detect/
    https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
    https://cloud.google.com/vision/docs/ocr
    https://api.ncloud-docs.com/docs/en/ai-application-service-ocr
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import random
import sys
from collections import Counter, defaultdict
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

from scripts import audit_supplement_crawling_image_taxonomy as audit  # noqa: E402

SCHEMA_VERSION = "supplement-learning-candidate-manifests-v1"
OCR_ROW_SCHEMA_VERSION = "supplement-review-ocr-ground-truth-candidate-v1"
YOLO_ROW_SCHEMA_VERSION = "supplement-detail-page-yolo-annotation-candidate-v1"
DEFAULT_ROOT = Path("data") / "nutrition_reference" / "crawling-image"
DEFAULT_MAX_REVIEW_PER_CATEGORY = 5
DEFAULT_MAX_DETAIL_PER_CATEGORY = 5
SOURCE_REF_PREFIX = "crawling-image"
RAW_FORBIDDEN_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "image_bytes",
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
OCR_REQUIRED_FIELDS = (
    "product_identity",
    "ingredient_amounts",
    "intake_method",
    "precautions",
    "allergen_warning",
)
SOURCE_DOC_URLS = (
    "https://docs.ultralytics.com/datasets/detect/",
    "https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html",
    "https://cloud.google.com/vision/docs/ocr",
    "https://api.ncloud-docs.com/docs/en/ai-application-service-ocr",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--ocr-output", type=Path, required=True)
    parser.add_argument("--yolo-output", type=Path, required=True)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <ocr-output>.summary.json.",
    )
    parser.add_argument(
        "--max-review-per-category", type=int, default=DEFAULT_MAX_REVIEW_PER_CATEGORY
    )
    parser.add_argument(
        "--max-detail-per-category", type=int, default=DEFAULT_MAX_DETAIL_PER_CATEGORY
    )
    parser.add_argument("--seed", type=int, default=20260603)
    parser.add_argument(
        "--review-personal-data-cleared",
        action="store_true",
        help="Mark selected review rows as PII-cleared and eligible for teacher OCR.",
    )
    parser.add_argument(
        "--source-run-id",
        default=None,
        help="Optional operator run id to carry through manifests without exposing paths.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write OCR/YOLO candidate manifests and a safe summary.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    ocr_output = args.ocr_output.expanduser().resolve()
    yolo_output = args.yolo_output.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else ocr_output.with_suffix(ocr_output.suffix + ".summary.json")
    )
    try:
        ocr_rows, yolo_rows, summary = build_learning_candidate_manifests(
            root=args.root,
            max_review_per_category=args.max_review_per_category,
            max_detail_per_category=args.max_detail_per_category,
            seed=args.seed,
            review_personal_data_cleared=args.review_personal_data_cleared,
            source_run_id=args.source_run_id,
        )
        _reject_unsafe_payload({"ocr_rows": ocr_rows, "yolo_rows": yolo_rows, "summary": summary})
        _write_jsonl(ocr_output, ocr_rows)
        _write_jsonl(yolo_output, yolo_rows)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, ValueError) as exc:
        failure = _failure_summary(
            error=exc,
            root=args.root,
            ocr_output=ocr_output,
            yolo_output=yolo_output,
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


def build_learning_candidate_manifests(
    *,
    root: Path,
    max_review_per_category: int = DEFAULT_MAX_REVIEW_PER_CATEGORY,
    max_detail_per_category: int = DEFAULT_MAX_DETAIL_PER_CATEGORY,
    seed: int = 20260603,
    review_personal_data_cleared: bool = False,
    source_run_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Return OCR and YOLO candidate rows from crawling-image.

    Args:
        root: Local crawling-image source root.
        max_review_per_category: Maximum review rows per category. Use ``0`` to
            disable review rows.
        max_detail_per_category: Maximum detail-page rows per category. Use
            ``0`` to disable detail rows.
        seed: Deterministic sampling seed.
        review_personal_data_cleared: Whether selected review rows have already
            passed PII screening for teacher OCR transfer.
        source_run_id: Optional operator run id for traceability.

    Returns:
        OCR rows, YOLO rows, and a safe summary.

    Raises:
        ValueError: If source or limit values are invalid.
    """
    _validate_limits(
        max_review_per_category=max_review_per_category,
        max_detail_per_category=max_detail_per_category,
    )
    resolved_root = root.expanduser().resolve()
    if not resolved_root.is_dir():
        raise ValueError("crawling image root is not a directory.")

    selected = _select_candidates(
        root=resolved_root,
        max_review_per_category=max_review_per_category,
        max_detail_per_category=max_detail_per_category,
        seed=seed,
    )
    ocr_rows = [
        _ocr_candidate_row(
            candidate,
            review_personal_data_cleared=review_personal_data_cleared,
            source_run_id=source_run_id,
        )
        for candidate in selected["review"]
    ]
    yolo_rows = [
        _yolo_candidate_row(candidate, source_run_id=source_run_id)
        for candidate in selected["detail_page"]
    ]
    summary = _summary(
        root=root,
        ocr_rows=ocr_rows,
        yolo_rows=yolo_rows,
        max_review_per_category=max_review_per_category,
        max_detail_per_category=max_detail_per_category,
        review_personal_data_cleared=review_personal_data_cleared,
        source_run_id=source_run_id,
    )
    _reject_unsafe_payload({"ocr_rows": ocr_rows, "yolo_rows": yolo_rows, "summary": summary})
    return ocr_rows, yolo_rows, summary


def _validate_limits(*, max_review_per_category: int, max_detail_per_category: int) -> None:
    """Validate manifest sampling limits.

    Args:
        max_review_per_category: Review candidate cap.
        max_detail_per_category: Detail candidate cap.

    Raises:
        ValueError: If any cap is negative.
    """
    if max_review_per_category < 0:
        raise ValueError("max_review_per_category must be nonnegative.")
    if max_detail_per_category < 0:
        raise ValueError("max_detail_per_category must be nonnegative.")


def _select_candidates(
    *,
    root: Path,
    max_review_per_category: int,
    max_detail_per_category: int,
    seed: int,
) -> dict[str, list[dict[str, Any]]]:
    """Select category-balanced review and detail candidates.

    Args:
        root: Resolved crawling-image root.
        max_review_per_category: Review cap per category.
        max_detail_per_category: Detail cap per category.
        seed: Deterministic shuffle seed.

    Returns:
        Mapping of source kind to candidate rows.
    """
    rng = random.Random(seed)
    by_kind_category: dict[str, dict[str, list[dict[str, Any]]]] = {
        audit.SOURCE_KIND_REVIEW: defaultdict(list),
        audit.SOURCE_KIND_DETAIL: defaultdict(list),
    }
    for category_dir in audit._iter_child_dirs(root):
        category_display = audit._strip_category_brackets(category_dir.name)
        category_key = audit._safe_key(category_display)
        for product_dir in audit._iter_child_dirs(category_dir):
            product_audit = audit._audit_product(root=root, product_dir=product_dir)
            for image_path in sorted(product_dir.rglob("*")):
                if not image_path.is_file() or not audit._is_image_file(image_path):
                    continue
                source_kind = audit._source_kind(image_path.relative_to(root))
                if source_kind not in by_kind_category:
                    continue
                by_kind_category[source_kind][category_key].append(
                    _candidate(
                        root=root,
                        image_path=image_path,
                        category_dir=category_dir,
                        category_key=category_key,
                        category_display=category_display,
                        product_audit=product_audit,
                        source_kind=source_kind,
                    )
                )

    selected: dict[str, list[dict[str, Any]]] = {
        audit.SOURCE_KIND_REVIEW: [],
        audit.SOURCE_KIND_DETAIL: [],
    }
    for source_kind, limit in (
        (audit.SOURCE_KIND_REVIEW, max_review_per_category),
        (audit.SOURCE_KIND_DETAIL, max_detail_per_category),
    ):
        if limit == 0:
            continue
        for category_key in sorted(by_kind_category[source_kind]):
            candidates = by_kind_category[source_kind][category_key]
            rng.shuffle(candidates)
            selected[source_kind].extend(candidates[:limit])
    return selected


def _candidate(
    *,
    root: Path,
    image_path: Path,
    category_dir: Path,
    category_key: str,
    category_display: str,
    product_audit: dict[str, Any],
    source_kind: str,
) -> dict[str, Any]:
    """Build a private candidate row before artifact-specific projection.

    Args:
        root: Resolved crawling-image root.
        image_path: Image path.
        category_dir: Parent category directory.
        category_key: Safe category key.
        category_display: Category label.
        product_audit: Sanitized product audit row.
        source_kind: Review/detail source kind.

    Returns:
        Private candidate row. The ``_image_path`` value is used only before
        public projection so large source trees do not hash every image.
    """
    relative_ref = image_path.relative_to(root).as_posix()
    image_ref_hash = audit._sha256_text(relative_ref)
    return {
        "_image_path": image_path,
        "source_ref": f"{SOURCE_REF_PREFIX}:{image_ref_hash[:32]}",
        "image_ref_hash": image_ref_hash,
        "image_size_bytes": image_path.stat().st_size,
        "image_mime_type": mimetypes.guess_type(image_path.name)[0] or "application/octet-stream",
        "category_key": category_key,
        "category_display_name": category_display,
        "source_folder_hash": audit._sha256_text(category_dir.name),
        "product_dir_hash": product_audit["product_dir_hash"],
        "source_product_id": product_audit["source_product_id"],
        "brand_candidate": product_audit["brand_candidate"],
        "source_kind": source_kind,
    }


def _ocr_candidate_row(
    candidate: dict[str, Any],
    *,
    review_personal_data_cleared: bool,
    source_run_id: str | None,
) -> dict[str, Any]:
    """Return one review-image OCR ground-truth candidate row.

    Args:
        candidate: Private candidate row.
        review_personal_data_cleared: Whether PII screening has cleared the row.
        source_run_id: Optional operator run id.

    Returns:
        JSON-safe OCR candidate row.
    """
    pii_status = (
        "operator_cleared_no_personal_data"
        if review_personal_data_cleared
        else "pending_local_screening"
    )
    ground_truth_status = (
        "pending_manual_transcription" if review_personal_data_cleared else "pending_pii_screening"
    )
    return {
        "schema_version": OCR_ROW_SCHEMA_VERSION,
        "source_run_id": source_run_id,
        "fixture_id": f"review-ocr-gt-{candidate['image_ref_hash'][:20]}",
        "source_ref": candidate["source_ref"],
        "image_ref_hash": candidate["image_ref_hash"],
        "image_sha256": _sha256_file(candidate["_image_path"]),
        "image_size_bytes": candidate["image_size_bytes"],
        "image_mime_type": candidate["image_mime_type"],
        "category_key": candidate["category_key"],
        "category_display_name": candidate["category_display_name"],
        "source_folder_hash": candidate["source_folder_hash"],
        "product_dir_hash": candidate["product_dir_hash"],
        "source_product_id": candidate["source_product_id"],
        "brand_candidate": candidate["brand_candidate"],
        "source_kind": audit.SOURCE_KIND_REVIEW,
        "candidate_purpose": "ocr_ground_truth_review",
        "ground_truth_status": ground_truth_status,
        "manual_ground_truth_required": True,
        "required_fields": list(OCR_REQUIRED_FIELDS),
        "teacher_ocr_providers": ["clova", "google_vision"],
        "target_ocr_provider": "paddleocr",
        "contains_personal_data": False if review_personal_data_cleared else None,
        "pii_screening_status": pii_status,
        "external_transfer_allowed": review_personal_data_cleared,
        "teacher_ocr_allowed": review_personal_data_cleared,
        "local_processing_allowed": True,
        "db_write_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def _yolo_candidate_row(candidate: dict[str, Any], *, source_run_id: str | None) -> dict[str, Any]:
    """Return one detail-page YOLO section annotation candidate row.

    Args:
        candidate: Private candidate row.
        source_run_id: Optional operator run id.

    Returns:
        JSON-safe YOLO candidate row.
    """
    return {
        "schema_version": YOLO_ROW_SCHEMA_VERSION,
        "source_run_id": source_run_id,
        "fixture_id": f"detail-yolo-{candidate['image_ref_hash'][:20]}",
        "source_ref": candidate["source_ref"],
        "image_ref_hash": candidate["image_ref_hash"],
        "image_sha256": _sha256_file(candidate["_image_path"]),
        "image_size_bytes": candidate["image_size_bytes"],
        "image_mime_type": candidate["image_mime_type"],
        "category_key": candidate["category_key"],
        "category_display_name": candidate["category_display_name"],
        "source_folder_hash": candidate["source_folder_hash"],
        "product_dir_hash": candidate["product_dir_hash"],
        "source_product_id": candidate["source_product_id"],
        "brand_candidate": candidate["brand_candidate"],
        "source_kind": audit.SOURCE_KIND_DETAIL,
        "candidate_purpose": "supplement_section_bbox_annotation",
        "annotation_task_type": "supplement_roi_box",
        "annotation_status": "pending_section_bbox_human_annotation",
        "section_class_names": list(SUPPLEMENT_SECTION_CLASS_NAMES),
        "coco_pretrained_allowed_for_final_labels": False,
        "custom_section_model_required": True,
        "contains_personal_data": False,
        "pii_screening_status": "not_required_detail_page",
        "external_transfer_allowed": False,
        "local_processing_allowed": True,
        "db_write_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def _summary(
    *,
    root: Path,
    ocr_rows: list[dict[str, Any]],
    yolo_rows: list[dict[str, Any]],
    max_review_per_category: int,
    max_detail_per_category: int,
    review_personal_data_cleared: bool,
    source_run_id: str | None,
) -> dict[str, Any]:
    """Return a safe aggregate summary.

    Args:
        root: Source root.
        ocr_rows: OCR candidate rows.
        yolo_rows: YOLO candidate rows.
        max_review_per_category: Review cap.
        max_detail_per_category: Detail cap.
        review_personal_data_cleared: PII clearance input flag.
        source_run_id: Optional operator run id.

    Returns:
        JSON-safe summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "source_run_id": source_run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_root_name": root.name,
        "source_root_hash": audit._sha256_text(str(root.expanduser())),
        "ocr_candidate_count": len(ocr_rows),
        "yolo_candidate_count": len(yolo_rows),
        "max_review_per_category": max_review_per_category,
        "max_detail_per_category": max_detail_per_category,
        "review_personal_data_cleared": review_personal_data_cleared,
        "ocr_category_counts": _category_counts(ocr_rows),
        "yolo_category_counts": _category_counts(yolo_rows),
        "ocr_external_transfer_allowed_count": sum(
            1 for row in ocr_rows if row["external_transfer_allowed"]
        ),
        "yolo_external_transfer_allowed_count": sum(
            1 for row in yolo_rows if row["external_transfer_allowed"]
        ),
        "manual_ground_truth_required_count": sum(
            1 for row in ocr_rows if row["manual_ground_truth_required"]
        ),
        "bbox_human_annotation_required_count": sum(
            1 for row in yolo_rows if row["annotation_status"].startswith("pending_")
        ),
        "db_write_performed": False,
        "ocr_or_yolo_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


def _category_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Return row counts by category key.

    Args:
        rows: Candidate rows.

    Returns:
        Stable count mapping.
    """
    return dict(sorted(Counter(str(row["category_key"]) for row in rows).items()))


def _sha256_file(path: Path) -> str:
    """Return a SHA-256 hash of file contents.

    Args:
        path: File to hash.

    Returns:
        Hex digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write JSONL rows.

    Args:
        path: Destination path.
        rows: Rows to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _reject_unsafe_payload(value: Any) -> None:
    """Reject local path markers and raw keys.

    Args:
        value: Payload candidate.

    Raises:
        ValueError: If unsafe data appears.
    """
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    for marker in LOCAL_PATH_MARKERS:
        if marker in serialized:
            raise ValueError("learning candidate manifest contains a local path literal.")
    _reject_raw_keys(value)


def _reject_raw_keys(value: Any) -> None:
    """Recursively reject raw OCR/provider key names.

    Args:
        value: Payload candidate.

    Raises:
        ValueError: If unsafe raw key appears.
    """
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in RAW_FORBIDDEN_KEYS:
                raise ValueError(f"learning candidate manifest contains raw key: {key}")
            _reject_raw_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_raw_keys(child)


def _failure_summary(
    *,
    error: Exception,
    root: Path,
    ocr_output: Path,
    yolo_output: Path,
) -> dict[str, Any]:
    """Return a redacted failure summary.

    Args:
        error: Failure exception.
        root: Requested source root.
        ocr_output: Requested OCR output.
        yolo_output: Requested YOLO output.

    Returns:
        JSON-safe failure payload.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "source_root_name": root.name,
        "source_root_hash": audit._sha256_text(str(root.expanduser())),
        "ocr_output_name": ocr_output.name,
        "ocr_output_hash": audit._sha256_text(str(ocr_output.expanduser())),
        "yolo_output_name": yolo_output.name,
        "yolo_output_hash": audit._sha256_text(str(yolo_output.expanduser())),
        "error_code": type(error).__name__,
        "error_message": "Learning candidate manifest build failed.",
        "ocr_candidate_count": 0,
        "yolo_candidate_count": 0,
        "db_write_performed": False,
        "ocr_or_yolo_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


if __name__ == "__main__":
    main()
