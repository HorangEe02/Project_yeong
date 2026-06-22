"""Build a redacted next-batch work order for supplement operator review.

This tool combines three already-redacted artifacts:

1. learning pipeline readiness report,
2. operator review batch progress preflight,
3. operator review workpack summary.

It selects the next incomplete batch and writes a single work order. It never
reads decision JSONL row payloads, source images, OCR text, provider payloads,
LLM outputs, or database records.
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
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from scripts import (  # noqa: E402
    build_supplement_learning_pipeline_readiness_report as readiness_reporter,
)
from scripts import build_supplement_operator_review_workpack as workpack_builder  # noqa: E402
from scripts import (  # noqa: E402
    preflight_supplement_operator_review_batch_progress as progress_preflight,
)

SCHEMA_VERSION = "supplement-operator-review-next-work-order-v1"
READINESS_SCHEMA = "supplement-learning-pipeline-readiness-v1"
WORKPACK_SCHEMA = "supplement-operator-review-workpack-v1"
BATCH_PROGRESS_SCHEMA = "supplement-operator-review-batch-progress-preflight-v1"
TRIAGE_SCHEMAS = frozenset(
    {
        "supplement-brand-review-batch-triage-v1",
        "supplement-operator-review-batch-triage-v1",
    }
)
QUEUE_STAGE_KEYS = {
    "brand_product_review": "brand_product_review",
    "review_pii_screening": "review_pii_screening",
    "yolo_section_annotation": "yolo_section_annotation",
}
QUEUE_POST_COMPLETION_GATES = {
    "brand_product_review": (
        "preflight_contact_sheet_before_csv_apply",
        "triage_review_csv_before_apply",
        "apply_review_csv_only_with_require_all_reviewed",
        "preflight_applied_batch_before_reconcile",
        "reconcile_operator_batch_files",
        "rerun_operator_batch_progress_preflight",
        "extract_reviewed_brand_decisions_for_partial_manifest_preview",
        "rerun_brand_decision_preflight",
        "create_approved_product_import_only_after_blank_invalid_counts_are_zero",
    ),
    "review_pii_screening": (
        "reconcile_operator_batch_files",
        "rerun_operator_batch_progress_preflight",
        "extract_reviewed_pii_decisions_for_partial_teacher_ocr_preview",
        "rerun_pii_decision_preflight",
        "apply_pii_screening_decisions_only_after_blank_invalid_counts_are_zero",
    ),
    "yolo_section_annotation": (
        "reconcile_operator_batch_files",
        "rerun_operator_batch_progress_preflight",
        "extract_reviewed_yolo_annotations_for_partial_dataset_preview",
        "rerun_yolo_annotation_preflight",
        "promote_yolo_templates_only_after_blank_pending_invalid_counts_are_zero",
    ),
}


class WorkOrderError(ValueError):
    """Raised when a next-batch work order cannot be trusted."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readiness", type=Path, required=True)
    parser.add_argument("--batch-progress", type=Path, required=True)
    parser.add_argument("--workpack-summary", type=Path, required=True)
    parser.add_argument("--batch-triage", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write the next-batch work order.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    input_paths = {
        "readiness": args.readiness.expanduser().resolve(),
        "batch_progress": args.batch_progress.expanduser().resolve(),
        "workpack_summary": args.workpack_summary.expanduser().resolve(),
    }
    if args.batch_triage is not None:
        input_paths["batch_triage"] = args.batch_triage.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    markdown_output = (
        args.markdown_output.expanduser().resolve() if args.markdown_output is not None else None
    )
    try:
        summary = build_next_batch_work_order(input_paths=input_paths)
        _write_json(output_path, summary)
        if markdown_output is not None:
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            markdown_output.write_text(build_work_order_markdown(summary), encoding="utf-8")
        print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    except (OSError, json.JSONDecodeError, WorkOrderError) as exc:
        failure = _failure_summary(input_paths=input_paths, output_path=output_path, error=exc)
        _write_json(output_path, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None


def build_next_batch_work_order(*, input_paths: Mapping[str, Path]) -> dict[str, Any]:
    """Build a redacted work order for the next incomplete review batch.

    Args:
        input_paths: Paths to readiness, progress, and workpack summary JSON.

    Returns:
        Work order summary.
    """
    readiness = _load_json_object(_required_input(input_paths, "readiness"))
    progress = _load_json_object(_required_input(input_paths, "batch_progress"))
    workpack = _load_json_object(_required_input(input_paths, "workpack_summary"))
    _require_schema(readiness, READINESS_SCHEMA)
    _require_schema(progress, BATCH_PROGRESS_SCHEMA)
    _require_schema(workpack, WORKPACK_SCHEMA)
    _reject_unsafe_payload(readiness)
    _reject_unsafe_payload(progress)
    _reject_unsafe_payload(workpack)

    next_batch_key = _next_batch_key(progress=progress, workpack=workpack)
    progress_row = _progress_row(progress=progress, batch_key=next_batch_key)
    workpack_row = _workpack_row(workpack=workpack, batch_key=next_batch_key)
    queue_key = _same_token(
        "queue_key",
        str(progress_row.get("queue_key") or ""),
        str(workpack_row.get("queue_key") or ""),
    )
    if queue_key not in QUEUE_STAGE_KEYS:
        raise WorkOrderError("Unsupported queue key in next batch.")
    _assert_same_range(progress_row=progress_row, workpack_row=workpack_row)
    stage = _stage_for_queue(readiness=readiness, queue_key=queue_key)
    batch_status = _safe_token(str(progress_row.get("batch_status") or "unknown"))
    status = "pending_operator_review" if batch_status != "complete" else "complete"
    reason_counts = _safe_mapping(progress_row.get("reason_counts"))
    triage_summary = _optional_triage_summary(input_paths=input_paths, queue_key=queue_key)
    blank_row_count = _non_negative_int(progress_row.get("blank_row_count"))
    pending_row_count = _non_negative_int(progress_row.get("pending_row_count"))
    invalid_row_count = _non_negative_int(progress_row.get("invalid_row_count"))
    missing_row_count = _non_negative_int(progress_row.get("missing_row_count"))
    stage_next_operator_action = _safe_token(str(stage.get("next_operator_action") or "unknown"))
    operator_next_action = _operator_next_action(
        queue_key=queue_key,
        blank_row_count=blank_row_count,
        pending_row_count=pending_row_count,
        invalid_row_count=invalid_row_count,
        missing_row_count=missing_row_count,
        fallback_action=stage_next_operator_action,
    )

    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_fingerprints": {
            key: _path_fingerprint(path) for key, path in sorted(input_paths.items())
        },
        "batch_key": next_batch_key,
        "queue_key": queue_key,
        "stage_key": QUEUE_STAGE_KEYS[queue_key],
        "stage_status": _safe_token(str(stage.get("status") or "unknown")),
        "stage_next_operator_action": stage_next_operator_action,
        "operator_next_action": operator_next_action,
        "batch_status": batch_status,
        "workpack_file_name": _safe_filename(str(workpack_row.get("workpack_file_name") or "")),
        "batch_file_name": _safe_filename(str(workpack_row.get("batch_file_name") or "")),
        "batch_review_file_name": _optional_safe_filename(
            workpack_row.get("batch_review_file_name")
        ),
        "source_editable_file_name": _safe_filename(
            str(workpack_row.get("source_editable_file_name") or "")
        ),
        "bundle_file_names": _safe_string_list(workpack_row.get("bundle_file_names")),
        "contact_sheet_available": workpack_row.get("contact_sheet_available") is True,
        "contact_sheet_dir_name": _optional_safe_filename(
            workpack_row.get("contact_sheet_dir_name")
        ),
        "contact_sheet_file_names": _safe_string_list(workpack_row.get("contact_sheet_file_names")),
        "contact_sheet_reviewable_row_count": _optional_non_negative_int(
            workpack_row.get("contact_sheet_reviewable_row_count")
        ),
        "contact_sheet_rows_with_thumbnails": _optional_non_negative_int(
            workpack_row.get("contact_sheet_rows_with_thumbnails")
        ),
        "contact_sheet_rows_without_thumbnails": _optional_non_negative_int(
            workpack_row.get("contact_sheet_rows_without_thumbnails")
        ),
        "contact_sheet_thumbnail_count": _optional_non_negative_int(
            workpack_row.get("contact_sheet_thumbnail_count")
        ),
        "operator_checklist": _safe_string_list(workpack_row.get("operator_checklist")),
        "post_completion_gates": list(QUEUE_POST_COMPLETION_GATES[queue_key]),
        "row_index_start": _positive_int(progress_row.get("row_index_start")),
        "row_index_end": _positive_int(progress_row.get("row_index_end")),
        "expected_row_count": _non_negative_int(progress_row.get("expected_row_count")),
        "valid_row_count": _non_negative_int(progress_row.get("valid_row_count")),
        "blank_row_count": blank_row_count,
        "pending_row_count": pending_row_count,
        "invalid_row_count": invalid_row_count,
        "missing_row_count": missing_row_count,
        "reason_counts": reason_counts,
        "triage_summary": triage_summary,
        "all_batches_complete": progress.get("all_batches_complete") is True,
        "total_blank_row_count": _non_negative_int(progress.get("total_blank_row_count")),
        "source_rows_read": False,
        "source_image_read_performed": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def build_work_order_markdown(summary: Mapping[str, Any]) -> str:
    """Build a redacted Markdown work order.

    Args:
        summary: Work order summary.

    Returns:
        Markdown text.
    """
    _reject_unsafe_payload(summary)
    bundle_files = _markdown_bullets(summary.get("bundle_file_names"))
    contact_sheet = _contact_sheet_markdown(summary)
    checklist = _markdown_bullets(summary.get("operator_checklist"))
    gates = _markdown_bullets(summary.get("post_completion_gates"))
    reason_counts = _markdown_mapping(summary.get("reason_counts"))
    triage = _triage_markdown(summary.get("triage_summary"))
    batch_review_line = _optional_batch_review_markdown_line(summary.get("batch_review_file_name"))
    markdown = "\n".join(
        [
            "# Supplement Operator Review Next Batch Work Order",
            "",
            f"Schema: `{SCHEMA_VERSION}`",
            "",
            "이 문서는 다음 수동 검수 batch의 redacted 작업 지시서입니다. row id, 제품명, OCR 원문, provider payload, 이미지 경로, source ref, 로컬 경로를 포함하지 않습니다.",
            "",
            "## Next Batch",
            "",
            f"- Batch: `{_safe_token(str(summary.get('batch_key') or 'unknown'))}`",
            f"- Queue: `{_safe_token(str(summary.get('queue_key') or 'unknown'))}`",
            f"- Stage: `{_safe_token(str(summary.get('stage_key') or 'unknown'))}`",
            f"- Stage status: `{_safe_token(str(summary.get('stage_status') or 'unknown'))}`",
            f"- Operator next action: `{_safe_token(str(summary.get('operator_next_action') or 'unknown'))}`",
            f"- Batch status: `{_safe_token(str(summary.get('batch_status') or 'unknown'))}`",
            f"- Workpack guide: `{_safe_filename(str(summary.get('workpack_file_name') or ''))}`",
            f"- Batch JSONL: `{_safe_filename(str(summary.get('batch_file_name') or ''))}`",
            batch_review_line,
            f"- Source editable file: `{_safe_filename(str(summary.get('source_editable_file_name') or ''))}`",
            f"- Row range: `{_positive_int(summary.get('row_index_start'))}-{_positive_int(summary.get('row_index_end'))}`",
            "",
            "## Progress",
            "",
            f"- Expected rows: `{_non_negative_int(summary.get('expected_row_count'))}`",
            f"- Valid rows: `{_non_negative_int(summary.get('valid_row_count'))}`",
            f"- Blank rows: `{_non_negative_int(summary.get('blank_row_count'))}`",
            f"- Pending rows: `{_non_negative_int(summary.get('pending_row_count'))}`",
            f"- Invalid rows: `{_non_negative_int(summary.get('invalid_row_count'))}`",
            f"- Missing rows: `{_non_negative_int(summary.get('missing_row_count'))}`",
            f"- Total blank rows across queues: `{_non_negative_int(summary.get('total_blank_row_count'))}`",
            "",
            "## Reason Counts",
            "",
            reason_counts,
            "",
            "## Batch Triage",
            "",
            triage,
            "",
            "## Source Bundle Files",
            "",
            bundle_files,
            "",
            "## Visual Review Contact Sheet",
            "",
            contact_sheet,
            "",
            "## Checklist",
            "",
            checklist,
            "",
            "## Post Completion Gates",
            "",
            gates,
            "",
            "## Rule",
            "",
            "preflight 통과 전에는 DB apply, teacher OCR transfer, YOLO dataset promotion, PaddleOCR 학습을 진행하지 않습니다.",
            "",
        ]
    )
    _reject_unsafe_payload(markdown)
    return markdown


def _path_fingerprint(path: Path) -> str:
    """Return a short non-secret path fingerprint for public artifacts.

    Args:
        path: Path to identify without exposing it.

    Returns:
        Short hexadecimal fingerprint with a non-hex prefix.
    """
    return f"fp-{progress_preflight._sha256_text(str(path.expanduser()))[:8]}"


def _operator_next_action(
    *,
    queue_key: str,
    blank_row_count: int,
    pending_row_count: int,
    invalid_row_count: int,
    missing_row_count: int,
    fallback_action: str,
) -> str:
    """Choose the next human action from current batch progress.

    Args:
        queue_key: Current operator queue key.
        blank_row_count: Rows still untouched in the selected batch.
        pending_row_count: Rows that remain pending after parsing.
        invalid_row_count: Rows with invalid decisions or annotations.
        missing_row_count: Expected rows absent from the editable file.
        fallback_action: Safe readiness-reported action for fully complete
            batches.

    Returns:
        Safe next action token.
    """
    if invalid_row_count > 0:
        return "fix_invalid_operator_review_rows"
    if missing_row_count > 0:
        return "restore_missing_operator_review_rows"
    if blank_row_count > 0:
        return {
            "brand_product_review": "complete_brand_product_human_review",
            "review_pii_screening": "complete_blank_privacy_decisions",
            "yolo_section_annotation": "complete_blank_yolo_section_annotations",
        }.get(queue_key, "complete_blank_operator_review_rows")
    if pending_row_count > 0:
        return "complete_pending_operator_review_rows"
    return fallback_action or "run_queue_preflight"


def _optional_batch_review_markdown_line(value: Any) -> str:
    """Return a Markdown line for an optional batch review CSV.

    Args:
        value: Candidate file name.

    Returns:
        Markdown line.
    """
    safe = _optional_safe_filename(value)
    if safe is None:
        return "- Batch review CSV: `none`"
    return f"- Batch review CSV: `{safe}`"


def _optional_triage_summary(*, input_paths: Mapping[str, Path], queue_key: str) -> dict[str, Any]:
    """Return a safe triage summary for the selected next batch.

    Args:
        input_paths: Input path mapping.
        queue_key: Selected next queue key.

    Returns:
        Triage summary, or an empty mapping when no triage input is present.
    """
    path = input_paths.get("batch_triage")
    if path is None:
        return {}
    if not path.is_file():
        raise WorkOrderError("Batch triage input artifact is missing.")
    payload = _load_json_object(path)
    schema_version = str(payload.get("schema_version") or "")
    if schema_version not in TRIAGE_SCHEMAS:
        raise WorkOrderError("Batch triage schema version does not match.")
    _reject_unsafe_payload(payload)
    triage_queue_key = _triage_queue_key(payload=payload, fallback_file_name=path.name)
    if triage_queue_key != queue_key:
        raise WorkOrderError("Batch triage queue does not match next batch.")
    return {
        "input_name": _safe_filename(path.name),
        "schema_version": _safe_token(schema_version),
        "queue_key": triage_queue_key,
        "row_count": _non_negative_int(payload.get("row_count")),
        "blank_row_count": _triage_blank_count(payload),
        "reviewed_or_valid_row_count": _triage_reviewed_or_valid_count(payload),
        "priority_counts": _safe_mapping(payload.get("priority_counts")),
        "reason_counts": _safe_mapping(payload.get("reason_counts")),
        "row_hints": _safe_row_hints(payload.get("row_hints"))[:10],
        "operator_next_steps": _safe_string_list(payload.get("operator_next_steps"))[:10],
    }


def _triage_queue_key(*, payload: Mapping[str, Any], fallback_file_name: str) -> str:
    """Return the queue key for a triage payload.

    Args:
        payload: Triage payload.
        fallback_file_name: Triage file name for brand batch inference.

    Returns:
        Queue key.
    """
    raw_queue_key = payload.get("queue_key")
    if isinstance(raw_queue_key, str) and raw_queue_key.strip():
        return _safe_token(raw_queue_key)
    if fallback_file_name.startswith("brand_product_review-"):
        return "brand_product_review"
    raise WorkOrderError("Batch triage is missing queue key.")


def _triage_blank_count(payload: Mapping[str, Any]) -> int:
    """Return blank row count across supported triage schemas.

    Args:
        payload: Triage payload.

    Returns:
        Blank row count.
    """
    return max(
        _non_negative_int(payload.get("blank_row_count")),
        _non_negative_int(payload.get("blank_decision_row_count")),
    )


def _triage_reviewed_or_valid_count(payload: Mapping[str, Any]) -> int:
    """Return reviewed or valid row count across supported triage schemas.

    Args:
        payload: Triage payload.

    Returns:
        Reviewed or valid row count.
    """
    return max(
        _non_negative_int(payload.get("reviewed_row_count")),
        _non_negative_int(payload.get("valid_row_count")),
    )


def _next_batch_key(*, progress: Mapping[str, Any], workpack: Mapping[str, Any]) -> str:
    """Return the next incomplete batch key from the progress artifact.

    Args:
        progress: Batch progress summary.
        workpack: Workpack summary. Its ``next_batch_key`` is a stale hint in
            static workpacks, so only its row inventory is validated later.

    Returns:
        Batch key.
    """
    progress_key = progress.get("next_incomplete_batch_key")
    if not isinstance(progress_key, str) or not progress_key.strip():
        raise WorkOrderError("Batch progress has no next incomplete batch.")
    if "batch_workpacks" not in workpack:
        raise WorkOrderError("Workpack summary has no batch rows.")
    return _safe_token(progress_key)


def _progress_row(*, progress: Mapping[str, Any], batch_key: str) -> Mapping[str, Any]:
    """Find the batch progress row.

    Args:
        progress: Batch progress summary.
        batch_key: Batch key.

    Returns:
        Batch row.
    """
    batches = progress.get("batches")
    if not isinstance(batches, Sequence) or isinstance(batches, str):
        raise WorkOrderError("Batch progress has no batch rows.")
    for row in batches:
        if isinstance(row, Mapping) and row.get("batch_key") == batch_key:
            return row
    raise WorkOrderError("Next batch is missing from batch progress rows.")


def _workpack_row(*, workpack: Mapping[str, Any], batch_key: str) -> Mapping[str, Any]:
    """Find the workpack row for a batch.

    Args:
        workpack: Workpack summary.
        batch_key: Batch key.

    Returns:
        Workpack row.
    """
    rows = workpack.get("batch_workpacks")
    if not isinstance(rows, Sequence) or isinstance(rows, str):
        raise WorkOrderError("Workpack summary has no batch rows.")
    for row in rows:
        if isinstance(row, Mapping) and row.get("batch_key") == batch_key:
            return row
    raise WorkOrderError("Next batch is missing from workpack rows.")


def _stage_for_queue(*, readiness: Mapping[str, Any], queue_key: str) -> Mapping[str, Any]:
    """Return the readiness stage that corresponds to a queue key.

    Args:
        readiness: Readiness report.
        queue_key: Queue key.

    Returns:
        Stage row.
    """
    stage_key = QUEUE_STAGE_KEYS[queue_key]
    stages = readiness.get("stages")
    if not isinstance(stages, Sequence) or isinstance(stages, str):
        raise WorkOrderError("Readiness report has no stages.")
    for stage in stages:
        if isinstance(stage, Mapping) and stage.get("stage_key") == stage_key:
            return stage
    raise WorkOrderError("Readiness stage is missing for next queue.")


def _assert_same_range(
    *,
    progress_row: Mapping[str, Any],
    workpack_row: Mapping[str, Any],
) -> None:
    """Verify progress and workpack row ranges match.

    Args:
        progress_row: Batch progress row.
        workpack_row: Workpack row.
    """
    for key in ("row_index_start", "row_index_end"):
        progress_value = _positive_int(progress_row.get(key))
        workpack_value = _positive_int(workpack_row.get(key))
        if progress_value != workpack_value:
            raise WorkOrderError("Batch row range mismatch between artifacts.")


def _load_json_object(path: Path) -> dict[str, Any]:
    """Load one JSON object.

    Args:
        path: JSON file path.

    Returns:
        Parsed object.
    """
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise WorkOrderError("Artifact must be a JSON object.")
    return value


def _required_input(input_paths: Mapping[str, Path], key: str) -> Path:
    """Return one required input path.

    Args:
        input_paths: Path mapping.
        key: Required key.

    Returns:
        Input path.
    """
    path = input_paths.get(key)
    if path is None or not path.is_file():
        raise WorkOrderError("Required input artifact is missing.")
    return path


def _require_schema(payload: Mapping[str, Any], expected_schema: str) -> None:
    """Validate an artifact schema version.

    Args:
        payload: Parsed artifact.
        expected_schema: Required schema.
    """
    if payload.get("schema_version") != expected_schema:
        raise WorkOrderError("Artifact schema version does not match.")


def _same_token(label: str, left: str, right: str) -> str:
    """Validate two safe tokens are equal.

    Args:
        label: Field label for error context.
        left: First token.
        right: Second token.

    Returns:
        Safe token.
    """
    left_token = _safe_token(left)
    right_token = _safe_token(right)
    if left_token != right_token:
        raise WorkOrderError(f"{label} mismatch between artifacts.")
    return left_token


def _safe_mapping(value: Any) -> dict[str, int]:
    """Return a safe string-to-int mapping.

    Args:
        value: Candidate mapping.

    Returns:
        Safe mapping.
    """
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise WorkOrderError("Expected aggregate reason mapping.")
    output: dict[str, int] = {}
    for key, item in value.items():
        output[_safe_token(str(key))] = _non_negative_int(item)
    return dict(sorted(output.items()))


def _safe_string_list(value: Any) -> list[str]:
    """Return safe filename or token values from a sequence.

    Args:
        value: Candidate sequence.

    Returns:
        Safe string list.
    """
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise WorkOrderError("Expected a string list.")
    output = []
    for item in value:
        text = str(item)
        if "." in text:
            output.append(_safe_filename(text))
        else:
            output.append(_safe_token(text))
    return output


def _optional_non_negative_int(value: Any) -> int | None:
    """Return a non-negative integer when present.

    Args:
        value: Candidate count value.

    Returns:
        Non-negative integer, or None for absent optional metadata.
    """
    if value is None:
        return None
    return _non_negative_int(value)


def _optional_safe_filename(value: Any) -> str | None:
    """Return a safe optional file name.

    Args:
        value: Candidate file name.

    Returns:
        Safe file name, or None.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    return _safe_filename(value)


def _markdown_bullets(value: Any) -> str:
    """Return a Markdown bullet list for safe string values.

    Args:
        value: Candidate string list.

    Returns:
        Markdown bullet list.
    """
    strings = _safe_string_list(value)
    if not strings:
        return "- none"
    return "\n".join(f"- `{item}`" for item in strings)


def _contact_sheet_markdown(summary: Mapping[str, Any]) -> str:
    """Build safe contact-sheet Markdown for a work order.

    Args:
        summary: Work order summary.

    Returns:
        Markdown contact-sheet guidance.
    """
    if summary.get("contact_sheet_available") is not True:
        return "- none"
    file_names = _markdown_bullets(summary.get("contact_sheet_file_names"))
    return "\n".join(
        [
            f"- Directory: `{_safe_filename(str(summary.get('contact_sheet_dir_name') or ''))}`",
            "- Files:",
            file_names,
            f"- Reviewable rows: `{_non_negative_int(summary.get('contact_sheet_reviewable_row_count'))}`",
            f"- Rows with thumbnails: `{_non_negative_int(summary.get('contact_sheet_rows_with_thumbnails'))}`",
            f"- Rows without thumbnails: `{_non_negative_int(summary.get('contact_sheet_rows_without_thumbnails'))}`",
            f"- Thumbnail count: `{_non_negative_int(summary.get('contact_sheet_thumbnail_count'))}`",
            "- Contact sheet는 브랜드/제품명 검수용 시각 근거입니다. 보이는 텍스트를 notes에 복사하지 않습니다.",
            "- CSV apply는 contact-sheet preflight와 전체 row review가 끝난 뒤 별도 batch copy에만 수행합니다.",
        ]
    )


def _markdown_mapping(value: Any) -> str:
    """Return a Markdown bullet list for a safe aggregate mapping.

    Args:
        value: Candidate mapping.

    Returns:
        Markdown bullet list.
    """
    mapping = _safe_mapping(value)
    if not mapping:
        return "- none"
    return "\n".join(f"- `{key}`: `{count}`" for key, count in mapping.items())


def _triage_markdown(value: Any) -> str:
    """Return Markdown for the optional triage summary.

    Args:
        value: Candidate triage summary.

    Returns:
        Markdown text.
    """
    if not isinstance(value, Mapping) or not value:
        return "- none"
    lines = [
        f"- Triage file: `{_safe_filename(str(value.get('input_name') or ''))}`",
        f"- Rows: `{_non_negative_int(value.get('row_count'))}`",
        f"- Blank rows: `{_non_negative_int(value.get('blank_row_count'))}`",
        f"- Reviewed/valid rows: `{_non_negative_int(value.get('reviewed_or_valid_row_count'))}`",
        "- Priorities:",
        _markdown_mapping(value.get("priority_counts")),
        "- Reasons:",
        _markdown_mapping(value.get("reason_counts")),
        "- Row hints:",
        _row_hints_markdown(value.get("row_hints")),
        "- Operator next steps:",
        _markdown_bullets(value.get("operator_next_steps")),
    ]
    return "\n".join(lines)


def _safe_row_hints(value: Any) -> list[dict[str, Any]]:
    """Return redacted row-index hints.

    Args:
        value: Candidate row hint list.

    Returns:
        Safe row hint rows.
    """
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise WorkOrderError("Expected row hint list.")
    hints = []
    for item in value:
        if not isinstance(item, Mapping):
            raise WorkOrderError("Expected row hint mapping.")
        reason_codes = item.get("reason_codes")
        reason_code = item.get("reason_code")
        hints.append(
            {
                "row_index": _positive_int(item.get("row_index")),
                "priority": _safe_token(str(item.get("priority") or "")),
                "reason_codes": (
                    _safe_string_list(reason_codes)
                    if reason_codes is not None
                    else [_safe_token(str(reason_code or ""))]
                ),
            }
        )
    return hints


def _row_hints_markdown(value: Any) -> str:
    """Return Markdown bullets for row hints.

    Args:
        value: Candidate row hint list.

    Returns:
        Markdown text.
    """
    hints = _safe_row_hints(value)
    if not hints:
        return "- none"
    return "\n".join(f"- row `{hint['row_index']}`: `{hint['priority']}`" for hint in hints[:5])


def _safe_filename(value: str) -> str:
    """Return a safe file name.

    Args:
        value: Candidate filename.

    Returns:
        Safe filename.
    """
    try:
        return workpack_builder.batch_exporter._safe_filename(value)
    except workpack_builder.batch_exporter.BatchFileExportError as exc:
        raise WorkOrderError(str(exc)) from exc


def _safe_token(value: str) -> str:
    """Return a safe non-path token.

    Args:
        value: Candidate token.

    Returns:
        Safe token.
    """
    try:
        return progress_preflight._safe_token(value)
    except progress_preflight.BatchProgressError as exc:
        raise WorkOrderError(str(exc)) from exc


def _positive_int(value: Any) -> int:
    """Return a positive integer.

    Args:
        value: Candidate integer.

    Returns:
        Positive integer.
    """
    try:
        return progress_preflight._positive_int(value)
    except progress_preflight.BatchProgressError as exc:
        raise WorkOrderError(str(exc)) from exc


def _non_negative_int(value: Any) -> int:
    """Return a non-negative integer.

    Args:
        value: Candidate integer.

    Returns:
        Non-negative integer.
    """
    try:
        return progress_preflight._non_negative_int(value)
    except progress_preflight.BatchProgressError as exc:
        raise WorkOrderError(str(exc)) from exc


def _reject_unsafe_payload(value: Any) -> None:
    """Reject raw text, provider payloads, or local path markers.

    Args:
        value: JSON-like payload.
    """
    try:
        readiness_reporter._reject_unsafe_payload(value)
    except readiness_reporter.PipelineReadinessError as exc:
        raise WorkOrderError(str(exc)) from exc


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
    """Return a compact CLI-safe summary.

    Args:
        summary: Full work order.

    Returns:
        CLI summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": summary["status"],
        "batch_key": summary["batch_key"],
        "queue_key": summary["queue_key"],
        "batch_status": summary["batch_status"],
        "blank_row_count": summary["blank_row_count"],
        "next_action": summary["operator_next_action"],
        "source_rows_read": False,
        "source_image_read_performed": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
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
        Redacted failure summary.
    """
    _ = error
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_fingerprints": {
            key: _path_fingerprint(path) for key, path in sorted(input_paths.items())
        },
        "output_name": output_path.name,
        "output_path_fingerprint": _path_fingerprint(output_path),
        "source_rows_read": False,
        "source_image_read_performed": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
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
