"""Export retry manifests from reconciled Tampermonkey OCR failures.

This script reads a source manifest and a reconciled redacted observation JSONL,
then writes collector-compatible retry rows only for remaining failures. It is
intended for iterative OCR experiments after base and retry observations have
already been deduplicated by fixture id. It never stores raw OCR text, provider
payloads, request headers, image bytes, raw model responses, secrets, or local
path literals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

SCHEMA_VERSION = "naver-tampermonkey-reconciled-failure-retry-manifest-v1"
SUMMARY_SCHEMA_VERSION = "naver-tampermonkey-reconciled-failure-retry-summary-v1"
DEFAULT_MANIFEST_NAME = "reconciled-failure-retry-manifest.jsonl"
DEFAULT_SUMMARY_NAME = "reconciled-failure-retry-manifest.summary.json"
FailureKind = Literal["all", "ocr_error", "llm_parse_error"]
SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
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


def main() -> None:
    """Export a retry manifest and redacted summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest-name", default=DEFAULT_MANIFEST_NAME)
    parser.add_argument("--summary-name", default=DEFAULT_SUMMARY_NAME)
    parser.add_argument(
        "--failure-kind",
        choices=("all", "ocr_error", "llm_parse_error"),
        default="all",
    )
    args = parser.parse_args()

    try:
        rows, summary = export_retry_manifest(
            manifest_path=args.manifest.expanduser().resolve(),
            observations_path=args.observations.expanduser().resolve(),
            output_dir=args.output_dir.expanduser().resolve(),
            manifest_name=args.manifest_name,
            summary_name=args.summary_name,
            failure_kind=args.failure_kind,
        )
        _write_outputs(
            rows=rows,
            summary=summary,
            output_dir=args.output_dir.expanduser().resolve(),
            manifest_name=args.manifest_name,
            summary_name=args.summary_name,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure = _failure_summary(
            manifest_path=args.manifest,
            observations_path=args.observations,
            output_dir=args.output_dir,
            error=exc,
        )
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None


def export_retry_manifest(
    *,
    manifest_path: Path,
    observations_path: Path,
    output_dir: Path,
    manifest_name: str = DEFAULT_MANIFEST_NAME,
    summary_name: str = DEFAULT_SUMMARY_NAME,
    failure_kind: FailureKind = "all",
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Build retry rows from remaining reconciled OCR/LLM failures.

    Args:
        manifest_path: Source redacted manifest containing collector image refs.
        observations_path: Reconciled redacted observation JSONL.
        output_dir: Planned output directory.
        manifest_name: Retry manifest filename.
        summary_name: Summary filename.
        failure_kind: Failure kind filter.

    Returns:
        Retry rows and summary.

    Raises:
        ValueError: If input rows are malformed or unsafe.
    """
    safe_manifest_name = _safe_filename(manifest_name, suffix=".jsonl", field_name="manifest_name")
    safe_summary_name = _safe_filename(summary_name, suffix=".json", field_name="summary_name")
    source_rows = _load_manifest_rows(manifest_path)
    observations = _read_jsonl(observations_path)
    retry_rows: list[dict[str, object]] = []
    skipped_missing_fixture_count = 0

    for observation in observations:
        _reject_unsafe_payload(observation)
        kind = _failure_kind(observation)
        if kind is None or failure_kind not in {"all", kind}:
            continue
        fixture_id = _safe_token(_required_str(observation, "fixture_id"))
        source_row = source_rows.get(fixture_id)
        if source_row is None:
            skipped_missing_fixture_count += 1
            continue
        retry_rows.append(
            _retry_row_from_source(
                source_row=source_row,
                observation=observation,
                failure_kind=kind,
            )
        )

    summary = _build_summary(
        rows=retry_rows,
        manifest_path=manifest_path,
        observations_path=observations_path,
        output_dir=output_dir,
        manifest_name=safe_manifest_name,
        summary_name=safe_summary_name,
        failure_kind=failure_kind,
        input_observation_count=len(observations),
        skipped_missing_fixture_count=skipped_missing_fixture_count,
    )
    _reject_unsafe_payload({"rows": retry_rows, "summary": summary})
    return retry_rows, summary


def _load_manifest_rows(path: Path) -> dict[str, dict[str, object]]:
    """Load source manifest rows keyed by fixture id."""
    rows: dict[str, dict[str, object]] = {}
    for row in _read_jsonl(path):
        fixture_id = row.get("fixture_id")
        if not isinstance(fixture_id, str) or not fixture_id:
            continue
        safe_fixture_id = _safe_token(fixture_id)
        if safe_fixture_id in rows:
            raise ValueError(f"Duplicate fixture_id in manifest: {safe_fixture_id}")
        rows[safe_fixture_id] = row
    return rows


def _failure_kind(row: dict[str, object]) -> FailureKind | None:
    """Return the failure kind for one reconciled observation."""
    status = _safe_optional_token(row.get("status"))
    llm_parse_status = _safe_optional_token(row.get("llm_parse_status"))
    if status == "error":
        return "ocr_error"
    if status == "completed" and llm_parse_status == "error":
        return "llm_parse_error"
    return None


def _retry_row_from_source(
    *,
    source_row: dict[str, object],
    observation: dict[str, object],
    failure_kind: FailureKind,
) -> dict[str, object]:
    """Return one collector-compatible retry row with bounded metadata."""
    _reject_unsafe_payload(source_row)
    retry_row = json.loads(json.dumps(source_row, ensure_ascii=False))
    if not isinstance(retry_row, dict):
        raise ValueError("Manifest row must be an object.")
    retry_row["retry_metadata"] = {
        "schema_version": SCHEMA_VERSION,
        "source_fixture_id": _safe_token(_required_str(observation, "fixture_id")),
        "failure_kind": failure_kind,
        "source_status": _safe_optional_token(observation.get("status")),
        "source_error_code": _safe_optional_token(observation.get("error_code")),
        "source_llm_parse_status": _safe_optional_token(observation.get("llm_parse_status")),
        "source_llm_parse_error_code": _safe_optional_token(
            observation.get("llm_parse_error_code")
        ),
        "suggested_next_action": _suggest_next_action(
            failure_kind=failure_kind,
            error_code=_safe_optional_token(observation.get("error_code")),
            llm_error_code=_safe_optional_token(observation.get("llm_parse_error_code")),
        ),
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(retry_row)
    return retry_row


def _suggest_next_action(
    *,
    failure_kind: FailureKind,
    error_code: str | None,
    llm_error_code: str | None,
) -> str:
    """Return a bounded next-action token for one failure."""
    if failure_kind == "llm_parse_error":
        if llm_error_code == "ollama_structured_output":
            return "retry_structured_parser_or_schema_prompt"
        return "inspect_llm_parser_runtime"
    if error_code in {"ocr_low_confidence", "ocr_empty_text"}:
        return "inspect_image_quality_or_layout_model"
    return "human_review"


def _build_summary(
    *,
    rows: list[dict[str, object]],
    manifest_path: Path,
    observations_path: Path,
    output_dir: Path,
    manifest_name: str,
    summary_name: str,
    failure_kind: FailureKind,
    input_observation_count: int,
    skipped_missing_fixture_count: int,
) -> dict[str, object]:
    """Build a redacted retry-manifest summary."""
    failure_kind_counts: Counter[str] = Counter()
    error_code_counts: Counter[str] = Counter()
    llm_error_code_counts: Counter[str] = Counter()
    category_key_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    for row in rows:
        metadata = row.get("retry_metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        failure_kind_counts[_safe_token(str(metadata.get("failure_kind") or "unknown"))] += 1
        action_counts[_safe_token(str(metadata.get("suggested_next_action") or "unknown"))] += 1
        error_code = _safe_optional_token(metadata.get("source_error_code"))
        if error_code:
            error_code_counts[error_code] += 1
        llm_error_code = _safe_optional_token(metadata.get("source_llm_parse_error_code"))
        if llm_error_code:
            llm_error_code_counts[llm_error_code] += 1
        db_labeling = row.get("db_labeling")
        if isinstance(db_labeling, dict):
            category_key = _safe_optional_token(db_labeling.get("category_key"))
            if category_key:
                category_key_counts[category_key] += 1

    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "manifest_name": _safe_filename(manifest_path.name, suffix=".jsonl", field_name="manifest"),
        "observations_name": _safe_filename(
            observations_path.name,
            suffix=".jsonl",
            field_name="observations",
        ),
        "output_dir_name": _safe_filename(output_dir.name, field_name="output_dir"),
        "manifest_path_hash": _sha256_text(str(manifest_path.expanduser())),
        "observations_path_hash": _sha256_text(str(observations_path.expanduser())),
        "output_dir_hash": _sha256_text(str(output_dir.expanduser())),
        "manifest_filename": manifest_name,
        "summary_filename": summary_name,
        "failure_kind_filter": failure_kind,
        "input_observation_count": input_observation_count,
        "retry_row_count": len(rows),
        "skipped_missing_fixture_count": skipped_missing_fixture_count,
        "failure_kind_counts": dict(sorted(failure_kind_counts.items())),
        "error_code_counts": dict(sorted(error_code_counts.items())),
        "llm_parse_error_code_counts": dict(sorted(llm_error_code_counts.items())),
        "category_key_counts": dict(sorted(category_key_counts.items())),
        "suggested_next_action_counts": dict(sorted(action_counts.items())),
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _write_outputs(
    *,
    rows: list[dict[str, object]],
    summary: dict[str, object],
    output_dir: Path,
    manifest_name: str,
    summary_name: str,
) -> None:
    """Write retry manifest and summary JSON."""
    safe_manifest_name = _safe_filename(manifest_name, suffix=".jsonl", field_name="manifest_name")
    safe_summary_name = _safe_filename(summary_name, suffix=".json", field_name="summary_name")
    _reject_unsafe_payload({"rows": rows, "summary": summary})
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / safe_manifest_name).write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (output_dir / safe_summary_name).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    """Read JSONL object rows and reject unsafe content."""
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("JSONL rows must be objects.")
        _reject_unsafe_payload(row)
        rows.append(row)
    return rows


def _failure_summary(
    *,
    manifest_path: Path,
    observations_path: Path,
    output_dir: Path,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted CLI failure summary."""
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "manifest_name": manifest_path.name,
        "observations_name": observations_path.name,
        "output_dir_name": output_dir.name,
        "manifest_path_hash": _sha256_text(str(manifest_path.expanduser())),
        "observations_path_hash": _sha256_text(str(observations_path.expanduser())),
        "output_dir_hash": _sha256_text(str(output_dir.expanduser())),
        "error_type": type(error).__name__,
        "error_message": _safe_public_error_message(error),
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }


def _required_str(row: dict[str, object], key: str) -> str:
    """Return a required non-empty string field."""
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing required field: {key}")
    return value.strip()


def _safe_optional_token(value: object) -> str | None:
    """Return a safe token or None for empty values."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Optional token must be a string when present.")
    if not value.strip():
        return None
    return _safe_token(value)


def _safe_token(value: str) -> str:
    """Return a bounded public-safe token."""
    token = value.strip()
    if not SAFE_TOKEN_PATTERN.fullmatch(token) or any(
        marker in token for marker in LOCAL_PATH_MARKERS
    ):
        raise ValueError("Unsafe token.")
    return token


def _safe_filename(value: str, *, suffix: str | None = None, field_name: str = "filename") -> str:
    """Return a bounded safe filename."""
    token = value.strip()
    if "/" in token or "\\" in token or not token:
        raise ValueError(f"Unsafe {field_name}.")
    if suffix is not None and not token.endswith(suffix):
        raise ValueError(f"{field_name} must end with {suffix}.")
    return _safe_token(token)


def _reject_unsafe_payload(value: object) -> None:
    """Reject raw fields and local path literals recursively."""
    if isinstance(value, dict):
        forbidden = RAW_FORBIDDEN_KEYS.intersection(str(key).lower() for key in value)
        if forbidden:
            raise ValueError(f"Payload contains forbidden raw field(s): {sorted(forbidden)}")
        for nested in value.values():
            _reject_unsafe_payload(nested)
        return
    if isinstance(value, list):
        for item in value:
            _reject_unsafe_payload(item)
        return
    if isinstance(value, str) and any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains a local path literal.")


def _safe_public_error_message(exc: BaseException) -> str:
    """Return a public error message without filesystem details."""
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


def _sha256_text(value: str) -> str:
    """Return SHA-256 for a text value."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
