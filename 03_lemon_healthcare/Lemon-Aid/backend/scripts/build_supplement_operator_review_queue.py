"""Build a redacted operator queue for supplement learning review gates.

This tool reads only redacted preflight/readiness JSON summaries and produces a
single operator-facing queue for the manual review gates that currently block
taxonomy DB import, review-image OCR ground truth, and supplement-section YOLO
promotion.

It does not read source images, OCR JSONL rows, provider payloads, model
responses, or database records. It does not write to the database, does not call
OCR/LLM providers, and does not train or promote a model.

References:
    https://docs.ultralytics.com/datasets/detect/
    https://docs.ultralytics.com/tasks/detect/
    https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
    https://supabase.com/docs/guides/database/postgres/row-level-security
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

SCHEMA_VERSION = "supplement-operator-review-queue-summary-v1"
MARKDOWN_SCHEMA_VERSION = "supplement-operator-review-queue-markdown-v1"
BRAND_PREFLIGHT_SCHEMA = "supplement-brand-review-decision-preflight-v1"
PII_PREFLIGHT_SCHEMA = "supplement-review-pii-screening-decision-preflight-v1"
YOLO_PREFLIGHT_SCHEMA = "supplement-yolo-annotation-decision-preflight-v1"
READINESS_SCHEMA = "supplement-learning-pipeline-readiness-v1"
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
LOCAL_PATH_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    "file://",
    "\\Users\\",
    "\\Volumes\\",
)
UNSAFE_TRUE_FLAGS = (
    "absolute_paths_stored",
    "db_write_performed",
    "export_artifact_written",
    "external_provider_call_performed",
    "image_path_printed",
    "labels_printed",
    "llm_call_performed",
    "local_absolute_path_printed",
    "local_path_literals_stored",
    "ocr_provider_call_performed",
    "paddleocr_training_performed",
    "product_dir_literals_stored",
    "product_literal_printed",
    "raw_ocr_text_stored",
    "raw_provider_payload_stored",
    "source_ref_printed",
    "training_execution_performed_by_script",
    "training_performed",
)


class OperatorReviewQueueError(ValueError):
    """Raised when operator review queue input cannot be trusted."""


@dataclass(frozen=True)
class QueueSpec:
    """Static mapping from a preflight artifact to one operator queue.

    Args:
        queue_key: Stable queue identifier.
        input_key: CLI input key.
        expected_schema: Required input schema version.
        stage_key: Readiness stage key.
        total_field: Field holding total rows needing review.
        pending_field: Field holding pending operator action count.
        blank_field: Field holding blank decision/box count.
        valid_field: Field holding reviewed/valid row count.
        ready_field: Field holding next-step readiness.
        next_artifact_role: Artifact role produced after this queue is completed.
        bundle_artifact_role: Existing local bundle role operators edit.
        operator_action: Human action code.
    """

    queue_key: str
    input_key: str
    expected_schema: str
    stage_key: str
    total_field: str
    pending_field: str
    blank_field: str
    valid_field: str
    ready_field: str
    next_artifact_role: str
    bundle_artifact_role: str
    operator_action: str


QUEUE_SPECS = (
    QueueSpec(
        queue_key="brand_product_review",
        input_key="brand_preflight",
        expected_schema=BRAND_PREFLIGHT_SCHEMA,
        stage_key="brand_product_review",
        total_field="brand_candidate_count",
        pending_field="pending_operator_action_count",
        blank_field="blank_decision_count",
        valid_field="valid_decision_count",
        ready_field="ready_for_requested_apply",
        next_artifact_role="approved_product_import",
        bundle_artifact_role="brand_review_bundle",
        operator_action="complete_operator_brand_review",
    ),
    QueueSpec(
        queue_key="review_pii_screening",
        input_key="pii_preflight",
        expected_schema=PII_PREFLIGHT_SCHEMA,
        stage_key="review_pii_screening",
        total_field="candidate_row_count",
        pending_field="pending_operator_action_count",
        blank_field="blank_decision_count",
        valid_field="valid_decision_count",
        ready_field="ready_for_requested_apply",
        next_artifact_role="pii_screening_apply",
        bundle_artifact_role="pii_screening_review_bundle",
        operator_action="complete_operator_pii_review",
    ),
    QueueSpec(
        queue_key="yolo_section_annotation",
        input_key="yolo_preflight",
        expected_schema=YOLO_PREFLIGHT_SCHEMA,
        stage_key="yolo_section_annotation",
        total_field="template_row_count",
        pending_field="pending_operator_action_count",
        blank_field="blank_box_row_count",
        valid_field="valid_accepted_row_count",
        ready_field="ready_for_requested_promotion",
        next_artifact_role="yolo_template_promotion",
        bundle_artifact_role="yolo_annotation_review_bundle",
        operator_action="complete_supplement_section_bbox_review",
    ),
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brand-preflight", type=Path, required=True)
    parser.add_argument("--pii-preflight", type=Path, required=True)
    parser.add_argument("--yolo-preflight", type=Path, required=True)
    parser.add_argument("--readiness", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write a redacted review queue summary and optional Markdown runbook.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    input_paths = {
        "brand_preflight": args.brand_preflight.expanduser().resolve(),
        "pii_preflight": args.pii_preflight.expanduser().resolve(),
        "yolo_preflight": args.yolo_preflight.expanduser().resolve(),
    }
    if args.readiness is not None:
        input_paths["readiness"] = args.readiness.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    markdown_output = (
        args.markdown_output.expanduser().resolve() if args.markdown_output is not None else None
    )
    try:
        summary = build_operator_review_queue(input_paths=input_paths)
        _write_json(output_path, summary)
        if markdown_output is not None:
            markdown = build_operator_review_markdown(summary)
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            markdown_output.write_text(markdown, encoding="utf-8")
        print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    except (OSError, json.JSONDecodeError, OperatorReviewQueueError) as exc:
        failure = _failure_summary(input_paths=input_paths, output_path=output_path, error=exc)
        _write_json(output_path, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None


def build_operator_review_queue(*, input_paths: Mapping[str, Path]) -> dict[str, Any]:
    """Build a redacted aggregate queue from preflight summaries.

    Args:
        input_paths: Mapping from expected input keys to summary JSON paths.

    Returns:
        Redacted queue summary.

    Raises:
        OperatorReviewQueueError: If an input is missing, unsafe, or has the
            wrong schema version.
    """
    payloads = _load_inputs(input_paths)
    readiness = payloads.get("readiness")
    stage_statuses = _stage_statuses(readiness)
    queues = [
        _queue_row(spec, payload=payloads[spec.input_key], stage_statuses=stage_statuses)
        for spec in QUEUE_SPECS
    ]
    total_pending = sum(
        _non_negative_int(queue["pending_operator_action_count"]) for queue in queues
    )
    ready_queue_count = sum(1 for queue in queues if queue["ready_for_next_step"] is True)
    queue_count = len(queues)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_hashes": {
            key: _sha256_text(str(path.expanduser())) for key, path in sorted(input_paths.items())
        },
        "queue_count": queue_count,
        "ready_queue_count": ready_queue_count,
        "pending_queue_count": queue_count - ready_queue_count,
        "total_pending_operator_action_count": total_pending,
        "ready_for_next_pipeline_step": total_pending == 0 and ready_queue_count == queue_count,
        "next_queue_key": _next_queue_key(queues),
        "queues": queues,
        "readiness_summary_attached": readiness is not None,
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


def build_operator_review_markdown(summary: Mapping[str, Any]) -> str:
    """Build a redacted Markdown runbook for the operator queue.

    Args:
        summary: Queue summary from ``build_operator_review_queue``.

    Returns:
        Markdown text without local paths or raw data.
    """
    _reject_unsafe_payload(summary)
    rows = []
    for queue in _queue_list(summary):
        rows.append(
            "| {queue_key} | {status} | {total} | {pending} | {blank} | {valid} | {action} |".format(
                queue_key=_safe_token(str(queue["queue_key"])),
                status=_safe_token(str(queue["queue_status"])),
                total=_non_negative_int(queue.get("total_review_row_count")),
                pending=_non_negative_int(queue.get("pending_operator_action_count")),
                blank=_non_negative_int(queue.get("blank_row_count")),
                valid=_non_negative_int(queue.get("valid_reviewed_row_count")),
                action=_safe_token(str(queue["next_operator_action"])),
            )
        )
    markdown = "\n".join(
        [
            "# Supplement Operator Review Queue",
            "",
            f"Schema: `{MARKDOWN_SCHEMA_VERSION}`",
            "",
            "이 문서는 redacted summary만 기반으로 합니다. 원본 이미지, OCR 원문, provider payload, 로컬 경로, 제품 폴더 literal은 포함하지 않습니다.",
            "",
            f"- Queue count: `{_non_negative_int(summary.get('queue_count'))}`",
            f"- Pending operator action count: `{_non_negative_int(summary.get('total_pending_operator_action_count'))}`",
            f"- Next queue: `{_safe_token(str(summary.get('next_queue_key') or 'none'))}`",
            "",
            "| Queue | Status | Total | Pending | Blank | Valid | Next action |",
            "| --- | --- | ---: | ---: | ---: | ---: | --- |",
            *rows,
            "",
            "## Safe Next Steps",
            "",
            "1. 각 local review bundle에서 사람이 decision 또는 bbox를 채웁니다.",
            "2. 해당 preflight를 다시 실행해 invalid/blank/pending count가 0인지 확인합니다.",
            "3. 통과한 queue만 apply 또는 promotion 스크립트로 다음 artifact를 생성합니다.",
            "4. 전체 readiness report를 다시 생성해 downstream gate 상태를 갱신합니다.",
            "",
        ]
    )
    _reject_unsafe_payload(markdown)
    return markdown


def _load_inputs(input_paths: Mapping[str, Path]) -> dict[str, dict[str, Any]]:
    """Load and validate all configured inputs.

    Args:
        input_paths: Input key to JSON path mapping.

    Returns:
        Input payloads keyed by input key.
    """
    required = {spec.input_key for spec in QUEUE_SPECS}
    missing = sorted(required - set(input_paths))
    if missing:
        raise OperatorReviewQueueError("Required preflight input is missing.")
    payloads = {key: _load_json_object(path) for key, path in sorted(input_paths.items())}
    for spec in QUEUE_SPECS:
        _require_schema(payloads[spec.input_key], spec.expected_schema)
    if "readiness" in payloads:
        _require_schema(payloads["readiness"], READINESS_SCHEMA)
    return payloads


def _load_json_object(path: Path) -> dict[str, Any]:
    """Read one JSON object and reject unsafe content.

    Args:
        path: JSON object path.

    Returns:
        Parsed JSON object.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise OperatorReviewQueueError("Review queue inputs must be JSON objects.")
    _reject_unsafe_payload(payload)
    _reject_unsafe_true_flags(payload)
    return payload


def _require_schema(payload: Mapping[str, Any], expected_schema: str) -> None:
    """Validate one input schema version.

    Args:
        payload: Parsed input payload.
        expected_schema: Required schema version.

    Raises:
        OperatorReviewQueueError: If schema does not match.
    """
    if payload.get("schema_version") != expected_schema:
        raise OperatorReviewQueueError("Review queue input schema does not match.")


def _queue_row(
    spec: QueueSpec,
    *,
    payload: Mapping[str, Any],
    stage_statuses: Mapping[str, str],
) -> dict[str, Any]:
    """Return one redacted queue row.

    Args:
        spec: Static queue definition.
        payload: Preflight payload.
        stage_statuses: Optional readiness stage statuses.

    Returns:
        Queue row.
    """
    total = _non_negative_int(payload.get(spec.total_field))
    pending = _non_negative_int(payload.get(spec.pending_field))
    blank = _non_negative_int(payload.get(spec.blank_field))
    valid = _non_negative_int(payload.get(spec.valid_field))
    invalid = _non_negative_int(payload.get("invalid_decision_count")) + _non_negative_int(
        payload.get("invalid_row_count")
    )
    ready = payload.get(spec.ready_field) is True
    queue_status = _queue_status(ready=ready, pending=pending, blank=blank, invalid=invalid)
    next_action = _safe_token(str(payload.get("next_operator_action") or spec.operator_action))
    row = {
        "queue_key": spec.queue_key,
        "stage_key": spec.stage_key,
        "readiness_stage_status": stage_statuses.get(spec.stage_key, "not_attached"),
        "queue_status": queue_status,
        "bundle_artifact_role": spec.bundle_artifact_role,
        "next_artifact_role": spec.next_artifact_role,
        "total_review_row_count": total,
        "pending_operator_action_count": pending,
        "blank_row_count": blank,
        "valid_reviewed_row_count": valid,
        "invalid_row_count": invalid,
        "ready_for_next_step": ready,
        "next_operator_action": next_action,
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


def _stage_statuses(readiness: Mapping[str, Any] | None) -> dict[str, str]:
    """Return readiness stage statuses by stage key.

    Args:
        readiness: Optional readiness report.

    Returns:
        Stage key to status mapping.
    """
    if readiness is None:
        return {}
    stages = readiness.get("stages")
    if not isinstance(stages, list):
        return {}
    statuses: dict[str, str] = {}
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        stage_key = stage.get("stage_key")
        status = stage.get("status")
        if isinstance(stage_key, str) and isinstance(status, str):
            statuses[_safe_token(stage_key)] = _safe_token(status)
    return statuses


def _queue_status(*, ready: bool, pending: int, blank: int, invalid: int) -> str:
    """Return one queue status token.

    Args:
        ready: Whether the queue is ready for the next pipeline artifact.
        pending: Pending operator action count.
        blank: Blank row count.
        invalid: Invalid row count.

    Returns:
        Status token.
    """
    if invalid:
        return "needs_fix"
    if ready:
        return "ready_for_next_step"
    if pending or blank:
        return "pending_operator_review"
    return "review_needed"


def _next_queue_key(queues: list[dict[str, Any]]) -> str | None:
    """Return the first queue still requiring operator action.

    Args:
        queues: Queue rows in operator order.

    Returns:
        Queue key or None when all queues are ready.
    """
    for queue in queues:
        if queue["ready_for_next_step"] is not True:
            return str(queue["queue_key"])
    return None


def _queue_list(summary: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return queue rows from a summary.

    Args:
        summary: Queue summary.

    Returns:
        Queue row mappings.
    """
    queues = summary.get("queues")
    if not isinstance(queues, list):
        raise OperatorReviewQueueError("Queue summary is missing queues.")
    if not all(isinstance(queue, Mapping) for queue in queues):
        raise OperatorReviewQueueError("Queue rows must be objects.")
    return queues


def _reject_unsafe_true_flags(payload: Mapping[str, Any]) -> None:
    """Reject any unsafe boolean execution/redaction flag set to true.

    Args:
        payload: Parsed input payload.

    Raises:
        OperatorReviewQueueError: If an unsafe flag is true.
    """
    for key in UNSAFE_TRUE_FLAGS:
        if payload.get(key) is True:
            raise OperatorReviewQueueError("Review queue input has an unsafe true flag.")


def _reject_unsafe_payload(value: Any) -> None:
    """Reject raw data keys and local path literals recursively.

    Args:
        value: JSON-like payload.

    Raises:
        OperatorReviewQueueError: If unsafe data is present.
    """
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in RAW_FORBIDDEN_KEYS:
                raise OperatorReviewQueueError("Unsafe raw/provider key found.")
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
        raise OperatorReviewQueueError("Unsafe local path marker found.")


def _validate_source_doc_urls(value: Any) -> None:
    """Validate official documentation URLs.

    Args:
        value: Candidate URL list.

    Raises:
        OperatorReviewQueueError: If URLs are not from the configured official
            documentation references.
    """
    if not isinstance(value, list):
        raise OperatorReviewQueueError("source_doc_urls must be a list.")
    allowed = set(SOURCE_DOC_URLS)
    for item in value:
        if item not in allowed:
            raise OperatorReviewQueueError("Unexpected source documentation URL.")


def _non_negative_int(value: object) -> int:
    """Return a nonnegative integer value.

    Args:
        value: Candidate integer.

    Returns:
        Nonnegative integer.
    """
    if isinstance(value, bool):
        return 0
    if isinstance(value, int) and value >= 0:
        return value
    return 0


def _safe_token(value: str) -> str:
    """Return a bounded token for public output.

    Args:
        value: Candidate token.

    Returns:
        Safe token.
    """
    cleaned = value.strip()
    if not cleaned:
        return "unknown"
    if any(marker in cleaned for marker in LOCAL_PATH_MARKERS) or "/" in cleaned or "\\" in cleaned:
        raise OperatorReviewQueueError("Unsafe token contains a path marker.")
    return cleaned[:120]


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
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _cli_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Return compact CLI-safe summary.

    Args:
        summary: Full queue summary.

    Returns:
        CLI summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "queue_count": _non_negative_int(summary.get("queue_count")),
        "pending_queue_count": _non_negative_int(summary.get("pending_queue_count")),
        "total_pending_operator_action_count": _non_negative_int(
            summary.get("total_pending_operator_action_count")
        ),
        "ready_for_next_pipeline_step": summary.get("ready_for_next_pipeline_step") is True,
        "next_queue_key": summary.get("next_queue_key"),
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
