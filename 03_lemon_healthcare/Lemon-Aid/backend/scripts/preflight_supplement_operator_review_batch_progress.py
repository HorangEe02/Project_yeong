"""Preflight supplement operator review progress by batch.

This tool reads the redacted batch plan plus the operator-edited decision or
annotation files and reports aggregate progress per batch. It is a progress
checker only: final apply/promotion readiness still belongs to the queue-level
preflight scripts.

The output never includes fixture ids, product text, raw OCR, provider payloads,
image paths, source refs, notes, or local absolute paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
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
    apply_supplement_brand_review_decisions as brand_applier,
)
from scripts import (  # noqa: E402
    apply_supplement_review_pii_screening_decisions as pii_applier,
)
from scripts import (  # noqa: E402
    build_supplement_operator_review_batch_plan as batch_plan_builder,
)
from scripts import (  # noqa: E402
    preflight_supplement_brand_review_decisions as brand_preflight,
)
from scripts import (  # noqa: E402
    preflight_supplement_review_pii_screening_decisions as pii_preflight,
)
from scripts import (  # noqa: E402
    preflight_supplement_yolo_annotation_decisions as yolo_preflight,
)
from scripts import (  # noqa: E402
    promote_supplement_yolo_annotation_template as yolo_promoter,
)

SCHEMA_VERSION = "supplement-operator-review-batch-progress-preflight-v1"
BATCH_PLAN_SCHEMA = "supplement-operator-review-batch-plan-v1"
SOURCE_DOC_URLS = (
    "https://docs.python.org/3/library/csv.html",
    *batch_plan_builder.SOURCE_DOC_URLS,
)
LOCAL_PATH_MARKERS = batch_plan_builder.LOCAL_PATH_MARKERS
RAW_FORBIDDEN_KEYS = batch_plan_builder.RAW_FORBIDDEN_KEYS
UNSAFE_TRUE_FLAGS = batch_plan_builder.UNSAFE_TRUE_FLAGS
QUEUE_KEYS = frozenset(
    {
        "brand_product_review",
        "review_pii_screening",
        "yolo_section_annotation",
    }
)


class BatchProgressError(ValueError):
    """Raised when batch progress input cannot be trusted."""


@dataclass(frozen=True)
class RowStatus:
    """Progress status for one editable row.

    Args:
        status: One of ``valid``, ``blank``, ``pending``, ``invalid``, or
            ``missing``.
        reason_code: Aggregate-safe reason code.
    """

    status: str
    reason_code: str


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
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write a redacted batch progress summary.

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
    output_path = args.output.expanduser().resolve()
    markdown_output = (
        args.markdown_output.expanduser().resolve() if args.markdown_output is not None else None
    )
    try:
        summary = preflight_operator_review_batch_progress(input_paths=input_paths)
        _write_json(output_path, summary)
        if markdown_output is not None:
            markdown = build_batch_progress_markdown(summary)
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            markdown_output.write_text(markdown, encoding="utf-8")
        print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    except (OSError, json.JSONDecodeError, BatchProgressError, ValueError) as exc:
        failure = _failure_summary(input_paths=input_paths, output_path=output_path, error=exc)
        _write_json(output_path, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None


def preflight_operator_review_batch_progress(
    *,
    input_paths: Mapping[str, Path],
) -> dict[str, Any]:
    """Return redacted batch progress by queue and row range.

    Args:
        input_paths: Input file paths keyed by argument name.

    Returns:
        Redacted progress summary.
    """
    plan = _load_json_object(_required_input(input_paths, "batch_plan"))
    _require_schema(plan, BATCH_PLAN_SCHEMA)
    editable_rows = _load_editable_rows(input_paths)
    batch_rows = _batch_rows(plan)
    batches = [
        _progress_for_batch(batch=batch, editable_rows=editable_rows) for batch in batch_rows
    ]
    complete_count = sum(1 for batch in batches if batch["batch_status"] == "complete")
    invalid_count = sum(1 for batch in batches if batch["batch_status"] == "invalid")
    pending_count = len(batches) - complete_count - invalid_count
    aggregate_reason_counts: dict[str, int] = {}
    for batch in batches:
        for reason, count in batch["reason_counts"].items():
            aggregate_reason_counts[reason] = aggregate_reason_counts.get(reason, 0) + count
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_hashes": {
            key: _fingerprint_text(str(path.expanduser()))
            for key, path in sorted(input_paths.items())
        },
        "batch_count": len(batches),
        "complete_batch_count": complete_count,
        "pending_batch_count": pending_count,
        "invalid_batch_count": invalid_count,
        "all_batches_complete": complete_count == len(batches) and invalid_count == 0,
        "next_incomplete_batch_key": _next_incomplete_batch_key(batches),
        "total_expected_row_count": sum(
            _non_negative_int(batch.get("expected_row_count")) for batch in batches
        ),
        "total_valid_row_count": sum(
            _non_negative_int(batch.get("valid_row_count")) for batch in batches
        ),
        "total_blank_row_count": sum(
            _non_negative_int(batch.get("blank_row_count")) for batch in batches
        ),
        "total_pending_row_count": sum(
            _non_negative_int(batch.get("pending_row_count")) for batch in batches
        ),
        "total_invalid_row_count": sum(
            _non_negative_int(batch.get("invalid_row_count")) for batch in batches
        ),
        "total_missing_row_count": sum(
            _non_negative_int(batch.get("missing_row_count")) for batch in batches
        ),
        "aggregate_reason_counts": dict(sorted(aggregate_reason_counts.items())),
        "batches": batches,
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


def build_batch_progress_markdown(summary: Mapping[str, Any]) -> str:
    """Build a redacted Markdown progress table.

    Args:
        summary: Progress summary.

    Returns:
        Markdown text.
    """
    _reject_unsafe_payload(summary)
    rows = []
    for batch in _summary_batches(summary):
        rows.append(
            "| {batch_key} | {status} | {valid} | {blank} | {pending} | {invalid} | {missing} |".format(
                batch_key=_safe_token(str(batch["batch_key"])),
                status=_safe_token(str(batch["batch_status"])),
                valid=_non_negative_int(batch.get("valid_row_count")),
                blank=_non_negative_int(batch.get("blank_row_count")),
                pending=_non_negative_int(batch.get("pending_row_count")),
                invalid=_non_negative_int(batch.get("invalid_row_count")),
                missing=_non_negative_int(batch.get("missing_row_count")),
            )
        )
    markdown = "\n".join(
        [
            "# Supplement Operator Review Batch Progress",
            "",
            f"Schema: `{SCHEMA_VERSION}`",
            "",
            "이 문서는 operator decision/annotation 파일의 aggregate 진행률만 표시합니다. fixture id, 제품명, OCR 원문, provider payload, 이미지 경로, 로컬 경로는 포함하지 않습니다.",
            "",
            f"- Batch count: `{_non_negative_int(summary.get('batch_count'))}`",
            f"- Complete batch count: `{_non_negative_int(summary.get('complete_batch_count'))}`",
            f"- Pending batch count: `{_non_negative_int(summary.get('pending_batch_count'))}`",
            f"- Invalid batch count: `{_non_negative_int(summary.get('invalid_batch_count'))}`",
            f"- Next incomplete batch: `{_safe_token(str(summary.get('next_incomplete_batch_key') or 'none'))}`",
            "",
            "| Batch | Status | Valid | Blank | Pending | Invalid | Missing |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
            *rows,
            "",
            "## Rule",
            "",
            "1. 모든 batch가 `complete`가 되어도 큐별 정식 preflight를 다시 실행해야 합니다.",
            "2. 정식 preflight의 blank/pending/invalid count가 0인 큐만 apply 또는 promotion으로 넘깁니다.",
            "",
        ]
    )
    _reject_unsafe_payload(markdown)
    return markdown


def _load_editable_rows(input_paths: Mapping[str, Path]) -> dict[str, list[dict[str, Any]]]:
    """Load editable rows by queue key.

    Args:
        input_paths: Input path mapping.

    Returns:
        Queue key to parsed JSONL rows.
    """
    output: dict[str, list[dict[str, Any]]] = {}
    mapping = {
        "brand_product_review": "brand_decisions",
        "review_pii_screening": "pii_decisions",
        "yolo_section_annotation": "yolo_annotations",
    }
    for queue_key, input_key in mapping.items():
        path = input_paths.get(input_key)
        if path is None:
            continue
        output[queue_key] = _read_jsonl(path=path)
    return output


def _progress_for_batch(
    *,
    batch: Mapping[str, Any],
    editable_rows: Mapping[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Return redacted progress for one batch.

    Args:
        batch: Batch plan row.
        editable_rows: Parsed editable rows by queue key.

    Returns:
        Progress row.
    """
    queue_key = _queue_key(batch.get("queue_key"))
    batch_key = _safe_token(str(batch.get("batch_key") or "unknown"))
    start = _positive_int(batch.get("row_index_start"))
    end = _positive_int(batch.get("row_index_end"))
    if end < start:
        raise BatchProgressError("Batch row range is invalid.")
    rows = editable_rows.get(queue_key)
    if rows is None:
        raise BatchProgressError("Editable file for a queued batch is missing.")
    expected_count = end - start + 1
    statuses = [
        _status_for_index(queue_key=queue_key, rows=rows, row_index=index)
        for index in range(start, end + 1)
    ]
    counts = _status_counts(statuses)
    status = _batch_status(
        expected_count=expected_count,
        valid_count=counts["valid"],
        blank_count=counts["blank"],
        pending_count=counts["pending"],
        invalid_count=counts["invalid"],
        missing_count=counts["missing"],
    )
    progress = {
        "batch_key": batch_key,
        "queue_key": queue_key,
        "batch_status": status,
        "row_index_start": start,
        "row_index_end": end,
        "expected_row_count": expected_count,
        "valid_row_count": counts["valid"],
        "blank_row_count": counts["blank"],
        "pending_row_count": counts["pending"],
        "invalid_row_count": counts["invalid"],
        "missing_row_count": counts["missing"],
        "reason_counts": dict(sorted(_reason_counts(statuses).items())),
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
    _reject_unsafe_payload(progress)
    return progress


def _status_for_index(
    *,
    queue_key: str,
    rows: list[dict[str, Any]],
    row_index: int,
) -> RowStatus:
    """Return progress status for one 1-based row index.

    Args:
        queue_key: Queue key.
        rows: Parsed editable rows.
        row_index: One-based row index.

    Returns:
        Row status.
    """
    zero_based = row_index - 1
    if zero_based < 0 or zero_based >= len(rows):
        return RowStatus("missing", "missing_row")
    row = rows[zero_based]
    try:
        if queue_key == "brand_product_review":
            return _brand_row_status(row)
        if queue_key == "review_pii_screening":
            return _pii_row_status(row)
        if queue_key == "yolo_section_annotation":
            return _yolo_row_status(row)
    except (ValueError, yolo_promoter.TemplatePromotionError) as exc:
        return RowStatus("invalid", _safe_reason_code(exc))
    raise BatchProgressError("Unsupported queue key.")


def _brand_row_status(row: dict[str, Any]) -> RowStatus:
    """Return aggregate status for one brand decision row.

    Args:
        row: Parsed brand decision row.

    Returns:
        Row status.
    """
    brand_applier._reject_unsafe_payload(row)
    if row.get("schema_version") not in {None, brand_applier.DECISION_SCHEMA_VERSION}:
        return RowStatus("invalid", "unsupported_schema")
    decision = row.get("brand_review_decision")
    if not isinstance(decision, dict):
        return RowStatus("invalid", "missing_decision_object")
    if brand_preflight._decision_is_blank(decision):
        return RowStatus("blank", "blank_decision")
    brand_applier._validate_decision(decision)
    return RowStatus("valid", "valid_decision")


def _pii_row_status(row: dict[str, Any]) -> RowStatus:
    """Return aggregate status for one PII decision row.

    Args:
        row: Parsed PII decision row.

    Returns:
        Row status.
    """
    pii_applier._reject_unsafe_payload(row)
    if row.get("schema_version") not in {None, pii_applier.DECISION_SCHEMA_VERSION}:
        return RowStatus("invalid", "unsupported_schema")
    decision = row.get("pii_screening_decision")
    if not isinstance(decision, dict):
        return RowStatus("invalid", "missing_decision_object")
    if pii_preflight._decision_is_blank(decision):
        return RowStatus("blank", "blank_decision")
    pii_applier._validate_decision(decision)
    return RowStatus("valid", "valid_decision")


def _yolo_row_status(row: dict[str, Any]) -> RowStatus:
    """Return aggregate status for one YOLO annotation row.

    Args:
        row: Parsed YOLO annotation row.

    Returns:
        Row status.
    """
    yolo_promoter._reject_unsafe_payload(row, allow_relative_image_paths=True)
    if row.get("schema_version") != yolo_promoter.TEMPLATE_ROW_SCHEMA_VERSION:
        return RowStatus("invalid", "unsupported_schema")
    label_snapshot = yolo_promoter._label_snapshot(row)
    boxes = yolo_preflight._validated_boxes(label_snapshot)
    if not boxes:
        return RowStatus("blank", "blank_boxes")
    if not yolo_promoter._row_marked_accepted(row):
        return RowStatus("pending", "boxes_not_accepted")
    return RowStatus("valid", "valid_annotation")


def _batch_status(
    *,
    expected_count: int,
    valid_count: int,
    blank_count: int,
    pending_count: int,
    invalid_count: int,
    missing_count: int,
) -> str:
    """Return aggregate batch status.

    Args:
        expected_count: Expected rows in batch.
        valid_count: Valid rows.
        blank_count: Blank rows.
        pending_count: Pending rows.
        invalid_count: Invalid rows.
        missing_count: Missing rows.

    Returns:
        Status token.
    """
    if invalid_count or missing_count:
        return "invalid"
    if valid_count == expected_count and blank_count == 0 and pending_count == 0:
        return "complete"
    return "pending"


def _status_counts(statuses: list[RowStatus]) -> dict[str, int]:
    """Count row statuses.

    Args:
        statuses: Row statuses.

    Returns:
        Status count mapping.
    """
    counts = dict.fromkeys(("valid", "blank", "pending", "invalid", "missing"), 0)
    for row_status in statuses:
        counts[row_status.status] = counts.get(row_status.status, 0) + 1
    return counts


def _reason_counts(statuses: list[RowStatus]) -> dict[str, int]:
    """Count aggregate reason codes.

    Args:
        statuses: Row statuses.

    Returns:
        Reason count mapping.
    """
    counts: dict[str, int] = {}
    for row_status in statuses:
        reason = _safe_token(row_status.reason_code)
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def _read_jsonl(*, path: Path) -> list[dict[str, Any]]:
    """Read one JSONL file without printing row payloads.

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
            raise BatchProgressError("Editable JSONL rows must be objects.")
        rows.append(value)
    return rows


def _next_incomplete_batch_key(batches: list[Mapping[str, Any]]) -> str | None:
    """Return the first incomplete batch key.

    Args:
        batches: Progress batch rows.

    Returns:
        Batch key or None.
    """
    for batch in batches:
        if batch.get("batch_status") != "complete":
            return str(batch.get("batch_key"))
    return None


def _load_json_object(path: Path) -> dict[str, Any]:
    """Load a JSON object and reject unsafe payloads.

    Args:
        path: JSON path.

    Returns:
        Parsed object.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BatchProgressError("Progress inputs must be JSON objects.")
    _reject_unsafe_payload(payload)
    _reject_unsafe_true_flags(payload)
    return payload


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
        raise BatchProgressError("Required progress input is missing.")
    return path


def _require_schema(payload: Mapping[str, Any], expected_schema: str) -> None:
    """Validate one schema version.

    Args:
        payload: Parsed payload.
        expected_schema: Required schema.
    """
    if payload.get("schema_version") != expected_schema:
        raise BatchProgressError("Progress input schema does not match.")


def _batch_rows(plan: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return batch plan rows.

    Args:
        plan: Batch plan.

    Returns:
        Batch row mappings.
    """
    batches = plan.get("batches")
    if not isinstance(batches, list):
        raise BatchProgressError("Batch plan is missing batches.")
    if not all(isinstance(batch, Mapping) for batch in batches):
        raise BatchProgressError("Batch rows must be objects.")
    return batches


def _summary_batches(summary: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return summary batch rows.

    Args:
        summary: Progress summary.

    Returns:
        Batch row mappings.
    """
    batches = summary.get("batches")
    if not isinstance(batches, list):
        raise BatchProgressError("Progress summary is missing batches.")
    if not all(isinstance(batch, Mapping) for batch in batches):
        raise BatchProgressError("Progress batch rows must be objects.")
    return batches


def _queue_key(value: object) -> str:
    """Return a supported queue key.

    Args:
        value: Candidate queue key.

    Returns:
        Queue key.
    """
    queue_key = _safe_token(str(value or "unknown"))
    if queue_key not in QUEUE_KEYS:
        raise BatchProgressError("Unsupported queue key.")
    return queue_key


def _positive_int(value: object) -> int:
    """Return a positive integer.

    Args:
        value: Candidate value.

    Returns:
        Positive integer.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise BatchProgressError("Expected a positive integer.")
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


def _reject_unsafe_true_flags(payload: Mapping[str, Any]) -> None:
    """Reject unsafe execution flags set to true.

    Args:
        payload: Parsed input payload.
    """
    for key in UNSAFE_TRUE_FLAGS:
        if payload.get(key) is True:
            raise BatchProgressError("Progress input has an unsafe true flag.")


def _reject_unsafe_payload(value: Any) -> None:
    """Reject raw data keys and local path markers in outputs.

    Args:
        value: JSON-like payload.
    """
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in RAW_FORBIDDEN_KEYS:
                raise BatchProgressError("Unsafe raw/provider key found.")
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
        raise BatchProgressError("Unsafe local path marker found.")


def _validate_source_doc_urls(value: Any) -> None:
    """Validate known official documentation URLs.

    Args:
        value: Candidate URL list.
    """
    if not isinstance(value, list):
        raise BatchProgressError("source_doc_urls must be a list.")
    allowed = set(SOURCE_DOC_URLS)
    for item in value:
        if item not in allowed:
            raise BatchProgressError("Unexpected source documentation URL.")


def _safe_token(value: str) -> str:
    """Return a bounded safe token.

    Args:
        value: Candidate token.

    Returns:
        Safe token.
    """
    cleaned = value.strip()
    if not cleaned:
        return "unknown"
    if any(marker in cleaned for marker in LOCAL_PATH_MARKERS) or "/" in cleaned or "\\" in cleaned:
        raise BatchProgressError("Unsafe token contains a path marker.")
    return cleaned[:120]


def _safe_reason_code(error: Exception) -> str:
    """Return a bounded reason code for a validation exception.

    Args:
        error: Validation exception.

    Returns:
        Safe reason code.
    """
    text = str(error).casefold()
    markers = (
        ("unsupported", "unsupported_schema"),
        ("schema", "unsupported_schema"),
        ("decision", "invalid_decision"),
        ("attestation", "missing_required_attestation"),
        ("operator_ prefix", "invalid_reviewer_id"),
        ("reviewed_manufacturer", "invalid_reviewed_manufacturer"),
        ("reviewed_product_name", "invalid_reviewed_product_name"),
        ("reason_codes", "invalid_reason_codes"),
        ("unsafe", "unsafe_field"),
        ("raw", "unsafe_field"),
        ("path", "unsafe_field"),
        ("label", "invalid_label"),
        ("coordinates", "invalid_box_coordinates"),
        ("positive", "invalid_box_area"),
        ("boxes", "invalid_boxes"),
    )
    for marker, code in markers:
        if marker in text:
            return code
    return "validation_error"


def _sha256_text(value: str) -> str:
    """Return a SHA-256 digest for text.

    Args:
        value: Text value.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fingerprint_text(value: str) -> str:
    """Return a short non-secret fingerprint for operator audit inputs.

    Args:
        value: Text value to fingerprint.

    Returns:
        Stable short fingerprint.
    """
    return f"fp-{_sha256_text(value)[:12]}"


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
        summary: Full progress summary.

    Returns:
        CLI summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "batch_count": _non_negative_int(summary.get("batch_count")),
        "complete_batch_count": _non_negative_int(summary.get("complete_batch_count")),
        "pending_batch_count": _non_negative_int(summary.get("pending_batch_count")),
        "invalid_batch_count": _non_negative_int(summary.get("invalid_batch_count")),
        "next_incomplete_batch_key": summary.get("next_incomplete_batch_key"),
        "total_valid_row_count": _non_negative_int(summary.get("total_valid_row_count")),
        "total_blank_row_count": _non_negative_int(summary.get("total_blank_row_count")),
        "total_pending_row_count": _non_negative_int(summary.get("total_pending_row_count")),
        "total_invalid_row_count": _non_negative_int(summary.get("total_invalid_row_count")),
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
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_hashes": {
            key: _fingerprint_text(str(path.expanduser()))
            for key, path in sorted(input_paths.items())
        },
        "output_name": output_path.name,
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
        return "local_file_read_error"
    if isinstance(error, json.JSONDecodeError):
        return "json_decode_error"
    return "validation_error"


if __name__ == "__main__":
    main()
