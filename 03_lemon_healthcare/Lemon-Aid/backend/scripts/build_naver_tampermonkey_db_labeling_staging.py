"""Build DB-labeling staging rows from Naver Tampermonkey OCR manifests.

The output is intentionally a review/import staging artifact, not a production
database writer. It keeps the manifest's bilingual category labels and chronic
fixture tags while removing local filesystem roots, raw OCR text, provider
payloads, image bytes, and product directory literals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

SCHEMA_VERSION = "naver-tampermonkey-db-labeling-staging-v1"
SHA256_HEX_LENGTH = 64
ALLOWED_IMAGE_ROOT_TOKENS = frozenset({"$NAVER_TAMPERMONKEY_SOURCE_ROOT"})
LOCAL_PATH_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    # Linux operator/CI roots so absolute-path rejection is OS-agnostic (pytest
    # tmp_path is /tmp/... on Linux but /private|/Users/... on macOS).
    "/tmp/",
    "/home/",
    "/root/",
    "/mnt/",
    "/opt/",
    "file://",
    "\\Users\\",
    "\\Volumes\\",
)
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


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the DB-labeling staging builder."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output>.summary.json.",
    )
    parser.add_argument(
        "--source-run-id",
        default=None,
        help="Optional operator run id to attach to every staging row.",
    )
    return parser.parse_args()


def main() -> None:
    """Build staging rows and write JSONL plus a redacted summary."""
    args = parse_args()
    manifest_path = args.manifest.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )

    try:
        rows = build_staging_rows(
            manifest_path=manifest_path,
            source_run_id=args.source_run_id,
        )
        summary = build_summary(rows=rows, manifest_path=manifest_path)
        _reject_raw_fields({"rows": rows, "summary": summary})

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
            manifest_path=manifest_path,
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


def build_staging_rows(
    *,
    manifest_path: Path,
    source_run_id: str | None = None,
) -> list[dict[str, object]]:
    """Return DB-labeling staging rows from a redacted manifest.

    Args:
        manifest_path: JSONL or JSON manifest path containing fixture rows.
        source_run_id: Optional operator run id for traceability.

    Returns:
        A list of JSON-safe staging rows.

    Raises:
        ValueError: If the manifest contains raw fields or unsafe labels.
    """
    manifest_rows = _read_manifest_rows(manifest_path)
    staging_rows = [
        _staging_row_from_manifest_row(row, source_run_id=source_run_id) for row in manifest_rows
    ]
    _reject_raw_fields(staging_rows)
    return staging_rows


def build_summary(
    *,
    rows: Sequence[dict[str, object]],
    manifest_path: Path,
) -> dict[str, object]:
    """Return a redacted summary for the staging output."""
    category_counts: dict[str, int] = {}
    section_counts: dict[str, int] = {}
    review_rows = 0
    external_allowed_rows = 0
    for row in rows:
        category_key = str(row.get("category_key") or "unknown")
        section = str(row.get("section") or "unknown")
        category_counts[category_key] = category_counts.get(category_key, 0) + 1
        section_counts[section] = section_counts.get(section, 0) + 1
        if section == "review":
            review_rows += 1
        if row.get("external_transfer_allowed") is True:
            external_allowed_rows += 1

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "manifest_name": manifest_path.name,
        "row_count": len(rows),
        "category_counts": dict(sorted(category_counts.items())),
        "section_counts": dict(sorted(section_counts.items())),
        "review_rows": review_rows,
        "external_allowed_rows": external_allowed_rows,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "product_dir_literals_stored": False,
    }


def _failure_summary(
    *,
    manifest_path: Path,
    output_path: Path,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted CLI failure summary without filesystem literals."""
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "manifest_name": manifest_path.name,
        "manifest_path_hash": _sha256_text(str(manifest_path.expanduser())),
        "output_name": output_path.name,
        "output_path_hash": _sha256_text(str(output_path.expanduser())),
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "row_count": 0,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "product_dir_literals_stored": False,
    }
    _reject_raw_fields(summary)
    return summary


def _staging_row_from_manifest_row(
    row: dict[str, object],
    *,
    source_run_id: str | None,
) -> dict[str, object]:
    """Convert one manifest row into a safe DB-labeling staging row."""
    _reject_raw_fields(row)
    fixture_id = _required_str(row, "fixture_id")
    image_ref = _safe_image_ref(_required_str(row, "image_path"), fixture_id=fixture_id)
    image_sha256 = _required_sha256(row, "image_sha256")
    db_labeling = _required_dict(row, "db_labeling")
    fixture_labels = row.get("fixture_labels")
    supplement_category = (
        fixture_labels.get("supplement_category")
        if isinstance(fixture_labels, dict)
        and isinstance(fixture_labels.get("supplement_category"), dict)
        else {}
    )

    category_key = _required_str(db_labeling, "category_key")
    section = str(row.get("section") or "unknown")
    contains_personal_data = row.get("contains_personal_data")
    external_transfer_allowed = row.get("external_transfer_allowed") is True
    if section == "review" and external_transfer_allowed and contains_personal_data is not False:
        raise ValueError(
            f"Review fixture cannot be externally staged without PII clearance: {fixture_id}"
        )

    staging_row: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "fixture_id": fixture_id,
        "source": str(row.get("source") or "naver_tampermonkey"),
        "section": section,
        "image_root_token": image_ref.partition("/")[0],
        "image_ref_hash": _sha256_text(image_ref),
        "image_sha256": image_sha256,
        "product_id": _optional_str(row.get("product_id")),
        "product_dir_hash": _optional_hash(row.get("product_dir")),
        "source_category": str(row.get("category") or "unknown"),
        "category_key": category_key,
        "display_name_ko": _optional_str(supplement_category.get("display_name_ko")),
        "display_name_en": _optional_str(supplement_category.get("display_name_en")),
        "language_targets": _normalized_string_list(db_labeling.get("language_targets")),
        "chronic_fixture_tags": _normalized_string_list(db_labeling.get("chronic_fixture_tags")),
        "caution_tags": _normalized_string_list(db_labeling.get("caution_tags")),
        "source_urls": _normalized_string_list(db_labeling.get("source_urls")),
        "label_status": str(db_labeling.get("status") or "pending_human_review"),
        "requires_human_review": True,
        "contains_personal_data": contains_personal_data,
        "pii_screening_status": _optional_str(row.get("pii_screening_status")),
        "external_transfer_allowed": external_transfer_allowed,
        "local_processing_allowed": row.get("local_processing_allowed") is True,
        "is_clinical_recommendation": False,
    }
    if source_run_id:
        staging_row["source_run_id"] = source_run_id
    return staging_row


def _read_manifest_rows(path: Path) -> list[dict[str, object]]:
    """Read JSONL, JSON list, or JSON object-with-cases manifest rows."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        rows = [
            json.loads(line)
            for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    else:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            rows = parsed
        elif isinstance(parsed, dict) and isinstance(parsed.get("cases"), list):
            rows = parsed["cases"]
        else:
            raise ValueError("Manifest must be JSONL, a JSON list, or an object with cases.")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("Manifest rows must be JSON objects.")
    cast_rows = [dict(row) for row in rows]
    _reject_raw_fields(cast_rows)
    return cast_rows


def _safe_image_ref(value: str, *, fixture_id: str) -> str:
    """Return a DB-safe image reference, rejecting local absolute paths."""
    token, separator, suffix = value.partition("/")
    if token not in ALLOWED_IMAGE_ROOT_TOKENS or not separator:
        raise ValueError(f"Fixture image_path must use an allowed token root: {fixture_id}")
    relative = PurePosixPath(suffix)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Fixture image_path must stay under its token root: {fixture_id}")
    return value


def _required_dict(row: dict[str, object], key: str) -> dict[str, object]:
    """Return a required object field."""
    value = row.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Manifest row requires object field: {key}")
    return value


def _required_str(row: dict[str, object], key: str) -> str:
    """Return a required non-empty string field."""
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Manifest row requires string field: {key}")
    if any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")
    return value.strip()


def _required_sha256(row: dict[str, object], key: str) -> str:
    """Return a required SHA-256 hex field."""
    value = _required_str(row, key)
    if len(value) != SHA256_HEX_LENGTH or any(
        char not in "0123456789abcdef" for char in value.lower()
    ):
        raise ValueError(f"Manifest row requires sha256 hex field: {key}")
    return value.lower()


def _optional_str(value: object) -> str | None:
    """Return a stripped optional string."""
    if not isinstance(value, str) or not value.strip():
        return None
    stripped = value.strip()
    if any(marker in stripped for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")
    return stripped


def _optional_hash(value: object) -> str | None:
    """Return a SHA-256 digest for optional metadata instead of storing literals."""
    text = _optional_str(value)
    if text is None:
        return None
    return _sha256_text(text)


def _sha256_text(value: str) -> str:
    """Return a SHA-256 digest for a UTF-8 text value."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalized_string_list(value: object) -> list[str]:
    """Return a sorted unique list of non-empty strings."""
    if not isinstance(value, list):
        return []
    strings = {item.strip() for item in value if isinstance(item, str) and item.strip()}
    if any(marker in item for item in strings for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")
    return sorted(strings)


def _reject_raw_fields(value: object) -> None:
    """Reject raw OCR/image/provider/model fields before writing artifacts."""
    if isinstance(value, dict):
        forbidden = RAW_FORBIDDEN_KEYS.intersection(str(key).lower() for key in value)
        if forbidden:
            raise ValueError(f"Payload contains forbidden raw field(s): {sorted(forbidden)}")
        for nested in value.values():
            _reject_raw_fields(nested)
    elif isinstance(value, list):
        for item in value:
            _reject_raw_fields(item)
    elif isinstance(value, str) and any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")


def _safe_error_code(exc: BaseException) -> str:
    """Return a bounded non-sensitive CLI error code."""
    if isinstance(exc, OSError):
        return "local_file_operation_error"
    if isinstance(exc, json.JSONDecodeError):
        return "json_decode_error"
    return "validation_error"


def _safe_public_error_message(exc: BaseException) -> str:
    """Return a bounded public error message without filesystem details."""
    if isinstance(exc, OSError):
        message = "Local file operation failed."
    elif isinstance(exc, json.JSONDecodeError):
        message = "JSON decode failed."
    else:
        message = str(exc).strip()
    if (
        not message
        or any(marker in message for marker in LOCAL_PATH_MARKERS)
        or "/" in message
        or "\\" in message
    ):
        return "Validation failed."
    return message[:200]


if __name__ == "__main__":
    main()
