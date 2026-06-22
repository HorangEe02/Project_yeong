"""Build a redacted post-completion command plan for operator review batches.

This planner turns the current next-batch work order into queue-specific
post-completion steps. It intentionally emits script keys and artifact roles
instead of shell commands, absolute paths, row payloads, OCR text, provider
payloads, or source refs.

The planner does not reconcile files, write to the database, call OCR/LLM
providers, materialize datasets, or train models. It only records the sequence
that should be followed after an operator-local batch preflight reports
``ready_for_reconcile=true``.
"""

from __future__ import annotations

import argparse
import json
import re
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

from scripts import build_supplement_operator_next_batch_work_order as work_order  # noqa: E402

SCHEMA_VERSION = "supplement-operator-post-completion-command-plan-v1"
WORK_ORDER_SCHEMA_VERSION = work_order.SCHEMA_VERSION
MAX_SAFE_PHRASE_LENGTH = 240
SAFE_TOKEN_PATTERN = re.compile(r"^[0-9A-Za-z가-힣_.:-]{1,200}$")
LOCAL_PATH_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    "file://",
    "\\Users\\",
    "\\Volumes\\",
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
        "image_path",
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
        "source_ref",
        "url",
    }
)
QUEUE_ORDER = (
    "brand_product_review",
    "review_pii_screening",
    "yolo_section_annotation",
)


class PostCompletionPlanError(ValueError):
    """Raised when a post-completion plan cannot be trusted."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-order", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write a redacted post-completion command plan.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    input_paths = {"work_order": args.work_order.expanduser().resolve()}
    output_path = args.output.expanduser().resolve()
    markdown_output = (
        args.markdown_output.expanduser().resolve() if args.markdown_output is not None else None
    )
    try:
        summary = build_post_completion_command_plan(input_paths=input_paths)
        _write_json(output_path, summary)
        if markdown_output is not None:
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            markdown_output.write_text(build_plan_markdown(summary), encoding="utf-8")
        print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    except (OSError, json.JSONDecodeError, PostCompletionPlanError) as exc:
        failure = _failure_summary(input_paths=input_paths, output_path=output_path, error=exc)
        _write_json(output_path, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None


def build_post_completion_command_plan(*, input_paths: Mapping[str, Path]) -> dict[str, Any]:
    """Build a redacted command plan for the work order's queue.

    Args:
        input_paths: Mapping with a ``work_order`` JSON path.

    Returns:
        Redacted post-completion plan.
    """
    path = _required_input(input_paths, "work_order")
    payload = _load_json_object(path)
    _require_schema(payload, WORK_ORDER_SCHEMA_VERSION)
    _reject_unsafe_payload(payload)
    queue_key = _queue_key(payload.get("queue_key"))
    batch_key = _safe_token(str(payload.get("batch_key") or "unknown"))
    batch_status = _safe_token(str(payload.get("batch_status") or "unknown"))
    counts = {
        "blank_row_count": _non_negative_int(payload.get("blank_row_count")),
        "pending_row_count": _non_negative_int(payload.get("pending_row_count")),
        "invalid_row_count": _non_negative_int(payload.get("invalid_row_count")),
        "missing_row_count": _non_negative_int(payload.get("missing_row_count")),
    }
    blocker_codes = _post_completion_blocker_codes(
        batch_status=batch_status,
        counts=counts,
    )
    execution_allowed = not blocker_codes
    queue_steps = _queue_steps(queue_key)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "input_name": path.name,
        "input_path_fingerprint": _path_fingerprint(path),
        "batch_key": batch_key,
        "queue_key": queue_key,
        "batch_status": batch_status,
        "post_completion_execution_allowed": execution_allowed,
        "operator_required_before_execution": not execution_allowed,
        "blocked_reason_codes": blocker_codes,
        "row_counts": counts,
        "step_count": len(queue_steps),
        "steps": queue_steps,
        "common_safety_rules": _common_safety_rules(queue_key),
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_image_read_performed": False,
        "source_rows_read": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def build_plan_markdown(summary: Mapping[str, Any]) -> str:
    """Build a redacted Markdown command plan.

    Args:
        summary: Plan summary.

    Returns:
        Markdown text.
    """
    _reject_unsafe_payload(summary)
    rows = [
        "| {index} | {script} | {purpose} | {gate} |".format(
            index=_non_negative_int(row.get("order")),
            script=_safe_token(str(row.get("script_key") or "unknown")),
            purpose=_safe_phrase(str(row.get("purpose") or "unknown")),
            gate=_safe_token(str(row.get("gate_policy") or "unknown")),
        )
        for row in _steps(summary.get("steps"))
    ]
    blockers = _markdown_bullets(summary.get("blocked_reason_codes"))
    safety_rules = _markdown_bullets(summary.get("common_safety_rules"))
    markdown = "\n".join(
        [
            "# Supplement Operator Post-Completion Command Plan",
            "",
            f"Schema: `{SCHEMA_VERSION}`",
            "",
            "This plan uses script keys and artifact roles only. It omits shell paths, row payloads, OCR text, provider payloads, source refs, and labels.",
            "",
            f"- Batch: `{_safe_token(str(summary.get('batch_key') or 'unknown'))}`",
            f"- Queue: `{_safe_token(str(summary.get('queue_key') or 'unknown'))}`",
            f"- Batch status: `{_safe_token(str(summary.get('batch_status') or 'unknown'))}`",
            f"- Execution allowed: `{_bool_text(summary.get('post_completion_execution_allowed'))}`",
            "",
            "## Blockers",
            "",
            blockers,
            "",
            "## Steps",
            "",
            "| # | Script key | Purpose | Gate policy |",
            "| ---: | --- | --- | --- |",
            *rows,
            "",
            "## Safety Rules",
            "",
            safety_rules,
            "",
        ]
    )
    _reject_unsafe_payload(markdown)
    return markdown


def _queue_steps(queue_key: str) -> list[dict[str, Any]]:
    """Return post-completion steps for one queue.

    Args:
        queue_key: Queue key.

    Returns:
        Ordered command plan steps.
    """
    if queue_key == "brand_product_review":
        pre_common = [
            _step(
                1,
                "preflight_supplement_brand_review_contact_sheet",
                "confirm csv and contact sheet row alignment",
                ("batch_review_csv", "contact_sheet_summary"),
                ("contact_sheet_preflight_summary",),
                "must_pass_before_csv_apply",
            ),
            _step(
                2,
                "build_supplement_brand_review_batch_triage",
                "summarize csv review priority without decisions",
                ("batch_review_csv",),
                ("brand_review_batch_triage_summary",),
                "operator_review_helper_no_decision",
            ),
            _step(
                3,
                "apply_supplement_brand_batch_review_csv_decisions",
                "copy fully reviewed csv fields into a batch jsonl copy",
                ("operator_batch_file", "batch_review_csv"),
                ("operator_batch_jsonl_copy", "csv_apply_summary"),
                "require_all_reviewed_no_source_overwrite",
            ),
        ]
        common = _common_steps(start_order=4)
        specific = [
            _step(
                7,
                "extract_supplement_brand_reviewed_decisions",
                "separate reviewed brand decisions from blank queue stubs",
                ("reconciled_brand_decisions",),
                ("reviewed_brand_decisions", "reviewed_brand_extract_summary"),
                "partial_preview_only",
            ),
            _step(
                8,
                "preflight_supplement_brand_review_decisions",
                "check strict brand decision readiness",
                ("reconciled_brand_decisions",),
                ("brand_decision_preflight_summary",),
                "strict_zero_blank_pending_invalid_required",
            ),
            _step(
                9,
                "gate_supplement_brand_db_import",
                "gate product import manifest preparation",
                ("brand_decision_preflight_summary",),
                ("brand_db_import_gate_summary",),
                "must_pass_before_product_manifest",
            ),
            _step(
                10,
                "apply_supplement_brand_review_decisions",
                "create approved product import manifest",
                ("reviewed_brand_decisions",),
                ("approved_product_import_manifest", "brand_apply_summary"),
                "dry_run_or_manifest_only_before_db_gate",
            ),
            _step(
                11,
                "import_supplement_taxonomy_approved_manifest",
                "dry run category product and mapping import",
                ("taxonomy_staging", "approved_product_import_manifest"),
                ("taxonomy_import_dry_run_summary",),
                "dry_run_before_product_db_apply",
            ),
            _step(
                12,
                "gate_supplement_product_db_apply",
                "gate reviewed product db apply",
                ("brand_db_import_gate_summary", "taxonomy_import_dry_run_summary"),
                ("product_db_apply_gate_summary",),
                "must_pass_before_db_apply",
            ),
            _step(
                13,
                "verify_supplement_taxonomy_db_import",
                "verify imported categories products and mappings",
                ("taxonomy_staging", "approved_product_import_manifest"),
                ("taxonomy_db_import_verification_summary",),
                "read_only_after_apply",
            ),
        ]
        return pre_common + common + specific
    if queue_key == "review_pii_screening":
        common = _common_steps(start_order=1)
        specific = [
            _step(
                4,
                "extract_supplement_pii_reviewed_decisions",
                "separate reviewed pii decisions from blank queue stubs",
                ("reconciled_pii_decisions",),
                ("reviewed_pii_decisions", "reviewed_pii_extract_summary"),
                "partial_teacher_ocr_preview_only",
            ),
            _step(
                5,
                "preflight_supplement_review_pii_screening_decisions",
                "check strict pii decision readiness",
                ("reconciled_pii_decisions",),
                ("pii_decision_preflight_summary",),
                "strict_zero_blank_pending_invalid_required",
            ),
            _step(
                6,
                "apply_supplement_review_pii_screening_decisions",
                "unlock pii cleared rows for teacher ocr comparison",
                ("reviewed_pii_decisions", "ocr_candidate_manifest"),
                ("teacher_safe_ocr_candidates", "pii_apply_summary"),
                "no_teacher_ocr_call",
            ),
            _step(
                7,
                "export_supplement_ocr_ground_truth_template",
                "create local manual ocr ground truth template from pii cleared rows",
                ("teacher_safe_ocr_candidates",),
                (
                    "ocr_ground_truth_template",
                    "ocr_ground_truth_template_summary",
                    "private_ground_truth_image_fixtures",
                ),
                "manual_gt_template_only_no_provider_call",
            ),
            _step(
                8,
                "build_supplement_ocr_ground_truth_review_bundle",
                "build editable ocr ground truth bundle for operator review",
                ("ocr_ground_truth_template",),
                ("human_reviewed_ground_truth", "gt_bundle_summary"),
                "operator_edits_required_before_preflight",
            ),
            _step(
                9,
                "preflight_supplement_ocr_ground_truth_manifest",
                "check operator edited ocr ground truth before benchmark build",
                ("human_reviewed_ground_truth",),
                ("ground_truth_preflight_summary",),
                "must_pass_before_ocr_benchmark_manifest",
            ),
            _step(
                10,
                "build_supplement_ocr_benchmark_manifest",
                "materialize human reviewed ocr benchmark fixtures",
                ("teacher_safe_ocr_candidates", "human_reviewed_ground_truth"),
                ("ocr_benchmark_manifest", "ocr_benchmark_manifest_summary"),
                "pii_cleared_human_gt_only",
            ),
            _step(
                11,
                "assign_paddleocr_benchmark_splits",
                "assign leakage safe benchmark splits by product hash",
                ("ocr_benchmark_manifest",),
                ("ocr_benchmark_split_manifest", "benchmark_split_summary"),
                "must_pass_before_provider_observations",
            ),
            _step(
                12,
                "gate_supplement_ocr_benchmark",
                "assert pii manual ground truth benchmark and split gates before teacher ocr",
                (
                    "pii_decision_preflight_summary",
                    "gt_bundle_summary",
                    "ground_truth_preflight_summary",
                    "benchmark_summary",
                    "benchmark_split_summary",
                ),
                ("ocr_benchmark_gate_summary",),
                "must_pass_before_teacher_ocr_eval",
            ),
            _step(
                13,
                "collect_supplement_ocr_observations",
                "collect clova google vision and paddleocr observations",
                ("ocr_benchmark_split_manifest",),
                ("redacted_provider_observations",),
                "external_ocr_requires_explicit_env_opt_in",
            ),
            _step(
                14,
                "merge_paddleocr_text_observations_into_benchmark",
                "join redacted observations into benchmark fixtures",
                ("ocr_benchmark_split_manifest", "redacted_provider_observations"),
                ("ocr_metric_benchmark_manifest", "ocr_metric_benchmark_summary"),
                "no_raw_ocr_merge",
            ),
            _step(
                15,
                "preflight_paddleocr_text_target_chain",
                "check heldout paddleocr metrics before final target gate",
                ("ocr_metric_benchmark_manifest",),
                ("paddleocr_text_target_chain_preflight",),
                "must_pass_before_text_eval_summary",
            ),
            _step(
                16,
                "build_paddleocr_text_extraction_eval_summary",
                "build redacted paddleocr heldout text eval summary",
                ("ocr_metric_benchmark_manifest",),
                ("paddleocr_text_extraction_eval_summary",),
                "privacy_cleared_human_gt_required",
            ),
            _step(
                17,
                "gate_paddleocr_text_extraction_target",
                "stop paddleocr training only if the 95 percent target is reached",
                ("paddleocr_text_extraction_eval_summary",),
                ("paddleocr_text_extraction_target_gate",),
                "stop_training_only_if_95_percent_target_reached",
            ),
        ]
        return common + specific
    if queue_key == "yolo_section_annotation":
        common = _common_steps(start_order=1)
        specific = [
            _step(
                4,
                "extract_supplement_yolo_reviewed_annotations",
                "separate reviewed yolo annotations from blank queue stubs",
                ("source_yolo_template", "reconciled_yolo_annotations"),
                ("reviewed_yolo_annotations", "reviewed_yolo_extract_summary"),
                "partial_dataset_preview_only",
            ),
            _step(
                5,
                "preflight_supplement_yolo_annotation_decisions",
                "check strict yolo annotation readiness",
                ("reconciled_yolo_annotations",),
                ("yolo_annotation_preflight_summary",),
                "strict_zero_blank_pending_invalid_required",
            ),
            _step(
                6,
                "promote_supplement_yolo_annotation_template",
                "promote reviewed section boxes into yolo export",
                ("reconciled_yolo_annotations",),
                ("yolo_export_manifest", "yolo_source_map", "yolo_promotion_summary"),
                "only_after_strict_annotation_preflight",
            ),
            _step(
                7,
                "materialize_supplement_section_yolo_dataset",
                "write ultralytics yolo image and label files",
                ("yolo_export_manifest", "yolo_source_map"),
                ("materialized_yolo_dataset", "materialize_summary"),
                "no_training_execution",
            ),
            _step(
                8,
                "validate_supplement_section_yolo_dataset",
                "validate materialized yolo dataset files",
                ("materialized_yolo_dataset",),
                ("yolo_dataset_validation_summary",),
                "must_pass_before_training_gate",
            ),
            _step(
                9,
                "gate_supplement_yolo_section_dataset",
                "gate yolo26 section dataset training readiness",
                (
                    "yolo_annotation_preflight_summary",
                    "yolo_promotion_summary",
                    "materialize_summary",
                    "yolo_dataset_validation_summary",
                ),
                ("yolo_section_dataset_gate_summary",),
                "must_pass_before_training",
            ),
        ]
        return common + specific
    raise PostCompletionPlanError("Unsupported queue key.")


def _common_safety_rules(queue_key: str) -> list[str]:
    """Return safety rules that apply to one queue.

    Args:
        queue_key: Queue key.

    Returns:
        Ordered safe rule tokens.
    """
    rules = [
        "run_local_batch_preflight_first",
        "run_reconcile_before_queue_preflight",
        "never_apply_or_promote_until_strict_gate_passes",
        "keep_raw_ocr_provider_payload_and_local_paths_out_of_outputs",
    ]
    if queue_key == "brand_product_review":
        return [
            "brand_csv_apply_requires_contact_sheet_preflight_and_all_rows_reviewed",
            *rules,
        ]
    return rules


def _common_steps(*, start_order: int) -> list[dict[str, Any]]:
    """Return common post-edit queue reconcile steps.

    Args:
        start_order: First common step order.

    Returns:
        Common command plan steps.
    """
    return [
        _step(
            start_order,
            "preflight_supplement_operator_review_batch_file",
            "confirm operator local batch is complete",
            ("batch_plan", "operator_batch_file"),
            ("batch_file_preflight_summary",),
            "must_pass_before_reconcile",
        ),
        _step(
            start_order + 1,
            "reconcile_supplement_operator_review_batch_files",
            "merge completed batch into reconciled queue copies",
            ("batch_plan", "source_editable_queue_files", "operator_batch_dir"),
            ("reconciled_queue_files", "reconcile_summary"),
            "no_source_overwrite",
        ),
        _step(
            start_order + 2,
            "preflight_supplement_operator_review_batch_progress",
            "confirm queue level batch progress after reconcile",
            ("batch_plan", "reconciled_queue_files"),
            ("batch_progress_summary",),
            "must_pass_before_queue_preflight",
        ),
    ]


def _path_fingerprint(path: Path) -> str:
    """Return a short non-secret path fingerprint for public artifacts.

    Args:
        path: Path to identify without exposing it.

    Returns:
        Short hexadecimal fingerprint.
    """
    return f"fp-{work_order.progress_preflight._sha256_text(str(path.expanduser()))[:8]}"


def _step(
    order: int,
    script_key: str,
    purpose: str,
    input_roles: Sequence[str],
    output_roles: Sequence[str],
    gate_policy: str,
) -> dict[str, Any]:
    """Build one safe step object.

    Args:
        order: One-based execution order.
        script_key: Script key without path separators.
        purpose: Human-readable purpose.
        input_roles: Logical input artifact roles.
        output_roles: Logical output artifact roles.
        gate_policy: Gate policy token.

    Returns:
        Safe step dictionary.
    """
    return {
        "order": order,
        "script_key": _safe_token(script_key),
        "purpose": _safe_phrase(purpose),
        "input_roles": [_safe_token(role) for role in input_roles],
        "output_roles": [_safe_token(role) for role in output_roles],
        "gate_policy": _safe_token(gate_policy),
    }


def _post_completion_blocker_codes(*, batch_status: str, counts: Mapping[str, int]) -> list[str]:
    """Return blocker reason codes for post-completion execution.

    Args:
        batch_status: Current work-order batch status.
        counts: Aggregate row counts.

    Returns:
        Safe blocker codes.
    """
    blockers: list[str] = []
    if batch_status != "complete":
        blockers.append("batch_not_complete")
    for key, reason in (
        ("blank_row_count", "blank_rows_remaining"),
        ("pending_row_count", "pending_rows_remaining"),
        ("invalid_row_count", "invalid_rows_remaining"),
        ("missing_row_count", "missing_rows_remaining"),
    ):
        if _non_negative_int(counts.get(key)) > 0:
            blockers.append(reason)
    return blockers


def _required_input(input_paths: Mapping[str, Path], key: str) -> Path:
    """Return a required input path.

    Args:
        input_paths: Input mapping.
        key: Required key.

    Returns:
        Input path.
    """
    value = input_paths.get(key)
    if value is None:
        raise PostCompletionPlanError("Required post-completion plan input is missing.")
    return value


def _load_json_object(path: Path) -> dict[str, Any]:
    """Load a JSON object.

    Args:
        path: Input path.

    Returns:
        JSON object.
    """
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PostCompletionPlanError("Post-completion plan input must be a JSON object.")
    return value


def _require_schema(payload: Mapping[str, Any], expected: str) -> None:
    """Validate schema version.

    Args:
        payload: JSON object.
        expected: Expected schema version.
    """
    if payload.get("schema_version") != expected:
        raise PostCompletionPlanError("Post-completion plan input schema is unsupported.")


def _queue_key(value: object) -> str:
    """Validate a queue key.

    Args:
        value: Candidate value.

    Returns:
        Queue key.
    """
    queue_key = _safe_token(str(value or ""))
    if queue_key not in QUEUE_ORDER:
        raise PostCompletionPlanError("Unsupported queue key.")
    return queue_key


def _steps(value: object) -> list[Mapping[str, Any]]:
    """Return summary steps.

    Args:
        value: Candidate value.

    Returns:
        Step mappings.
    """
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _safe_token(value: str) -> str:
    """Return a safe token.

    Args:
        value: Candidate token.

    Returns:
        Safe token.
    """
    if not SAFE_TOKEN_PATTERN.fullmatch(value):
        raise PostCompletionPlanError("Unsafe token in post-completion plan.")
    return value


def _safe_phrase(value: str) -> str:
    """Return a safe human phrase.

    Args:
        value: Candidate phrase.

    Returns:
        Safe phrase.
    """
    if "://" in value or any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise PostCompletionPlanError("Unsafe phrase in post-completion plan.")
    if "/" in value or "\\" in value:
        raise PostCompletionPlanError("Unsafe phrase in post-completion plan.")
    if len(value) > MAX_SAFE_PHRASE_LENGTH:
        raise PostCompletionPlanError("Post-completion plan phrase is too long.")
    return value


def _non_negative_int(value: object) -> int:
    """Return a non-negative integer.

    Args:
        value: Candidate value.

    Returns:
        Non-negative integer.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PostCompletionPlanError("Expected a non-negative integer.")
    return value


def _reject_unsafe_payload(value: Any) -> None:
    """Reject paths, raw data keys, source refs, URLs, and secrets.

    Args:
        value: JSON-like value.
    """
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key in RAW_FORBIDDEN_KEYS:
                raise PostCompletionPlanError("Unsafe key in post-completion plan payload.")
            _reject_unsafe_payload(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_unsafe_payload(nested)
    elif isinstance(value, str) and (
        "://" in value
        or value.startswith("/")
        or any(marker in value for marker in LOCAL_PATH_MARKERS)
    ):
        raise PostCompletionPlanError("Unsafe string in post-completion plan payload.")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write one JSON object.

    Args:
        path: Output path.
        payload: JSON payload.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _markdown_bullets(value: object) -> str:
    """Render tokens as Markdown bullets.

    Args:
        value: Candidate list.

    Returns:
        Markdown bullet text.
    """
    if not isinstance(value, list) or not value:
        return "- `none`"
    return "\n".join(f"- `{_safe_token(str(item))}`" for item in value)


def _bool_text(value: object) -> str:
    """Return bool as lower-case text.

    Args:
        value: Candidate bool.

    Returns:
        ``true`` or ``false``.
    """
    return "true" if value is True else "false"


def _cli_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Return stdout-safe summary.

    Args:
        summary: Full summary.

    Returns:
        Compact summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "batch_key": summary["batch_key"],
        "queue_key": summary["queue_key"],
        "batch_status": summary["batch_status"],
        "post_completion_execution_allowed": summary["post_completion_execution_allowed"],
        "blocked_reason_codes": summary["blocked_reason_codes"],
        "step_count": summary["step_count"],
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_image_read_performed": False,
    }


def _failure_summary(
    *,
    input_paths: Mapping[str, Path],
    output_path: Path,
    error: Exception,
) -> dict[str, Any]:
    """Return redacted failure summary.

    Args:
        input_paths: Input path mapping.
        output_path: Planned output path.
        error: Raised exception.

    Returns:
        Failure summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "output_name": output_path.name,
        "error_code": _safe_error_code(error),
        "error_message": _safe_error_message(error),
        "post_completion_execution_allowed": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_image_read_performed": False,
    }


def _safe_error_code(error: Exception) -> str:
    """Return a safe error code.

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


def _safe_error_message(error: Exception) -> str:
    """Return a safe error message.

    Args:
        error: Raised exception.

    Returns:
        Error message.
    """
    if isinstance(error, OSError):
        return "Local file read failed."
    message = str(error).strip() or "Validation failed."
    if "/" in message or "\\" in message or any(marker in message for marker in LOCAL_PATH_MARKERS):
        return "Validation failed."
    return message[:160]


if __name__ == "__main__":
    main()
