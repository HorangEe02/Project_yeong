"""Build a local-only PII screening manifest for Naver review images.

This script is the handoff before any review-image OCR work. It scans the local
Tampermonkey crawl root, emits only review-section image rows, and keeps every
row external-transfer disabled until a human PII screening decision exists. It
does not run OCR, call LLMs, upload images, open a database connection, or store
product directory literals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import build_naver_tampermonkey_ocr_manifest as manifest_builder  # noqa: E402

SCHEMA_VERSION = "naver-tampermonkey-review-pii-screening-manifest-v1"
DEFAULT_MANIFEST_NAME = "review-pii-screening-manifest.jsonl"
DEFAULT_SUMMARY_NAME = "review-pii-screening-manifest.summary.json"
RAW_FORBIDDEN_KEYS = manifest_builder.RAW_FORBIDDEN_KEYS
LOCAL_PATH_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    "file://",
    "\\Users\\",
    "\\Volumes\\",
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for review PII screening manifest generation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=manifest_builder.DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--manifest-name", default=DEFAULT_MANIFEST_NAME)
    parser.add_argument("--summary-name", default=DEFAULT_SUMMARY_NAME)
    parser.add_argument(
        "--category-taxonomy",
        type=Path,
        default=manifest_builder.DEFAULT_CATEGORY_TAXONOMY_PATH,
    )
    parser.add_argument(
        "--image-root-env-var",
        default=manifest_builder.DEFAULT_IMAGE_ROOT_ENV_VAR,
    )
    parser.add_argument("--scan-limit", type=int, default=200_000)
    parser.add_argument(
        "--sample-size",
        type=int,
        default=0,
        help="Maximum review rows to emit. Use 0 to emit all review candidates.",
    )
    parser.add_argument("--seed", type=int, default=20260524)
    parser.add_argument("--min-width", type=int, default=160)
    parser.add_argument("--min-height", type=int, default=120)
    parser.add_argument("--max-bytes", type=int, default=50_000_000)
    return parser.parse_args()


def main() -> None:
    """Write review PII screening manifest and summary artifacts."""
    args = parse_args()
    try:
        summary = build_review_pii_screening_manifest(
            source_root=args.source_root.expanduser().resolve(),
            output_dir=args.output_dir.expanduser().resolve(),
            manifest_name=args.manifest_name,
            summary_name=args.summary_name,
            category_taxonomy_path=args.category_taxonomy,
            image_root_env_var=args.image_root_env_var,
            scan_limit=args.scan_limit,
            sample_size=args.sample_size,
            seed=args.seed,
            min_width=args.min_width,
            min_height=args.min_height,
            max_bytes=args.max_bytes,
        )
    except (OSError, ValueError) as exc:
        failure = _failure_summary(
            source_root=args.source_root,
            manifest_name=args.manifest_name,
            summary_name=args.summary_name,
            error=exc,
        )
        output_dir = args.output_dir.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        failure_summary_name = _fallback_summary_name(args.summary_name)
        (output_dir / failure_summary_name).write_text(
            json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_review_pii_screening_manifest(
    *,
    source_root: Path,
    output_dir: Path,
    manifest_name: str = DEFAULT_MANIFEST_NAME,
    summary_name: str = DEFAULT_SUMMARY_NAME,
    category_taxonomy_path: Path | None = manifest_builder.DEFAULT_CATEGORY_TAXONOMY_PATH,
    image_root_env_var: str = manifest_builder.DEFAULT_IMAGE_ROOT_ENV_VAR,
    scan_limit: int = 200_000,
    sample_size: int = 0,
    seed: int = 20260524,
    min_width: int = 160,
    min_height: int = 120,
    max_bytes: int = 50_000_000,
) -> dict[str, object]:
    """Build local-only review image rows for human PII screening.

    Args:
        source_root: Local Tampermonkey crawl root.
        output_dir: Destination directory for generated artifacts.
        manifest_name: JSONL output filename.
        summary_name: JSON summary filename.
        category_taxonomy_path: Supplement category taxonomy path.
        image_root_env_var: Env-token root used by local tools to resolve images.
        scan_limit: Maximum files to inspect under ``source_root``.
        sample_size: Maximum review rows. ``0`` emits every review candidate.
        seed: Deterministic sampling seed when ``sample_size`` is non-zero.
        min_width: Minimum decoded image width.
        min_height: Minimum decoded image height.
        max_bytes: Maximum accepted file size.

    Returns:
        Redacted generation summary.

    Raises:
        ValueError: If options are invalid or unsafe payloads would be written.
    """
    safe_manifest_name = _safe_output_filename(manifest_name, field_name="manifest_name")
    safe_summary_name = _safe_output_filename(summary_name, field_name="summary_name")
    _validate_options(
        source_root=source_root,
        image_root_env_var=image_root_env_var,
        scan_limit=scan_limit,
        sample_size=sample_size,
        min_width=min_width,
        min_height=min_height,
        max_bytes=max_bytes,
    )
    candidates, inventory = manifest_builder.scan_naver_tampermonkey_images(
        source_root=source_root,
        scan_limit=scan_limit,
        min_width=min_width,
        min_height=min_height,
        max_bytes=max_bytes,
    )
    review_candidates = [item for item in candidates if item.section == "review"]
    selected = _select_review_candidates(
        review_candidates,
        sample_size=sample_size,
        seed=seed,
    )
    taxonomy = manifest_builder.load_category_taxonomy(category_taxonomy_path)
    rows = [
        _screening_row(
            candidate,
            index=index,
            taxonomy=taxonomy,
            image_root_env_var=image_root_env_var,
        )
        for index, candidate in enumerate(selected, 1)
    ]
    category_counts = Counter(str(row["category_key"]) for row in rows)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_root_hash": _sha256_text(str(source_root)),
        "source_root_exists": source_root.exists(),
        "files_seen": inventory["files_seen"],
        "candidate_count": inventory["candidate_count"],
        "review_candidate_count": len(review_candidates),
        "manifest_row_count": len(rows),
        "sample_size": sample_size,
        "category_key_count": len(category_counts),
        "category_key_counts": dict(sorted(category_counts.items())),
        "external_transfer_allowed_rows": 0,
        "pending_local_screening_rows": len(rows),
        "product_dir_literals_stored": False,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload({"rows": rows, "summary": summary})

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / safe_manifest_name
    summary_path = output_dir / safe_summary_name
    manifest_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {**summary, "manifest_name": safe_manifest_name, "summary_name": safe_summary_name}


def _failure_summary(
    *,
    source_root: Path,
    manifest_name: str,
    summary_name: str,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted manifest-generation failure summary."""
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "source_root_hash": _sha256_text(str(source_root)),
        "source_root_exists": source_root.exists(),
        "manifest_name": _safe_name_or_default(manifest_name, DEFAULT_MANIFEST_NAME),
        "summary_name": _safe_name_or_default(summary_name, DEFAULT_SUMMARY_NAME),
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "files_seen": 0,
        "candidate_count": 0,
        "review_candidate_count": 0,
        "manifest_row_count": 0,
        "sample_size": 0,
        "category_key_count": 0,
        "category_key_counts": {},
        "external_transfer_allowed_rows": 0,
        "pending_local_screening_rows": 0,
        "product_dir_literals_stored": False,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _select_review_candidates(
    candidates: list[manifest_builder.NaverImageCandidate],
    *,
    sample_size: int,
    seed: int,
) -> list[manifest_builder.NaverImageCandidate]:
    """Return all review candidates or a deterministic sample."""
    if sample_size == 0 or sample_size >= len(candidates):
        return sorted(candidates, key=lambda item: item.relative_path.as_posix())
    return manifest_builder.select_manifest_candidates(
        candidates,
        section="review",
        sample_size=sample_size,
        seed=seed,
    )


def _screening_row(
    candidate: manifest_builder.NaverImageCandidate,
    *,
    index: int,
    taxonomy: dict[str, object],
    image_root_env_var: str,
) -> dict[str, object]:
    """Return one local-only PII screening row."""
    category_label = manifest_builder.build_category_label(
        candidate.category,
        category_taxonomy=taxonomy,
    )
    image_ref = f"${image_root_env_var}/{candidate.relative_path.as_posix()}"
    row = {
        "schema_version": SCHEMA_VERSION,
        "fixture_id": f"naver-tm-review-pii-{index:06d}",
        "source": "naver_tampermonkey",
        "section": "review",
        "image_path": image_ref,
        "image_ref_hash": _sha256_text(image_ref),
        "file_size_bytes": candidate.size_bytes,
        "mime_type": candidate.mime_type,
        "width": candidate.width,
        "height": candidate.height,
        "product": {
            "product_id": candidate.product_id,
            "product_dir_hash": _sha256_text(candidate.product_dir),
        },
        "category_key": category_label["category_key"],
        "category_display": {
            "ko": category_label["display_name_ko"],
            "en": category_label["display_name_en"],
        },
        "language_targets": category_label["language_targets"],
        "chronic_fixture_tags": category_label["condition_tags"],
        "caution_tags": category_label["caution_tags"],
        "contains_personal_data": None,
        "pii_screening_status": "pending_local_screening",
        "external_transfer_allowed": False,
        "local_processing_allowed": True,
        "is_clinical_recommendation": False,
        "clinical_recommendation_forbidden": True,
        "operator_decision_required": True,
    }
    _reject_unsafe_payload(row)
    return row


def _validate_options(
    *,
    source_root: Path,
    image_root_env_var: str,
    scan_limit: int,
    sample_size: int,
    min_width: int,
    min_height: int,
    max_bytes: int,
) -> None:
    """Validate review screening generation options."""
    manifest_builder._validate_options(
        source_root=source_root,
        image_root_env_var=image_root_env_var,
        sample_size=max(sample_size, 1),
        scan_limit=scan_limit,
        min_width=min_width,
        min_height=min_height,
        max_bytes=max_bytes,
    )
    if sample_size < 0:
        raise ValueError("sample_size must be zero or positive.")


def _reject_unsafe_payload(value: object) -> None:
    """Reject raw payload keys and local absolute path literals."""
    if isinstance(value, dict):
        forbidden = RAW_FORBIDDEN_KEYS.intersection(str(key).lower() for key in value)
        if forbidden:
            raise ValueError(f"Payload contains forbidden raw field(s): {sorted(forbidden)}")
        if "product_dir" in {str(key).lower() for key in value}:
            raise ValueError("Payload must not store product_dir literals.")
        for nested in value.values():
            _reject_unsafe_payload(nested)
    elif isinstance(value, list | tuple):
        for item in value:
            _reject_unsafe_payload(item)
    elif isinstance(value, str) and any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")


def _safe_output_filename(value: str, *, field_name: str) -> str:
    """Return a filename that cannot escape the requested output directory."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty filename.")
    stripped = value.strip()
    if (
        stripped in {".", ".."}
        or "/" in stripped
        or "\\" in stripped
        or Path(stripped).name != stripped
        or any(marker in stripped for marker in LOCAL_PATH_MARKERS)
    ):
        raise ValueError(f"{field_name} must be a filename, not a path.")
    return stripped


def _safe_name_or_default(value: str, default: str) -> str:
    """Return a safe filename for failure summaries without raising."""
    try:
        return _safe_output_filename(value, field_name="filename")
    except ValueError:
        return default


def _fallback_summary_name(value: str) -> str:
    """Return a safe summary filename even when user input is invalid."""
    return _safe_name_or_default(value, DEFAULT_SUMMARY_NAME)


def _safe_error_code(exc: BaseException) -> str:
    """Return a non-sensitive CLI error code."""
    if isinstance(exc, OSError):
        return "local_file_error"
    return "validation_error"


def _safe_public_error_message(exc: BaseException) -> str:
    """Return a bounded public error message without filesystem details."""
    if isinstance(exc, OSError):
        return "Local file operation failed."
    message = str(exc).strip()
    if not message:
        return "Validation failed."
    if any(marker in message for marker in LOCAL_PATH_MARKERS):
        return "Validation failed."
    if "/" in message or "\\" in message:
        return "Validation failed."
    return message[:200]


def _sha256_text(value: str) -> str:
    """Return SHA-256 for redacted identifiers."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
