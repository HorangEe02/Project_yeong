"""Export operator-local supplement review batch JSONL files.

The aggregate batch plan intentionally omits row payloads. This script bridges
that plan to the operator workflow by copying only the requested row ranges
from the editable queue files into smaller batch JSONL files.

The batch JSONL files are local working copies for human review. The JSON and
Markdown summaries remain redacted and never include fixture ids, product text,
source refs, raw OCR, provider payloads, image paths, or absolute local paths.
Original editable files are never modified.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "supplement-operator-review-batch-file-export-v1"
BATCH_PLAN_SCHEMA = "supplement-operator-review-batch-plan-v1"
MARKDOWN_SCHEMA_VERSION = "supplement-operator-review-batch-file-export-markdown-v1"
MAX_SAFE_FILENAME_LENGTH = 160
QUEUE_INPUT_KEYS = {
    "brand_product_review": "brand_decisions",
    "review_pii_screening": "pii_decisions",
    "yolo_section_annotation": "yolo_annotations",
}
LOCAL_PATH_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    "file://",
    "\\Users\\",
    "\\Volumes\\",
)
SOURCE_DOC_URLS = (
    "https://docs.python.org/3/library/csv.html",
    "https://docs.ultralytics.com/datasets/detect/",
    "https://docs.ultralytics.com/tasks/detect/",
    "https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html",
    "https://cloud.google.com/vision/docs/ocr",
    "https://api.ncloud-docs.com/docs/en/ai-application-service-ocr",
    "https://docs.sqlalchemy.org/en/21/orm/queryguide/select.html",
    "https://www.postgresql.org/docs/current/ddl-constraints.html",
    "https://supabase.com/docs/guides/database/postgres/row-level-security",
)
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
UNSAFE_TRUE_FLAGS = (
    "absolute_paths_stored",
    "db_write_performed",
    "external_provider_call_performed",
    "llm_call_performed",
    "ocr_provider_call_performed",
    "paddleocr_training_performed",
    "product_dir_literals_stored",
    "raw_ocr_text_stored",
    "raw_provider_payload_stored",
    "training_execution_performed_by_script",
    "training_export_performed",
)


class BatchFileExportError(ValueError):
    """Raised when batch export inputs or outputs cannot be trusted."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-plan", type=Path, required=True)
    parser.add_argument("--brand-decisions", type=Path, default=None)
    parser.add_argument("--brand-review-csv", type=Path, default=None)
    parser.add_argument("--pii-decisions", type=Path, default=None)
    parser.add_argument("--yolo-annotations", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, default=None)
    parser.add_argument("--markdown-output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write batch JSONL files plus redacted summary artifacts.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    input_paths = {
        "batch_plan": args.batch_plan.expanduser().resolve(),
    }
    optional_inputs = {
        "brand_decisions": args.brand_decisions,
        "brand_review_csv": args.brand_review_csv,
        "pii_decisions": args.pii_decisions,
        "yolo_annotations": args.yolo_annotations,
    }
    for key, value in optional_inputs.items():
        if value is not None:
            input_paths[key] = value.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    summary_output = (
        args.summary_output.expanduser().resolve()
        if args.summary_output is not None
        else output_dir / "summary.json"
    )
    markdown_output = (
        args.markdown_output.expanduser().resolve() if args.markdown_output is not None else None
    )
    try:
        summary = export_operator_review_batch_files(
            input_paths=input_paths,
            output_dir=output_dir,
        )
        _write_json(summary_output, summary)
        if markdown_output is not None:
            markdown = build_batch_file_export_markdown(summary)
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            markdown_output.write_text(markdown, encoding="utf-8")
        print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    except (OSError, json.JSONDecodeError, BatchFileExportError) as exc:
        failure = _failure_summary(input_paths=input_paths, output_dir=output_dir, error=exc)
        _write_json(summary_output, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None


def export_operator_review_batch_files(
    *,
    input_paths: Mapping[str, Path],
    output_dir: Path,
) -> dict[str, Any]:
    """Export batch JSONL files from a redacted batch plan.

    Args:
        input_paths: Input file paths keyed by argument name.
        output_dir: Directory where batch files will be written.

    Returns:
        Redacted export summary.

    Raises:
        BatchFileExportError: If required inputs are missing or unsafe.
    """
    plan = _load_json_object(_required_input(input_paths, "batch_plan"))
    _require_schema(plan, BATCH_PLAN_SCHEMA)
    batch_rows = _batch_rows(plan)
    editable_rows = _load_editable_rows(input_paths=input_paths, batch_rows=batch_rows)
    brand_review_rows = _load_brand_review_rows(input_paths=input_paths)
    output_dir.mkdir(parents=True, exist_ok=True)
    exports = [
        _export_one_batch(
            batch=batch,
            editable_rows=editable_rows,
            brand_review_rows=brand_review_rows,
            output_dir=output_dir,
        )
        for batch in batch_rows
    ]
    queue_batch_counts: dict[str, int] = {}
    queue_row_counts: dict[str, int] = {}
    for row in exports:
        queue_key = str(row["queue_key"])
        queue_batch_counts[queue_key] = queue_batch_counts.get(queue_key, 0) + 1
        queue_row_counts[queue_key] = queue_row_counts.get(queue_key, 0) + int(
            row["exported_row_count"]
        )
    batch_review_files = _batch_review_file_rows(
        exports=exports,
        source_review_csv_name=(
            _safe_filename(input_paths["brand_review_csv"].name)
            if "brand_review_csv" in input_paths
            else None
        ),
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_hashes": {
            key: _sha256_text(str(path.expanduser())) for key, path in sorted(input_paths.items())
        },
        "output_dir_name": output_dir.name,
        "output_dir_hash": _sha256_text(str(output_dir.expanduser())),
        "source_batch_plan_schema": plan.get("schema_version"),
        "batch_file_count": len(exports),
        "batch_review_file_count": len(batch_review_files),
        "exported_row_count": sum(int(row["exported_row_count"]) for row in exports),
        "queue_batch_counts": dict(sorted(queue_batch_counts.items())),
        "queue_row_counts": dict(sorted(queue_row_counts.items())),
        "next_batch_key": _next_batch_key(exports),
        "batch_files": exports,
        "batch_review_files": batch_review_files,
        "original_editable_files_modified": False,
        "operator_local_batch_files_written": True,
        "operator_local_batch_review_files_written": bool(batch_review_files),
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    _reject_unsafe_payload(summary)
    return summary


def build_batch_file_export_markdown(summary: Mapping[str, Any]) -> str:
    """Build a redacted Markdown index for exported batch files.

    Args:
        summary: Export summary from ``export_operator_review_batch_files``.

    Returns:
        Markdown text.
    """
    _reject_unsafe_payload(summary)
    rows = []
    for row in _export_rows(summary):
        rows.append(
            "| {batch_key} | {queue_key} | {file_name} | {source_name} | {start} | {end} | {count} |".format(
                batch_key=_safe_token(str(row["batch_key"])),
                queue_key=_safe_token(str(row["queue_key"])),
                file_name=_safe_filename(str(row["batch_file_name"])),
                source_name=_safe_filename(str(row["source_editable_file_name"])),
                start=_positive_int(row.get("row_index_start")),
                end=_positive_int(row.get("row_index_end")),
                count=_non_negative_int(row.get("exported_row_count")),
            )
        )
    markdown = "\n".join(
        [
            "# Supplement Operator Review Batch Files",
            "",
            f"Schema: `{MARKDOWN_SCHEMA_VERSION}`",
            "",
            "이 문서는 batch 파일명과 row range만 표시합니다. fixture id, 제품명, OCR 원문, provider payload, 이미지 경로, source ref, 로컬 경로는 포함하지 않습니다.",
            "",
            f"- Batch file count: `{_non_negative_int(summary.get('batch_file_count'))}`",
            f"- Batch review CSV count: `{_non_negative_int(summary.get('batch_review_file_count'))}`",
            f"- Exported row count: `{_non_negative_int(summary.get('exported_row_count'))}`",
            f"- Next batch: `{_safe_token(str(summary.get('next_batch_key') or 'none'))}`",
            "",
            "| Batch | Queue | Batch file | Source editable file | Start row | End row | Rows |",
            "| --- | --- | --- | --- | ---: | ---: | ---: |",
            *rows,
            "",
            "## Merge Rule",
            "",
            "1. Batch JSONL은 operator-local working copy입니다.",
            "2. 검수 완료 row를 큐별 원본 editable JSONL에 reconcile한 뒤 기존 queue preflight를 다시 실행합니다.",
            "3. preflight가 통과하기 전에는 DB apply, OCR teacher transfer, YOLO dataset promotion을 진행하지 않습니다.",
            "",
        ]
    )
    _reject_unsafe_payload(markdown)
    return markdown


def _export_one_batch(
    *,
    batch: Mapping[str, Any],
    editable_rows: Mapping[str, list[dict[str, Any]]],
    brand_review_rows: Mapping[str, dict[str, str]] | None,
    output_dir: Path,
) -> dict[str, Any]:
    """Write one batch JSONL file and return its redacted summary row.

    Args:
        batch: Batch plan row.
        editable_rows: Parsed editable rows by queue key.
        output_dir: Export directory.

    Returns:
        Redacted batch export row.
    """
    queue_key = _queue_key(batch.get("queue_key"))
    batch_key = _safe_token(str(batch.get("batch_key") or "unknown"))
    start = _positive_int(batch.get("row_index_start"))
    end = _positive_int(batch.get("row_index_end"))
    if end < start:
        raise BatchFileExportError("Batch row range is invalid.")
    rows = editable_rows.get(queue_key)
    if rows is None:
        raise BatchFileExportError("Editable file for a queued batch is missing.")
    if end > len(rows):
        raise BatchFileExportError("Batch row range exceeds editable row count.")
    selected_rows = rows[start - 1 : end]
    file_name = _batch_file_name(batch_key=batch_key)
    _write_jsonl(output_dir / file_name, selected_rows)
    batch_review_file_name = None
    if queue_key == "brand_product_review" and brand_review_rows is not None:
        batch_review_file_name = _brand_review_batch_file_name(batch_key=batch_key)
        _write_brand_review_csv(
            output_dir / batch_review_file_name,
            batch_rows=selected_rows,
            brand_review_rows=brand_review_rows,
        )
    exported = {
        "batch_key": batch_key,
        "queue_key": queue_key,
        "batch_file_name": file_name,
        "batch_review_file_name": batch_review_file_name,
        "source_editable_file_name": _safe_filename(str(batch.get("editable_file_name") or "")),
        "row_index_start": start,
        "row_index_end": end,
        "exported_row_count": len(selected_rows),
        "original_editable_file_modified": False,
        "operator_local_batch_file_written": True,
        "operator_local_batch_review_file_written": batch_review_file_name is not None,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(exported)
    return exported


def _batch_review_file_rows(
    *,
    exports: list[Mapping[str, Any]],
    source_review_csv_name: str | None,
) -> list[dict[str, Any]]:
    """Return redacted review CSV file rows for summary output.

    Args:
        exports: Batch export rows.
        source_review_csv_name: Source review CSV file name, if provided.

    Returns:
        Redacted batch review file summary rows.
    """
    if source_review_csv_name is None:
        return []
    rows: list[dict[str, Any]] = []
    for row in exports:
        batch_review_file_name = row.get("batch_review_file_name")
        if not isinstance(batch_review_file_name, str) or not batch_review_file_name.strip():
            continue
        rows.append(
            {
                "batch_key": _safe_token(str(row.get("batch_key") or "unknown")),
                "queue_key": _queue_key(row.get("queue_key")),
                "batch_review_file_name": _safe_filename(batch_review_file_name),
                "source_review_csv_name": source_review_csv_name,
                "exported_review_row_count": _non_negative_int(row.get("exported_row_count")),
            }
        )
    return rows


def _load_brand_review_rows(
    *,
    input_paths: Mapping[str, Path],
) -> dict[str, dict[str, str]] | None:
    """Load optional brand review CSV rows keyed by fixture id.

    Args:
        input_paths: Input path mapping.

    Returns:
        Fixture-id keyed review rows, or None when no CSV was provided.
    """
    path = input_paths.get("brand_review_csv")
    if path is None:
        return None
    rows: dict[str, dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "fixture_id" not in reader.fieldnames:
            raise BatchFileExportError("Brand review CSV requires fixture_id column.")
        _reject_unsafe_csv_columns(reader.fieldnames)
        for row in reader:
            fixture_id = _safe_token(row.get("fixture_id") or "")
            if fixture_id in rows:
                raise BatchFileExportError("Brand review CSV has duplicate fixture_id.")
            _reject_unsafe_csv_row(row)
            rows[fixture_id] = {key: value or "" for key, value in row.items()}
    if not rows:
        raise BatchFileExportError("Brand review CSV is empty.")
    return rows


def _write_brand_review_csv(
    path: Path,
    *,
    batch_rows: list[Mapping[str, Any]],
    brand_review_rows: Mapping[str, dict[str, str]],
) -> None:
    """Write a batch-local brand review CSV in batch row order.

    Args:
        path: Destination CSV path.
        batch_rows: Selected brand decision rows.
        brand_review_rows: Full review rows keyed by fixture id.
    """
    selected: list[dict[str, str]] = []
    for batch_row in batch_rows:
        fixture_id = _safe_token(str(batch_row.get("fixture_id") or ""))
        review_row = brand_review_rows.get(fixture_id)
        if review_row is None:
            raise BatchFileExportError("Batch brand decision row is missing review CSV context.")
        selected.append(review_row)
    if not selected:
        raise BatchFileExportError("Brand review batch is empty.")
    fieldnames = list(selected[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(selected)


def _load_editable_rows(
    *,
    input_paths: Mapping[str, Path],
    batch_rows: list[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Load only editable files required by the batch plan.

    Args:
        input_paths: Input path mapping.
        batch_rows: Batch plan rows.

    Returns:
        Queue key to parsed JSONL rows.
    """
    required_queues = {_queue_key(batch.get("queue_key")) for batch in batch_rows}
    rows_by_queue: dict[str, list[dict[str, Any]]] = {}
    for queue_key in sorted(required_queues):
        input_key = QUEUE_INPUT_KEYS[queue_key]
        path = _required_input(input_paths, input_key)
        rows_by_queue[queue_key] = _read_jsonl(path=path)
    return rows_by_queue


def _read_jsonl(*, path: Path) -> list[dict[str, Any]]:
    """Read one editable JSONL file.

    Args:
        path: JSONL path.

    Returns:
        Parsed object rows.
    """
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise BatchFileExportError("Editable JSONL rows must be objects.")
        _reject_unsafe_editable_row(value)
        rows.append(value)
    return rows


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    """Write selected editable rows as a local batch JSONL file.

    Args:
        path: Destination JSONL path.
        rows: Rows to write.
    """
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    """Load one JSON object and reject unsafe summary payloads.

    Args:
        path: JSON path.

    Returns:
        Parsed object.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BatchFileExportError("Batch export inputs must be JSON objects.")
    _reject_unsafe_payload(payload)
    _reject_unsafe_true_flags(payload)
    return payload


def _require_schema(payload: Mapping[str, Any], expected_schema: str) -> None:
    """Validate one schema version.

    Args:
        payload: Parsed payload.
        expected_schema: Required schema version.
    """
    if payload.get("schema_version") != expected_schema:
        raise BatchFileExportError("Batch export input schema does not match.")


def _batch_rows(plan: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return batch rows from a plan.

    Args:
        plan: Batch plan.

    Returns:
        Batch row mappings.
    """
    batches = plan.get("batches")
    if not isinstance(batches, list):
        raise BatchFileExportError("Batch plan is missing batches.")
    if not all(isinstance(batch, Mapping) for batch in batches):
        raise BatchFileExportError("Batch rows must be objects.")
    return batches


def _export_rows(summary: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return export summary rows.

    Args:
        summary: Export summary.

    Returns:
        Export rows.
    """
    rows = summary.get("batch_files")
    if not isinstance(rows, list):
        raise BatchFileExportError("Export summary is missing batch files.")
    if not all(isinstance(row, Mapping) for row in rows):
        raise BatchFileExportError("Export rows must be objects.")
    return rows


def _required_input(input_paths: Mapping[str, Path], key: str) -> Path:
    """Return a required input path.

    Args:
        input_paths: Input mapping.
        key: Required key.

    Returns:
        Input path.
    """
    path = input_paths.get(key)
    if path is None:
        raise BatchFileExportError("Required batch export input is missing.")
    return path


def _queue_key(value: object) -> str:
    """Return a supported queue key.

    Args:
        value: Candidate queue key.

    Returns:
        Queue key.
    """
    queue_key = _safe_token(str(value or "unknown"))
    if queue_key not in QUEUE_INPUT_KEYS:
        raise BatchFileExportError("Unsupported queue key.")
    return queue_key


def _batch_file_name(*, batch_key: str) -> str:
    """Return a safe batch JSONL file name.

    Args:
        batch_key: Batch key from the redacted plan.

    Returns:
        Safe file name.
    """
    return _safe_filename(f"{batch_key.replace(':', '-')}.jsonl")


def _brand_review_batch_file_name(*, batch_key: str) -> str:
    """Return a safe batch-local review CSV file name.

    Args:
        batch_key: Batch key from the redacted plan.

    Returns:
        Safe CSV file name.
    """
    return _safe_filename(f"{batch_key.replace(':', '-')}.review.csv")


def _next_batch_key(exports: list[Mapping[str, Any]]) -> str | None:
    """Return the first exported batch key.

    Args:
        exports: Export rows.

    Returns:
        Batch key or None.
    """
    if not exports:
        return None
    return str(exports[0].get("batch_key"))


def _reject_unsafe_editable_row(value: Any) -> None:
    """Reject raw/provider payloads in rows before copying them.

    Args:
        value: Editable row payload.
    """
    if isinstance(value, Mapping):
        _reject_unsafe_true_flags(value)
        for key, item in value.items():
            if str(key).lower() in RAW_FORBIDDEN_KEYS:
                raise BatchFileExportError("Unsafe raw/provider key found in editable row.")
            _reject_unsafe_editable_row(item)
        return
    if isinstance(value, list | tuple):
        for item in value:
            _reject_unsafe_editable_row(item)
        return
    if isinstance(value, str) and any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise BatchFileExportError("Unsafe local path marker found in editable row.")


def _reject_unsafe_csv_columns(fieldnames: list[str]) -> None:
    """Reject unsafe CSV column names.

    Args:
        fieldnames: CSV header names.
    """
    for fieldname in fieldnames:
        if fieldname.lower() in RAW_FORBIDDEN_KEYS:
            raise BatchFileExportError("Unsafe raw/provider key found in review CSV.")


def _reject_unsafe_csv_row(row: Mapping[str, str | None]) -> None:
    """Reject local path markers in review CSV values.

    Args:
        row: CSV row.
    """
    for value in row.values():
        if value and any(marker in value for marker in LOCAL_PATH_MARKERS):
            raise BatchFileExportError("Unsafe local path marker found in review CSV.")


def _reject_unsafe_true_flags(payload: Mapping[str, Any]) -> None:
    """Reject unsafe execution flags set to true.

    Args:
        payload: Parsed payload.
    """
    for key in UNSAFE_TRUE_FLAGS:
        if payload.get(key) is True:
            raise BatchFileExportError("Batch export input has an unsafe true flag.")


def _reject_unsafe_payload(value: Any) -> None:
    """Reject raw data keys and local path markers recursively.

    Args:
        value: JSON-like payload.
    """
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in RAW_FORBIDDEN_KEYS:
                raise BatchFileExportError("Unsafe raw/provider key found.")
            if key == "source_doc_urls":
                _validate_source_doc_urls(item)
                continue
            _reject_unsafe_payload(item)
        return
    if isinstance(value, list | tuple):
        for item in value:
            _reject_unsafe_payload(item)
        return
    if isinstance(value, str) and any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise BatchFileExportError("Unsafe local path marker found.")


def _validate_source_doc_urls(value: Any) -> None:
    """Validate known official documentation URLs.

    Args:
        value: Candidate URL list.
    """
    if not isinstance(value, list):
        raise BatchFileExportError("source_doc_urls must be a list.")
    allowed = set(SOURCE_DOC_URLS)
    for item in value:
        if item not in allowed:
            raise BatchFileExportError("Unexpected source documentation URL.")


def _safe_filename(value: str) -> str:
    """Return a bounded file name.

    Args:
        value: Candidate file name.

    Returns:
        Safe file name.
    """
    cleaned = value.strip()
    if not cleaned:
        raise BatchFileExportError("File name cannot be blank.")
    if any(marker in cleaned for marker in LOCAL_PATH_MARKERS) or "/" in cleaned or "\\" in cleaned:
        raise BatchFileExportError("Unsafe file name contains a path marker.")
    if len(cleaned) > MAX_SAFE_FILENAME_LENGTH:
        raise BatchFileExportError("File name is too long.")
    return cleaned


def _safe_token(value: str) -> str:
    """Return a bounded token.

    Args:
        value: Candidate token.

    Returns:
        Safe token.
    """
    cleaned = value.strip()
    if not cleaned:
        return "unknown"
    if any(marker in cleaned for marker in LOCAL_PATH_MARKERS) or "/" in cleaned or "\\" in cleaned:
        raise BatchFileExportError("Unsafe token contains a path marker.")
    return cleaned[:120]


def _positive_int(value: object) -> int:
    """Return a positive integer.

    Args:
        value: Candidate value.

    Returns:
        Positive integer.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise BatchFileExportError("Expected a positive integer.")
    return value


def _non_negative_int(value: object) -> int:
    """Return a nonnegative integer value.

    Args:
        value: Candidate value.

    Returns:
        Nonnegative integer.
    """
    if isinstance(value, bool):
        return 0
    if isinstance(value, int) and value >= 0:
        return value
    return 0


def _sha256_text(value: str) -> str:
    """Return a SHA-256 digest for text.

    Args:
        value: Text value.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write one JSON object.

    Args:
        path: Destination path.
        payload: JSON payload.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _cli_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Return compact CLI-safe summary.

    Args:
        summary: Full export summary.

    Returns:
        CLI summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "batch_file_count": _non_negative_int(summary.get("batch_file_count")),
        "batch_review_file_count": _non_negative_int(summary.get("batch_review_file_count")),
        "exported_row_count": _non_negative_int(summary.get("exported_row_count")),
        "next_batch_key": summary.get("next_batch_key"),
        "original_editable_files_modified": False,
        "operator_local_batch_review_files_written": summary.get(
            "operator_local_batch_review_files_written"
        )
        is True,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
    }


def _failure_summary(
    *,
    input_paths: Mapping[str, Path],
    output_dir: Path,
    error: Exception,
) -> dict[str, Any]:
    """Return a redacted failure summary.

    Args:
        input_paths: Input path mapping.
        output_dir: Planned output directory.
        error: Raised exception.

    Returns:
        Redacted failure summary.
    """
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_hashes": {
            key: _sha256_text(str(path.expanduser())) for key, path in sorted(input_paths.items())
        },
        "output_dir_name": output_dir.name,
        "output_dir_hash": _sha256_text(str(output_dir.expanduser())),
        "error_code": _safe_error_code(error),
        "original_editable_files_modified": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _safe_error_code(error: Exception) -> str:
    """Return a public error code.

    Args:
        error: Raised exception.

    Returns:
        Error code.
    """
    if isinstance(error, OSError):
        return "local_file_error"
    if isinstance(error, json.JSONDecodeError):
        return "json_decode_error"
    text = str(error).casefold()
    if "missing" in text:
        return "missing_input"
    if "unsafe" in text:
        return "unsafe_input"
    if "range" in text:
        return "invalid_batch_range"
    return "validation_error"


if __name__ == "__main__":
    main()
