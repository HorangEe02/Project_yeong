"""Export a sanitized queue of learning image objects awaiting manual review."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.db.session import get_sessionmaker  # noqa: E402
from src.learning.pipeline import (  # noqa: E402
    LEARNING_IMAGE_STATUS_PENDING_MANUAL_REVIEW,
    evaluate_learning_metadata_storage_filter,
)
from src.models.db.learning import LearningImageObject  # noqa: E402

SCHEMA_VERSION = "learning-manual-review-queue-v1"
SUMMARY_SCHEMA_VERSION = "learning-manual-review-queue-summary-v1"
MIN_LIMIT = 1
MAX_LIMIT = 500
FORBIDDEN_OUTPUT_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "image_bytes",
        "object_uri",
        "owner_subject_hash",
        "provider_payload",
        "raw_ocr_text",
        "raw_provider_payload",
        "request_headers",
        "review_metadata_snapshot",
        "secret",
        "service_key",
    }
)
NORMALIZED_FORBIDDEN_OUTPUT_KEYS = frozenset(
    "".join(character for character in key.casefold() if character.isalnum())
    for key in FORBIDDEN_OUTPUT_KEYS
)
FORBIDDEN_OUTPUT_STRING_MARKERS = (
    "bearer ",
    "object_uri",
    "owner_subject_hash",
    "provider_payload",
    "raw_ocr_text",
    "raw_provider_payload",
    "request_headers",
    "sb_secret_",
    "service_role",
    "/Users/",
    "/Volumes/",
    "/private/",
    "s3://",
    "file://",
)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output>.summary.json.",
    )
    parser.add_argument(
        "--limit",
        type=_bounded_limit,
        default=100,
        help=f"Maximum pending review rows to export ({MIN_LIMIT}-{MAX_LIMIT}).",
    )
    return parser.parse_args()


def main() -> None:
    """Run the CLI entrypoint."""
    args = parse_args()
    output_path = args.output.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )
    try:
        rows, summary = asyncio.run(export_manual_review_queue(limit=args.limit))
        _reject_unsafe_output({"rows": rows, "summary": summary})
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
    except (OSError, ValueError) as exc:
        summary = _failure_summary(output_path=output_path, error=exc)
        try:
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None


async def export_manual_review_queue(
    *,
    limit: int,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Load pending learning image review rows and return sanitized artifacts.

    Args:
        limit: Maximum pending rows to export.

    Returns:
        JSONL rows and a redacted summary.
    """
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        image_objects = await _load_pending_review_objects(session=session, limit=limit)
    rows = [_review_queue_row(image_object) for image_object in image_objects]
    summary = _summary(rows=rows, limit=limit)
    _reject_unsafe_output({"rows": rows, "summary": summary})
    return rows, summary


async def _load_pending_review_objects(
    *,
    session: Any,
    limit: int,
) -> list[LearningImageObject]:
    """Return pending manual-review image objects.

    Args:
        session: Async DB session.
        limit: Maximum row count.

    Returns:
        Pending review image objects.
    """
    statement = (
        select(LearningImageObject)
        .where(
            LearningImageObject.status == LEARNING_IMAGE_STATUS_PENDING_MANUAL_REVIEW,
            LearningImageObject.deleted_at.is_(None),
        )
        .order_by(LearningImageObject.created_at.asc(), LearningImageObject.id.asc())
        .limit(limit)
    )
    return list((await session.scalars(statement)).all())


def _review_queue_row(image_object: LearningImageObject) -> dict[str, object]:
    """Return a sanitized queue row for one pending review object.

    Args:
        image_object: Pending review object.

    Returns:
        JSON-safe queue row without object URI, owner hash, raw text, or metadata body.
    """
    metadata = image_object.review_metadata_snapshot
    storage_decision = evaluate_learning_metadata_storage_filter(metadata)
    return {
        "schema_version": SCHEMA_VERSION,
        "image_object_id": str(image_object.id),
        "analysis_id": str(image_object.analysis_id),
        "status": image_object.status,
        "object_storage_provider": image_object.object_storage_provider,
        "image_mime_type": image_object.image_mime_type,
        "image_size_bytes": image_object.image_size_bytes,
        "retained_until": image_object.retained_until.isoformat(),
        "created_at": image_object.created_at.isoformat(),
        "metadata_safety_status": storage_decision.reason,
        "metadata_summary": _metadata_summary(metadata),
    }


def _metadata_summary(metadata: dict[str, Any]) -> dict[str, object]:
    """Return review metadata shape without exporting metadata values.

    Args:
        metadata: Sanitized metadata snapshot stored for manual review.

    Returns:
        Bounded metadata summary.
    """
    ingredients = metadata.get("ingredients")
    ingredient_count = len(ingredients) if isinstance(ingredients, list) else 0
    return {
        "top_level_keys": sorted(str(key) for key in metadata)[:20],
        "top_level_key_count": len(metadata),
        "ingredient_count": ingredient_count,
        "has_display_name": _non_empty_string(metadata.get("display_name")),
        "has_manufacturer": _non_empty_string(metadata.get("manufacturer")),
        "has_source_analysis_run_id": _non_empty_string(metadata.get("source_analysis_run_id")),
        "has_matched_product_id": _non_empty_string(metadata.get("matched_product_id")),
    }


def _summary(
    *,
    rows: Sequence[dict[str, object]],
    limit: int,
) -> dict[str, object]:
    """Return a sanitized queue export summary.

    Args:
        rows: Exported rows.
        limit: Requested limit.

    Returns:
        Redacted summary.
    """
    provider_counts: dict[str, int] = {}
    unsafe_metadata_count = 0
    for row in rows:
        provider = str(row.get("object_storage_provider") or "unknown")
        provider_counts[provider] = provider_counts.get(provider, 0) + 1
        if row.get("metadata_safety_status") != "passed":
            unsafe_metadata_count += 1
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "limit": limit,
        "row_count": len(rows),
        "provider_counts": dict(sorted(provider_counts.items())),
        "unsafe_metadata_count": unsafe_metadata_count,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "object_uri_stored": False,
        "owner_subject_hash_stored": False,
    }


def _bounded_limit(raw_limit: str) -> int:
    """Validate a bounded review queue export limit.

    Args:
        raw_limit: Candidate limit from argparse.

    Returns:
        Validated limit.

    Raises:
        argparse.ArgumentTypeError: If limit is invalid.
    """
    try:
        limit = int(raw_limit)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("limit must be an integer") from exc
    if limit < MIN_LIMIT or limit > MAX_LIMIT:
        raise argparse.ArgumentTypeError(f"limit must be between {MIN_LIMIT} and {MAX_LIMIT}")
    return limit


def _failure_summary(
    *,
    output_path: Path,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted failure summary.

    Args:
        output_path: Requested output path.
        error: Raised error.

    Returns:
        Redacted failure summary.
    """
    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "output_name": output_path.name,
        "output_path_hash": _sha256_text(str(output_path.expanduser())),
        "error_type": type(error).__name__,
        "row_count": 0,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "object_uri_stored": False,
        "owner_subject_hash_stored": False,
    }
    _reject_unsafe_output(summary)
    return summary


def _non_empty_string(value: object) -> bool:
    """Return whether a value is a non-empty string.

    Args:
        value: Candidate value.

    Returns:
        True when the value is a non-empty string.
    """
    return isinstance(value, str) and bool(value.strip())


def _sha256_text(value: str) -> str:
    """Return a SHA-256 digest for a text value.

    Args:
        value: Text to hash.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _reject_unsafe_output(value: object) -> None:
    """Reject queue artifacts that contain forbidden raw or location markers.

    Args:
        value: Candidate JSON-safe artifact.

    Raises:
        ValueError: If a forbidden marker appears.
    """
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized_key = str(key).casefold()
            normalized_policy_key = _normalize_policy_key(str(key))
            if (
                normalized_key in FORBIDDEN_OUTPUT_KEYS
                or normalized_policy_key in NORMALIZED_FORBIDDEN_OUTPUT_KEYS
            ):
                raise ValueError(f"Unsafe manual review queue output key: {key}")
            _reject_unsafe_output(nested)
        return
    if isinstance(value, list):
        for item in value:
            _reject_unsafe_output(item)
        return
    if isinstance(value, str):
        value_lower = value.casefold()
        normalized_policy_value = _normalize_policy_key(value)
        if normalized_policy_value in NORMALIZED_FORBIDDEN_OUTPUT_KEYS:
            raise ValueError("Unsafe manual review queue output value.")
        for marker in FORBIDDEN_OUTPUT_STRING_MARKERS:
            if marker.casefold() in value_lower:
                raise ValueError("Unsafe manual review queue output value.")


def _normalize_policy_key(value: str) -> str:
    """Normalize key-like strings before forbidden output comparison.

    Args:
        value: Candidate key or key-like value.

    Returns:
        Lowercase alphanumeric text for snake/camel/kebab-case equivalence.
    """
    return "".join(character for character in value.casefold() if character.isalnum())


if __name__ == "__main__":
    main()
