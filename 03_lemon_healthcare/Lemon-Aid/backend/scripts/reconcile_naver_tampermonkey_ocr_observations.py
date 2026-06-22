"""Reconcile base and retry Tampermonkey OCR observations.

This script selects one redacted observation per ``fixture_id`` and provider
from base and retry JSONL artifacts. It is used after retry runs so coverage
metrics do not double-count failed attempts. It never writes raw OCR text,
provider payloads, request headers, image bytes, raw model responses, secrets,
or local path literals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = "naver-tampermonkey-ocr-observation-reconcile-v1"
DEFAULT_SUMMARY_SUFFIX = ".summary.json"
SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
MAX_SAFE_TOKEN_LENGTH = 120
SOURCE_LABEL_HASH_CHARS = 12
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
    """Reconcile observation JSONL files from CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--observations",
        type=Path,
        action="append",
        required=True,
        help="Observation JSONL path. Repeat in priority order; later ties win.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Summary JSON path. Defaults to <output>.summary.json.",
    )
    args = parser.parse_args()

    output_path = args.output.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else output_path.with_suffix(output_path.suffix + DEFAULT_SUMMARY_SUFFIX)
    )
    observation_paths = [path.expanduser().resolve() for path in args.observations]

    try:
        rows, summary = reconcile_observations(observation_paths=observation_paths)
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
            observation_paths=observation_paths,
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


def reconcile_observations(
    *,
    observation_paths: list[Path],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Select one best redacted observation per fixture/provider.

    Args:
        observation_paths: Observation JSONL files in increasing priority order.

    Returns:
        Reconciled rows and a redacted summary.
    """
    selected: dict[tuple[str, str], tuple[tuple[int, ...], dict[str, object]]] = {}
    selected_source_names: dict[tuple[str, str], str] = {}
    input_count = 0
    duplicate_group_counts: Counter[tuple[str, str]] = Counter()

    for source_index, path in enumerate(observation_paths):
        source_name = _safe_source_label(path)
        for row_index, row in enumerate(_read_jsonl(path)):
            input_count += 1
            fixture_id = _safe_token(_required_str(row, "fixture_id"))
            provider = _safe_token(_required_str(row, "provider"))
            key = (fixture_id, provider)
            duplicate_group_counts[key] += 1
            score = _observation_score(row, source_index=source_index, row_index=row_index)
            current = selected.get(key)
            if current is None or score > current[0]:
                selected[key] = (score, row)
                selected_source_names[key] = source_name

    rows = [selected[key][1] for key in sorted(selected)]
    summary = _build_summary(
        rows=rows,
        observation_paths=observation_paths,
        input_observation_count=input_count,
        duplicate_group_count=sum(1 for count in duplicate_group_counts.values() if count > 1),
        selected_source_names=selected_source_names,
    )
    _reject_unsafe_payload({"rows": rows, "summary": summary})
    return rows, summary


def _observation_score(
    row: dict[str, object],
    *,
    source_index: int,
    row_index: int,
) -> tuple[int, ...]:
    """Return a deterministic quality score for one observation row."""
    status_rank = {"completed": 3, "error": 2, "not_run": 1}.get(str(row.get("status")), 0)
    llm_status_rank = {"completed": 3, "error": 1}.get(str(row.get("llm_parse_status")), 0)
    parser_rank = 1 if row.get("parser_success") is True else 0
    text_rank = 1 if row.get("text_non_empty") is True else 0
    ingredient_count = _bounded_int(row.get("llm_parsed_ingredient_count"))
    if ingredient_count is None and isinstance(row.get("llm_parsed_ingredients"), list):
        ingredient_count = len(row["llm_parsed_ingredients"])  # type: ignore[arg-type]
    return (
        status_rank,
        llm_status_rank,
        parser_rank,
        text_rank,
        ingredient_count or 0,
        source_index,
        row_index,
    )


def _build_summary(
    *,
    rows: list[dict[str, object]],
    observation_paths: list[Path],
    input_observation_count: int,
    duplicate_group_count: int,
    selected_source_names: dict[tuple[str, str], str],
) -> dict[str, object]:
    """Build a redacted reconciliation summary."""
    status_counts: Counter[str] = Counter()
    provider_counts: Counter[str] = Counter()
    llm_status_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    for _key, source_name in selected_source_names.items():
        source_counts[source_name] += 1
    for row in rows:
        provider_counts[_safe_token(str(row.get("provider") or "unknown"))] += 1
        status_counts[_safe_token(str(row.get("status") or "unknown"))] += 1
        llm_status = row.get("llm_parse_status")
        if isinstance(llm_status, str) and llm_status:
            llm_status_counts[_safe_token(llm_status)] += 1
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_file_count": len(observation_paths),
        "input_observation_count": input_observation_count,
        "output_observation_count": len(rows),
        "duplicate_group_count": duplicate_group_count,
        "observation_names": [_safe_source_label(path) for path in observation_paths],
        "observation_path_hashes": [
            _sha256_text(str(path.expanduser())) for path in observation_paths
        ],
        "provider_counts": dict(sorted(provider_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "llm_parse_status_counts": dict(sorted(llm_status_counts.items())),
        "selected_source_counts": dict(sorted(source_counts.items())),
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    """Read JSONL observation rows and reject unsafe content."""
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("Observation JSONL rows must be objects.")
        _reject_unsafe_payload(row)
        rows.append(row)
    return rows


def _failure_summary(
    *,
    observation_paths: list[Path],
    output_path: Path,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted CLI failure summary."""
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "observation_file_count": len(observation_paths),
        "observation_names": [_safe_source_label(path) for path in observation_paths],
        "observation_path_hashes": [
            _sha256_text(str(path.expanduser())) for path in observation_paths
        ],
        "output_name": output_path.name,
        "output_path_hash": _sha256_text(str(output_path.expanduser())),
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _required_str(row: dict[str, object], key: str) -> str:
    """Return a required string field."""
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Observation requires string field: {key}")
    return value.strip()


def _bounded_int(value: object) -> int | None:
    """Return a non-negative integer or None."""
    if not isinstance(value, int) or value < 0:
        return None
    return min(value, 10_000)


def _safe_token(value: str) -> str:
    """Return a bounded public-safe token."""
    token = value.strip()
    if not SAFE_TOKEN_PATTERN.fullmatch(token) or any(
        marker in token for marker in LOCAL_PATH_MARKERS
    ):
        raise ValueError("Unsafe token.")
    return token


def _safe_filename(value: str) -> str:
    """Return a bounded filename token."""
    token = value.strip()
    if "/" in token or "\\" in token:
        raise ValueError("Unsafe filename.")
    return _safe_token(token)


def _safe_source_label(path: Path) -> str:
    """Return a source label using only path component names."""
    parts = [path.name]
    if path.parent.name:
        parts.insert(0, path.parent.name)
    if path.parent.parent.name and path.parent.parent.name != path.parent.name:
        parts.insert(0, path.parent.parent.name)
    label = ":".join(parts)
    try:
        return _safe_filename(label)
    except ValueError:
        digest = _sha256_text(label)[:SOURCE_LABEL_HASH_CHARS]
        suffix = _safe_filename(path.name)
        prefix = f"source-{digest}:"
        available = MAX_SAFE_TOKEN_LENGTH - len(prefix)
        if len(suffix) > available:
            suffix_digest = _sha256_text(suffix)[:SOURCE_LABEL_HASH_CHARS]
            suffix = f"{suffix[: available - SOURCE_LABEL_HASH_CHARS - 1]}:{suffix_digest}"
        return _safe_token(f"{prefix}{suffix}")


def _reject_unsafe_payload(value: object) -> None:
    """Reject raw fields and local path literals recursively."""
    if isinstance(value, dict):
        forbidden = RAW_FORBIDDEN_KEYS.intersection(str(key).lower() for key in value)
        if forbidden:
            raise ValueError(f"Payload contains forbidden raw field(s): {sorted(forbidden)}")
        for nested in value.values():
            _reject_unsafe_payload(nested)
    elif isinstance(value, list | tuple):
        for item in value:
            _reject_unsafe_payload(item)
    elif isinstance(value, str) and any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")


def _safe_error_code(exc: BaseException) -> str:
    """Return a bounded non-sensitive error code."""
    if isinstance(exc, OSError):
        return "local_file_operation_error"
    if isinstance(exc, json.JSONDecodeError):
        return "json_decode_error"
    return "validation_error"


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
