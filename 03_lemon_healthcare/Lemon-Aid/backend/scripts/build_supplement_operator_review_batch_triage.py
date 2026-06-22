"""Build a redacted triage report for one supplement operator JSONL batch.

This helper ranks PII-screening and YOLO-section annotation batch rows by
review urgency. It never exposes fixture ids, image paths, source refs, bbox
coordinates, OCR text, provider payloads, or product folder literals. The
output is for human review ordering only; it does not approve rows, run OCR,
call external providers, train models, or write database state.

References:
    https://docs.python.org/3/library/argparse.html
    https://docs.python.org/3/library/json.html
    https://www.postgresql.org/docs/current/ddl-constraints.html
    https://supabase.com/docs/guides/database/postgres/row-level-security
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
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

SCHEMA_VERSION = "supplement-operator-review-batch-triage-v1"
MARKDOWN_SCHEMA_VERSION = "supplement-operator-review-batch-triage-markdown-v1"
SUPPORTED_QUEUE_KEYS = frozenset({"review_pii_screening", "yolo_section_annotation"})
SOURCE_DOC_URLS = progress.SOURCE_DOC_URLS
PUBLIC_FORBIDDEN_MARKERS = (
    "fixture_id",
    "image_path",
    "image_ref_hash",
    "image_sha256",
    "source_ref",
    "source_product_id",
    "label_snapshot",
    "x_center",
    "y_center",
    "width",
    "height",
)


class OperatorReviewBatchTriageError(ValueError):
    """Raised when an operator review batch cannot be triaged safely."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-key", required=True)
    parser.add_argument("--batch-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, default=None)
    parser.add_argument("--max-row-hints", type=int, default=25)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write a redacted operator batch triage report.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    input_paths = {"batch_file": args.batch_file.expanduser().resolve()}
    output_path = args.output.expanduser().resolve()
    markdown_output = (
        args.markdown_output.expanduser().resolve() if args.markdown_output is not None else None
    )
    try:
        summary = build_operator_review_batch_triage(
            queue_key=args.queue_key,
            input_paths=input_paths,
            max_row_hints=args.max_row_hints,
        )
        _write_json(output_path, summary)
        if markdown_output is not None:
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            markdown_output.write_text(build_markdown(summary), encoding="utf-8")
        print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    except (OSError, json.JSONDecodeError, OperatorReviewBatchTriageError, ValueError) as exc:
        failure = _failure_summary(input_paths=input_paths, output_path=output_path, error=exc)
        _write_json(output_path, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None


def build_operator_review_batch_triage(
    *,
    queue_key: str,
    input_paths: Mapping[str, Path],
    max_row_hints: int = 25,
) -> dict[str, Any]:
    """Return a redacted triage summary for one operator JSONL batch.

    Args:
        queue_key: Supported operator queue key.
        input_paths: Mapping containing ``batch_file``.
        max_row_hints: Maximum redacted row-index hints to include.

    Returns:
        Aggregate triage summary.

    Raises:
        OperatorReviewBatchTriageError: If the batch is malformed or unsafe.
    """
    safe_queue_key = _queue_key(queue_key)
    if max_row_hints < 0:
        raise OperatorReviewBatchTriageError("max_row_hints must be nonnegative.")
    batch_file = _required_input(input_paths, "batch_file")
    rows = progress._read_jsonl(path=batch_file)
    if not rows:
        raise OperatorReviewBatchTriageError("Operator batch JSONL is empty.")
    row_summaries = [
        _row_triage(queue_key=safe_queue_key, rows=rows, row_index=index)
        for index in range(1, len(rows) + 1)
    ]
    status_counts = Counter(item["status"] for item in row_summaries)
    priority_counts = Counter(item["priority"] for item in row_summaries)
    reason_counts = Counter(item["reason_code"] for item in row_summaries)
    row_hints = [
        {
            "row_index": item["row_index"],
            "priority": item["priority"],
            "reason_code": item["reason_code"],
        }
        for item in sorted(row_summaries, key=_row_hint_sort_key)
        if item["priority"] != "p4_reviewed"
    ][:max_row_hints]
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "queue_key": safe_queue_key,
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_hashes": {
            key: _sha256_text(str(path.expanduser())) for key, path in sorted(input_paths.items())
        },
        "batch_file_name": _safe_filename(batch_file.name),
        "row_count": len(rows),
        "valid_row_count": status_counts.get("valid", 0),
        "blank_row_count": status_counts.get("blank", 0),
        "pending_row_count": status_counts.get("pending", 0),
        "invalid_row_count": status_counts.get("invalid", 0),
        "missing_row_count": status_counts.get("missing", 0),
        "status_counts": dict(sorted(status_counts.items())),
        "priority_counts": dict(sorted(priority_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "row_hints_truncated": len(row_hints)
        < sum(1 for item in row_summaries if item["priority"] != "p4_reviewed"),
        "row_hints": row_hints,
        "operator_next_steps": _operator_next_steps(
            queue_key=safe_queue_key,
            status_counts=status_counts,
            reason_counts=reason_counts,
        ),
        "automatic_decision_performed": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "ocr_provider_call_performed": False,
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
    _reject_public_payload(summary)
    return summary


def build_markdown(summary: Mapping[str, Any]) -> str:
    """Build a redacted Markdown triage report.

    Args:
        summary: Triage summary.

    Returns:
        Markdown report.
    """
    _reject_public_payload(summary)
    markdown = "\n".join(
        [
            "# Supplement Operator Review Batch Triage",
            "",
            f"Schema: `{MARKDOWN_SCHEMA_VERSION}`",
            "",
            "이 문서는 operator JSONL batch의 검토 우선순위만 표시합니다.",
            "fixture id, 이미지 경로, source ref, bbox 좌표, OCR 원문, provider payload는 포함하지 않습니다.",
            "",
            "## Batch",
            "",
            f"- Queue: `{_safe_token(str(summary.get('queue_key') or 'unknown'))}`",
            f"- File: `{_safe_filename(str(summary.get('batch_file_name') or 'unknown.jsonl'))}`",
            f"- Rows: `{_non_negative_int(summary.get('row_count'))}`",
            f"- Valid rows: `{_non_negative_int(summary.get('valid_row_count'))}`",
            f"- Blank rows: `{_non_negative_int(summary.get('blank_row_count'))}`",
            f"- Pending rows: `{_non_negative_int(summary.get('pending_row_count'))}`",
            f"- Invalid rows: `{_non_negative_int(summary.get('invalid_row_count'))}`",
            "",
            "## Priority Counts",
            "",
            _markdown_mapping(summary.get("priority_counts")),
            "",
            "## Reason Counts",
            "",
            _markdown_mapping(summary.get("reason_counts")),
            "",
            "## Row Hints",
            "",
            _markdown_row_hints(summary.get("row_hints")),
            "",
            "## Next Steps",
            "",
            _markdown_list(summary.get("operator_next_steps")),
            "",
            "## Rule",
            "",
            "이 triage는 수동 검토 순서만 제안합니다. PII clearance, teacher OCR, YOLO dataset promotion, training은 별도 gate를 통과해야 합니다.",
            "",
        ]
    )
    _reject_public_payload(markdown)
    return markdown


def _row_triage(
    *,
    queue_key: str,
    rows: list[dict[str, Any]],
    row_index: int,
) -> dict[str, Any]:
    """Return redacted triage facts for one JSONL row.

    Args:
        queue_key: Supported queue key.
        rows: Parsed batch rows.
        row_index: One-based row index.

    Returns:
        Row triage dictionary with no payload fields.
    """
    status = progress._status_for_index(queue_key=queue_key, rows=rows, row_index=row_index)
    priority = _priority(queue_key=queue_key, status=status.status, reason_code=status.reason_code)
    return {
        "row_index": row_index,
        "status": _safe_token(status.status),
        "priority": priority,
        "reason_code": _safe_token(status.reason_code),
    }


def _priority(*, queue_key: str, status: str, reason_code: str) -> str:
    """Return a review priority token.

    Args:
        queue_key: Supported queue key.
        status: Row validation status.
        reason_code: Row validation reason code.

    Returns:
        Priority token.
    """
    if status in {"invalid", "missing"}:
        return "p0_fix_invalid_row"
    if status == "pending":
        return "p1_complete_pending_review"
    if status == "blank" and queue_key == "review_pii_screening":
        return "p2_privacy_screening_required"
    if status == "blank" and queue_key == "yolo_section_annotation":
        return "p2_bbox_annotation_required"
    if reason_code in {"valid_decision", "valid_annotation"}:
        return "p4_reviewed"
    return "p3_standard_review"


def _row_hint_sort_key(item: Mapping[str, Any]) -> tuple[int, int]:
    """Sort row hints by priority then row index.

    Args:
        item: Row triage item.

    Returns:
        Sort key.
    """
    rank = {
        "p0_fix_invalid_row": 0,
        "p1_complete_pending_review": 1,
        "p2_privacy_screening_required": 2,
        "p2_bbox_annotation_required": 2,
        "p3_standard_review": 3,
        "p4_reviewed": 4,
    }
    return (rank.get(str(item.get("priority")), 9), _non_negative_int(item.get("row_index")))


def _operator_next_steps(
    *,
    queue_key: str,
    status_counts: Mapping[str, int],
    reason_counts: Mapping[str, int],
) -> list[str]:
    """Return aggregate operator next-step tokens.

    Args:
        queue_key: Supported queue key.
        status_counts: Status count mapping.
        reason_counts: Reason count mapping.

    Returns:
        Safe next-step tokens.
    """
    steps: list[str] = []
    if status_counts.get("invalid", 0) or status_counts.get("missing", 0):
        steps.append("fix_invalid_or_missing_rows_before_reconcile")
    if reason_counts.get("boxes_not_accepted", 0):
        steps.append("accept_or_reject_existing_bbox_rows")
    if reason_counts.get("blank_boxes", 0):
        steps.append("draw_section_bboxes_or_mark_rejected")
    if reason_counts.get("blank_decision", 0):
        steps.append("complete_blank_privacy_decisions")
    if queue_key == "review_pii_screening":
        steps.extend(
            [
                "run_batch_file_preflight_before_reconcile",
                "run_strict_pii_preflight_before_teacher_ocr",
            ]
        )
    elif queue_key == "yolo_section_annotation":
        steps.extend(
            [
                "run_batch_file_preflight_before_reconcile",
                "run_strict_yolo_preflight_before_dataset_materialization",
            ]
        )
    return steps


def _queue_key(value: str) -> str:
    """Return a supported queue key.

    Args:
        value: Candidate queue key.

    Returns:
        Safe supported queue key.
    """
    queue_key = _safe_token(value)
    if queue_key not in SUPPORTED_QUEUE_KEYS:
        raise OperatorReviewBatchTriageError("Unsupported operator triage queue key.")
    return queue_key


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
        raise OperatorReviewBatchTriageError("Required operator triage input is missing.")
    return path


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write one JSON object.

    Args:
        path: Destination path.
        payload: JSON payload.
    """
    _reject_public_payload(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _cli_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Return a compact CLI-safe summary.

    Args:
        summary: Full summary.

    Returns:
        CLI summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "queue_key": _safe_token(str(summary.get("queue_key") or "unknown")),
        "row_count": _non_negative_int(summary.get("row_count")),
        "blank_row_count": _non_negative_int(summary.get("blank_row_count")),
        "pending_row_count": _non_negative_int(summary.get("pending_row_count")),
        "invalid_row_count": _non_negative_int(summary.get("invalid_row_count")),
        "priority_counts": summary.get("priority_counts"),
        "db_write_performed": False,
    }


def _failure_summary(
    *,
    input_paths: Mapping[str, Path],
    output_path: Path,
    error: Exception,
) -> dict[str, Any]:
    """Return a redacted failure summary.

    Args:
        input_paths: Input path mapping.
        output_path: Planned output path.
        error: Raised exception.

    Returns:
        Failure summary.
    """
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
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
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_public_payload(summary)
    return summary


def _reject_public_payload(value: Any) -> None:
    """Reject unsafe public output payloads.

    Args:
        value: JSON-like value or Markdown text.
    """
    try:
        progress._reject_unsafe_payload(value)
    except ValueError as exc:
        raise OperatorReviewBatchTriageError(str(exc)) from exc
    dumped = (
        json.dumps(value, ensure_ascii=False, sort_keys=True)
        if not isinstance(value, str)
        else value
    )
    if any(marker in dumped for marker in PUBLIC_FORBIDDEN_MARKERS):
        raise OperatorReviewBatchTriageError("Public triage payload contains private row fields.")


def _markdown_mapping(value: Any) -> str:
    """Return a Markdown mapping list.

    Args:
        value: Candidate mapping.

    Returns:
        Markdown bullet list.
    """
    if not isinstance(value, Mapping) or not value:
        return "- none"
    return "\n".join(
        f"- `{_safe_token(str(key))}`: `{_non_negative_int(item)}`"
        for key, item in sorted(value.items())
    )


def _markdown_row_hints(value: Any) -> str:
    """Return redacted row-index hints as Markdown.

    Args:
        value: Candidate row hint list.

    Returns:
        Markdown bullet list.
    """
    if not isinstance(value, list) or not value:
        return "- none"
    lines = []
    for item in value:
        if not isinstance(item, Mapping):
            raise OperatorReviewBatchTriageError("Expected row hint mapping.")
        lines.append(
            f"- row `{_non_negative_int(item.get('row_index'))}`: "
            f"`{_safe_token(str(item.get('priority') or 'unknown'))}` "
            f"(`{_safe_token(str(item.get('reason_code') or 'unknown'))}`)"
        )
    return "\n".join(lines)


def _markdown_list(value: Any) -> str:
    """Return a Markdown token list.

    Args:
        value: Candidate token list.

    Returns:
        Markdown bullet list.
    """
    if not isinstance(value, list) or not value:
        return "- none"
    return "\n".join(f"- `{_safe_token(str(item))}`" for item in value)


def _safe_token(value: str) -> str:
    """Return a safe token.

    Args:
        value: Candidate token.

    Returns:
        Safe token.
    """
    try:
        return progress._safe_token(value)
    except ValueError as exc:
        raise OperatorReviewBatchTriageError(str(exc)) from exc


def _safe_filename(value: str) -> str:
    """Return a safe filename.

    Args:
        value: Candidate filename.

    Returns:
        Safe filename.
    """
    if "/" in value or "\\" in value:
        raise OperatorReviewBatchTriageError("Unsafe filename contains a path marker.")
    return value[:200]


def _non_negative_int(value: Any) -> int:
    """Return a non-negative integer.

    Args:
        value: Candidate value.

    Returns:
        Integer or zero.
    """
    return progress._non_negative_int(value)


def _sha256_text(value: str) -> str:
    """Return SHA-256 digest for local artifact identity.

    Args:
        value: Text value.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_error_code(error: Exception) -> str:
    """Return a public error code.

    Args:
        error: Raised exception.

    Returns:
        Error code.
    """
    text = str(error).casefold()
    if "unsupported" in text:
        return "unsupported_queue"
    if "unsafe" in text:
        return "unsafe_input"
    if "missing" in text:
        return "missing_input"
    if "empty" in text:
        return "empty_input"
    return "validation_error"


if __name__ == "__main__":
    main()
