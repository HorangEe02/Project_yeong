"""Merge redacted OCR observations into benchmark fixture rows.

``collect_supplement_ocr_observations.py`` writes flat, redacted provider
observation JSONL. The PaddleOCR 95 percent target summary builder expects
fixture rows with an ``observations`` array. This adapter joins both artifacts
by ``fixture_id`` without reading raw OCR text, image bytes, provider payloads,
database rows, or local source-image paths.

References:
    https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
    https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppocr/model_train/detection.html
    https://paddlepaddle.github.io/PaddleOCR/v2.10.0/en/ppocr/model_train/recognition.html
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "supplement-ocr-provider-metric-benchmark-merge-v1"
ROW_SCHEMA_VERSION = "supplement-ocr-provider-metric-benchmark-fixture-v1"
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
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
        "secret",
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
SECRET_LIKE_MARKERS = (
    "bearer ",
    "ngrok-free.dev",
    "sb_secret_",
    "service_role",
    "aws_secret_access_key",
    "-----begin",
)
SOURCE_DOC_URLS = (
    "https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html",
    "https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppocr/model_train/detection.html",
    "https://paddlepaddle.github.io/PaddleOCR/v2.10.0/en/ppocr/model_train/recognition.html",
)


class PaddleOCRObservationMergeError(ValueError):
    """Raised when observations cannot be safely merged into benchmark rows."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-manifest", required=True, type=Path)
    parser.add_argument("--observations", required=True, type=Path, nargs="+")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output>.summary.json.",
    )
    parser.add_argument(
        "--allow-unmatched-observations",
        action="store_true",
        help="Ignore observation fixture ids missing from the benchmark manifest.",
    )
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None) -> int:
    """Run the merge adapter and write redacted artifacts.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else args.output.expanduser().resolve().with_suffix(args.output.suffix + ".summary.json")
    )
    try:
        rows, summary = merge_observations_into_benchmark(
            benchmark_manifest=args.benchmark_manifest,
            observation_paths=tuple(args.observations),
            allow_unmatched_observations=args.allow_unmatched_observations,
        )
    except (OSError, json.JSONDecodeError, PaddleOCRObservationMergeError, ValueError) as exc:
        rows = []
        summary = _error_summary(error=exc)
        exit_code = 1
    else:
        exit_code = 0

    _write_jsonl(args.output, rows)
    _write_json(summary_path, summary)
    print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    return exit_code


def merge_observations_into_benchmark(
    *,
    benchmark_manifest: Path,
    observation_paths: tuple[Path, ...],
    allow_unmatched_observations: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Attach redacted provider observations to benchmark fixture rows.

    Args:
        benchmark_manifest: JSONL fixture manifest with expected GT.
        observation_paths: Flat provider observation JSONL files.
        allow_unmatched_observations: Whether to ignore observations that do
            not match a benchmark fixture id.

    Returns:
        Merged fixture rows and redacted summary.

    Raises:
        PaddleOCRObservationMergeError: If rows are unsafe or unmatched.
    """
    benchmark_rows = _read_jsonl(benchmark_manifest)
    fixture_ids = {
        _safe_token(row.get("fixture_id"), field_name="fixture_id") for row in benchmark_rows
    }
    observations_by_fixture: dict[str, list[dict[str, Any]]] = {}
    observation_count = 0
    unmatched_observation_count = 0
    provider_counts: Counter[str] = Counter()

    for observation_path in observation_paths:
        for observation in _read_jsonl(observation_path):
            _reject_unsafe_payload(observation)
            fixture_id = _safe_token(
                observation.get("fixture_id"), field_name="observation.fixture_id"
            )
            if fixture_id not in fixture_ids:
                unmatched_observation_count += 1
                if not allow_unmatched_observations:
                    raise PaddleOCRObservationMergeError(
                        "observation fixture_id not found in benchmark."
                    )
                continue
            provider = _safe_token(observation.get("provider"), field_name="observation.provider")
            provider_counts[provider] += 1
            observation_count += 1
            observations_by_fixture.setdefault(fixture_id, []).append(dict(observation))

    merged_rows: list[dict[str, Any]] = []
    fixtures_with_observations = 0
    for benchmark_row in benchmark_rows:
        _reject_unsafe_payload(benchmark_row)
        fixture_id = _safe_token(benchmark_row.get("fixture_id"), field_name="fixture_id")
        observations = observations_by_fixture.get(fixture_id, [])
        if observations:
            fixtures_with_observations += 1
        row = dict(benchmark_row)
        row["schema_version"] = ROW_SCHEMA_VERSION
        row["observations"] = observations
        row["db_write_performed"] = False
        row["source_rows_read"] = False
        row["source_image_read_performed"] = False
        row["raw_ocr_text_stored"] = False
        row["raw_provider_payload_stored"] = False
        row["absolute_paths_stored"] = False
        merged_rows.append(row)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "benchmark_manifest_name": benchmark_manifest.name,
        "observation_file_count": len(observation_paths),
        "benchmark_fixture_count": len(benchmark_rows),
        "observation_count": observation_count,
        "unmatched_observation_count": unmatched_observation_count,
        "fixtures_with_observations": fixtures_with_observations,
        "provider_counts": dict(sorted(provider_counts.items())),
        "db_write_performed": False,
        "source_rows_read": False,
        "source_image_read_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    _reject_unsafe_payload({"rows": merged_rows, "summary": summary})
    return merged_rows, summary


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL object rows.

    Args:
        path: JSONL path.

    Returns:
        Parsed object rows.

    Raises:
        PaddleOCRObservationMergeError: If a line is not an object.
    """
    if not path.is_file():
        raise PaddleOCRObservationMergeError("input JSONL file does not exist.")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parsed = json.loads(stripped)
        if not isinstance(parsed, dict):
            raise PaddleOCRObservationMergeError(f"JSONL line {line_number} must be an object.")
        rows.append(parsed)
    return rows


def _safe_token(value: Any, *, field_name: str) -> str:
    """Return a safe token value.

    Args:
        value: Candidate value.
        field_name: Diagnostic field name.

    Returns:
        Safe token string.
    """
    if not isinstance(value, str) or not value.strip():
        raise PaddleOCRObservationMergeError(f"{field_name} must be a non-empty string.")
    token = value.strip()
    if not TOKEN_PATTERN.fullmatch(token):
        raise PaddleOCRObservationMergeError(f"{field_name} must be a stable token.")
    return token


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write JSONL rows.

    Args:
        path: Destination path.
        rows: Redacted rows.
    """
    _reject_unsafe_payload(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write one JSON object.

    Args:
        path: Destination path.
        payload: Redacted payload.
    """
    _reject_unsafe_payload(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _reject_unsafe_payload(value: Any) -> None:
    """Reject raw OCR, provider payloads, local paths, and secrets.

    Args:
        value: JSON-like payload.

    Raises:
        ValueError: If unsafe content is detected.
    """
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).lower()
            if key_text in RAW_FORBIDDEN_KEYS:
                raise ValueError(key_text)
            _reject_unsafe_payload(child)
        return
    if isinstance(value, list | tuple):
        for child in value:
            _reject_unsafe_payload(child)
        return
    if isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in SECRET_LIKE_MARKERS):
            raise ValueError("secret-like marker")
        if any(marker in value for marker in LOCAL_PATH_MARKERS):
            raise ValueError("local path literal")


def _cli_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Return stdout-safe status.

    Args:
        summary: Redacted summary artifact.

    Returns:
        Compact CLI status.
    """
    return {
        "schema_version": "paddleocr-observation-merge-cli-v1",
        "status": summary.get("status", "ok"),
        "benchmark_fixture_count": summary.get("benchmark_fixture_count", 0),
        "observation_count": summary.get("observation_count", 0),
        "fixtures_with_observations": summary.get("fixtures_with_observations", 0),
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
    }


def _error_summary(*, error: Exception) -> dict[str, Any]:
    """Return a redacted error summary.

    Args:
        error: Exception that blocked merging.

    Returns:
        Safe failure summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "error_type": type(error).__name__,
        "benchmark_fixture_count": 0,
        "observation_count": 0,
        "unmatched_observation_count": 0,
        "fixtures_with_observations": 0,
        "provider_counts": {},
        "db_write_performed": False,
        "source_rows_read": False,
        "source_image_read_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


if __name__ == "__main__":
    raise SystemExit(run_cli())
