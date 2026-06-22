"""Build a redacted batch plan for supplement operator review queues.

The batch plan helps operators split manual review work across the three
blocking supplement-learning queues without copying row payloads. It reads only
redacted queue and bundle summary JSON files, then emits row-number ranges for
the bundle files that already exist.

It does not read source images, JSONL decision rows, OCR text, provider
payloads, model responses, or database records. It does not write to the
database and does not promote training artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

QUEUE_SCHEMA_VERSION = "supplement-operator-review-queue-summary-v1"
SCHEMA_VERSION = "supplement-operator-review-batch-plan-v1"
MARKDOWN_SCHEMA_VERSION = "supplement-operator-review-batch-plan-markdown-v1"
BRAND_BUNDLE_SCHEMA = "supplement-brand-review-bundle-v1"
PII_BUNDLE_SCHEMA = "supplement-review-pii-screening-review-bundle-v1"
YOLO_BUNDLE_SCHEMA = "supplement-yolo-annotation-review-bundle-v1"
MIN_BATCH_SIZE = 1
MAX_BATCH_SIZE = 200
DEFAULT_BATCH_SIZE = 50
MAX_SAFE_FILENAME_LENGTH = 160
LOCAL_PATH_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    "file://",
    "\\Users\\",
    "\\Volumes\\",
)
SOURCE_DOC_URLS = (
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


class OperatorBatchPlanError(ValueError):
    """Raised when a batch plan input or output is unsafe."""


@dataclass(frozen=True)
class BundleSpec:
    """Static bundle summary contract for one operator queue.

    Args:
        queue_key: Queue key from the aggregate review queue.
        input_key: Optional CLI input key for the bundle summary.
        expected_schema: Required bundle summary schema version.
        file_fields: Ordered candidate fields that hold the editable file name.
        default_file_name: Safe fallback file name when no summary is attached.
        checklist: Short operator checklist items for the batch.
    """

    queue_key: str
    input_key: str
    expected_schema: str
    file_fields: tuple[str, ...]
    default_file_name: str
    checklist: tuple[str, ...]


BUNDLE_SPECS = (
    BundleSpec(
        queue_key="brand_product_review",
        input_key="brand_bundle_summary",
        expected_schema=BRAND_BUNDLE_SCHEMA,
        file_fields=("decision_template_name", "csv_name"),
        default_file_name="decisions.todo.jsonl",
        checklist=(
            "fill_reviewed_manufacturer",
            "fill_reviewed_product_name",
            "set_approve_or_reject_decision",
            "keep_db_import_attestation_explicit",
        ),
    ),
    BundleSpec(
        queue_key="review_pii_screening",
        input_key="pii_bundle_summary",
        expected_schema=PII_BUNDLE_SCHEMA,
        file_fields=("decision_template_name",),
        default_file_name="decisions.todo.jsonl",
        checklist=(
            "inspect_hashed_fixture_image",
            "set_pii_screening_decision",
            "use_operator_prefixed_reviewer_id",
            "do_not_copy_visible_text_into_notes",
        ),
    ),
    BundleSpec(
        queue_key="yolo_section_annotation",
        input_key="yolo_bundle_summary",
        expected_schema=YOLO_BUNDLE_SCHEMA,
        file_fields=("annotation_template_name",),
        default_file_name="annotation.todo.jsonl",
        checklist=(
            "draw_required_section_bbox",
            "use_supported_section_labels_only",
            "set_training_export_allowed_after_review",
            "do_not_export_until_preflight_passes",
        ),
    ),
)
BUNDLE_SPEC_BY_QUEUE = {spec.queue_key: spec for spec in BUNDLE_SPECS}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-summary", type=Path, required=True)
    parser.add_argument("--brand-bundle-summary", type=Path, default=None)
    parser.add_argument("--pii-bundle-summary", type=Path, default=None)
    parser.add_argument("--yolo-bundle-summary", type=Path, default=None)
    parser.add_argument("--batch-size", type=_batch_size_arg, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write a redacted batch plan and optional Markdown checklist.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    input_paths = {
        "queue_summary": args.queue_summary.expanduser().resolve(),
    }
    optional_inputs = {
        "brand_bundle_summary": args.brand_bundle_summary,
        "pii_bundle_summary": args.pii_bundle_summary,
        "yolo_bundle_summary": args.yolo_bundle_summary,
    }
    for key, value in optional_inputs.items():
        if value is not None:
            input_paths[key] = value.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    markdown_output = (
        args.markdown_output.expanduser().resolve() if args.markdown_output is not None else None
    )
    try:
        plan = build_operator_review_batch_plan(
            input_paths=input_paths,
            batch_size=args.batch_size,
        )
        _write_json(output_path, plan)
        if markdown_output is not None:
            markdown = build_operator_review_batch_markdown(plan)
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            markdown_output.write_text(markdown, encoding="utf-8")
        print(json.dumps(_cli_summary(plan), ensure_ascii=False, sort_keys=True))
    except (OSError, json.JSONDecodeError, OperatorBatchPlanError) as exc:
        failure = _failure_summary(input_paths=input_paths, output_path=output_path, error=exc)
        _write_json(output_path, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None


def build_operator_review_batch_plan(
    *,
    input_paths: Mapping[str, Path],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, Any]:
    """Build a redacted operator batch plan from queue summaries.

    Args:
        input_paths: Input summary paths keyed by CLI input names.
        batch_size: Maximum pending rows per operator batch.

    Returns:
        Batch plan JSON object.

    Raises:
        OperatorBatchPlanError: If inputs are unsafe or malformed.
    """
    if batch_size < MIN_BATCH_SIZE or batch_size > MAX_BATCH_SIZE:
        raise OperatorBatchPlanError("Batch size is outside the allowed range.")
    queue_summary = _load_json_object(_required_input_path(input_paths, "queue_summary"))
    _require_schema(queue_summary, QUEUE_SCHEMA_VERSION)
    bundle_summaries = _load_bundle_summaries(input_paths)
    queue_rows = _queue_rows(queue_summary)
    batches = _build_batches(
        queue_rows=queue_rows,
        bundle_summaries=bundle_summaries,
        batch_size=batch_size,
    )
    queue_batch_counts: dict[str, int] = {}
    for batch in batches:
        key = str(batch["queue_key"])
        queue_batch_counts[key] = queue_batch_counts.get(key, 0) + 1
    plan = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_hashes": {
            key: _sha256_text(str(path.expanduser())) for key, path in sorted(input_paths.items())
        },
        "batch_size": batch_size,
        "queue_count": _non_negative_int(queue_summary.get("queue_count")),
        "pending_queue_count": _non_negative_int(queue_summary.get("pending_queue_count")),
        "total_pending_operator_action_count": _non_negative_int(
            queue_summary.get("total_pending_operator_action_count")
        ),
        "batch_count": len(batches),
        "queue_batch_counts": dict(sorted(queue_batch_counts.items())),
        "next_queue_key": _optional_safe_token(queue_summary.get("next_queue_key")),
        "ready_for_next_pipeline_step": queue_summary.get("ready_for_next_pipeline_step") is True,
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
    _reject_unsafe_payload(plan)
    return plan


def build_operator_review_batch_markdown(plan: Mapping[str, Any]) -> str:
    """Build a redacted Markdown checklist from a batch plan.

    Args:
        plan: Batch plan JSON object.

    Returns:
        Markdown text.
    """
    _reject_unsafe_payload(plan)
    rows = []
    for batch in _batch_rows(plan):
        rows.append(
            "| {batch_key} | {queue_key} | {file_name} | {start} | {end} | {count} |".format(
                batch_key=_safe_token(str(batch["batch_key"])),
                queue_key=_safe_token(str(batch["queue_key"])),
                file_name=_safe_filename(str(batch["editable_file_name"])),
                start=_non_negative_int(batch.get("row_index_start")),
                end=_non_negative_int(batch.get("row_index_end")),
                count=_non_negative_int(batch.get("pending_row_count")),
            )
        )
    markdown = "\n".join(
        [
            "# Supplement Operator Review Batch Plan",
            "",
            f"Schema: `{MARKDOWN_SCHEMA_VERSION}`",
            "",
            "이 문서는 redacted summary만 기반으로 합니다. 원본 이미지, OCR 원문, provider payload, 로컬 경로, 제품 폴더 literal은 포함하지 않습니다.",
            "",
            f"- Batch size: `{_non_negative_int(plan.get('batch_size'))}`",
            f"- Batch count: `{_non_negative_int(plan.get('batch_count'))}`",
            f"- Pending operator action count: `{_non_negative_int(plan.get('total_pending_operator_action_count'))}`",
            f"- Next queue: `{_safe_token(str(plan.get('next_queue_key') or 'none'))}`",
            "",
            "| Batch | Queue | Editable file | Start row | End row | Pending rows |",
            "| --- | --- | --- | ---: | ---: | ---: |",
            *rows,
            "",
            "## Completion Rule",
            "",
            "1. 배치별 row range를 사람이 검수합니다.",
            "2. 큐별 preflight를 다시 실행해 blank/pending/invalid count가 0인지 확인합니다.",
            "3. preflight가 통과한 큐만 다음 apply 또는 promotion 단계로 넘깁니다.",
            "",
        ]
    )
    _reject_unsafe_payload(markdown)
    return markdown


def _load_bundle_summaries(input_paths: Mapping[str, Path]) -> dict[str, dict[str, Any]]:
    """Load optional bundle summaries keyed by queue key.

    Args:
        input_paths: Input path mapping.

    Returns:
        Bundle summaries keyed by queue key.
    """
    bundle_summaries: dict[str, dict[str, Any]] = {}
    for spec in BUNDLE_SPECS:
        path = input_paths.get(spec.input_key)
        if path is None:
            continue
        summary = _load_json_object(path)
        _require_schema(summary, spec.expected_schema)
        bundle_summaries[spec.queue_key] = summary
    return bundle_summaries


def _build_batches(
    *,
    queue_rows: list[Mapping[str, Any]],
    bundle_summaries: Mapping[str, Mapping[str, Any]],
    batch_size: int,
) -> list[dict[str, Any]]:
    """Build all batch rows in queue order.

    Args:
        queue_rows: Queue rows from the aggregate queue summary.
        bundle_summaries: Optional bundle summaries by queue key.
        batch_size: Maximum pending rows per batch.

    Returns:
        Batch rows.
    """
    batches: list[dict[str, Any]] = []
    for queue_position, queue in enumerate(queue_rows, start=1):
        queue_key = _safe_token(str(queue.get("queue_key") or "unknown"))
        spec = BUNDLE_SPEC_BY_QUEUE.get(queue_key)
        if spec is None:
            raise OperatorBatchPlanError("Unknown queue key in operator queue summary.")
        pending = _non_negative_int(queue.get("pending_operator_action_count"))
        if pending == 0:
            continue
        bundle_summary = bundle_summaries.get(queue_key, {})
        editable_file = _editable_file_name(spec=spec, bundle_summary=bundle_summary)
        review_index = _optional_file_name(bundle_summary.get("html_index_name"))
        readme_name = _optional_file_name(bundle_summary.get("readme_name"))
        batch_count = (pending + batch_size - 1) // batch_size
        for batch_index in range(1, batch_count + 1):
            start = ((batch_index - 1) * batch_size) + 1
            end = min(batch_index * batch_size, pending)
            batch = {
                "batch_key": f"{queue_key}:{batch_index:03d}",
                "queue_key": queue_key,
                "queue_order": queue_position,
                "batch_index": batch_index,
                "batch_count_for_queue": batch_count,
                "queue_status": _safe_token(str(queue.get("queue_status") or "unknown")),
                "editable_file_name": editable_file,
                "review_index_name": review_index,
                "readme_name": readme_name,
                "row_index_start": start,
                "row_index_end": end,
                "pending_row_count": end - start + 1,
                "total_queue_pending_count": pending,
                "next_operator_action": _safe_token(
                    str(queue.get("next_operator_action") or "unknown")
                ),
                "operator_checklist": list(spec.checklist),
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
            _reject_unsafe_payload(batch)
            batches.append(batch)
    return batches


def _editable_file_name(
    *,
    spec: BundleSpec,
    bundle_summary: Mapping[str, Any],
) -> str:
    """Return the operator-editable file name for a queue.

    Args:
        spec: Queue bundle contract.
        bundle_summary: Optional bundle summary.

    Returns:
        Safe file name.
    """
    for field in spec.file_fields:
        file_name = _optional_file_name(bundle_summary.get(field))
        if file_name is not None:
            return file_name
    return _safe_filename(spec.default_file_name)


def _queue_rows(queue_summary: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return queue rows from a queue summary.

    Args:
        queue_summary: Aggregate queue summary.

    Returns:
        Queue row mappings.
    """
    rows = queue_summary.get("queues")
    if not isinstance(rows, list):
        raise OperatorBatchPlanError("Queue summary is missing queues.")
    if not all(isinstance(row, Mapping) for row in rows):
        raise OperatorBatchPlanError("Queue rows must be objects.")
    return rows


def _batch_rows(plan: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return batch rows from a plan.

    Args:
        plan: Batch plan.

    Returns:
        Batch row mappings.
    """
    rows = plan.get("batches")
    if not isinstance(rows, list):
        raise OperatorBatchPlanError("Batch plan is missing batches.")
    if not all(isinstance(row, Mapping) for row in rows):
        raise OperatorBatchPlanError("Batch rows must be objects.")
    return rows


def _load_json_object(path: Path) -> dict[str, Any]:
    """Read and validate one JSON object.

    Args:
        path: JSON object path.

    Returns:
        Parsed JSON object.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise OperatorBatchPlanError("Batch plan inputs must be JSON objects.")
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
        raise OperatorBatchPlanError("Batch plan input schema does not match.")


def _required_input_path(input_paths: Mapping[str, Path], key: str) -> Path:
    """Return a required input path.

    Args:
        input_paths: Input path mapping.
        key: Required key.

    Returns:
        Path for the key.
    """
    path = input_paths.get(key)
    if path is None:
        raise OperatorBatchPlanError("Required batch plan input is missing.")
    return path


def _reject_unsafe_true_flags(payload: Mapping[str, Any]) -> None:
    """Reject unsafe boolean flags set to true.

    Args:
        payload: Parsed input payload.
    """
    for key in UNSAFE_TRUE_FLAGS:
        if payload.get(key) is True:
            raise OperatorBatchPlanError("Batch plan input has an unsafe true flag.")


def _reject_unsafe_payload(value: Any) -> None:
    """Reject raw data keys and local path literals recursively.

    Args:
        value: JSON-like payload.
    """
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in RAW_FORBIDDEN_KEYS:
                raise OperatorBatchPlanError("Unsafe raw/provider key found.")
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
        raise OperatorBatchPlanError("Unsafe local path marker found.")


def _validate_source_doc_urls(value: Any) -> None:
    """Validate known official documentation URLs.

    Args:
        value: Candidate URL list.
    """
    if not isinstance(value, list):
        raise OperatorBatchPlanError("source_doc_urls must be a list.")
    allowed = set(SOURCE_DOC_URLS)
    for item in value:
        if item not in allowed:
            raise OperatorBatchPlanError("Unexpected source documentation URL.")


def _batch_size_arg(raw_value: str) -> int:
    """Validate a CLI batch size.

    Args:
        raw_value: Candidate CLI value.

    Returns:
        Validated batch size.

    Raises:
        argparse.ArgumentTypeError: If the value is outside the allowed range.
    """
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("batch-size must be an integer") from exc
    if value < MIN_BATCH_SIZE or value > MAX_BATCH_SIZE:
        raise argparse.ArgumentTypeError(
            f"batch-size must be between {MIN_BATCH_SIZE} and {MAX_BATCH_SIZE}"
        )
    return value


def _safe_filename(value: str) -> str:
    """Return a safe file name.

    Args:
        value: Candidate file name.

    Returns:
        Safe file name.
    """
    cleaned = value.strip()
    if not cleaned:
        raise OperatorBatchPlanError("File name cannot be blank.")
    if any(marker in cleaned for marker in LOCAL_PATH_MARKERS) or "/" in cleaned or "\\" in cleaned:
        raise OperatorBatchPlanError("Unsafe file name contains a path marker.")
    if len(cleaned) > MAX_SAFE_FILENAME_LENGTH:
        raise OperatorBatchPlanError("File name is too long.")
    return cleaned


def _optional_file_name(value: object) -> str | None:
    """Return an optional safe file name.

    Args:
        value: Candidate value.

    Returns:
        Safe file name or None.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    return _safe_filename(value)


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
        raise OperatorBatchPlanError("Unsafe token contains a path marker.")
    return cleaned[:120]


def _optional_safe_token(value: object) -> str | None:
    """Return an optional safe token.

    Args:
        value: Candidate value.

    Returns:
        Safe token or None.
    """
    if value is None:
        return None
    return _safe_token(str(value))


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


def _cli_summary(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Return compact CLI-safe summary.

    Args:
        plan: Full batch plan.

    Returns:
        CLI summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "batch_size": _non_negative_int(plan.get("batch_size")),
        "batch_count": _non_negative_int(plan.get("batch_count")),
        "pending_queue_count": _non_negative_int(plan.get("pending_queue_count")),
        "total_pending_operator_action_count": _non_negative_int(
            plan.get("total_pending_operator_action_count")
        ),
        "next_queue_key": plan.get("next_queue_key"),
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
            key: _sha256_text(str(path.expanduser())) for key, path in sorted(input_paths.items())
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
