"""Reconcile operator-local supplement review batch JSONL files.

Batch files are intentionally exported as local working copies. This script
checks those edited batch files against the redacted batch plan and writes
queue-level reconciled JSONL copies that can be inspected before replacing the
original editable files.

The script never overwrites source decision/annotation files. Summaries and
Markdown output are redacted and contain only counts, file names, queue keys,
and row ranges.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from scripts import (  # noqa: E402
    export_supplement_operator_review_batch_files as batch_exporter,
)

SCHEMA_VERSION = "supplement-operator-review-batch-file-reconcile-v1"
MARKDOWN_SCHEMA_VERSION = "supplement-operator-review-batch-file-reconcile-markdown-v1"
RECONCILED_FILE_NAMES = {
    "brand_product_review": "brand_product_review.reconciled.jsonl",
    "review_pii_screening": "review_pii_screening.reconciled.jsonl",
    "yolo_section_annotation": "yolo_section_annotation.reconciled.jsonl",
}


class BatchFileReconcileError(ValueError):
    """Raised when batch reconciliation cannot be trusted."""


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
    parser.add_argument("--pii-decisions", type=Path, default=None)
    parser.add_argument("--yolo-annotations", type=Path, default=None)
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument(
        "--batch-file-override",
        action="append",
        default=[],
        nargs=2,
        metavar=("BATCH_KEY", "BATCH_FILE"),
        help=(
            "Use BATCH_FILE for one batch key while reading all other batch files "
            "from --batch-dir. This preserves the original editable batch files."
        ),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, default=None)
    parser.add_argument("--markdown-output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write reconciled JSONL copies plus redacted summaries.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    input_paths = {
        "batch_plan": args.batch_plan.expanduser().resolve(),
    }
    optional_inputs = {
        "brand_decisions": args.brand_decisions,
        "pii_decisions": args.pii_decisions,
        "yolo_annotations": args.yolo_annotations,
    }
    for key, value in optional_inputs.items():
        if value is not None:
            input_paths[key] = value.expanduser().resolve()
    batch_dir = args.batch_dir.expanduser().resolve()
    batch_file_overrides = _batch_file_overrides_from_args(args.batch_file_override)
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
        summary = reconcile_operator_review_batch_files(
            input_paths=input_paths,
            batch_dir=batch_dir,
            output_dir=output_dir,
            batch_file_overrides=batch_file_overrides,
        )
        _write_json(summary_output, summary)
        if markdown_output is not None:
            markdown = build_reconcile_markdown(summary)
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            markdown_output.write_text(markdown, encoding="utf-8")
        print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    except (OSError, json.JSONDecodeError, BatchFileReconcileError) as exc:
        failure = _failure_summary(
            input_paths=input_paths,
            batch_dir=batch_dir,
            output_dir=output_dir,
            error=exc,
        )
        _write_json(summary_output, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None


def reconcile_operator_review_batch_files(
    *,
    input_paths: Mapping[str, Path],
    batch_dir: Path,
    output_dir: Path,
    batch_file_overrides: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    """Reconcile edited batch files into queue-level JSONL copies.

    Args:
        input_paths: Original editable input paths keyed by argument name.
        batch_dir: Directory that contains operator-local batch JSONL files.
        output_dir: Directory where reconciled queue-level JSONL copies are written.
        batch_file_overrides: Optional per-batch JSONL files that replace files
            from ``batch_dir`` without modifying source editable files.

    Returns:
        Redacted reconciliation summary.
    """
    plan = batch_exporter._load_json_object(_required_input(input_paths, "batch_plan"))
    batch_exporter._require_schema(plan, batch_exporter.BATCH_PLAN_SCHEMA)
    batch_rows = batch_exporter._batch_rows(plan)
    originals = _load_original_rows(input_paths=input_paths, batch_rows=batch_rows)
    merged = {queue_key: list(rows) for queue_key, rows in originals.items()}
    touched_ranges: dict[str, set[int]] = {queue_key: set() for queue_key in originals}
    safe_batch_file_overrides = _validated_batch_file_overrides(
        batch_rows=batch_rows,
        batch_file_overrides=batch_file_overrides or {},
    )
    batch_summaries = []
    for batch in batch_rows:
        summary_row = _reconcile_one_batch(
            batch=batch,
            batch_dir=batch_dir,
            batch_file_overrides=safe_batch_file_overrides,
            originals=originals,
            merged=merged,
            touched_ranges=touched_ranges,
        )
        batch_summaries.append(summary_row)
    output_dir.mkdir(parents=True, exist_ok=True)
    queue_summaries = [
        _write_reconciled_queue_copy(queue_key=queue_key, rows=rows, output_dir=output_dir)
        for queue_key, rows in sorted(merged.items())
    ]
    queue_batch_counts: dict[str, int] = {}
    queue_changed_counts: dict[str, int] = {}
    for row in batch_summaries:
        queue_key = str(row["queue_key"])
        queue_batch_counts[queue_key] = queue_batch_counts.get(queue_key, 0) + 1
        queue_changed_counts[queue_key] = queue_changed_counts.get(queue_key, 0) + int(
            row["changed_row_count"]
        )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_hashes": {
            key: _fingerprint_text(str(path.expanduser()))
            for key, path in sorted(input_paths.items())
        },
        "batch_dir_name": batch_dir.name,
        "batch_dir_hash": _fingerprint_text(str(batch_dir.expanduser())),
        "batch_file_override_count": len(safe_batch_file_overrides),
        "batch_file_override_names": {
            batch_key: path.name for batch_key, path in sorted(safe_batch_file_overrides.items())
        },
        "output_dir_name": output_dir.name,
        "output_dir_hash": _fingerprint_text(str(output_dir.expanduser())),
        "batch_count": len(batch_summaries),
        "expected_row_count": sum(int(row["expected_row_count"]) for row in batch_summaries),
        "changed_row_count": sum(int(row["changed_row_count"]) for row in batch_summaries),
        "unchanged_row_count": sum(int(row["unchanged_row_count"]) for row in batch_summaries),
        "queue_batch_counts": dict(sorted(queue_batch_counts.items())),
        "queue_changed_counts": dict(sorted(queue_changed_counts.items())),
        "reconciled_copy_count": len(queue_summaries),
        "human_review_changes_detected": any(
            int(row["changed_row_count"]) > 0 for row in batch_summaries
        ),
        "ready_for_batch_progress_preflight": True,
        "queue_outputs": queue_summaries,
        "batches": batch_summaries,
        "original_editable_files_modified": False,
        "reconciled_copies_written": True,
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
        "source_doc_urls": list(batch_exporter.SOURCE_DOC_URLS),
    }
    _reject_unsafe_payload(summary)
    return summary


def build_reconcile_markdown(summary: Mapping[str, Any]) -> str:
    """Build a redacted Markdown reconciliation report.

    Args:
        summary: Reconciliation summary.

    Returns:
        Markdown text.
    """
    _reject_unsafe_payload(summary)
    rows = []
    for row in _batch_summary_rows(summary):
        rows.append(
            "| {batch_key} | {queue_key} | {batch_file} | {expected} | {changed} | {unchanged} |".format(
                batch_key=batch_exporter._safe_token(str(row["batch_key"])),
                queue_key=batch_exporter._safe_token(str(row["queue_key"])),
                batch_file=batch_exporter._safe_filename(str(row["batch_file_name"])),
                expected=batch_exporter._non_negative_int(row.get("expected_row_count")),
                changed=batch_exporter._non_negative_int(row.get("changed_row_count")),
                unchanged=batch_exporter._non_negative_int(row.get("unchanged_row_count")),
            )
        )
    markdown = "\n".join(
        [
            "# Supplement Operator Review Batch Reconcile",
            "",
            f"Schema: `{MARKDOWN_SCHEMA_VERSION}`",
            "",
            "이 문서는 batch reconciliation count만 표시합니다. fixture id, 제품명, OCR 원문, provider payload, 이미지 경로, source ref, 로컬 경로는 포함하지 않습니다.",
            "",
            f"- Batch count: `{batch_exporter._non_negative_int(summary.get('batch_count'))}`",
            f"- Expected row count: `{batch_exporter._non_negative_int(summary.get('expected_row_count'))}`",
            f"- Changed row count: `{batch_exporter._non_negative_int(summary.get('changed_row_count'))}`",
            f"- Reconciled copy count: `{batch_exporter._non_negative_int(summary.get('reconciled_copy_count'))}`",
            f"- Human review changes detected: `{bool(summary.get('human_review_changes_detected'))}`",
            "",
            "| Batch | Queue | Batch file | Expected rows | Changed rows | Unchanged rows |",
            "| --- | --- | --- | ---: | ---: | ---: |",
            *rows,
            "",
            "## Next Gate",
            "",
            "1. Reconciled copy를 확인한 뒤 원본 editable JSONL로 반영합니다.",
            "2. 42차 batch progress preflight와 큐별 정식 preflight를 다시 실행합니다.",
            "3. preflight가 통과하기 전에는 DB apply, teacher OCR transfer, YOLO dataset promotion을 진행하지 않습니다.",
            "",
        ]
    )
    _reject_unsafe_payload(markdown)
    return markdown


def _reconcile_one_batch(
    *,
    batch: Mapping[str, Any],
    batch_dir: Path,
    batch_file_overrides: Mapping[str, Path],
    originals: Mapping[str, list[dict[str, Any]]],
    merged: dict[str, list[dict[str, Any]]],
    touched_ranges: dict[str, set[int]],
) -> dict[str, Any]:
    """Reconcile one batch file into the merged row set.

    Args:
        batch: Batch plan row.
        batch_dir: Batch directory.
        batch_file_overrides: Optional per-batch reviewed JSONL files.
        originals: Original editable rows by queue key.
        merged: Mutable merged rows by queue key.
        touched_ranges: Mutable row-index coverage map.

    Returns:
        Redacted batch reconciliation row.
    """
    queue_key = batch_exporter._queue_key(batch.get("queue_key"))
    batch_key = batch_exporter._safe_token(str(batch.get("batch_key") or "unknown"))
    start = batch_exporter._positive_int(batch.get("row_index_start"))
    end = batch_exporter._positive_int(batch.get("row_index_end"))
    if end < start:
        raise BatchFileReconcileError("Batch row range is invalid.")
    expected_count = end - start + 1
    original_rows = originals.get(queue_key)
    if original_rows is None:
        raise BatchFileReconcileError("Original editable file for batch is missing.")
    if end > len(original_rows):
        raise BatchFileReconcileError("Batch row range exceeds original row count.")
    covered = touched_ranges[queue_key]
    overlap = [index for index in range(start, end + 1) if index in covered]
    if overlap:
        raise BatchFileReconcileError("Batch row ranges overlap.")
    covered.update(range(start, end + 1))
    batch_file_name = _batch_file_name(batch_key)
    batch_file_path = batch_file_overrides.get(batch_key, batch_dir / batch_file_name)
    batch_rows = _read_batch_rows(batch_file_path)
    if len(batch_rows) != expected_count:
        raise BatchFileReconcileError("Batch file row count does not match plan.")
    original_slice = original_rows[start - 1 : end]
    changed_count = sum(
        1
        for original, reviewed in zip(original_slice, batch_rows, strict=True)
        if _row_key(original) != _row_key(reviewed)
    )
    merged[queue_key][start - 1 : end] = batch_rows
    row = {
        "batch_key": batch_key,
        "queue_key": queue_key,
        "batch_file_name": batch_file_name,
        "batch_file_override_used": batch_key in batch_file_overrides,
        "row_index_start": start,
        "row_index_end": end,
        "expected_row_count": expected_count,
        "changed_row_count": changed_count,
        "unchanged_row_count": expected_count - changed_count,
        "original_editable_file_modified": False,
        "reconciled_copy_written": True,
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
    _reject_unsafe_payload(row)
    return row


def _load_original_rows(
    *,
    input_paths: Mapping[str, Path],
    batch_rows: list[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Load original editable JSONL rows required by the batch plan.

    Args:
        input_paths: Original editable paths.
        batch_rows: Batch plan rows.

    Returns:
        Queue key to parsed rows.
    """
    required_queues = {batch_exporter._queue_key(batch.get("queue_key")) for batch in batch_rows}
    rows_by_queue: dict[str, list[dict[str, Any]]] = {}
    for queue_key in sorted(required_queues):
        input_key = batch_exporter.QUEUE_INPUT_KEYS[queue_key]
        path = _required_input(input_paths, input_key)
        rows_by_queue[queue_key] = _read_batch_rows(path)
    return rows_by_queue


def _read_batch_rows(path: Path) -> list[dict[str, Any]]:
    """Read JSONL rows and enforce local safety limits.

    Args:
        path: JSONL path.

    Returns:
        Parsed rows.
    """
    rows: list[dict[str, Any]] = []
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BatchFileReconcileError(
            "Required batch JSONL file is missing or unreadable."
        ) from exc
    for line in content.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise BatchFileReconcileError("Batch JSONL rows must be objects.")
        _reject_unsafe_editable_row(row)
        rows.append(row)
    return rows


def _write_reconciled_queue_copy(
    *,
    queue_key: str,
    rows: list[Mapping[str, Any]],
    output_dir: Path,
) -> dict[str, Any]:
    """Write one reconciled queue-level JSONL copy.

    Args:
        queue_key: Queue key.
        rows: Merged rows.
        output_dir: Destination directory.

    Returns:
        Redacted output row.
    """
    file_name = batch_exporter._safe_filename(RECONCILED_FILE_NAMES[queue_key])
    path = output_dir / file_name
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    output = {
        "queue_key": queue_key,
        "reconciled_file_name": file_name,
        "row_count": len(rows),
        "original_editable_file_modified": False,
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
    _reject_unsafe_payload(output)
    return output


def _batch_file_name(batch_key: str) -> str:
    """Return the expected batch file name.

    Args:
        batch_key: Batch key.

    Returns:
        Batch file name.
    """
    return batch_exporter._safe_filename(f"{batch_key.replace(':', '-')}.jsonl")


def _row_key(row: Mapping[str, Any]) -> str:
    """Return a stable serialized row for equality checks.

    Args:
        row: JSON row.

    Returns:
        Stable JSON string.
    """
    return json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _batch_summary_rows(summary: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return batch rows from a reconciliation summary.

    Args:
        summary: Reconciliation summary.

    Returns:
        Batch rows.
    """
    rows = summary.get("batches")
    if not isinstance(rows, list):
        raise BatchFileReconcileError("Reconciliation summary is missing batches.")
    if not all(isinstance(row, Mapping) for row in rows):
        raise BatchFileReconcileError("Reconciliation batch rows must be objects.")
    return rows


def _required_input(input_paths: Mapping[str, Path], key: str) -> Path:
    """Return a required input path.

    Args:
        input_paths: Input path mapping.
        key: Required input key.

    Returns:
        Input path.
    """
    path = input_paths.get(key)
    if path is None:
        raise BatchFileReconcileError("Required reconciliation input is missing.")
    return path


def _batch_file_overrides_from_args(raw_overrides: list[list[str]]) -> dict[str, Path]:
    """Parse per-batch override arguments.

    Args:
        raw_overrides: CLI ``--batch-file-override`` pairs.

    Returns:
        Batch key to resolved batch JSONL path.

    Raises:
        BatchFileReconcileError: If duplicate or unsafe override keys are supplied.
    """
    overrides: dict[str, Path] = {}
    for raw_key, raw_path in raw_overrides:
        batch_key = batch_exporter._safe_token(str(raw_key))
        if not batch_key:
            raise BatchFileReconcileError("Batch file override key is unsafe.")
        if batch_key in overrides:
            raise BatchFileReconcileError("Duplicate batch file override key.")
        overrides[batch_key] = Path(raw_path).expanduser().resolve()
    return overrides


def _validated_batch_file_overrides(
    *,
    batch_rows: list[Mapping[str, Any]],
    batch_file_overrides: Mapping[str, Path],
) -> dict[str, Path]:
    """Validate override batch keys against the redacted batch plan.

    Args:
        batch_rows: Batch plan rows.
        batch_file_overrides: Candidate override paths by batch key.

    Returns:
        Validated override paths by batch key.

    Raises:
        BatchFileReconcileError: If an override does not map to a planned batch.
    """
    planned_batch_keys = {
        batch_exporter._safe_token(str(batch.get("batch_key") or "unknown")) for batch in batch_rows
    }
    unknown_batch_keys = sorted(set(batch_file_overrides) - planned_batch_keys)
    if unknown_batch_keys:
        raise BatchFileReconcileError("Batch file override key is not present in the batch plan.")
    return dict(batch_file_overrides)


def _reject_unsafe_editable_row(value: Any) -> None:
    """Reject raw/provider fields and local absolute path markers in row payloads.

    Args:
        value: JSON-like row payload.
    """
    if isinstance(value, Mapping):
        _reject_unsafe_true_flags(value)
        for key, item in value.items():
            if str(key).lower() in batch_exporter.RAW_FORBIDDEN_KEYS:
                raise BatchFileReconcileError("Unsafe raw/provider key found in editable row.")
            _reject_unsafe_editable_row(item)
        return
    if isinstance(value, list | tuple):
        for item in value:
            _reject_unsafe_editable_row(item)
        return
    if isinstance(value, str) and any(
        marker in value for marker in batch_exporter.LOCAL_PATH_MARKERS
    ):
        raise BatchFileReconcileError("Unsafe local path marker found in editable row.")


def _reject_unsafe_true_flags(payload: Mapping[str, Any]) -> None:
    """Reject unsafe execution flags set to true in editable rows.

    Args:
        payload: Parsed row.
    """
    for key in batch_exporter.UNSAFE_TRUE_FLAGS:
        if payload.get(key) is True:
            raise BatchFileReconcileError("Reconciliation input has an unsafe true flag.")


def _reject_unsafe_payload(value: Any) -> None:
    """Reject unsafe public output fields.

    Args:
        value: JSON-like output payload.
    """
    try:
        batch_exporter._reject_unsafe_payload(value)
    except batch_exporter.BatchFileExportError as exc:
        raise BatchFileReconcileError(str(exc)) from exc


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
        summary: Full reconciliation summary.

    Returns:
        CLI summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "batch_count": batch_exporter._non_negative_int(summary.get("batch_count")),
        "expected_row_count": batch_exporter._non_negative_int(summary.get("expected_row_count")),
        "changed_row_count": batch_exporter._non_negative_int(summary.get("changed_row_count")),
        "reconciled_copy_count": batch_exporter._non_negative_int(
            summary.get("reconciled_copy_count")
        ),
        "human_review_changes_detected": bool(summary.get("human_review_changes_detected")),
        "original_editable_files_modified": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
    }


def _failure_summary(
    *,
    input_paths: Mapping[str, Path],
    batch_dir: Path,
    output_dir: Path,
    error: Exception,
) -> dict[str, Any]:
    """Return a redacted failure summary.

    Args:
        input_paths: Input path mapping.
        batch_dir: Batch directory.
        output_dir: Reconciled output directory.
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
            key: _fingerprint_text(str(path.expanduser()))
            for key, path in sorted(input_paths.items())
        },
        "batch_dir_name": batch_dir.name,
        "batch_dir_hash": _fingerprint_text(str(batch_dir.expanduser())),
        "output_dir_name": output_dir.name,
        "output_dir_hash": _fingerprint_text(str(output_dir.expanduser())),
        "error_code": _safe_error_code(error),
        "original_editable_files_modified": False,
        "reconciled_copies_written": False,
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
    markers = (
        ("missing", "missing_input"),
        ("unsafe", "unsafe_input"),
        ("range", "invalid_batch_range"),
        ("count", "row_count_mismatch"),
    )
    for marker, code in markers:
        if marker in text:
            return code
    return "validation_error"


def _fingerprint_text(value: str) -> str:
    """Return a short non-secret fingerprint for operator artifact inputs.

    Args:
        value: Text value to fingerprint.

    Returns:
        Stable short fingerprint.
    """
    return f"fp-{batch_exporter._sha256_text(value)[:12]}"


if __name__ == "__main__":
    main()
