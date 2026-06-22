"""Build a redacted dependency audit for supplement learning milestones.

The audit connects current gate results to the operator review queue:

* product catalog DB import depends on brand/product review,
* OCR teacher benchmark depends on review-image PII screening,
* YOLO section dataset promotion depends on section annotation review.

It reads only redacted summary artifacts. It does not read source rows, source
images, OCR text, provider payloads, LLM outputs, or database records.

References:
    https://docs.python.org/3/library/argparse.html
    https://docs.python.org/3/library/json.html
    https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
    https://cloud.google.com/vision/docs/ocr
    https://api.ncloud-docs.com/docs/en/ai-application-service-ocr
    https://docs.ultralytics.com/datasets/detect/
    https://docs.ultralytics.com/tasks/detect/
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import build_supplement_ocr_benchmark_manifest as benchmark  # noqa: E402
from scripts import build_supplement_operator_next_batch_work_order as work_order  # noqa: E402
from scripts import gate_supplement_brand_db_import as brand_gate  # noqa: E402
from scripts import gate_supplement_ocr_benchmark as ocr_gate  # noqa: E402
from scripts import gate_supplement_yolo_section_dataset as yolo_gate  # noqa: E402
from scripts import (  # noqa: E402
    preflight_supplement_operator_review_batch_progress as progress_preflight,
)

SCHEMA_VERSION = "supplement-learning-dependency-audit-v1"
BATCH_PROGRESS_SCHEMA = progress_preflight.SCHEMA_VERSION
WORKPACK_SCHEMA = work_order.WORKPACK_SCHEMA
BRAND_GATE_SCHEMA = brand_gate.SCHEMA_VERSION
OCR_GATE_SCHEMA = ocr_gate.SCHEMA_VERSION
YOLO_GATE_SCHEMA = yolo_gate.SCHEMA_VERSION
QUEUE_KEYS = (
    "brand_product_review",
    "review_pii_screening",
    "yolo_section_annotation",
)
OUTCOME_SPECS = {
    "product_catalog_db_import": {
        "queue_key": "brand_product_review",
        "gate_input": "brand_db_import_gate",
        "allowed_key": "product_import_manifest_allowed",
        "status_key": "status",
        "blocked_status": "blocked_by_operator_review",
        "ready_status": "ready_for_product_import_manifest",
    },
    "ocr_teacher_benchmark": {
        "queue_key": "review_pii_screening",
        "gate_input": "ocr_benchmark_gate",
        "allowed_key": "teacher_ocr_benchmark_allowed",
        "status_key": "status",
        "blocked_status": "blocked_by_pii_screening",
        "ready_status": "ready_for_teacher_ocr_eval",
    },
    "yolo_section_dataset": {
        "queue_key": "yolo_section_annotation",
        "gate_input": "yolo_section_dataset_gate",
        "allowed_key": "section_yolo_training_allowed_now",
        "status_key": "status",
        "blocked_status": "blocked_by_missing_yolo_section_dataset_gate",
        "ready_status": "ready_for_section_yolo_training_dataset",
        "missing_gate_next_steps": (
            "run_yolo_annotation_preflight_require_all_reviewed",
            "run_yolo_template_promotion_after_strict_preflight",
            "materialize_and_validate_yolo_section_dataset",
            "run_yolo_section_dataset_gate",
        ),
    },
}
SOURCE_DOC_URLS = (
    "https://docs.python.org/3/library/argparse.html",
    "https://docs.python.org/3/library/json.html",
    "https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html",
    "https://cloud.google.com/vision/docs/ocr",
    "https://api.ncloud-docs.com/docs/en/ai-application-service-ocr",
    "https://docs.ultralytics.com/datasets/detect/",
    "https://docs.ultralytics.com/tasks/detect/",
)


class DependencyAuditError(ValueError):
    """Raised when a dependency audit input cannot be trusted."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-progress", type=Path, required=True)
    parser.add_argument("--workpack-summary", type=Path, required=True)
    parser.add_argument("--brand-db-import-gate", type=Path, required=True)
    parser.add_argument("--ocr-benchmark-gate", type=Path, required=True)
    parser.add_argument("--yolo-section-dataset-gate", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write a dependency audit JSON and optional Markdown report.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    input_paths = {
        "batch_progress": args.batch_progress.expanduser().resolve(),
        "workpack_summary": args.workpack_summary.expanduser().resolve(),
        "brand_db_import_gate": args.brand_db_import_gate.expanduser().resolve(),
        "ocr_benchmark_gate": args.ocr_benchmark_gate.expanduser().resolve(),
    }
    if args.yolo_section_dataset_gate is not None:
        input_paths["yolo_section_dataset_gate"] = (
            args.yolo_section_dataset_gate.expanduser().resolve()
        )
    output_path = args.output.expanduser().resolve()
    markdown_output = (
        args.markdown_output.expanduser().resolve() if args.markdown_output is not None else None
    )
    try:
        summary = build_dependency_audit(input_paths=input_paths)
        _write_json(output_path, summary)
        if markdown_output is not None:
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            markdown_output.write_text(build_markdown(summary), encoding="utf-8")
        print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    except (OSError, json.JSONDecodeError, DependencyAuditError, ValueError) as exc:
        failure = _failure_summary(input_paths=input_paths, output_path=output_path, error=exc)
        _write_json(output_path, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None


def build_dependency_audit(*, input_paths: Mapping[str, Path]) -> dict[str, Any]:
    """Build a redacted dependency audit from summary artifacts.

    Args:
        input_paths: Required summary artifact paths.

    Returns:
        Dependency audit summary.

    Raises:
        DependencyAuditError: If an input is missing, unsafe, or unsupported.
    """
    progress = _load_json_object(_required_input(input_paths, "batch_progress"))
    workpack = _load_json_object(_required_input(input_paths, "workpack_summary"))
    brand = _load_json_object(_required_input(input_paths, "brand_db_import_gate"))
    ocr = _load_json_object(_required_input(input_paths, "ocr_benchmark_gate"))
    yolo = (
        _load_json_object(input_paths["yolo_section_dataset_gate"])
        if input_paths.get("yolo_section_dataset_gate") is not None
        else None
    )
    _require_schema(progress, BATCH_PROGRESS_SCHEMA)
    _require_schema(workpack, WORKPACK_SCHEMA)
    _require_schema(brand, BRAND_GATE_SCHEMA)
    _require_schema(ocr, OCR_GATE_SCHEMA)
    if yolo is not None:
        _require_schema(yolo, YOLO_GATE_SCHEMA)
    for payload in (progress, workpack, brand, ocr, yolo):
        if payload is None:
            continue
        _reject_unsafe_payload(payload)
        _reject_unsafe_true_flags(payload)

    gate_payloads = {
        "brand_db_import_gate": brand,
        "ocr_benchmark_gate": ocr,
    }
    if yolo is not None:
        gate_payloads["yolo_section_dataset_gate"] = yolo
    outcomes = [
        _outcome_summary(
            outcome_key=outcome_key,
            spec=spec,
            progress=progress,
            workpack=workpack,
            gate_payloads=gate_payloads,
        )
        for outcome_key, spec in OUTCOME_SPECS.items()
    ]
    blocked_outcomes = [row["outcome_key"] for row in outcomes if row["allowed_now"] is not True]
    recommended_sequence = [
        row["next_batch"]["batch_key"]
        for row in outcomes
        if isinstance(row.get("next_batch"), Mapping)
    ]
    status = "ready" if not blocked_outcomes else "blocked_by_operator_review"
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_hashes": {
            key: progress_preflight._sha256_text(str(path.expanduser()))
            for key, path in sorted(input_paths.items())
        },
        "outcomes": outcomes,
        "blocked_outcomes": blocked_outcomes,
        "recommended_operator_sequence": recommended_sequence,
        "batch_count": _non_negative_int(progress.get("batch_count")),
        "complete_batch_count": _non_negative_int(progress.get("complete_batch_count")),
        "pending_batch_count": _non_negative_int(progress.get("pending_batch_count")),
        "invalid_batch_count": _non_negative_int(progress.get("invalid_batch_count")),
        "total_blank_row_count": _non_negative_int(progress.get("total_blank_row_count")),
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_rows_read": False,
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


def build_markdown(summary: Mapping[str, Any]) -> str:
    """Build a redacted Markdown dependency audit.

    Args:
        summary: Dependency audit summary.

    Returns:
        Markdown report.
    """
    _reject_unsafe_payload(summary)
    outcome_lines = []
    for row in _outcome_rows(summary):
        next_batch = row.get("next_batch")
        if isinstance(next_batch, Mapping):
            next_batch_text = (
                f"`{_safe_token(str(next_batch.get('batch_key') or 'unknown'))}` "
                f"({ _safe_filename(str(next_batch.get('workpack_file_name') or 'unknown.md')) })"
            )
        else:
            next_batch_text = "`none`"
        outcome_lines.append(
            "| {outcome} | {status} | {allowed} | {queue} | {batch} |".format(
                outcome=_safe_token(str(row.get("outcome_key") or "unknown")),
                status=_safe_token(str(row.get("gate_status") or "unknown")),
                allowed=_bool_text(row.get("allowed_now")),
                queue=_safe_token(str(row.get("blocking_queue_key") or "none")),
                batch=next_batch_text,
            )
        )
    sequence = _markdown_token_list(summary.get("recommended_operator_sequence"))
    markdown = "\n".join(
        [
            "# Supplement Learning Dependency Audit",
            "",
            f"Schema: `{SCHEMA_VERSION}`",
            "",
            "이 문서는 목표별 blocker와 다음 operator batch를 aggregate 수준에서 연결합니다. row id, 제품명, OCR 원문, provider payload, 이미지 경로, 로컬 경로를 포함하지 않습니다.",
            "",
            f"- Status: `{_safe_token(str(summary.get('status') or 'unknown'))}`",
            f"- Batch count: `{_non_negative_int(summary.get('batch_count'))}`",
            f"- Pending batch count: `{_non_negative_int(summary.get('pending_batch_count'))}`",
            f"- Total blank rows: `{_non_negative_int(summary.get('total_blank_row_count'))}`",
            "",
            "| Outcome | Gate status | Allowed now | Blocking queue | Next batch |",
            "| --- | --- | --- | --- | --- |",
            *outcome_lines,
            "",
            "## Recommended Operator Sequence",
            "",
            sequence,
            "",
            "## Rule",
            "",
            "1. 각 outcome의 다음 batch를 채운 뒤 reconcile과 queue-level preflight를 다시 실행합니다.",
            "2. DB import, teacher OCR benchmark, YOLO promotion, PaddleOCR training은 해당 gate가 explicit allow를 반환하기 전까지 실행하지 않습니다.",
            "",
        ]
    )
    _reject_unsafe_payload(markdown)
    return markdown


def _outcome_summary(
    *,
    outcome_key: str,
    spec: Mapping[str, Any],
    progress: Mapping[str, Any],
    workpack: Mapping[str, Any],
    gate_payloads: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Return one outcome dependency summary.

    Args:
        outcome_key: Stable outcome token.
        spec: Outcome spec.
        progress: Batch progress summary.
        workpack: Workpack summary.
        gate_payloads: Gate payloads keyed by input name.

    Returns:
        Redacted outcome summary.
    """
    queue_key = _queue_key(spec.get("queue_key"))
    gate_input = spec.get("gate_input")
    gate_payload = gate_payloads.get(str(gate_input)) if isinstance(gate_input, str) else None
    if isinstance(gate_input, str) and gate_payload is None:
        allowed_now = False
        gate_status = _safe_token(str(spec.get("blocked_status") or "gate_missing"))
        gate_next_steps = _safe_string_list(spec.get("missing_gate_next_steps"))
    elif gate_payload is None:
        allowed_now = _queue_complete(progress=progress, queue_key=queue_key)
        gate_status = str(spec["ready_status"] if allowed_now else spec["blocked_status"])
        gate_next_steps: list[str] = []
    else:
        allowed_now = gate_payload.get(str(spec.get("allowed_key"))) is True
        gate_status = _safe_token(str(gate_payload.get(str(spec.get("status_key"))) or "unknown"))
        gate_next_steps = _safe_string_list(gate_payload.get("next_steps"))
    next_batch = _next_queue_batch(progress=progress, workpack=workpack, queue_key=queue_key)
    if allowed_now and next_batch is None:
        blocker = "none"
    elif next_batch is None:
        blocker = "gate_followup"
    else:
        blocker = queue_key
    return {
        "outcome_key": _safe_token(outcome_key),
        "gate_status": gate_status,
        "allowed_now": allowed_now,
        "blocking_queue_key": blocker,
        "next_batch": next_batch,
        "gate_next_steps": gate_next_steps,
    }


def _next_queue_batch(
    *,
    progress: Mapping[str, Any],
    workpack: Mapping[str, Any],
    queue_key: str,
) -> dict[str, Any] | None:
    """Return the first incomplete batch for a queue.

    Args:
        progress: Batch progress summary.
        workpack: Workpack summary.
        queue_key: Queue key.

    Returns:
        Batch summary, or None when no pending batch exists.
    """
    for batch in _progress_batches(progress):
        if batch.get("queue_key") != queue_key or batch.get("batch_status") == "complete":
            continue
        batch_key = _safe_token(str(batch.get("batch_key") or "unknown"))
        workpack_row = _workpack_row(workpack=workpack, batch_key=batch_key)
        return {
            "batch_key": batch_key,
            "queue_key": queue_key,
            "batch_status": _safe_token(str(batch.get("batch_status") or "unknown")),
            "workpack_file_name": _safe_filename(
                str(workpack_row.get("workpack_file_name") or "unknown.md")
            ),
            "batch_file_name": _safe_filename(
                str(workpack_row.get("batch_file_name") or "unknown.jsonl")
            ),
            "source_editable_file_name": _safe_filename(
                str(workpack_row.get("source_editable_file_name") or "unknown.jsonl")
            ),
            "row_index_start": _positive_int(batch.get("row_index_start")),
            "row_index_end": _positive_int(batch.get("row_index_end")),
            "expected_row_count": _non_negative_int(batch.get("expected_row_count")),
            "valid_row_count": _non_negative_int(batch.get("valid_row_count")),
            "blank_row_count": _non_negative_int(batch.get("blank_row_count")),
            "pending_row_count": _non_negative_int(batch.get("pending_row_count")),
            "invalid_row_count": _non_negative_int(batch.get("invalid_row_count")),
            "missing_row_count": _non_negative_int(batch.get("missing_row_count")),
        }
    return None


def _queue_complete(*, progress: Mapping[str, Any], queue_key: str) -> bool:
    """Return whether every batch in a queue is complete.

    Args:
        progress: Batch progress summary.
        queue_key: Queue key.

    Returns:
        True when the queue has at least one batch and all are complete.
    """
    queue_batches = [
        batch for batch in _progress_batches(progress) if batch.get("queue_key") == queue_key
    ]
    return bool(queue_batches) and all(
        batch.get("batch_status") == "complete" for batch in queue_batches
    )


def _progress_batches(progress: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return progress batch rows.

    Args:
        progress: Batch progress summary.

    Returns:
        Batch rows.
    """
    batches = progress.get("batches")
    if not isinstance(batches, list) or not all(isinstance(row, Mapping) for row in batches):
        raise DependencyAuditError("Batch progress rows are missing.")
    return batches


def _workpack_row(*, workpack: Mapping[str, Any], batch_key: str) -> Mapping[str, Any]:
    """Return a workpack row by batch key.

    Args:
        workpack: Workpack summary.
        batch_key: Batch key.

    Returns:
        Workpack row.
    """
    rows = workpack.get("batch_workpacks")
    if not isinstance(rows, Sequence) or isinstance(rows, str):
        raise DependencyAuditError("Workpack rows are missing.")
    for row in rows:
        if isinstance(row, Mapping) and row.get("batch_key") == batch_key:
            return row
    raise DependencyAuditError("Workpack row for next batch is missing.")


def _load_json_object(path: Path) -> dict[str, Any]:
    """Load one JSON object.

    Args:
        path: JSON file path.

    Returns:
        Parsed JSON object.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DependencyAuditError("Dependency audit input must be a JSON object.")
    return payload


def _required_input(input_paths: Mapping[str, Path], key: str) -> Path:
    """Return a required input path.

    Args:
        input_paths: Input mapping.
        key: Required input key.

    Returns:
        Existing path.
    """
    path = input_paths.get(key)
    if path is None or not path.is_file():
        raise DependencyAuditError("Required dependency audit input is missing.")
    return path


def _require_schema(payload: Mapping[str, Any], expected_schema: str) -> None:
    """Validate one summary schema.

    Args:
        payload: Parsed input.
        expected_schema: Expected schema version.
    """
    if payload.get("schema_version") != expected_schema:
        raise DependencyAuditError("Dependency audit input schema does not match.")


def _outcome_rows(summary: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return outcome rows.

    Args:
        summary: Dependency audit summary.

    Returns:
        Outcome rows.
    """
    rows = summary.get("outcomes")
    if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
        raise DependencyAuditError("Dependency audit outcomes are missing.")
    return rows


def _safe_string_list(value: Any) -> list[str]:
    """Return safe string tokens.

    Args:
        value: Candidate list.

    Returns:
        Safe string list.
    """
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise DependencyAuditError("Expected a string list.")
    return [_safe_token(str(item)) for item in value]


def _markdown_token_list(value: Any) -> str:
    """Return Markdown bullets for safe tokens.

    Args:
        value: Candidate token list.

    Returns:
        Markdown bullet list.
    """
    tokens = _safe_string_list(value)
    if not tokens:
        return "- none"
    return "\n".join(f"- `{token}`" for token in tokens)


def _queue_key(value: Any) -> str:
    """Return a supported queue key.

    Args:
        value: Candidate queue key.

    Returns:
        Queue key.
    """
    queue_key = _safe_token(str(value or "unknown"))
    if queue_key not in QUEUE_KEYS:
        raise DependencyAuditError("Unsupported dependency queue key.")
    return queue_key


def _safe_token(value: str) -> str:
    """Return a safe token.

    Args:
        value: Candidate token.

    Returns:
        Safe token.
    """
    try:
        return progress_preflight._safe_token(value)
    except progress_preflight.BatchProgressError as exc:
        raise DependencyAuditError(str(exc)) from exc


def _safe_filename(value: str) -> str:
    """Return a safe filename.

    Args:
        value: Candidate filename.

    Returns:
        Safe filename.
    """
    try:
        return work_order._safe_filename(value)
    except work_order.WorkOrderError as exc:
        raise DependencyAuditError(str(exc)) from exc


def _positive_int(value: Any) -> int:
    """Return a positive integer.

    Args:
        value: Candidate integer.

    Returns:
        Positive integer.
    """
    try:
        return work_order._positive_int(value)
    except work_order.WorkOrderError as exc:
        raise DependencyAuditError(str(exc)) from exc


def _non_negative_int(value: Any) -> int:
    """Return a non-negative integer.

    Args:
        value: Candidate integer.

    Returns:
        Non-negative integer.
    """
    try:
        return work_order._non_negative_int(value)
    except work_order.WorkOrderError as exc:
        raise DependencyAuditError(str(exc)) from exc


def _bool_text(value: object) -> str:
    """Return lowercase boolean text.

    Args:
        value: Candidate boolean.

    Returns:
        ``true`` or ``false``.
    """
    return "true" if value is True else "false"


def _reject_unsafe_payload(value: Any) -> None:
    """Reject raw OCR/provider payloads and local path literals.

    Args:
        value: Candidate JSON-like payload.
    """
    try:
        benchmark._reject_unsafe_payload(value)
    except ValueError as exc:
        raise DependencyAuditError(str(exc)) from exc


def _reject_unsafe_true_flags(payload: Mapping[str, Any]) -> None:
    """Reject execution flags set to true.

    Args:
        payload: Parsed summary payload.
    """
    unsafe_flags = (
        "db_write_performed",
        "ocr_provider_call_performed",
        "external_provider_call_performed",
        "llm_call_performed",
        "training_execution_performed_by_script",
        "source_rows_read",
        "source_image_read_performed",
        "paddleocr_training_performed",
        "raw_ocr_text_stored",
        "raw_provider_payload_stored",
        "absolute_paths_stored",
        "product_dir_literals_stored",
        "local_path_literals_stored",
    )
    for key in unsafe_flags:
        if payload.get(key) is True:
            raise DependencyAuditError("Dependency audit input has an unsafe true flag.")


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
        summary: Dependency audit summary.

    Returns:
        CLI summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": summary["status"],
        "blocked_outcomes": summary["blocked_outcomes"],
        "recommended_operator_sequence": summary["recommended_operator_sequence"],
        "pending_batch_count": summary["pending_batch_count"],
        "total_blank_row_count": summary["total_blank_row_count"],
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
        Redacted failure payload.
    """
    _ = error
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "output_name": output_path.name,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_rows_read": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


if __name__ == "__main__":
    main()
