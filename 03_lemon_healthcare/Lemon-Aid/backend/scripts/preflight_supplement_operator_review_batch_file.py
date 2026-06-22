"""Preflight one operator-local supplement review batch file.

Operator review batches are intentionally edited as small local JSONL files
before they are reconciled into queue-level decision or annotation files. This
script validates one batch file directly so reviewers can confirm a batch is
complete before running reconciliation.

The output is aggregate-only: it does not include fixture ids, product text,
OCR text, provider payloads, image paths, source refs, or local absolute paths.

References:
    https://docs.python.org/3/library/argparse.html
    https://docs.python.org/3/library/json.html
    https://www.postgresql.org/docs/current/ddl-constraints.html
    https://supabase.com/docs/guides/database/postgres/row-level-security
"""

from __future__ import annotations

import argparse
import csv
import hashlib
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

from scripts import preflight_supplement_operator_review_batch_progress as progress  # noqa: E402

SCHEMA_VERSION = "supplement-operator-review-batch-file-preflight-v1"
SOURCE_DOC_URLS = progress.SOURCE_DOC_URLS


class BatchFilePreflightError(ValueError):
    """Raised when a single batch file cannot be trusted."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-plan", type=Path, required=True)
    parser.add_argument("--batch-key", required=True)
    parser.add_argument("--batch-file", type=Path, required=True)
    parser.add_argument("--batch-review-csv", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write one batch file preflight report.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    input_paths = {
        "batch_plan": args.batch_plan.expanduser().resolve(),
        "batch_file": args.batch_file.expanduser().resolve(),
    }
    if args.batch_review_csv is not None:
        input_paths["batch_review_csv"] = args.batch_review_csv.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    markdown_output = (
        args.markdown_output.expanduser().resolve() if args.markdown_output is not None else None
    )
    try:
        summary = preflight_operator_review_batch_file(
            input_paths=input_paths,
            batch_key=args.batch_key,
        )
        _write_json(output_path, summary)
        if markdown_output is not None:
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            markdown_output.write_text(build_markdown(summary), encoding="utf-8")
        print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    except (OSError, json.JSONDecodeError, BatchFilePreflightError, ValueError) as exc:
        failure = _failure_summary(
            input_paths=input_paths,
            batch_key=args.batch_key,
            output_path=output_path,
            error=exc,
        )
        _write_json(output_path, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None


def preflight_operator_review_batch_file(
    *,
    input_paths: Mapping[str, Path],
    batch_key: str,
) -> dict[str, Any]:
    """Return redacted completion status for one operator-local batch file.

    Args:
        input_paths: ``batch_plan`` and ``batch_file`` paths.
        batch_key: Batch key from the redacted batch plan.

    Returns:
        Redacted batch file preflight summary.
    """
    safe_batch_key = progress._safe_token(batch_key)
    plan = progress._load_json_object(_required_input(input_paths, "batch_plan"))
    progress._require_schema(plan, progress.BATCH_PLAN_SCHEMA)
    batch = _find_batch(plan, batch_key=safe_batch_key)
    queue_key = progress._queue_key(batch.get("queue_key"))
    start = progress._positive_int(batch.get("row_index_start"))
    end = progress._positive_int(batch.get("row_index_end"))
    if end < start:
        raise BatchFilePreflightError("Batch row range is invalid.")
    expected_count = end - start + 1
    batch_file = _required_input(input_paths, "batch_file")
    rows = progress._read_jsonl(path=batch_file)
    review_csv_summary = _review_csv_summary(
        queue_key=queue_key,
        rows=rows,
        review_csv_path=input_paths.get("batch_review_csv"),
    )
    statuses = [
        progress._status_for_index(queue_key=queue_key, rows=rows, row_index=index)
        for index in range(1, expected_count + 1)
    ]
    counts = progress._status_counts(statuses)
    reason_counts = progress._reason_counts(statuses)
    actual_row_count = len(rows)
    extra_row_count = max(0, actual_row_count - expected_count)
    if extra_row_count:
        reason_counts["extra_rows"] = extra_row_count
    batch_status = progress._batch_status(
        expected_count=expected_count,
        valid_count=counts["valid"],
        blank_count=counts["blank"],
        pending_count=counts["pending"],
        invalid_count=counts["invalid"],
        missing_count=counts["missing"],
    )
    if extra_row_count:
        batch_status = "invalid"
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_hashes": {
            key: _sha256_text(str(path.expanduser())) for key, path in sorted(input_paths.items())
        },
        "batch_key": safe_batch_key,
        "queue_key": queue_key,
        "batch_file_name": batch_file.name,
        **review_csv_summary,
        "source_editable_file_name": _safe_filename(
            str(
                batch.get("editable_file_name")
                or batch.get("source_editable_file_name")
                or "unknown.jsonl"
            )
        ),
        "row_index_start": start,
        "row_index_end": end,
        "expected_row_count": expected_count,
        "actual_row_count": actual_row_count,
        "valid_row_count": counts["valid"],
        "blank_row_count": counts["blank"],
        "pending_row_count": counts["pending"],
        "invalid_row_count": counts["invalid"],
        "missing_row_count": counts["missing"],
        "extra_row_count": extra_row_count,
        "reason_counts": dict(sorted(reason_counts.items())),
        "batch_status": batch_status,
        "ready_for_reconcile": batch_status == "complete" and extra_row_count == 0,
        "next_steps": _next_steps(batch_status=batch_status, extra_row_count=extra_row_count),
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
    progress._reject_unsafe_payload(summary)
    return summary


def build_markdown(summary: Mapping[str, Any]) -> str:
    """Build a redacted Markdown preflight report.

    Args:
        summary: Batch file preflight summary.

    Returns:
        Markdown report text.
    """
    progress._reject_unsafe_payload(summary)
    reason_lines = "\n".join(
        f"- `{progress._safe_token(str(reason))}`: `{progress._non_negative_int(count)}`"
        for reason, count in sorted(_mapping(summary.get("reason_counts")).items())
    )
    next_steps = "\n".join(
        f"- `{progress._safe_token(str(step))}`" for step in _token_list(summary.get("next_steps"))
    )
    markdown = "\n".join(
        [
            "# Supplement Operator Review Batch File Preflight",
            "",
            f"Schema: `{SCHEMA_VERSION}`",
            "",
            "이 문서는 operator-local batch JSONL 1개가 reconcile 가능한지 aggregate count만 표시합니다.",
            "",
            f"- Batch: `{progress._safe_token(str(summary.get('batch_key')))}`",
            f"- Queue: `{progress._safe_token(str(summary.get('queue_key')))}`",
            f"- Status: `{progress._safe_token(str(summary.get('batch_status')))}`",
            f"- Ready for reconcile: `{_bool_text(summary.get('ready_for_reconcile'))}`",
            f"- Batch review CSV status: `{progress._safe_token(str(summary.get('batch_review_csv_status') or 'unknown'))}`",
            f"- Batch review CSV rows: `{progress._non_negative_int(summary.get('batch_review_csv_row_count'))}`",
            f"- Batch review CSV matches batch: `{_bool_text(summary.get('batch_review_csv_matches_batch'))}`",
            "",
            "## Counts",
            "",
            f"- Expected rows: `{progress._non_negative_int(summary.get('expected_row_count'))}`",
            f"- Actual rows: `{progress._non_negative_int(summary.get('actual_row_count'))}`",
            f"- Valid rows: `{progress._non_negative_int(summary.get('valid_row_count'))}`",
            f"- Blank rows: `{progress._non_negative_int(summary.get('blank_row_count'))}`",
            f"- Pending rows: `{progress._non_negative_int(summary.get('pending_row_count'))}`",
            f"- Invalid rows: `{progress._non_negative_int(summary.get('invalid_row_count'))}`",
            f"- Missing rows: `{progress._non_negative_int(summary.get('missing_row_count'))}`",
            f"- Extra rows: `{progress._non_negative_int(summary.get('extra_row_count'))}`",
            "",
            "## Reason Counts",
            "",
            reason_lines or "- none",
            "",
            "## Next Steps",
            "",
            next_steps,
            "",
            "## Rule",
            "",
            "이 preflight가 `complete`여도 reconcile 후 queue-level preflight와 downstream gate를 다시 실행해야 합니다.",
            "",
        ]
    )
    progress._reject_unsafe_payload(markdown)
    return markdown


def _review_csv_summary(
    *,
    queue_key: str,
    rows: list[dict[str, Any]],
    review_csv_path: Path | None,
) -> dict[str, Any]:
    """Validate optional operator-local review CSV context for a batch.

    Args:
        queue_key: Supported queue key.
        rows: Batch JSONL rows.
        review_csv_path: Optional batch review CSV path.

    Returns:
        Redacted CSV status summary.

    Raises:
        BatchFilePreflightError: If the CSV is unsupported or mismatched.
    """
    if review_csv_path is None:
        return {
            "batch_review_csv_name": None,
            "batch_review_csv_required": queue_key == "brand_product_review",
            "batch_review_csv_status": "not_provided",
            "batch_review_csv_row_count": 0,
            "batch_review_csv_matches_batch": False,
        }
    if queue_key != "brand_product_review":
        raise BatchFilePreflightError(
            "Batch review CSV is only supported for brand review batches."
        )
    csv_fixture_ids = _read_review_csv_fixture_ids(review_csv_path)
    batch_fixture_ids = [_safe_fixture_id(row.get("fixture_id")) for row in rows]
    if csv_fixture_ids != batch_fixture_ids:
        raise BatchFilePreflightError("Batch review CSV fixture order does not match batch JSONL.")
    return {
        "batch_review_csv_name": _safe_filename(review_csv_path.name),
        "batch_review_csv_required": True,
        "batch_review_csv_status": "matched",
        "batch_review_csv_row_count": len(csv_fixture_ids),
        "batch_review_csv_matches_batch": True,
    }


def _read_review_csv_fixture_ids(path: Path) -> list[str]:
    """Read fixture ids from a batch-local review CSV.

    Args:
        path: CSV path.

    Returns:
        Safe fixture id list in CSV order.

    Raises:
        BatchFilePreflightError: If the CSV is malformed or unsafe.
    """
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames
            if fieldnames is None or "fixture_id" not in fieldnames:
                raise BatchFilePreflightError("Batch review CSV requires fixture_id column.")
            _reject_unsafe_csv_columns(fieldnames)
            fixture_ids: list[str] = []
            for row in reader:
                _reject_unsafe_csv_row(row)
                fixture_ids.append(_safe_fixture_id(row.get("fixture_id")))
    except OSError as exc:
        raise BatchFilePreflightError("Batch review CSV is missing or unreadable.") from exc
    if not fixture_ids:
        raise BatchFilePreflightError("Batch review CSV is empty.")
    return fixture_ids


def _reject_unsafe_csv_columns(fieldnames: list[str]) -> None:
    """Reject raw/provider CSV column names.

    Args:
        fieldnames: CSV header names.
    """
    for fieldname in fieldnames:
        if fieldname.lower() in progress.RAW_FORBIDDEN_KEYS:
            raise BatchFilePreflightError("Unsafe raw/provider key found in review CSV.")


def _reject_unsafe_csv_row(row: Mapping[str, str | None]) -> None:
    """Reject local path markers in CSV values.

    Args:
        row: CSV row.
    """
    for value in row.values():
        if value and any(marker in value for marker in progress.LOCAL_PATH_MARKERS):
            raise BatchFilePreflightError("Unsafe local path marker found in review CSV.")


def _safe_fixture_id(value: object) -> str:
    """Return a safe fixture id.

    Args:
        value: Candidate fixture id.

    Returns:
        Safe fixture id.

    Raises:
        BatchFilePreflightError: If the value is blank.
    """
    safe = progress._safe_token(str(value or ""))
    if safe == "unknown":
        raise BatchFilePreflightError("Batch row requires fixture_id.")
    return safe


def _find_batch(plan: Mapping[str, Any], *, batch_key: str) -> Mapping[str, Any]:
    """Return one batch plan row by key.

    Args:
        plan: Parsed batch plan.
        batch_key: Safe batch key.

    Returns:
        Matching batch row.
    """
    for batch in progress._batch_rows(plan):
        if batch.get("batch_key") == batch_key:
            return batch
    raise BatchFilePreflightError("Requested batch key is not in the batch plan.")


def _required_input(input_paths: Mapping[str, Path], key: str) -> Path:
    """Return one required input path.

    Args:
        input_paths: Input path mapping.
        key: Required key.

    Returns:
        Existing path.
    """
    path = input_paths.get(key)
    if path is None or not path.is_file():
        raise BatchFilePreflightError("Required batch file preflight input is missing.")
    return path


def _mapping(value: Any) -> Mapping[str, Any]:
    """Return a mapping or fail closed.

    Args:
        value: Candidate mapping.

    Returns:
        Mapping value.
    """
    if not isinstance(value, Mapping):
        raise BatchFilePreflightError("Expected a mapping.")
    return value


def _token_list(value: Any) -> list[str]:
    """Return a safe token list.

    Args:
        value: Candidate token list.

    Returns:
        Token list.
    """
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise BatchFilePreflightError("Expected a token list.")
    return value


def _next_steps(*, batch_status: str, extra_row_count: int) -> list[str]:
    """Return next operator actions.

    Args:
        batch_status: Current aggregate batch status.
        extra_row_count: Extra rows beyond planned batch size.

    Returns:
        Safe step tokens.
    """
    if batch_status == "complete" and extra_row_count == 0:
        return [
            "run_reconcile_operator_batch_files",
            "run_operator_batch_progress_preflight",
            "run_queue_level_preflight",
        ]
    return [
        "finish_current_batch_edits",
        "keep_row_count_equal_to_batch_plan",
        "rerun_batch_file_preflight",
    ]


def _safe_filename(value: str) -> str:
    """Return a safe file name.

    Args:
        value: Candidate file name.

    Returns:
        Safe file name.
    """
    cleaned = value.strip()
    if (
        not cleaned
        or "/" in cleaned
        or "\\" in cleaned
        or any(marker in cleaned for marker in progress.LOCAL_PATH_MARKERS)
    ):
        raise BatchFilePreflightError("Unsafe file name.")
    return cleaned[:120]


def _bool_text(value: object) -> str:
    """Return lowercase boolean text.

    Args:
        value: Candidate boolean.

    Returns:
        ``true`` or ``false``.
    """
    return "true" if value is True else "false"


def _sha256_text(value: str) -> str:
    """Return SHA-256 digest for local artifact identity.

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
    progress._reject_unsafe_payload(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _cli_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Return compact CLI-safe summary.

    Args:
        summary: Full summary.

    Returns:
        CLI summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "batch_key": summary.get("batch_key"),
        "batch_status": summary.get("batch_status"),
        "ready_for_reconcile": summary.get("ready_for_reconcile"),
        "valid_row_count": progress._non_negative_int(summary.get("valid_row_count")),
        "blank_row_count": progress._non_negative_int(summary.get("blank_row_count")),
        "invalid_row_count": progress._non_negative_int(summary.get("invalid_row_count")),
        "missing_row_count": progress._non_negative_int(summary.get("missing_row_count")),
        "extra_row_count": progress._non_negative_int(summary.get("extra_row_count")),
        "db_write_performed": False,
    }


def _failure_summary(
    *,
    input_paths: Mapping[str, Path],
    batch_key: str,
    output_path: Path,
    error: Exception,
) -> dict[str, Any]:
    """Return a redacted failure summary.

    Args:
        input_paths: Input path mapping.
        batch_key: Requested batch key.
        output_path: Planned output path.
        error: Raised exception.

    Returns:
        Failure summary.
    """
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "batch_key": progress._safe_token(str(batch_key or "unknown")),
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_hashes": {
            key: _sha256_text(str(path.expanduser())) for key, path in sorted(input_paths.items())
        },
        "output_name": output_path.name,
        "output_hash": _sha256_text(str(output_path.expanduser())),
        "error_code": _safe_error_code(error),
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
    progress._reject_unsafe_payload(summary)
    return summary


def _safe_error_code(error: Exception) -> str:
    """Return a public error code.

    Args:
        error: Raised exception.

    Returns:
        Error code.
    """
    typed_codes = (
        (OSError, "local_file_error"),
        (json.JSONDecodeError, "json_decode_error"),
    )
    for error_type, code in typed_codes:
        if isinstance(error, error_type):
            return code
    text = str(error).casefold()
    text_codes = (
        ("unsafe", "unsafe_input"),
        ("schema", "unsupported_schema"),
        ("missing", "missing_input"),
        ("batch", "batch_plan_error"),
    )
    for marker, code in text_codes:
        if marker in text:
            return code
    return "validation_error"


if __name__ == "__main__":
    main()
