"""Build a requirement-level completion audit for supplement learning.

This audit maps the original supplement taxonomy/OCR/YOLO/PaddleOCR objective
to current redacted evidence. It is intentionally conservative: a requirement is
complete only when the current readiness report proves the relevant stage is
verified. It does not read source images, source OCR text, provider payloads, LLM
outputs, database records, or local product folder names.

References:
    https://docs.ultralytics.com/datasets/detect/
    https://docs.ultralytics.com/tasks/detect/
    https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
    https://cloud.google.com/vision/docs/ocr
    https://api.ncloud-docs.com/docs/en/ai-application-service-ocr
    https://docs.sqlalchemy.org/en/21/orm/queryguide/select.html
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
    build_supplement_learning_pipeline_readiness_report as readiness_reporter,
)
from scripts import build_supplement_operator_next_batch_work_order as work_order  # noqa: E402
from scripts import (  # noqa: E402
    build_supplement_operator_post_completion_command_plan as post_completion,
)
from scripts import (  # noqa: E402
    preflight_supplement_operator_review_batch_progress as progress_preflight,
)

SCHEMA_VERSION = "supplement-learning-completion-audit-v1"
READINESS_SCHEMA = readiness_reporter.SCHEMA_VERSION
BATCH_PROGRESS_SCHEMA = progress_preflight.SCHEMA_VERSION
WORK_ORDER_SCHEMA = work_order.SCHEMA_VERSION
POST_COMPLETION_SCHEMA = post_completion.SCHEMA_VERSION
COMMAND_CHECKLIST_SCHEMA = "supplement-operator-next-command-checklist-v1"
TAXONOMY_AUDIT_SCHEMA = "supplement-crawling-image-taxonomy-audit-v1"
TAXONOMY_STAGING_SCHEMA = "supplement-taxonomy-db-staging-v1"
SOURCE_DOC_URLS = readiness_reporter.SOURCE_DOC_URLS
MAX_INTERNAL_COMMAND_TEXT_LENGTH = 8_000
MAX_MARKDOWN_CELL_TEXT_LENGTH = 1_200
REQUIREMENT_QUEUE_KEYS = {
    "brand_product_db_import": "brand_product_review",
    "review_image_ground_truth_privacy_gate": "review_pii_screening",
    "detail_page_yolo_bbox_annotation": "yolo_section_annotation",
}
UNSAFE_TRUE_FLAGS = frozenset(
    {
        "absolute_paths_stored",
        "database_connection_opened",
        "db_write_performed",
        "external_provider_call_performed",
        "llm_call_performed",
        "local_absolute_path_printed",
        "local_path_literals_stored",
        "ocr_provider_call_performed",
        "paddleocr_training_performed",
        "product_dir_literals_stored",
        "product_literal_printed",
        "raw_ocr_text_stored",
        "raw_provider_payload_stored",
        "source_image_read_performed",
        "source_rows_read",
        "training_execution_performed_by_script",
    }
)
REQUIREMENT_SPECS: tuple[dict[str, Any], ...] = (
    {
        "requirement_key": "source_structure_audited",
        "title": "crawling-image structure verified",
        "stage_keys": ("taxonomy_structure_audit",),
        "objective_mapping": "Verify category/product/review/detail-page folder structure.",
    },
    {
        "requirement_key": "taxonomy_staging_redesign_ready",
        "title": "taxonomy staging reflects actual source shape",
        "stage_keys": ("taxonomy_db_staging",),
        "objective_mapping": "Redesign DB staging if brand/product structure differs.",
    },
    {
        "requirement_key": "brand_product_db_import",
        "title": "brand/product DB import is approved",
        "stage_keys": ("brand_product_review",),
        "objective_mapping": "Store products under categories and brands after review.",
    },
    {
        "requirement_key": "category_seed_db_apply_preflight_ready",
        "title": "category seed DB apply preflight is ready",
        "stage_keys": ("category_seed_db_apply_preflight",),
        "objective_mapping": "Prepare local category seed DB apply without opening a DB connection or writing data.",
    },
    {
        "requirement_key": "category_seed_db_verified",
        "title": "category seed DB import is verified",
        "stage_keys": ("category_seed_db_verification",),
        "objective_mapping": "Verify source category folders are persisted as category seed rows.",
    },
    {
        "requirement_key": "taxonomy_db_import_verified",
        "title": "reviewed brand/product DB import is verified",
        "stage_keys": ("taxonomy_db_import_verification",),
        "objective_mapping": "Verify categories and reviewed products in DB.",
    },
    {
        "requirement_key": "review_image_ground_truth_privacy_gate",
        "title": "review images are cleared for ground truth",
        "stage_keys": ("review_pii_screening",),
        "objective_mapping": "Use review images as OCR ground-truth only after screening.",
    },
    {
        "requirement_key": "private_image_tracking_guard",
        "title": "private source and review images are not tracked",
        "stage_keys": ("private_image_tracking_check",),
        "objective_mapping": "Do not commit crawling-image source data or local review image artifacts.",
    },
    {
        "requirement_key": "manual_ocr_ground_truth",
        "title": "manual OCR ground truth is ready",
        "stage_keys": ("manual_ocr_ground_truth",),
        "objective_mapping": "Create exact label text ground truth from review images.",
    },
    {
        "requirement_key": "teacher_ocr_paddleocr_comparison",
        "title": "CLOVA/Google Vision/PaddleOCR comparison is complete",
        "stage_keys": ("teacher_ocr_comparison",),
        "objective_mapping": "Compare teacher OCR outputs with final PaddleOCR output.",
    },
    {
        "requirement_key": "detail_page_yolo_bbox_annotation",
        "title": "detail-page section bboxes are reviewed",
        "stage_keys": ("yolo_section_annotation",),
        "objective_mapping": "Label section boxes for ingredients, amounts, intake, cautions.",
    },
    {
        "requirement_key": "section_yolo_dataset_ready",
        "title": "YOLO section dataset is materialized",
        "stage_keys": ("yolo_section_dataset",),
        "objective_mapping": "Turn accepted bbox labels into a YOLO section dataset.",
    },
    {
        "requirement_key": "paddleocr_training_loop_ready",
        "title": "PaddleOCR training loop is gated and ready",
        "stage_keys": (
            "paddleocr_text_target_chain_preflight",
            "paddleocr_improvement_triage",
            "paddleocr_annotation_tasks",
            "paddleocr_finetune_plan",
            "paddleocr_metric_gate",
            "paddleocr_promotion_runbook",
        ),
        "objective_mapping": "Feed ground truth back into PaddleOCR and gate metrics.",
    },
    {
        "requirement_key": "privacy_security_controls",
        "title": "privacy and safety controls are preserved",
        "stage_keys": (),
        "objective_mapping": "Do not leak paths, raw OCR, provider payloads, or run unsafe writes.",
    },
)


class CompletionAuditError(ValueError):
    """Raised when a completion audit input cannot be trusted."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional test argument list.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readiness", type=Path, required=True)
    parser.add_argument("--batch-progress", type=Path, required=True)
    parser.add_argument("--next-work-order", type=Path, required=True)
    parser.add_argument("--post-completion-plan", type=Path, required=True)
    parser.add_argument("--next-command-checklist", type=Path, default=None)
    parser.add_argument("--taxonomy-audit", type=Path, default=None)
    parser.add_argument("--taxonomy-staging", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write a completion audit JSON and optional Markdown report.

    Args:
        argv: Optional test argument list.
    """
    args = parse_args(argv)
    input_paths = {
        "readiness": args.readiness.expanduser().resolve(),
        "batch_progress": args.batch_progress.expanduser().resolve(),
        "next_work_order": args.next_work_order.expanduser().resolve(),
        "post_completion_plan": args.post_completion_plan.expanduser().resolve(),
    }
    if args.taxonomy_audit is not None:
        input_paths["taxonomy_audit"] = args.taxonomy_audit.expanduser().resolve()
    if args.taxonomy_staging is not None:
        input_paths["taxonomy_staging"] = args.taxonomy_staging.expanduser().resolve()
    if args.next_command_checklist is not None:
        input_paths["next_command_checklist"] = args.next_command_checklist.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    markdown_output = (
        args.markdown_output.expanduser().resolve() if args.markdown_output is not None else None
    )
    try:
        audit = build_completion_audit(input_paths=input_paths)
        _write_json(output_path, audit)
        if markdown_output is not None:
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            markdown_output.write_text(build_markdown(audit), encoding="utf-8")
        print(json.dumps(_cli_summary(audit), ensure_ascii=False, sort_keys=True))
    except (OSError, json.JSONDecodeError, CompletionAuditError) as exc:
        failure = _failure_summary(input_paths=input_paths, output_path=output_path, error=exc)
        _write_json(output_path, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None


def build_completion_audit(*, input_paths: Mapping[str, Path]) -> dict[str, Any]:
    """Build a conservative requirement-by-requirement completion audit.

    Args:
        input_paths: Required and optional redacted summary artifact paths.

    Returns:
        Redacted completion audit.

    Raises:
        CompletionAuditError: If an input is missing, unsafe, or unsupported.
    """
    readiness = _load_json_object(_required_input(input_paths, "readiness"))
    progress = _load_json_object(_required_input(input_paths, "batch_progress"))
    next_work_order = _load_json_object(_required_input(input_paths, "next_work_order"))
    post_plan = _load_json_object(_required_input(input_paths, "post_completion_plan"))
    command_checklist = _optional_json_object(input_paths, "next_command_checklist")
    taxonomy_audit = _optional_json_object(input_paths, "taxonomy_audit")
    taxonomy_staging = _optional_json_object(input_paths, "taxonomy_staging")

    _require_schema(readiness, READINESS_SCHEMA)
    _require_schema(progress, BATCH_PROGRESS_SCHEMA)
    _require_schema(next_work_order, WORK_ORDER_SCHEMA)
    _require_schema(post_plan, POST_COMPLETION_SCHEMA)
    if command_checklist is not None:
        _require_schema(command_checklist, COMMAND_CHECKLIST_SCHEMA)
    if taxonomy_audit is not None:
        _require_schema(taxonomy_audit, TAXONOMY_AUDIT_SCHEMA)
    if taxonomy_staging is not None:
        _require_schema(taxonomy_staging, TAXONOMY_STAGING_SCHEMA)

    payloads = [readiness, progress, next_work_order, post_plan]
    if command_checklist is not None:
        payloads.append(command_checklist)
    if taxonomy_audit is not None:
        payloads.append(taxonomy_audit)
    if taxonomy_staging is not None:
        payloads.append(taxonomy_staging)
    for payload in payloads:
        _reject_unsafe_payload(payload)
        _reject_unsafe_true_flags(payload)

    stage_by_key = _stage_by_key(readiness)
    artifact_by_role = _artifact_summary_by_role(readiness)
    requirements = [
        _requirement_summary(
            spec=spec,
            stage_by_key=stage_by_key,
            artifact_by_role=artifact_by_role,
            progress=progress,
            next_work_order=next_work_order,
            post_plan=post_plan,
            command_checklist=command_checklist,
            taxonomy_audit=taxonomy_audit,
            taxonomy_staging=taxonomy_staging,
        )
        for spec in REQUIREMENT_SPECS
    ]
    verified = sum(1 for row in requirements if row["status"] == "verified")
    pending = sum(1 for row in requirements if row["status"] == "pending_operator_review")
    blocked = sum(1 for row in requirements if row["status"].startswith("blocked"))
    incomplete = [row["requirement_key"] for row in requirements if row["status"] != "verified"]
    operator_review_gate = _operator_review_completion_gate(
        progress=progress,
        post_plan=post_plan,
    )
    objective_completion_allowed = (
        not incomplete and operator_review_gate["completion_allowed"] is True
    )
    audit = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "overall_status": (
            "complete_verified"
            if objective_completion_allowed
            else _overall_status(
                pending_count=pending,
                blocked_count=blocked,
                operator_review_gate=operator_review_gate,
            )
        ),
        "objective_completion_allowed": objective_completion_allowed,
        "requirement_count": len(requirements),
        "verified_requirement_count": verified,
        "pending_requirement_count": pending,
        "blocked_requirement_count": blocked,
        "incomplete_requirement_keys": incomplete,
        "operator_review_completion_gate": operator_review_gate,
        "current_blocker_batch_key": _safe_string(next_work_order.get("batch_key")),
        "current_blocker_queue_key": _safe_string(next_work_order.get("queue_key")),
        "current_blocker_blank_row_count": _non_negative_int(
            next_work_order.get("blank_row_count")
        ),
        "total_blank_row_count": _non_negative_int(progress.get("total_blank_row_count")),
        "post_completion_execution_allowed": post_plan.get("post_completion_execution_allowed")
        is True,
        "post_completion_blocker_codes": _safe_string_list(post_plan.get("blocked_reason_codes")),
        "operator_next_action": _safe_string(
            next_work_order.get("operator_next_action")
            or next_work_order.get("stage_next_operator_action")
        ),
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_hashes": {
            key: _fingerprint_text(str(path.expanduser()))
            for key, path in sorted(input_paths.items())
        },
        "requirements": requirements,
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
    _reject_unsafe_payload(audit)
    _reject_unsafe_true_flags(audit)
    return audit


def build_markdown(audit: Mapping[str, Any]) -> str:
    """Build a redacted Markdown completion audit.

    Args:
        audit: Completion audit payload.

    Returns:
        Markdown report.
    """
    _reject_unsafe_payload(audit)
    _reject_unsafe_true_flags(audit)
    lines = [
        "# Supplement Learning Completion Audit",
        "",
        f"- Schema: `{SCHEMA_VERSION}`",
        f"- Overall status: `{_safe_string(audit.get('overall_status'))}`",
        f"- Completion allowed: `{str(audit.get('objective_completion_allowed') is True).lower()}`",
        f"- Requirements: `{_non_negative_int(audit.get('verified_requirement_count'))}` verified / "
        f"`{_non_negative_int(audit.get('pending_requirement_count'))}` pending / "
        f"`{_non_negative_int(audit.get('blocked_requirement_count'))}` blocked",
        f"- Current blocker batch: `{_safe_string(audit.get('current_blocker_batch_key'))}`",
        f"- Total blank rows: `{_non_negative_int(audit.get('total_blank_row_count'))}`",
        f"- Operator review gate: `{_safe_string(_operator_gate(audit).get('status'))}`",
        "",
        "## Requirements",
        "",
        "| Requirement | Status | Evidence | Next action |",
        "| --- | --- | --- | --- |",
    ]
    for row in _requirement_rows(audit):
        lines.append(
            "| "
            + " | ".join(
                (
                    _md_cell(row.get("title")),
                    f"`{_safe_string(row.get('status'))}`",
                    _md_cell("; ".join(_safe_string_list(row.get("evidence")))),
                    _md_cell(_safe_string(row.get("next_action"))),
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- Source images read: `false`",
            "- DB write performed: `false`",
            "- OCR provider call performed: `false`",
            "- LLM call performed: `false`",
            "- Raw OCR/provider payload stored: `false`",
            f"- Completion gate blockers: `{', '.join(_safe_string_list(_operator_gate(audit).get('blocker_codes')))}`",
            "",
            "## Source Docs",
            "",
        ]
    )
    lines.extend(f"- {url}" for url in audit.get("source_doc_urls", []))
    return "\n".join(lines) + "\n"


def _requirement_summary(
    *,
    spec: Mapping[str, Any],
    stage_by_key: Mapping[str, Mapping[str, Any]],
    artifact_by_role: Mapping[str, Mapping[str, Any]],
    progress: Mapping[str, Any],
    next_work_order: Mapping[str, Any],
    post_plan: Mapping[str, Any],
    command_checklist: Mapping[str, Any] | None,
    taxonomy_audit: Mapping[str, Any] | None,
    taxonomy_staging: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build one requirement row from readiness and queue evidence.

    Args:
        spec: Requirement specification.
        stage_by_key: Readiness stages keyed by stage id.
        artifact_by_role: Readiness artifact summaries keyed by role.
        progress: Operator batch progress payload.
        next_work_order: Current next-batch work order.
        post_plan: Current post-completion command plan.
        command_checklist: Optional current next-command checklist.
        taxonomy_audit: Optional taxonomy audit payload.
        taxonomy_staging: Optional taxonomy staging summary payload.

    Returns:
        Redacted requirement summary.
    """
    requirement_key = _safe_string(spec.get("requirement_key"))
    stage_keys = tuple(str(key) for key in spec.get("stage_keys", ()))
    if requirement_key == "privacy_security_controls":
        teacher_gate = _teacher_ocr_fail_closed_gate_evidence(
            post_plan=post_plan,
            command_checklist=command_checklist,
        )
        return {
            "requirement_key": requirement_key,
            "title": _safe_string(spec.get("title")),
            "objective_mapping": _safe_string(spec.get("objective_mapping")),
            "status": (
                "verified" if not teacher_gate["blocker_codes"] else "blocked_invalid_artifact"
            ),
            "stage_keys": [],
            "evidence": [
                "unsafe input flags are false",
                "redaction scan rejected raw OCR/provider/path payload fields",
                *teacher_gate["evidence"],
            ],
            "blocker_codes": teacher_gate["blocker_codes"],
            "next_action": (
                "continue_using_redacted_summaries_only"
                if not teacher_gate["blocker_codes"]
                else "regenerate_fail_closed_teacher_ocr_command_plan"
            ),
        }
    if requirement_key == "paddleocr_training_loop_ready":
        early_stop = artifact_by_role.get("paddleocr_accuracy_stop_gate")
        if _paddleocr_early_stop_verified(early_stop):
            return {
                "requirement_key": requirement_key,
                "title": _safe_string(spec.get("title")),
                "objective_mapping": _safe_string(spec.get("objective_mapping")),
                "status": "verified",
                "stage_keys": list(stage_keys),
                "evidence": [
                    "paddleocr_accuracy_stop_gate:verified",
                    "human_ground_truth_compared=true",
                    "text_extraction_accuracy_ge_95=true",
                    "training_loop_stop_allowed=true",
                ],
                "blocker_codes": [],
                "next_action": "stop_paddleocr_training_loop_after_operator_completion",
            }

    stages = [_stage_or_blocked(stage_by_key, stage_key) for stage_key in stage_keys]
    status = _aggregate_stage_status(stages)
    evidence = _requirement_evidence(
        requirement_key=requirement_key,
        stages=stages,
        progress=progress,
        post_plan=post_plan,
        taxonomy_audit=taxonomy_audit,
        taxonomy_staging=taxonomy_staging,
    )
    blockers = sorted(
        {code for stage in stages for code in _safe_string_list(stage.get("blocker_codes"))}
    )
    if requirement_key == "paddleocr_training_loop_ready":
        early_stop = artifact_by_role.get("paddleocr_accuracy_stop_gate")
        evidence.extend(_paddleocr_early_stop_evidence(early_stop))
        if early_stop is not None and not _paddleocr_early_stop_verified(early_stop):
            blockers.append("paddleocr_accuracy_stop_gate:not_allowed")
            blockers = sorted(set(blockers))
    next_action = _next_action(stages, next_work_order=next_work_order, post_plan=post_plan)
    return {
        "requirement_key": requirement_key,
        "title": _safe_string(spec.get("title")),
        "objective_mapping": _safe_string(spec.get("objective_mapping")),
        "status": status,
        "stage_keys": list(stage_keys),
        "evidence": evidence,
        "blocker_codes": blockers,
        "next_action": next_action,
    }


def _requirement_evidence(
    *,
    requirement_key: str,
    stages: list[Mapping[str, Any]],
    progress: Mapping[str, Any],
    post_plan: Mapping[str, Any],
    taxonomy_audit: Mapping[str, Any] | None,
    taxonomy_staging: Mapping[str, Any] | None,
) -> list[str]:
    """Return short safe evidence phrases for a requirement.

    Args:
        requirement_key: Requirement key.
        stages: Matching readiness stages.
        progress: Operator batch progress payload.
        post_plan: Current post-completion command plan.
        taxonomy_audit: Optional taxonomy audit payload.
        taxonomy_staging: Optional taxonomy staging summary payload.

    Returns:
        Bounded evidence strings.
    """
    evidence = [
        f"{_safe_string(stage.get('stage_key'))}:{_safe_string(stage.get('status'))}"
        for stage in stages
    ]
    if requirement_key == "paddleocr_training_loop_ready":
        status_counts: dict[str, int] = {}
        for stage in stages:
            status = _safe_string(stage.get("status"))
            status_counts[status] = status_counts.get(status, 0) + 1
        evidence = [
            f"stage_count={len(stages)}",
            *[
                f"{status}_count={count}"
                for status, count in sorted(status_counts.items())
                if status
            ],
        ]
    if requirement_key == "source_structure_audited" and taxonomy_audit is not None:
        evidence.extend(_taxonomy_count_evidence(taxonomy_audit))
    if requirement_key == "taxonomy_staging_redesign_ready" and taxonomy_staging is not None:
        evidence.extend(_taxonomy_count_evidence(taxonomy_staging))
    if requirement_key in {
        "brand_product_db_import",
        "review_image_ground_truth_privacy_gate",
        "detail_page_yolo_bbox_annotation",
    }:
        queue_key = REQUIREMENT_QUEUE_KEYS[requirement_key]
        queue_summary = _queue_progress_summary(progress=progress, queue_key=queue_key)
        evidence.append(f"queue={queue_key}")
        evidence.append(f"queue_next_batch={_safe_string(queue_summary.get('next_batch_key'))}")
        evidence.append(
            f"queue_blank_rows={_non_negative_int(queue_summary.get('blank_row_count'))}"
        )
        evidence.append(
            f"queue_pending_batches={_non_negative_int(queue_summary.get('pending_batch_count'))}"
        )
        evidence.append(
            "post_completion_allowed="
            f"{str(post_plan.get('post_completion_execution_allowed') is True).lower()}"
        )
    return evidence


def _artifact_summary_by_role(readiness: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """Return readiness artifact summaries keyed by role.

    Args:
        readiness: Readiness report payload.

    Returns:
        Artifact summary mapping. Missing or malformed rows are ignored because
        completion must still be driven by stage evidence.
    """
    summaries = readiness.get("artifact_summaries")
    if not isinstance(summaries, list):
        return {}
    artifacts: dict[str, Mapping[str, Any]] = {}
    for summary in summaries:
        if not isinstance(summary, Mapping):
            continue
        role = _safe_string(summary.get("role"))
        if role:
            artifacts[role] = summary
    return artifacts


def _teacher_ocr_fail_closed_gate_evidence(
    *,
    post_plan: Mapping[str, Any],
    command_checklist: Mapping[str, Any] | None,
) -> dict[str, list[str]]:
    """Verify teacher OCR commands are fail-closed behind benchmark readiness.

    Args:
        post_plan: Current post-completion command plan.
        command_checklist: Optional generated next-command checklist.

    Returns:
        Redacted evidence and blocker codes. No shell command, file path, source
        row, OCR text, or provider payload is returned.
    """
    evidence: list[str] = []
    blockers: list[str] = []
    plan_result = _teacher_ocr_plan_sequence_evidence(post_plan)
    evidence.extend(plan_result["evidence"])
    blockers.extend(plan_result["blocker_codes"])
    checklist_result = _teacher_ocr_checklist_gate_evidence(command_checklist)
    evidence.extend(checklist_result["evidence"])
    blockers.extend(checklist_result["blocker_codes"])
    return {
        "evidence": evidence,
        "blocker_codes": sorted(set(blockers)),
    }


def _teacher_ocr_plan_sequence_evidence(post_plan: Mapping[str, Any]) -> dict[str, list[str]]:
    """Verify post-completion step order around teacher OCR.

    Args:
        post_plan: Current post-completion command plan.

    Returns:
        Redacted evidence and blocker codes.
    """
    required_order = (
        "build_supplement_ocr_benchmark_manifest",
        "assign_paddleocr_benchmark_splits",
        "gate_supplement_ocr_benchmark",
        "collect_supplement_ocr_observations",
    )
    steps = post_plan.get("steps")
    if not isinstance(steps, list):
        return {
            "evidence": ["teacher_ocr_plan_sequence=missing_steps"],
            "blocker_codes": ["teacher_ocr_plan_steps_missing"],
        }
    script_indices: dict[str, int] = {}
    gate_policy_by_script: dict[str, str] = {}
    input_roles_by_script: dict[str, set[str]] = {}
    for index, step in enumerate(steps):
        if not isinstance(step, Mapping):
            continue
        script_key = _safe_string(step.get("script_key"))
        if not script_key or script_key in script_indices:
            continue
        script_indices[script_key] = index
        gate_policy_by_script[script_key] = _safe_string(step.get("gate_policy"))
        input_roles = step.get("input_roles")
        if isinstance(input_roles, list):
            input_roles_by_script[script_key] = {
                _safe_string(role) for role in input_roles if _safe_string(role)
            }
    blockers = [
        f"teacher_ocr_plan_missing_{script_key}"
        for script_key in required_order
        if script_key not in script_indices
    ]
    if not blockers:
        indices = [script_indices[script_key] for script_key in required_order]
        if indices != sorted(indices):
            blockers.append("teacher_ocr_plan_sequence_out_of_order")
    gate_inputs = input_roles_by_script.get("gate_supplement_ocr_benchmark", set())
    required_gate_inputs = {
        "pii_decision_preflight_summary",
        "gt_bundle_summary",
        "ground_truth_preflight_summary",
        "benchmark_summary",
        "benchmark_split_summary",
    }
    missing_gate_inputs = sorted(required_gate_inputs - gate_inputs)
    blockers.extend(f"teacher_ocr_plan_gate_input_missing_{item}" for item in missing_gate_inputs)
    if (
        gate_policy_by_script.get("gate_supplement_ocr_benchmark")
        != "must_pass_before_teacher_ocr_eval"
    ):
        blockers.append("teacher_ocr_plan_gate_policy_not_strict")
    if (
        gate_policy_by_script.get("collect_supplement_ocr_observations")
        != "external_ocr_requires_explicit_env_opt_in"
    ):
        blockers.append("teacher_ocr_provider_opt_in_policy_missing")
    evidence = [
        "teacher_ocr_plan_sequence=" + ("verified" if not blockers else "blocked"),
        "teacher_ocr_plan_gate_inputs=" + ("verified" if not missing_gate_inputs else "missing"),
        "teacher_ocr_plan_provider_opt_in="
        + str(
            gate_policy_by_script.get("collect_supplement_ocr_observations")
            == "external_ocr_requires_explicit_env_opt_in"
        ).lower(),
    ]
    return {
        "evidence": evidence,
        "blocker_codes": blockers,
    }


def _teacher_ocr_checklist_gate_evidence(
    command_checklist: Mapping[str, Any] | None,
) -> dict[str, list[str]]:
    """Verify generated shell commands fail closed before provider OCR.

    Args:
        command_checklist: Optional generated command checklist.

    Returns:
        Redacted evidence and blocker codes.
    """
    if command_checklist is None:
        return {
            "evidence": ["teacher_ocr_command_checklist=missing"],
            "blocker_codes": ["teacher_ocr_command_checklist_missing"],
        }
    commands = command_checklist.get("commands")
    if not isinstance(commands, list):
        return {
            "evidence": ["teacher_ocr_command_checklist=missing_commands"],
            "blocker_codes": ["teacher_ocr_command_checklist_commands_missing"],
        }
    script_indices: dict[str, int] = {}
    command_by_script: dict[str, str] = {}
    gate_policy_by_script: dict[str, str] = {}
    for index, row in enumerate(commands):
        if not isinstance(row, Mapping):
            continue
        script_key = _safe_string(row.get("script_key"))
        if not script_key or script_key in script_indices:
            continue
        script_indices[script_key] = index
        command_by_script[script_key] = _command_text_for_internal_validation(row.get("command"))
        gate_policy_by_script[script_key] = _safe_string(row.get("gate_policy"))
    blockers: list[str] = []
    required_order = (
        "build_supplement_ocr_benchmark_manifest",
        "assign_paddleocr_benchmark_splits",
        "gate_supplement_ocr_benchmark",
        "collect_supplement_ocr_observations",
    )
    blockers.extend(
        f"teacher_ocr_command_missing_{script_key}"
        for script_key in required_order
        if script_key not in script_indices
    )
    if not blockers:
        indices = [script_indices[script_key] for script_key in required_order]
        if indices != sorted(indices):
            blockers.append("teacher_ocr_command_sequence_out_of_order")
    gate_command = command_by_script.get("gate_supplement_ocr_benchmark", "")
    required_gate_flags = (
        "--ground-truth-bundle-summary",
        "--ground-truth-preflight",
        "--benchmark-summary",
        "--benchmark-split-summary",
        "--require-ready-for-teacher-ocr-eval",
    )
    missing_flags = [flag for flag in required_gate_flags if flag not in gate_command]
    blockers.extend(f"teacher_ocr_command_gate_flag_missing_{flag[2:]}" for flag in missing_flags)
    if (
        gate_policy_by_script.get("gate_supplement_ocr_benchmark")
        != "must_pass_before_teacher_ocr_eval"
    ):
        blockers.append("teacher_ocr_command_gate_policy_not_strict")
    if (
        gate_policy_by_script.get("collect_supplement_ocr_observations")
        != "external_ocr_requires_explicit_env_opt_in"
    ):
        blockers.append("teacher_ocr_command_provider_opt_in_policy_missing")
    evidence = [
        "teacher_ocr_command_sequence=" + ("verified" if not blockers else "blocked"),
        "teacher_ocr_command_ready_required="
        + str("--require-ready-for-teacher-ocr-eval" in gate_command).lower(),
        "teacher_ocr_command_provider_opt_in="
        + str(
            gate_policy_by_script.get("collect_supplement_ocr_observations")
            == "external_ocr_requires_explicit_env_opt_in"
        ).lower(),
    ]
    return {
        "evidence": evidence,
        "blocker_codes": blockers,
    }


def _paddleocr_early_stop_verified(artifact: Mapping[str, Any] | None) -> bool:
    """Return whether PaddleOCR can stop further training from a 95 percent gate.

    Args:
        artifact: Optional readiness artifact summary.

    Returns:
        True only when human-GT comparison, privacy clearance, threshold pass,
        and explicit stop permission are all present.
    """
    if artifact is None:
        return False
    return (
        artifact.get("human_ground_truth_compared") is True
        and artifact.get("privacy_review_cleared") is True
        and artifact.get("text_extraction_accuracy_meets_95_percent") is True
        and artifact.get("training_loop_stop_allowed") is True
    )


def _paddleocr_early_stop_evidence(artifact: Mapping[str, Any] | None) -> list[str]:
    """Return safe PaddleOCR early-stop evidence strings.

    Args:
        artifact: Optional readiness artifact summary.

    Returns:
        Redacted evidence strings.
    """
    if artifact is None:
        return ["paddleocr_accuracy_stop_gate:missing"]
    return [
        "paddleocr_accuracy_stop_gate:provided",
        "human_ground_truth_compared="
        f"{str(artifact.get('human_ground_truth_compared') is True).lower()}",
        "text_extraction_accuracy_ge_95="
        f"{str(artifact.get('text_extraction_accuracy_meets_95_percent') is True).lower()}",
        "training_loop_stop_allowed="
        f"{str(artifact.get('training_loop_stop_allowed') is True).lower()}",
    ]


def _operator_review_completion_gate(
    *,
    progress: Mapping[str, Any],
    post_plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a hard completion gate from operator-review aggregate progress.

    Args:
        progress: Operator batch-progress payload.
        post_plan: Current post-completion command plan.

    Returns:
        Redacted gate summary. Completion is allowed only when every operator
        batch is complete, no unresolved review rows remain, and the
        post-completion plan says follow-up commands are safe to run.
    """
    total_blank_rows = _non_negative_int(progress.get("total_blank_row_count"))
    total_pending_rows = _non_negative_int(progress.get("total_pending_row_count"))
    total_invalid_rows = _non_negative_int(progress.get("total_invalid_row_count"))
    total_missing_rows = _non_negative_int(progress.get("total_missing_row_count"))
    all_batches_complete = progress.get("all_batches_complete") is True
    post_completion_allowed = post_plan.get("post_completion_execution_allowed") is True
    blocker_codes: list[str] = []
    if not all_batches_complete:
        blocker_codes.append("operator_batches_not_complete")
    if total_blank_rows:
        blocker_codes.append("operator_blank_rows_remaining")
    if total_pending_rows:
        blocker_codes.append("operator_pending_rows_remaining")
    if total_invalid_rows:
        blocker_codes.append("operator_invalid_rows_remaining")
    if total_missing_rows:
        blocker_codes.append("operator_missing_rows_remaining")
    if not post_completion_allowed:
        post_blockers = _safe_string_list(post_plan.get("blocked_reason_codes"))
        blocker_codes.extend(post_blockers or ["post_completion_execution_not_allowed"])
    blocker_codes = sorted(set(blocker_codes))
    completion_allowed = not blocker_codes
    return {
        "status": "verified" if completion_allowed else "blocked_operator_review_incomplete",
        "completion_allowed": completion_allowed,
        "all_batches_complete": all_batches_complete,
        "post_completion_execution_allowed": post_completion_allowed,
        "total_blank_row_count": total_blank_rows,
        "total_pending_row_count": total_pending_rows,
        "total_invalid_row_count": total_invalid_rows,
        "total_missing_row_count": total_missing_rows,
        "blocker_codes": blocker_codes,
        "next_action": (
            "run_post_completion_commands"
            if completion_allowed
            else "complete_all_operator_review_batches_before_completion"
        ),
    }


def _queue_progress_summary(*, progress: Mapping[str, Any], queue_key: str) -> dict[str, Any]:
    """Return aggregate progress for one operator queue.

    Args:
        progress: Operator batch-progress payload.
        queue_key: Queue identifier to summarize.

    Returns:
        Safe aggregate counts for the queue.
    """
    batches = progress.get("batches")
    if not isinstance(batches, list):
        return {
            "next_batch_key": "",
            "blank_row_count": 0,
            "pending_batch_count": 0,
        }

    blank_row_count = 0
    pending_batch_count = 0
    next_batch_key = ""
    for batch in batches:
        if not isinstance(batch, Mapping):
            continue
        if _safe_string(batch.get("queue_key")) != queue_key:
            continue
        blank_row_count += _non_negative_int(batch.get("blank_row_count"))
        if _safe_string(batch.get("batch_status")) != "complete":
            pending_batch_count += 1
            if not next_batch_key:
                next_batch_key = _safe_string(batch.get("batch_key"))
    return {
        "next_batch_key": next_batch_key,
        "blank_row_count": blank_row_count,
        "pending_batch_count": pending_batch_count,
    }


def _taxonomy_count_evidence(payload: Mapping[str, Any]) -> list[str]:
    """Extract safe aggregate count evidence from taxonomy payloads.

    Args:
        payload: Redacted taxonomy audit or staging summary.

    Returns:
        Count evidence strings.
    """
    keys = (
        "category_count",
        "product_candidate_count",
        "brand_candidate_count",
        "review_image_count",
        "detail_page_image_count",
        "category_seed_count",
        "row_count",
        "total_row_count",
    )
    evidence = []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, int) and value >= 0:
            evidence.append(f"{key}={value}")
    return evidence


def _aggregate_stage_status(stages: list[Mapping[str, Any]]) -> str:
    """Aggregate one or more readiness stage statuses.

    Args:
        stages: Readiness stage rows.

    Returns:
        Conservative aggregate status.
    """
    statuses = [_safe_string(stage.get("status")) for stage in stages]
    if statuses and all(status == "verified" for status in statuses):
        return "verified"
    if any(status.startswith("blocked") for status in statuses):
        return "blocked_missing_artifact"
    if any(status == "pending_operator_review" for status in statuses):
        return "pending_operator_review"
    return "blocked_missing_artifact"


def _next_action(
    stages: list[Mapping[str, Any]],
    *,
    next_work_order: Mapping[str, Any],
    post_plan: Mapping[str, Any],
) -> str:
    """Choose a safe next action for a requirement.

    Args:
        stages: Matching readiness stages.
        next_work_order: Current next-batch work order.
        post_plan: Current post-completion command plan.

    Returns:
        Safe next action string.
    """
    for stage in stages:
        if stage.get("status") != "verified":
            action = _safe_string(stage.get("next_operator_action"))
            if action:
                return action
    if post_plan.get("post_completion_execution_allowed") is not True:
        return "complete_current_operator_batch_before_post_completion_steps"
    return _safe_string(
        next_work_order.get("operator_next_action")
        or next_work_order.get("stage_next_operator_action")
    )


def _stage_by_key(readiness: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """Return readiness stages keyed by stage key.

    Args:
        readiness: Readiness report payload.

    Returns:
        Stage mapping.
    """
    stages = readiness.get("stages")
    if not isinstance(stages, list):
        raise CompletionAuditError("Readiness report is missing stages.")
    result: dict[str, Mapping[str, Any]] = {}
    for stage in stages:
        if not isinstance(stage, Mapping):
            raise CompletionAuditError("Readiness report has invalid stage rows.")
        stage_key = stage.get("stage_key")
        if not isinstance(stage_key, str) or not stage_key:
            raise CompletionAuditError("Readiness stage is missing stage_key.")
        result[stage_key] = stage
    return result


def _stage_or_blocked(
    stage_by_key: Mapping[str, Mapping[str, Any]],
    stage_key: str,
) -> Mapping[str, Any]:
    """Return a readiness stage or a synthetic missing stage.

    Args:
        stage_by_key: Stage mapping.
        stage_key: Requested stage key.

    Returns:
        Existing or synthetic blocked stage.
    """
    stage = stage_by_key.get(stage_key)
    if stage is not None:
        return stage
    return {
        "stage_key": stage_key,
        "status": "blocked_missing_artifact",
        "blocker_codes": ["stage_missing_from_readiness_report"],
        "next_operator_action": "regenerate_readiness_report",
    }


def _overall_status(
    *,
    pending_count: int,
    blocked_count: int,
    operator_review_gate: Mapping[str, Any],
) -> str:
    """Return conservative overall completion status.

    Args:
        pending_count: Requirement count pending human review.
        blocked_count: Requirement count blocked by missing evidence.
        operator_review_gate: Hard completion gate payload.

    Returns:
        Stable status string.
    """
    if blocked_count:
        return "in_progress_blocked_by_missing_evidence"
    if pending_count:
        return "in_progress_pending_operator_review"
    if operator_review_gate.get("completion_allowed") is not True:
        return "in_progress_blocked_by_operator_review_gate"
    return "in_progress_unverified"


def _load_json_object(path: Path) -> dict[str, Any]:
    """Load a JSON object.

    Args:
        path: JSON path.

    Returns:
        JSON object.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CompletionAuditError("Expected a JSON object input.")
    return payload


def _optional_json_object(
    input_paths: Mapping[str, Path],
    key: str,
) -> dict[str, Any] | None:
    """Load an optional JSON object.

    Args:
        input_paths: Input path mapping.
        key: Optional key.

    Returns:
        JSON object or None.
    """
    path = input_paths.get(key)
    if path is None:
        return None
    return _load_json_object(path)


def _required_input(input_paths: Mapping[str, Path], key: str) -> Path:
    """Return a required input path.

    Args:
        input_paths: Input path mapping.
        key: Required key.

    Returns:
        Existing path.
    """
    path = input_paths.get(key)
    if path is None:
        raise CompletionAuditError(f"Missing required input: {key}")
    if not path.exists():
        raise CompletionAuditError(f"Input does not exist: {key}")
    return path


def _require_schema(payload: Mapping[str, Any], expected: str) -> None:
    """Validate a JSON schema version.

    Args:
        payload: JSON payload.
        expected: Expected schema version.
    """
    if payload.get("schema_version") != expected:
        raise CompletionAuditError("Unsupported schema version.")


def _reject_unsafe_payload(payload: Any) -> None:
    """Reject raw OCR/provider/path payload leakage.

    Args:
        payload: Payload to scan.
    """
    try:
        readiness_reporter._reject_unsafe_payload(payload)
    except readiness_reporter.PipelineReadinessError as exc:
        raise CompletionAuditError(str(exc)) from exc


def _reject_unsafe_true_flags(payload: Any) -> None:
    """Reject true values for dangerous side-effect flags.

    Args:
        payload: Payload to scan recursively.
    """
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if key in UNSAFE_TRUE_FLAGS and value is True:
                raise CompletionAuditError("Unsafe side-effect flag is true.")
            _reject_unsafe_true_flags(value)
    elif isinstance(payload, list):
        for item in payload:
            _reject_unsafe_true_flags(item)


def _command_text_for_internal_validation(value: Any) -> str:
    """Return bounded command text for structural checks only.

    Args:
        value: Candidate command value.

    Returns:
        Command text used only for local substring checks.

    Raises:
        CompletionAuditError: If the command text is too large or unsafe.
    """
    if not isinstance(value, str):
        return ""
    command = value.strip()
    if len(command) > MAX_INTERNAL_COMMAND_TEXT_LENGTH:
        raise CompletionAuditError("Command checklist row is too long.")
    _reject_unsafe_payload({"command_text_for_validation": command})
    return command


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write indented JSON.

    Args:
        path: Destination path.
        payload: JSON payload.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _failure_summary(
    *,
    input_paths: Mapping[str, Path],
    output_path: Path,
    error: Exception,
) -> dict[str, Any]:
    """Build a redacted failure summary.

    Args:
        input_paths: Input path mapping.
        output_path: Output path.
        error: Raised exception.

    Returns:
        Failure summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "failed",
        "error_type": type(error).__name__,
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "output_name": output_path.name,
        "objective_completion_allowed": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def _cli_summary(audit: Mapping[str, Any]) -> dict[str, Any]:
    """Return a compact redacted CLI summary.

    Args:
        audit: Completion audit.

    Returns:
        Summary object.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "overall_status": audit.get("overall_status"),
        "objective_completion_allowed": audit.get("objective_completion_allowed"),
        "verified_requirement_count": audit.get("verified_requirement_count"),
        "pending_requirement_count": audit.get("pending_requirement_count"),
        "blocked_requirement_count": audit.get("blocked_requirement_count"),
        "current_blocker_batch_key": audit.get("current_blocker_batch_key"),
        "total_blank_row_count": audit.get("total_blank_row_count"),
        "operator_review_gate_status": _operator_gate(audit).get("status"),
    }


def _requirement_rows(audit: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return requirement rows.

    Args:
        audit: Completion audit.

    Returns:
        Requirement mappings.
    """
    rows = audit.get("requirements")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


def _operator_gate(audit: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the operator completion gate from an audit payload.

    Args:
        audit: Completion audit payload.

    Returns:
        Gate mapping or an empty mapping.
    """
    gate = audit.get("operator_review_completion_gate")
    if isinstance(gate, Mapping):
        return gate
    return {}


def _safe_string(value: Any) -> str:
    """Return a bounded safe string.

    Args:
        value: Candidate value.

    Returns:
        Safe string.
    """
    if not isinstance(value, str):
        return ""
    return value.strip()[:240]


def _safe_string_list(value: Any) -> list[str]:
    """Return a bounded list of safe strings.

    Args:
        value: Candidate value.

    Returns:
        Safe strings.
    """
    if not isinstance(value, list):
        return []
    return [_safe_string(item) for item in value[:40] if _safe_string(item)]


def _non_negative_int(value: Any) -> int:
    """Return a non-negative integer.

    Args:
        value: Candidate value.

    Returns:
        Integer >= 0.
    """
    if isinstance(value, bool):
        return 0
    if isinstance(value, int) and value >= 0:
        return value
    return 0


def _md_cell(value: Any) -> str:
    """Escape a Markdown table cell.

    Args:
        value: Cell value.

    Returns:
        Escaped cell text.
    """
    if not isinstance(value, str):
        return ""
    text = value.strip()[:MAX_MARKDOWN_CELL_TEXT_LENGTH]
    _reject_unsafe_payload(text)
    return text.replace("|", "/")


def _fingerprint_text(value: str) -> str:
    """Return a short non-secret fingerprint for operator audit inputs."""
    return f"fp-{progress_preflight._sha256_text(value)[:12]}"


if __name__ == "__main__":
    main()
