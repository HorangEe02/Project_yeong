"""Build repo-relative commands for the next supplement operator batch.

This checklist turns the current redacted work order into concrete commands the
operator can run after editing the next local batch review file. It intentionally
outputs repo-relative paths only. It does not execute any command, read source
images, call OCR/LLM providers, write to the database, or expose row payloads.

References:
    https://docs.python.org/3/library/argparse.html
    https://docs.python.org/3/library/json.html
    https://www.postgresql.org/docs/current/ddl-constraints.html
    https://supabase.com/docs/guides/database/postgres/row-level-security
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

from scripts import build_supplement_operator_next_batch_work_order as work_order  # noqa: E402
from scripts import (  # noqa: E402
    build_supplement_operator_post_completion_command_plan as post_completion,
)
from scripts import (  # noqa: E402
    preflight_supplement_operator_review_batch_progress as progress_preflight,
)

SCHEMA_VERSION = "supplement-operator-next-command-checklist-v1"
WORK_ORDER_SCHEMA = work_order.SCHEMA_VERSION
POST_COMPLETION_SCHEMA = post_completion.SCHEMA_VERSION
BATCH_NUMBER_DIGIT_COUNT = 3
COMMAND_MAX_LENGTH = 8000
LOCAL_PATH_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    "file://",
    "\\Users\\",
    "\\Volumes\\",
)
COMMAND_EXECUTION_RULES: dict[str, tuple[str, tuple[str, ...], bool, bool]] = {
    "build_supplement_brand_review_batch_triage": ("runnable_now", (), False, False),
    "preflight_supplement_brand_review_contact_sheet": ("runnable_now", (), False, False),
    "build_supplement_operator_review_batch_triage": ("runnable_now", (), False, False),
    "apply_supplement_brand_batch_review_csv_decisions": (
        "blocked_until_operator_edits",
        ("all_brand_review_csv_rows_reviewed",),
        True,
        False,
    ),
    "preflight_supplement_operator_review_batch_file": (
        "blocked_until_operator_edits",
        ("operator_edits_current_batch",),
        True,
        False,
    ),
    "reconcile_supplement_operator_review_batch_files": (
        "blocked_until_batch_preflight",
        ("batch_file_preflight_ready_for_reconcile",),
        False,
        False,
    ),
    "preflight_supplement_operator_review_batch_progress": (
        "blocked_until_reconcile",
        ("reconciled_queue_copies_ready",),
        False,
        False,
    ),
    "extract_supplement_brand_reviewed_decisions": (
        "blocked_until_reconcile",
        ("reconciled_brand_queue_ready",),
        False,
        False,
    ),
    "preflight_supplement_brand_review_decisions": (
        "blocked_until_all_brand_rows_reviewed",
        ("all_brand_review_rows_reviewed",),
        True,
        False,
    ),
    "gate_supplement_brand_db_import": (
        "blocked_until_strict_brand_preflight",
        ("brand_review_preflight_passed",),
        False,
        False,
    ),
    "apply_supplement_brand_review_decisions": (
        "blocked_until_brand_import_gate",
        ("brand_db_import_gate_passed",),
        False,
        False,
    ),
    "extract_supplement_pii_reviewed_decisions": (
        "blocked_until_reconcile",
        ("reconciled_pii_queue_ready",),
        False,
        False,
    ),
    "preflight_supplement_review_pii_screening_decisions": (
        "blocked_until_all_pii_rows_reviewed",
        ("strict_pii_review_complete_before_teacher_ocr_eval",),
        True,
        False,
    ),
    "apply_supplement_review_pii_screening_decisions": (
        "blocked_until_strict_pii_preflight",
        ("pii_review_preflight_passed",),
        False,
        False,
    ),
    "export_supplement_ocr_ground_truth_template": (
        "blocked_until_pii_apply",
        ("teacher_safe_ocr_candidates_ready",),
        False,
        False,
    ),
    "build_supplement_ocr_ground_truth_review_bundle": (
        "blocked_until_gt_template",
        ("ocr_ground_truth_template_ready",),
        False,
        False,
    ),
    "preflight_supplement_ocr_ground_truth_manifest": (
        "blocked_until_manual_gt_edits",
        ("operator_completed_manual_ocr_ground_truth",),
        True,
        False,
    ),
    "build_supplement_ocr_benchmark_manifest": (
        "blocked_until_gt_preflight",
        ("ocr_ground_truth_preflight_passed",),
        False,
        False,
    ),
    "assign_paddleocr_benchmark_splits": (
        "blocked_until_benchmark_manifest",
        ("ocr_benchmark_manifest_ready",),
        False,
        False,
    ),
    "gate_supplement_ocr_benchmark": (
        "blocked_until_benchmark_splits",
        ("ocr_benchmark_manifest_and_splits_ready",),
        False,
        False,
    ),
    "collect_supplement_ocr_observations": (
        "blocked_until_teacher_ocr_gate",
        ("ocr_benchmark_gate_passed", "explicit_external_ocr_opt_in"),
        False,
        True,
    ),
    "merge_paddleocr_text_observations_into_benchmark": (
        "blocked_until_provider_observations",
        ("ocr_provider_observations_ready",),
        False,
        False,
    ),
    "preflight_paddleocr_text_target_chain": (
        "blocked_until_metric_benchmark",
        ("ocr_provider_metric_benchmark_ready",),
        False,
        False,
    ),
    "build_paddleocr_text_extraction_eval_summary": (
        "blocked_until_target_chain_preflight",
        ("paddleocr_text_target_chain_preflight_passed", "privacy_review_cleared"),
        False,
        False,
    ),
    "gate_paddleocr_text_extraction_target": (
        "blocked_until_holdout_eval_summary",
        ("paddleocr_holdout_eval_summary_ready",),
        False,
        False,
    ),
    "extract_supplement_yolo_reviewed_annotations": (
        "blocked_until_reconcile",
        ("reconciled_yolo_queue_ready",),
        False,
        False,
    ),
    "preflight_supplement_yolo_annotation_decisions": (
        "blocked_until_all_yolo_rows_reviewed",
        ("strict_yolo_annotation_complete_before_dataset_materialization",),
        True,
        False,
    ),
    "promote_supplement_yolo_annotation_template": (
        "blocked_until_strict_yolo_preflight",
        ("yolo_annotation_preflight_passed",),
        False,
        False,
    ),
    "materialize_supplement_section_yolo_dataset": (
        "blocked_until_yolo_promotion",
        ("yolo_template_promotion_ready",),
        False,
        False,
    ),
    "validate_supplement_section_yolo_dataset": (
        "blocked_until_yolo_materialize",
        ("yolo_dataset_materialized",),
        False,
        False,
    ),
    "gate_supplement_yolo_section_dataset": (
        "blocked_until_yolo_validation",
        ("yolo_dataset_validation_passed",),
        False,
        False,
    ),
}


class OperatorCommandChecklistError(ValueError):
    """Raised when command checklist inputs cannot be trusted."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional test argument list.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--operator-dir", type=Path, required=True)
    parser.add_argument("--todo-dir", type=Path, required=True)
    parser.add_argument("--taxonomy-staging", type=Path, default=None)
    parser.add_argument(
        "--batch-override-dir",
        type=Path,
        default=None,
        help=(
            "Optional directory of already-applied batch JSONL files to preserve "
            "when generating reconcile commands for the next batch."
        ),
    )
    parser.add_argument("--next-work-order", type=Path, required=True)
    parser.add_argument("--post-completion-plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write command checklist JSON and optional Markdown.

    Args:
        argv: Optional test argument list.
    """
    args = parse_args(argv)
    repo_root = args.repo_root.expanduser().resolve()
    input_paths = {
        "next_work_order": args.next_work_order.expanduser().resolve(),
        "post_completion_plan": args.post_completion_plan.expanduser().resolve(),
    }
    output_path = args.output.expanduser().resolve()
    markdown_output = (
        args.markdown_output.expanduser().resolve() if args.markdown_output is not None else None
    )
    taxonomy_staging = (
        args.taxonomy_staging.expanduser().resolve() if args.taxonomy_staging is not None else None
    )
    batch_override_dir = (
        args.batch_override_dir.expanduser().resolve()
        if args.batch_override_dir is not None
        else None
    )
    try:
        checklist = build_command_checklist(
            repo_root=repo_root,
            operator_dir=args.operator_dir.expanduser().resolve(),
            todo_dir=args.todo_dir.expanduser().resolve(),
            input_paths=input_paths,
            taxonomy_staging=taxonomy_staging,
            batch_override_dir=batch_override_dir,
        )
        _write_json(output_path, checklist)
        if markdown_output is not None:
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            markdown_output.write_text(build_markdown(checklist), encoding="utf-8")
        print(json.dumps(_cli_summary(checklist), ensure_ascii=False, sort_keys=True))
    except (OSError, json.JSONDecodeError, OperatorCommandChecklistError) as exc:
        failure = _failure_summary(input_paths=input_paths, output_path=output_path, error=exc)
        _write_json(output_path, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None


def build_command_checklist(
    *,
    repo_root: Path,
    operator_dir: Path,
    todo_dir: Path,
    input_paths: Mapping[str, Path],
    taxonomy_staging: Path | None = None,
    batch_override_dir: Path | None = None,
) -> dict[str, Any]:
    """Build repo-relative commands for the current next batch.

    Args:
        repo_root: Repository root used to relativize paths.
        operator_dir: Operator review artifact directory.
        todo_dir: Date-specific todo artifact directory.
        input_paths: Work-order and post-completion plan paths.
        taxonomy_staging: Optional explicit taxonomy staging artifact. When
            supplied, brand/product commands use this path instead of the
            date-specific todo fallback.
        batch_override_dir: Optional directory containing already-applied batch
            JSONL files. These are preserved in generated reconcile commands so
            later queue work does not accidentally drop earlier completed
            batch decisions.

    Returns:
        Redacted command checklist.
    """
    next_work_order = _load_json_object(_required_input(input_paths, "next_work_order"))
    post_plan = _load_json_object(_required_input(input_paths, "post_completion_plan"))
    _require_schema(next_work_order, WORK_ORDER_SCHEMA)
    _require_schema(post_plan, POST_COMPLETION_SCHEMA)
    _reject_unsafe_payload(next_work_order)
    _reject_unsafe_payload(post_plan)

    queue_key = _safe_token(next_work_order.get("queue_key"))
    batch_key = _safe_batch_key(next_work_order.get("batch_key"))
    batch_file_name = _safe_file_name(next_work_order.get("batch_file_name"))
    batch_review_file_name = _safe_file_name(next_work_order.get("batch_review_file_name"))
    blank_row_count = _non_negative_int(next_work_order.get("blank_row_count"))
    operator_next_action = _safe_token(
        next_work_order.get("operator_next_action")
        or next_work_order.get("stage_next_operator_action")
    )
    if not queue_key or not batch_key or not batch_file_name:
        raise OperatorCommandChecklistError("Next work order does not contain an editable batch.")
    if queue_key == "brand_product_review" and not batch_review_file_name:
        raise OperatorCommandChecklistError("Brand work order does not contain a review CSV.")
    paths = _command_paths(
        repo_root=repo_root,
        operator_dir=operator_dir,
        todo_dir=todo_dir,
        batch_file_name=batch_file_name,
        batch_review_file_name=batch_review_file_name,
        taxonomy_staging=taxonomy_staging,
    )
    preserved_batch_overrides = _batch_file_overrides_from_dir(
        repo_root=repo_root,
        batch_override_dir=batch_override_dir,
    )
    commands = _commands_for_queue(
        queue_key=queue_key,
        paths=paths,
        batch_key=batch_key,
        preserved_batch_overrides=preserved_batch_overrides,
    )
    checklist = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "ready_after_operator_edits",
        "queue_key": queue_key,
        "batch_key": batch_key,
        "current_blocker_queue_key": queue_key,
        "current_blocker_batch_key": batch_key,
        "current_blocker_blank_row_count": blank_row_count,
        "operator_next_action": operator_next_action or _blocked_until(queue_key)[0],
        "batch_file_name": batch_file_name,
        "batch_review_file_name": batch_review_file_name,
        "source_editable_file_name": _safe_file_name(
            next_work_order.get("source_editable_file_name")
        ),
        "command_count": len(commands),
        "commands": commands,
        "preserved_batch_override_count": len(preserved_batch_overrides),
        "preserved_batch_override_names": dict(sorted(preserved_batch_overrides.items())),
        "blocked_until": _blocked_until(queue_key),
        "post_completion_execution_allowed_now": post_plan.get("post_completion_execution_allowed")
        is True,
        "post_completion_blocker_codes": _safe_string_list(post_plan.get("blocked_reason_codes")),
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "input_path_fingerprints": {
            key: _path_fingerprint(path) for key, path in sorted(input_paths.items())
        },
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
        "source_doc_urls": _source_doc_urls(post_plan),
    }
    _reject_unsafe_payload(checklist)
    return checklist


def build_markdown(checklist: Mapping[str, Any]) -> str:
    """Build Markdown command checklist.

    Args:
        checklist: Command checklist payload.

    Returns:
        Markdown report.
    """
    _reject_unsafe_payload(checklist)
    lines = [
        "# Supplement Operator Next Command Checklist",
        "",
        f"- Schema: `{SCHEMA_VERSION}`",
        f"- Queue: `{_safe_token(checklist.get('queue_key'))}`",
        f"- Batch: `{_safe_batch_key(checklist.get('batch_key'))}`",
        f"- Current blocker: `{_safe_batch_key(checklist.get('current_blocker_batch_key'))}`",
        f"- Blank rows in current blocker: `{_non_negative_int(checklist.get('current_blocker_blank_row_count'))}`",
        f"- Operator next action: `{_safe_token(checklist.get('operator_next_action'))}`",
        f"- Batch file: `{_safe_file_name(checklist.get('batch_file_name'))}`",
        f"- Status: `{_safe_token(checklist.get('status'))}`",
        "",
        "## Commands",
        "",
    ]
    for row in _mapping_rows(checklist.get("commands")):
        lines.extend(
            [
                f"### {_non_negative_int(row.get('order'))}. {_safe_token(row.get('script_key'))}",
                "",
                _safe_sentence(row.get("purpose")),
                "",
                "```sh",
                _safe_command(row.get("command")),
                "```",
                "",
                f"- Gate policy: `{_safe_token(row.get('gate_policy'))}`",
                f"- Execution state: `{_safe_token(row.get('execution_state'))}`",
                f"- Blocked by: `{', '.join(_safe_string_list(row.get('blocked_by'))) or 'none'}`",
                f"- Requires operator input: `{_safe_bool(row.get('requires_operator_input'))}`",
                f"- Requires external opt-in: `{_safe_bool(row.get('requires_external_opt_in'))}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Safety",
            "",
            "- Commands are not executed by this generator.",
            "- Paths are repo-relative.",
            "- DB apply is not included in this checklist.",
            "- Source image, OCR text, provider payload, row payload, and product folder literals are not emitted.",
            "",
            "## Source Docs",
            "",
        ]
    )
    lines.extend(f"- {url}" for url in checklist.get("source_doc_urls", []))
    return "\n".join(lines) + "\n"


def _command_paths(
    *,
    repo_root: Path,
    operator_dir: Path,
    todo_dir: Path,
    batch_file_name: str,
    batch_review_file_name: str,
    taxonomy_staging: Path | None = None,
) -> dict[str, str]:
    """Return repo-relative paths used by generated commands.

    Args:
        repo_root: Repository root.
        operator_dir: Operator artifact directory.
        todo_dir: Todo artifact directory.
        batch_file_name: Current batch file name.
        batch_review_file_name: Current brand batch CSV review file name.
        taxonomy_staging: Optional explicit taxonomy staging artifact.

    Returns:
        Path role to repo-relative path.
    """
    reconciled_dir = operator_dir / "reconciled"
    applied_batch_dir = operator_dir / "batches-applied"
    review_csv_name = (
        batch_review_file_name or f"{batch_file_name.removesuffix('.jsonl')}.review.csv"
    )
    batch_stem = batch_file_name.removesuffix(".jsonl")
    batch_suffix = _batch_suffix(batch_file_name)
    taxonomy_staging_path = taxonomy_staging or _taxonomy_staging_path(todo_dir)
    taxonomy_staging_rel = _rel(repo_root, taxonomy_staging_path)
    if taxonomy_staging is not None and not taxonomy_staging_path.exists():
        raise OperatorCommandChecklistError("Taxonomy staging input does not exist.")
    return {
        "python": "backend/.venv/bin/python",
        "batch_plan": _rel(repo_root, operator_dir / "operator-review-batch-plan.json"),
        "source_batch_file": _rel(repo_root, operator_dir / "batches" / batch_file_name),
        "batch_review_csv": _rel(repo_root, operator_dir / "batches" / review_csv_name),
        "batch_triage_json": _rel(
            repo_root, operator_dir / f"{batch_file_name.removesuffix('.jsonl')}.triage.json"
        ),
        "batch_triage_md": _rel(
            repo_root, operator_dir / f"{batch_file_name.removesuffix('.jsonl')}.triage.md"
        ),
        "brand_contact_sheet_summary": _rel(
            repo_root,
            operator_dir
            / f"brand-detail-contact-sheet-{batch_suffix}"
            / "brand-detail-contact-sheet.summary.json",
        ),
        "brand_contact_sheet_preflight_json": _rel(
            repo_root,
            operator_dir / f"{batch_stem}.contact-sheet-preflight.json",
        ),
        "brand_contact_sheet_preflight_md": _rel(
            repo_root,
            operator_dir / f"{batch_stem}.contact-sheet-preflight.md",
        ),
        "applied_batch_file": _rel(repo_root, applied_batch_dir / batch_file_name),
        "applied_batch_summary": _rel(
            repo_root, applied_batch_dir / f"{batch_file_name}.csv-apply.summary.json"
        ),
        "applied_batch_md": _rel(repo_root, applied_batch_dir / f"{batch_file_name}.csv-apply.md"),
        "applied_batch_preflight_json": _rel(
            repo_root, applied_batch_dir / f"{batch_file_name}.preflight.json"
        ),
        "applied_batch_preflight_md": _rel(
            repo_root, applied_batch_dir / f"{batch_file_name}.preflight.md"
        ),
        "batch_file": _rel(repo_root, operator_dir / "batches" / batch_file_name),
        "batch_preflight_json": _rel(
            repo_root, operator_dir / "batches" / f"{batch_file_name}.preflight.json"
        ),
        "batch_preflight_md": _rel(
            repo_root, operator_dir / "batches" / f"{batch_file_name}.preflight.md"
        ),
        "brand_decisions": _rel(
            repo_root, operator_dir / "brand-product-review-bundle" / "decisions.todo.jsonl"
        ),
        "pii_decisions": _rel(
            repo_root, operator_dir / "review-pii-screening-bundle" / "decisions.todo.jsonl"
        ),
        "yolo_annotations": _rel(
            repo_root, operator_dir / "yolo-section-annotation-bundle" / "annotation.todo.jsonl"
        ),
        "batch_dir": _rel(repo_root, operator_dir / "batches"),
        "reconciled_dir": _rel(repo_root, reconciled_dir),
        "reconcile_summary": _rel(repo_root, reconciled_dir / "reconcile.summary.json"),
        "reconcile_md": _rel(repo_root, reconciled_dir / "reconcile.summary.md"),
        "reconciled_brand": _rel(
            repo_root, reconciled_dir / "brand_product_review.reconciled.jsonl"
        ),
        "reconciled_pii": _rel(repo_root, reconciled_dir / "review_pii_screening.reconciled.jsonl"),
        "reconciled_yolo": _rel(
            repo_root, reconciled_dir / "yolo_section_annotation.reconciled.jsonl"
        ),
        "progress_json": _rel(repo_root, reconciled_dir / "operator-review-batch-progress.json"),
        "progress_md": _rel(repo_root, reconciled_dir / "operator-review-batch-progress.md"),
        "taxonomy_staging": taxonomy_staging_rel,
        "reviewed_brand": _rel(
            repo_root, reconciled_dir / "brand-product-reviewed.decisions.jsonl"
        ),
        "reviewed_brand_summary": _rel(
            repo_root, reconciled_dir / "brand-product-reviewed.summary.json"
        ),
        "brand_preflight_json": _rel(
            repo_root, reconciled_dir / "brand-product-review-preflight.json"
        ),
        "brand_gate_json": _rel(repo_root, reconciled_dir / "brand-db-import-gate.json"),
        "brand_gate_md": _rel(repo_root, reconciled_dir / "brand-db-import-gate.md"),
        "approved_manifest": _rel(
            repo_root, reconciled_dir / "approved-product-import-manifest.jsonl"
        ),
        "approved_manifest_summary": _rel(
            repo_root, reconciled_dir / "approved-product-import-manifest.summary.json"
        ),
        "ocr_candidate_manifest": _rel(
            repo_root,
            operator_dir / "supplement-review-ocr-ground-truth-candidates.jsonl",
        ),
        "ocr_ground_truth_template": _rel(
            repo_root,
            operator_dir / "ocr-ground-truth-template.jsonl",
        ),
        "ocr_ground_truth_template_summary": _rel(
            repo_root,
            operator_dir / "ocr-ground-truth-template.summary.json",
        ),
        "ocr_ground_truth_materialized_image_dir": _rel(
            repo_root,
            operator_dir / "ocr-ground-truth-materialized-images",
        ),
        "ocr_ground_truth_review_bundle_dir": _rel(
            repo_root,
            operator_dir / "ocr-ground-truth-review-bundle",
        ),
        "ocr_ground_truth_bundle_summary": _rel(
            repo_root,
            operator_dir / "ocr-ground-truth-review-bundle" / "summary.json",
        ),
        "crawling_image_root": "data/nutrition_reference/crawling-image",
        "ocr_ground_truth": _rel(
            repo_root,
            operator_dir / "ocr-ground-truth-review-bundle" / "ground-truth.todo.jsonl",
        ),
        "ocr_ground_truth_preflight_json": _rel(
            repo_root,
            reconciled_dir / "ocr-ground-truth-preflight.json",
        ),
        "ocr_ground_truth_preflight_md": _rel(
            repo_root,
            reconciled_dir / "ocr-ground-truth-preflight.md",
        ),
        "reviewed_pii": _rel(repo_root, reconciled_dir / "pii-reviewed.decisions.jsonl"),
        "reviewed_pii_summary": _rel(repo_root, reconciled_dir / "pii-reviewed.summary.json"),
        "pii_preflight_json": _rel(repo_root, reconciled_dir / "pii-review-preflight.json"),
        "pii_apply_output": _rel(repo_root, reconciled_dir / "teacher-safe-ocr-candidates.jsonl"),
        "pii_apply_summary": _rel(
            repo_root, reconciled_dir / "teacher-safe-ocr-candidates.summary.json"
        ),
        "ocr_benchmark_gate_json": _rel(repo_root, reconciled_dir / "ocr-benchmark-gate.json"),
        "ocr_benchmark_gate_md": _rel(repo_root, reconciled_dir / "ocr-benchmark-gate.md"),
        "ocr_benchmark_manifest": _rel(repo_root, reconciled_dir / "ocr-benchmark-manifest.jsonl"),
        "ocr_benchmark_manifest_summary": _rel(
            repo_root,
            reconciled_dir / "ocr-benchmark-manifest.summary.json",
        ),
        "ocr_benchmark_materialized_image_dir": _rel(
            repo_root,
            reconciled_dir / "ocr-benchmark-materialized-images",
        ),
        "ocr_benchmark_split_manifest": _rel(
            repo_root,
            reconciled_dir / "ocr-benchmark-manifest.split.jsonl",
        ),
        "ocr_benchmark_split_summary": _rel(
            repo_root,
            reconciled_dir / "ocr-benchmark-manifest.split.summary.json",
        ),
        "ocr_observation_dir": _rel(repo_root, reconciled_dir / "ocr-provider-observations"),
        "ocr_observations": _rel(
            repo_root,
            reconciled_dir / "ocr-provider-observations" / "supplement-ocr-observations.jsonl",
        ),
        "ocr_metric_benchmark_manifest": _rel(
            repo_root,
            reconciled_dir / "ocr-provider-metric-benchmark.jsonl",
        ),
        "ocr_metric_benchmark_summary": _rel(
            repo_root,
            reconciled_dir / "ocr-provider-metric-benchmark.summary.json",
        ),
        "paddleocr_text_target_preflight_json": _rel(
            repo_root,
            reconciled_dir / "paddleocr-text-target-chain-preflight.json",
        ),
        "paddleocr_text_target_preflight_md": _rel(
            repo_root,
            reconciled_dir / "paddleocr-text-target-chain-preflight.md",
        ),
        "paddleocr_text_eval_summary": _rel(
            repo_root,
            reconciled_dir / "paddleocr-text-extraction-eval-summary.json",
        ),
        "paddleocr_text_target_gate_json": _rel(
            repo_root,
            reconciled_dir / "paddleocr-text-extraction-target-gate.json",
        ),
        "paddleocr_text_target_gate_md": _rel(
            repo_root,
            reconciled_dir / "paddleocr-text-extraction-target-gate.md",
        ),
        "yolo_template": _rel(repo_root, operator_dir / "yolo-section-annotation-template.jsonl"),
        "reviewed_yolo": _rel(repo_root, reconciled_dir / "yolo-reviewed.annotations.jsonl"),
        "yolo_source_map": _rel(repo_root, reconciled_dir / "yolo-reviewed.source-map.json"),
        "reviewed_yolo_summary": _rel(repo_root, reconciled_dir / "yolo-reviewed.summary.json"),
        "yolo_preflight_json": _rel(repo_root, reconciled_dir / "yolo-annotation-preflight.json"),
        "yolo_export_manifest": _rel(repo_root, reconciled_dir / "yolo-section-export.json"),
        "yolo_promotion_summary": _rel(
            repo_root, reconciled_dir / "yolo-section-export.summary.json"
        ),
        "yolo_dataset_yaml": _rel(
            repo_root, reconciled_dir / "yolo-section-dataset" / "dataset.yaml"
        ),
        "yolo_materialize_summary": _rel(
            repo_root, reconciled_dir / "yolo-section-dataset.materialize.json"
        ),
        "yolo_validation_summary": _rel(
            repo_root, reconciled_dir / "yolo-section-dataset.validation.json"
        ),
        "yolo_dataset_gate_json": _rel(
            repo_root, reconciled_dir / "yolo-section-dataset-gate.json"
        ),
        "yolo_dataset_gate_md": _rel(repo_root, reconciled_dir / "yolo-section-dataset-gate.md"),
    }


def _commands_for_queue(
    *,
    queue_key: str,
    paths: Mapping[str, str],
    batch_key: str,
    preserved_batch_overrides: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Return queue-specific post-edit commands.

    Args:
        queue_key: Current operator queue key.
        paths: Repo-relative command paths.
        batch_key: Current batch key.
        preserved_batch_overrides: Already-applied batch files to preserve when
            reconciling queue copies.

    Returns:
        Ordered command rows for the current queue.
    """
    preserved_overrides = dict(preserved_batch_overrides or {})
    if queue_key == "brand_product_review":
        applied_paths = dict(paths)
        applied_paths["batch_file"] = paths["applied_batch_file"]
        applied_paths["batch_preflight_json"] = paths["applied_batch_preflight_json"]
        applied_paths["batch_preflight_md"] = paths["applied_batch_preflight_md"]
        override_paths = dict(preserved_overrides)
        override_paths[batch_key] = paths["applied_batch_file"]
        return (
            _brand_review_contact_sheet_preflight_commands(paths=paths)
            + _brand_review_csv_triage_commands(paths=paths, start_order=2)
            + _brand_review_csv_apply_commands(paths=paths, start_order=3)
            + _common_reconcile_commands(
                paths=applied_paths,
                batch_key=batch_key,
                start_order=4,
                batch_file_override_paths=override_paths,
                batch_review_csv_path=paths["batch_review_csv"],
            )
            + _brand_product_commands(paths=paths, start_order=7)
        )
    if queue_key == "review_pii_screening":
        return (
            _operator_jsonl_triage_commands(queue_key=queue_key, paths=paths)
            + _common_reconcile_commands(
                paths=paths,
                batch_key=batch_key,
                start_order=2,
                batch_file_override_paths=preserved_overrides,
            )
            + _review_pii_commands(paths=paths, start_order=5)
        )
    if queue_key == "yolo_section_annotation":
        return (
            _operator_jsonl_triage_commands(queue_key=queue_key, paths=paths)
            + _common_reconcile_commands(
                paths=paths,
                batch_key=batch_key,
                start_order=2,
                batch_file_override_paths=preserved_overrides,
            )
            + _yolo_section_commands(paths=paths, start_order=5)
        )
    raise OperatorCommandChecklistError("Unsupported queue key.")


def _path_fingerprint(path: Path) -> str:
    """Return a short non-secret path fingerprint for public artifacts.

    Args:
        path: Path to identify without exposing it.

    Returns:
        Short hexadecimal fingerprint.
    """
    return f"fp-{progress_preflight._sha256_text(str(path.expanduser()))[:8]}"


def _blocked_until(queue_key: str) -> list[str]:
    """Return queue-specific blockers for command execution.

    Args:
        queue_key: Current operator queue key.

    Returns:
        Safe blocker code list.
    """
    if queue_key == "review_pii_screening":
        return [
            "operator_edits_current_batch",
            "batch_file_preflight_ready_for_reconcile",
            "strict_pii_review_complete_before_teacher_ocr_eval",
            "ocr_ground_truth_review_bundle_ready_before_manual_gt",
            "manual_ocr_ground_truth_preflight_ready_before_benchmark",
            "ocr_benchmark_manifest_ready_before_provider_observations",
            "paddleocr_text_target_gate_requires_privacy_cleared_holdout_metrics",
        ]
    if queue_key == "yolo_section_annotation":
        return [
            "operator_edits_current_batch",
            "batch_file_preflight_ready_for_reconcile",
            "strict_yolo_annotation_complete_before_dataset_materialization",
        ]
    return [
        "operator_edits_current_batch",
        "contact_sheet_preflight_ready_for_csv_apply",
        "all_brand_review_csv_rows_reviewed",
        "applied_batch_file_preflight_ready_for_reconcile",
        "batch_file_preflight_ready_for_reconcile",
        "strict_brand_review_complete_before_product_import",
    ]


def _common_reconcile_commands(
    *,
    paths: Mapping[str, str],
    batch_key: str,
    start_order: int = 1,
    batch_file_override_paths: Mapping[str, str] | None = None,
    batch_review_csv_path: str | None = None,
) -> list[dict[str, Any]]:
    """Return common post-edit reconcile commands.

    Args:
        paths: Repo-relative command paths.
        batch_key: Current batch key.
        start_order: First command order.
        batch_file_override_paths: Optional batch JSONL copies to pass into
            reconcile without overwriting original editable batch files.
        batch_review_csv_path: Optional brand review CSV path to validate against
            the current batch JSONL.

    Returns:
        Ordered common command rows.
    """
    override_arg = "".join(
        f" --batch-file-override {override_batch_key} {override_path}"
        for override_batch_key, override_path in sorted((batch_file_override_paths or {}).items())
    )
    review_csv_arg = f" --batch-review-csv {batch_review_csv_path}" if batch_review_csv_path else ""
    return [
        _command(
            order=start_order,
            script_key="preflight_supplement_operator_review_batch_file",
            purpose="Confirm the edited local batch is complete before reconcile.",
            gate_policy="must_pass_before_reconcile",
            command=(
                f"{paths['python']} backend/scripts/preflight_supplement_operator_review_batch_file.py "
                f"--batch-plan {paths['batch_plan']} --batch-key {batch_key} "
                f"--batch-file {paths['batch_file']} --output {paths['batch_preflight_json']} "
                f"--markdown-output {paths['batch_preflight_md']}"
                f"{review_csv_arg}"
            ),
        ),
        _command(
            order=start_order + 1,
            script_key="reconcile_supplement_operator_review_batch_files",
            purpose="Merge completed batch files into reconciled queue copies without overwriting sources.",
            gate_policy="no_source_overwrite",
            command=(
                f"{paths['python']} backend/scripts/reconcile_supplement_operator_review_batch_files.py "
                f"--batch-plan {paths['batch_plan']} --brand-decisions {paths['brand_decisions']} "
                f"--pii-decisions {paths['pii_decisions']} --yolo-annotations {paths['yolo_annotations']} "
                f"--batch-dir {paths['batch_dir']} --output-dir {paths['reconciled_dir']} "
                f"--summary-output {paths['reconcile_summary']} --markdown-output {paths['reconcile_md']}"
                f"{override_arg}"
            ),
        ),
        _command(
            order=start_order + 2,
            script_key="preflight_supplement_operator_review_batch_progress",
            purpose="Confirm queue-level progress after reconcile.",
            gate_policy="must_pass_before_queue_preflight",
            command=(
                f"{paths['python']} backend/scripts/preflight_supplement_operator_review_batch_progress.py "
                f"--batch-plan {paths['batch_plan']} --brand-decisions {paths['reconciled_brand']} "
                f"--pii-decisions {paths['reconciled_pii']} --yolo-annotations {paths['reconciled_yolo']} "
                f"--output {paths['progress_json']} --markdown-output {paths['progress_md']}"
            ),
        ),
    ]


def _batch_file_overrides_from_dir(
    *,
    repo_root: Path,
    batch_override_dir: Path | None,
) -> dict[str, str]:
    """Return repo-relative batch override files from an optional directory.

    Args:
        repo_root: Repository root used to enforce repo-relative paths.
        batch_override_dir: Directory containing already-applied batch JSONL
            files, or ``None`` when no previous batch override should be
            preserved.

    Returns:
        Mapping from safe batch key to repo-relative JSONL path.

    Raises:
        OperatorCommandChecklistError: If the directory or file names are
            outside the repo or do not map to supported batch keys.
    """
    if batch_override_dir is None:
        return {}
    if not batch_override_dir.exists() or not batch_override_dir.is_dir():
        raise OperatorCommandChecklistError("Batch override directory does not exist.")
    overrides: dict[str, str] = {}
    for path in sorted(batch_override_dir.glob("*.jsonl")):
        batch_key = _batch_key_from_file_name(path.name)
        if batch_key in overrides:
            raise OperatorCommandChecklistError("Duplicate batch override key.")
        overrides[batch_key] = _rel(repo_root, path)
    return overrides


def _batch_key_from_file_name(file_name: str) -> str:
    """Convert an applied batch JSONL file name into a safe batch key.

    Args:
        file_name: File name such as ``brand_product_review-001.jsonl``.

    Returns:
        Batch key such as ``brand_product_review:001``.

    Raises:
        OperatorCommandChecklistError: If the file name is unsupported.
    """
    safe_name = _safe_file_name(file_name)
    if not safe_name.endswith(".jsonl"):
        raise OperatorCommandChecklistError("Batch override file must be JSONL.")
    stem = safe_name.removesuffix(".jsonl")
    if "-" not in stem:
        raise OperatorCommandChecklistError("Batch override file name is unsupported.")
    queue_key, batch_number = stem.rsplit("-", 1)
    if queue_key not in {"brand_product_review", "review_pii_screening", "yolo_section_annotation"}:
        raise OperatorCommandChecklistError("Batch override queue key is unsupported.")
    if not batch_number.isdigit() or len(batch_number) != BATCH_NUMBER_DIGIT_COUNT:
        raise OperatorCommandChecklistError("Batch override number is unsupported.")
    return f"{queue_key}:{batch_number}"


def _brand_review_contact_sheet_preflight_commands(
    *,
    paths: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Return the brand review contact sheet alignment preflight command.

    Args:
        paths: Repo-relative command paths.

    Returns:
        Ordered command rows.
    """
    return [
        _command(
            order=1,
            script_key="preflight_supplement_brand_review_contact_sheet",
            purpose="Confirm the CSV and safe visual contact sheet still describe the same rows.",
            gate_policy="must_pass_before_csv_apply",
            command=(
                f"{paths['python']} backend/scripts/preflight_supplement_brand_review_contact_sheet.py "
                f"--batch-review-csv {paths['batch_review_csv']} "
                f"--contact-sheet-summary {paths['brand_contact_sheet_summary']} "
                f"--output {paths['brand_contact_sheet_preflight_json']} "
                f"--markdown-output {paths['brand_contact_sheet_preflight_md']} "
                "--require-all-rows-with-thumbnails"
            ),
        )
    ]


def _brand_review_csv_triage_commands(
    *,
    paths: Mapping[str, str],
    start_order: int = 1,
) -> list[dict[str, Any]]:
    """Return the brand review CSV triage command.

    Args:
        paths: Repo-relative command paths.
        start_order: First command order.

    Returns:
        Ordered command rows.
    """
    return [
        _command(
            order=start_order,
            script_key="build_supplement_brand_review_batch_triage",
            purpose="Summarize CSV review priority and catch partial rows before apply.",
            gate_policy="operator_review_helper_no_decision",
            command=(
                f"{paths['python']} backend/scripts/build_supplement_brand_review_batch_triage.py "
                f"--batch-review-csv {paths['batch_review_csv']} "
                f"--output {paths['batch_triage_json']} "
                f"--markdown-output {paths['batch_triage_md']}"
            ),
        )
    ]


def _operator_jsonl_triage_commands(
    *, queue_key: str, paths: Mapping[str, str]
) -> list[dict[str, Any]]:
    """Return the PII/YOLO JSONL batch triage command.

    Args:
        queue_key: Current operator queue key.
        paths: Repo-relative command paths.

    Returns:
        Ordered command rows.
    """
    return [
        _command(
            order=1,
            script_key="build_supplement_operator_review_batch_triage",
            purpose="Summarize JSONL review priority without exposing row payloads.",
            gate_policy="operator_review_helper_no_decision",
            command=(
                f"{paths['python']} backend/scripts/build_supplement_operator_review_batch_triage.py "
                f"--queue-key {queue_key} --batch-file {paths['source_batch_file']} "
                f"--output {paths['batch_triage_json']} "
                f"--markdown-output {paths['batch_triage_md']}"
            ),
        )
    ]


def _brand_review_csv_apply_commands(
    *,
    paths: Mapping[str, str],
    start_order: int = 1,
) -> list[dict[str, Any]]:
    """Return the brand review CSV to JSONL copy command.

    Args:
        paths: Repo-relative command paths.
        start_order: First command order.

    Returns:
        Ordered command rows.
    """
    return [
        _command(
            order=start_order,
            script_key="apply_supplement_brand_batch_review_csv_decisions",
            purpose=(
                "Apply only a fully reviewed operator CSV into a separate batch JSONL copy "
                "without overwriting the source batch."
            ),
            gate_policy="require_all_reviewed_no_source_overwrite",
            command=(
                f"{paths['python']} backend/scripts/apply_supplement_brand_batch_review_csv_decisions.py "
                f"--batch-file {paths['source_batch_file']} "
                f"--batch-review-csv {paths['batch_review_csv']} "
                f"--output {paths['applied_batch_file']} "
                f"--summary-output {paths['applied_batch_summary']} "
                f"--markdown-output {paths['applied_batch_md']} "
                "--reviewer-id operator_batch --reviewed-at-safe-token operator_csv_review "
                "--attest-brand-product-review-completed "
                "--attest-not-using-product-folder-literal-as-manufacturer "
                "--attest-product-name-reviewed-from-label-or-safe-catalog "
                "--attest-no-raw-ocr-or-provider-payload-copied "
                "--attest-db-import-allowed "
                "--require-all-reviewed"
            ),
        )
    ]


def _brand_product_commands(
    *, paths: Mapping[str, str], start_order: int = 4
) -> list[dict[str, Any]]:
    """Return brand/product review post-edit commands.

    Args:
        paths: Repo-relative command paths.
        start_order: First brand command order.

    Returns:
        Ordered command rows.
    """
    return [
        _command(
            order=start_order,
            script_key="extract_supplement_brand_reviewed_decisions",
            purpose="Separate reviewed brand decisions from blank queue stubs for preview-only gating.",
            gate_policy="partial_preview_only",
            command=(
                f"{paths['python']} backend/scripts/extract_supplement_brand_reviewed_decisions.py "
                f"--taxonomy-staging {paths['taxonomy_staging']} --decisions {paths['reconciled_brand']} "
                f"--output {paths['reviewed_brand']} --summary {paths['reviewed_brand_summary']}"
            ),
        ),
        _command(
            order=start_order + 1,
            script_key="preflight_supplement_brand_review_decisions",
            purpose="Run strict brand review preflight; this must reach zero blank rows before DB import.",
            gate_policy="strict_zero_blank_pending_invalid_required",
            command=(
                f"{paths['python']} backend/scripts/preflight_supplement_brand_review_decisions.py "
                f"--taxonomy-staging {paths['taxonomy_staging']} --decisions {paths['reconciled_brand']} "
                f"--output {paths['brand_preflight_json']} --require-all-reviewed"
            ),
        ),
        _command(
            order=start_order + 2,
            script_key="gate_supplement_brand_db_import",
            purpose="Gate approved product import manifest creation after strict brand preflight.",
            gate_policy="must_pass_before_product_manifest",
            command=(
                f"{paths['python']} backend/scripts/gate_supplement_brand_db_import.py "
                f"--brand-decision-preflight {paths['brand_preflight_json']} "
                f"--output {paths['brand_gate_json']} --markdown-output {paths['brand_gate_md']}"
            ),
        ),
        _command(
            order=start_order + 3,
            script_key="apply_supplement_brand_review_decisions",
            purpose="Create the approved product import manifest after all brand rows are reviewed.",
            gate_policy="manifest_only_no_db_write",
            command=(
                f"{paths['python']} backend/scripts/apply_supplement_brand_review_decisions.py "
                f"--taxonomy-staging {paths['taxonomy_staging']} --decisions {paths['reconciled_brand']} "
                f"--output {paths['approved_manifest']} --summary {paths['approved_manifest_summary']} "
                "--require-all-reviewed"
            ),
        ),
    ]


def _review_pii_commands(*, paths: Mapping[str, str], start_order: int = 4) -> list[dict[str, Any]]:
    """Return PII-screening review post-edit commands.

    Args:
        paths: Repo-relative command paths.
        start_order: First PII command order.

    Returns:
        Ordered command rows.
    """
    return [
        _command(
            order=start_order,
            script_key="extract_supplement_pii_reviewed_decisions",
            purpose="Separate reviewed PII decisions from blank queue stubs for teacher OCR gating.",
            gate_policy="partial_teacher_ocr_preview_only",
            command=(
                f"{paths['python']} backend/scripts/extract_supplement_pii_reviewed_decisions.py "
                f"--candidate-manifest {paths['ocr_candidate_manifest']} "
                f"--decisions {paths['reconciled_pii']} --output {paths['reviewed_pii']} "
                f"--summary {paths['reviewed_pii_summary']}"
            ),
        ),
        _command(
            order=start_order + 1,
            script_key="preflight_supplement_review_pii_screening_decisions",
            purpose="Run strict PII decision preflight before any teacher OCR benchmark can run.",
            gate_policy="strict_zero_blank_pending_invalid_required",
            command=(
                f"{paths['python']} backend/scripts/preflight_supplement_review_pii_screening_decisions.py "
                f"--candidate-manifest {paths['ocr_candidate_manifest']} "
                f"--decisions {paths['reconciled_pii']} --output {paths['pii_preflight_json']} "
                "--require-all-reviewed"
            ),
        ),
        _command(
            order=start_order + 2,
            script_key="apply_supplement_review_pii_screening_decisions",
            purpose="Write teacher-safe OCR candidate manifest after strict PII review passes.",
            gate_policy="no_teacher_ocr_call",
            command=(
                f"{paths['python']} backend/scripts/apply_supplement_review_pii_screening_decisions.py "
                f"--candidate-manifest {paths['ocr_candidate_manifest']} "
                f"--decisions {paths['reviewed_pii']} --output {paths['pii_apply_output']} "
                f"--summary {paths['pii_apply_summary']} --require-all-reviewed"
            ),
        ),
        _command(
            order=start_order + 3,
            script_key="export_supplement_ocr_ground_truth_template",
            purpose="Create a local manual OCR ground-truth template from PII-cleared rows.",
            gate_policy="manual_gt_template_only_no_provider_call",
            command=(
                f"{paths['python']} backend/scripts/export_supplement_ocr_ground_truth_template.py "
                f"--candidate-manifest {paths['pii_apply_output']} "
                f"--output {paths['ocr_ground_truth_template']} "
                f"--summary {paths['ocr_ground_truth_template_summary']} "
                f"--source-root {paths['crawling_image_root']} "
                f"--materialized-image-dir {paths['ocr_ground_truth_materialized_image_dir']}"
            ),
        ),
        _command(
            order=start_order + 4,
            script_key="build_supplement_ocr_ground_truth_review_bundle",
            purpose="Build the editable OCR ground-truth review bundle used by the manual preflight.",
            gate_policy="operator_edits_required_before_preflight",
            command=(
                f"{paths['python']} backend/scripts/build_supplement_ocr_ground_truth_review_bundle.py "
                f"--template {paths['ocr_ground_truth_template']} "
                f"--output-dir {paths['ocr_ground_truth_review_bundle_dir']}"
            ),
        ),
        _command(
            order=start_order + 5,
            script_key="preflight_supplement_ocr_ground_truth_manifest",
            purpose="Check operator-edited OCR ground truth before benchmark materialization.",
            gate_policy="must_pass_before_ocr_benchmark_manifest",
            command=(
                f"{paths['python']} backend/scripts/preflight_supplement_ocr_ground_truth_manifest.py "
                f"--ground-truth {paths['ocr_ground_truth']} "
                f"--output {paths['ocr_ground_truth_preflight_json']} "
                f"--markdown-output {paths['ocr_ground_truth_preflight_md']} "
                "--required-expected-section ingredient_amounts "
                "--required-expected-section intake_method "
                "--required-expected-section precautions "
                "--required-expected-section allergen_warnings"
            ),
        ),
        _command(
            order=start_order + 6,
            script_key="build_supplement_ocr_benchmark_manifest",
            purpose="Materialize human-reviewed OCR benchmark fixtures after PII and manual GT gates pass.",
            gate_policy="pii_cleared_human_gt_only",
            command=(
                f"{paths['python']} backend/scripts/build_supplement_ocr_benchmark_manifest.py "
                f"--candidate-manifest {paths['pii_apply_output']} "
                f"--ground-truth {paths['ocr_ground_truth']} "
                f"--output {paths['ocr_benchmark_manifest']} "
                f"--summary {paths['ocr_benchmark_manifest_summary']} "
                f"--source-root {paths['crawling_image_root']} "
                f"--materialized-image-dir {paths['ocr_benchmark_materialized_image_dir']} "
                "--required-expected-section ingredient_amounts "
                "--required-expected-section intake_method "
                "--required-expected-section precautions "
                "--required-expected-section allergen_warnings"
            ),
        ),
        _command(
            order=start_order + 7,
            script_key="assign_paddleocr_benchmark_splits",
            purpose="Assign leakage-safe train holdout test splits grouped by product hash.",
            gate_policy="must_pass_before_provider_observations",
            command=(
                f"{paths['python']} backend/scripts/assign_paddleocr_benchmark_splits.py "
                f"--benchmark-manifest {paths['ocr_benchmark_manifest']} "
                f"--output {paths['ocr_benchmark_split_manifest']} "
                f"--summary {paths['ocr_benchmark_split_summary']}"
            ),
        ),
        _command(
            order=start_order + 8,
            script_key="gate_supplement_ocr_benchmark",
            purpose="Assert PII, manual GT, benchmark manifest, and split gates before teacher OCR.",
            gate_policy="must_pass_before_teacher_ocr_eval",
            command=(
                f"{paths['python']} backend/scripts/gate_supplement_ocr_benchmark.py "
                f"--pii-preflight {paths['pii_preflight_json']} "
                f"--ground-truth-bundle-summary {paths['ocr_ground_truth_bundle_summary']} "
                f"--ground-truth-preflight {paths['ocr_ground_truth_preflight_json']} "
                f"--benchmark-summary {paths['ocr_benchmark_manifest_summary']} "
                f"--benchmark-split-summary {paths['ocr_benchmark_split_summary']} "
                f"--output {paths['ocr_benchmark_gate_json']} "
                f"--markdown-output {paths['ocr_benchmark_gate_md']} "
                "--require-ready-for-teacher-ocr-eval"
            ),
        ),
        _command(
            order=start_order + 9,
            script_key="collect_supplement_ocr_observations",
            purpose="Collect redacted CLOVA Google Vision and PaddleOCR observations for the benchmark split.",
            gate_policy="external_ocr_requires_explicit_env_opt_in",
            command=(
                f"{paths['python']} backend/scripts/collect_supplement_ocr_observations.py "
                f"--manifest {paths['ocr_benchmark_split_manifest']} "
                f"--output-dir {paths['ocr_observation_dir']} "
                "--providers clova_ocr,google_vision_document,paddleocr_local"
            ),
        ),
        _command(
            order=start_order + 10,
            script_key="merge_paddleocr_text_observations_into_benchmark",
            purpose="Join redacted provider observations back into benchmark fixtures for text target evaluation.",
            gate_policy="no_raw_ocr_merge",
            command=(
                f"{paths['python']} backend/scripts/merge_paddleocr_text_observations_into_benchmark.py "
                f"--benchmark-manifest {paths['ocr_benchmark_split_manifest']} "
                f"--observations {paths['ocr_observations']} "
                f"--output {paths['ocr_metric_benchmark_manifest']} "
                f"--summary {paths['ocr_metric_benchmark_summary']}"
            ),
        ),
        _command(
            order=start_order + 11,
            script_key="preflight_paddleocr_text_target_chain",
            purpose="Verify held-out PaddleOCR text metrics are ready for the 95 percent target gate.",
            gate_policy="must_pass_before_text_eval_summary",
            command=(
                f"{paths['python']} backend/scripts/preflight_paddleocr_text_target_chain.py "
                f"--benchmark-manifest {paths['ocr_metric_benchmark_manifest']} "
                f"--output {paths['paddleocr_text_target_preflight_json']} "
                f"--markdown-output {paths['paddleocr_text_target_preflight_md']} "
                "--eval-split holdout --min-fixtures 30"
            ),
        ),
        _command(
            order=start_order + 12,
            script_key="build_paddleocr_text_extraction_eval_summary",
            purpose="Build the redacted PaddleOCR held-out text extraction eval summary with privacy review assertion.",
            gate_policy="privacy_cleared_human_gt_required",
            command=(
                f"{paths['python']} backend/scripts/build_paddleocr_text_extraction_eval_summary.py "
                f"--benchmark-manifest {paths['ocr_metric_benchmark_manifest']} "
                f"--output {paths['paddleocr_text_eval_summary']} "
                "--provider paddleocr_local --eval-split holdout "
                "--leakage-check-passed --privacy-review-cleared"
            ),
        ),
        _command(
            order=start_order + 13,
            script_key="gate_paddleocr_text_extraction_target",
            purpose="Stop PaddleOCR training only when held-out human GT text extraction reaches the 95 percent target.",
            gate_policy="stop_training_only_if_95_percent_target_reached",
            command=(
                f"{paths['python']} backend/scripts/gate_paddleocr_text_extraction_target.py "
                f"--eval-summary {paths['paddleocr_text_eval_summary']} "
                f"--output {paths['paddleocr_text_target_gate_json']} "
                f"--markdown-output {paths['paddleocr_text_target_gate_md']} "
                "--min-fixtures 30"
            ),
        ),
    ]


def _yolo_section_commands(
    *, paths: Mapping[str, str], start_order: int = 4
) -> list[dict[str, Any]]:
    """Return YOLO section-annotation post-edit commands.

    Args:
        paths: Repo-relative command paths.
        start_order: First YOLO command order.

    Returns:
        Ordered command rows.
    """
    return [
        _command(
            order=start_order,
            script_key="extract_supplement_yolo_reviewed_annotations",
            purpose="Separate reviewed YOLO section annotations from blank queue stubs.",
            gate_policy="partial_dataset_preview_only",
            command=(
                f"{paths['python']} backend/scripts/extract_supplement_yolo_reviewed_annotations.py "
                f"--template {paths['yolo_template']} --annotations {paths['reconciled_yolo']} "
                f"--output {paths['reviewed_yolo']} --source-map {paths['yolo_source_map']} "
                f"--summary {paths['reviewed_yolo_summary']}"
            ),
        ),
        _command(
            order=start_order + 1,
            script_key="preflight_supplement_yolo_annotation_decisions",
            purpose="Run strict YOLO annotation preflight before dataset materialization.",
            gate_policy="strict_zero_blank_pending_invalid_required",
            command=(
                f"{paths['python']} backend/scripts/preflight_supplement_yolo_annotation_decisions.py "
                f"--template {paths['reviewed_yolo']} --source-map {paths['yolo_source_map']} "
                f"--output {paths['yolo_preflight_json']} --require-all-reviewed"
            ),
        ),
        _command(
            order=start_order + 2,
            script_key="promote_supplement_yolo_annotation_template",
            purpose="Promote reviewed supplement section boxes into an Ultralytics-compatible export.",
            gate_policy="only_after_strict_annotation_preflight",
            command=(
                f"{paths['python']} backend/scripts/promote_supplement_yolo_annotation_template.py "
                f"--template {paths['reviewed_yolo']} --output {paths['yolo_export_manifest']} "
                f"--source-map {paths['yolo_source_map']} --summary {paths['yolo_promotion_summary']}"
            ),
        ),
        _command(
            order=start_order + 3,
            script_key="materialize_supplement_section_yolo_dataset",
            purpose="Materialize reviewed section boxes into YOLO dataset files without training.",
            gate_policy="no_training_execution",
            command=(
                f"{paths['python']} backend/scripts/materialize_supplement_section_yolo_dataset.py "
                f"--export {paths['yolo_export_manifest']} --source-map {paths['yolo_source_map']} "
                f"--dataset-yaml {paths['yolo_dataset_yaml']} > {paths['yolo_materialize_summary']}"
            ),
        ),
        _command(
            order=start_order + 4,
            script_key="validate_supplement_section_yolo_dataset",
            purpose="Validate materialized YOLO dataset files before any training gate.",
            gate_policy="must_pass_before_training_gate",
            command=(
                f"{paths['python']} backend/scripts/validate_supplement_section_yolo_dataset.py "
                f"{paths['yolo_dataset_yaml']} --require-files > {paths['yolo_validation_summary']}"
            ),
        ),
        _command(
            order=start_order + 5,
            script_key="gate_supplement_yolo_section_dataset",
            purpose="Gate supplement YOLO section dataset readiness before YOLO26 training.",
            gate_policy="must_pass_before_training",
            command=(
                f"{paths['python']} backend/scripts/gate_supplement_yolo_section_dataset.py "
                f"--annotation-preflight {paths['yolo_preflight_json']} "
                f"--template-promotion-summary {paths['yolo_promotion_summary']} "
                f"--dataset-materialize-summary {paths['yolo_materialize_summary']} "
                f"--dataset-validation-summary {paths['yolo_validation_summary']} "
                f"--output {paths['yolo_dataset_gate_json']} "
                f"--markdown-output {paths['yolo_dataset_gate_md']}"
            ),
        ),
    ]


def _command(
    *,
    order: int,
    script_key: str,
    purpose: str,
    gate_policy: str,
    command: str,
) -> dict[str, Any]:
    """Build a safe command row.

    Args:
        order: Command order.
        script_key: Script identifier.
        purpose: Human-readable purpose.
        gate_policy: Gate policy.
        command: Repo-relative command.

    Returns:
        Command row.
    """
    (
        execution_state,
        blocked_by,
        requires_operator_input,
        requires_external_opt_in,
    ) = _execution_rule(script_key)
    safe_row = {
        "order": order,
        "script_key": _safe_token(script_key),
        "purpose": _safe_sentence(purpose),
        "gate_policy": _safe_token(gate_policy),
        "execution_state": _safe_token(execution_state),
        "blocked_by": [_safe_token(blocker) for blocker in blocked_by],
        "requires_operator_input": requires_operator_input,
        "requires_external_opt_in": requires_external_opt_in,
        "command": _safe_command(command),
    }
    _reject_unsafe_payload(safe_row)
    return safe_row


def _execution_rule(script_key: str) -> tuple[str, tuple[str, ...], bool, bool]:
    """Return command-level execution readiness metadata.

    Args:
        script_key: Script identifier.

    Returns:
        Tuple of execution state, blocking codes, operator-input flag, and
        external opt-in flag.

    Raises:
        OperatorCommandChecklistError: If a command is not explicitly modeled.
    """
    safe_script_key = _safe_token(script_key)
    rule = COMMAND_EXECUTION_RULES.get(safe_script_key)
    if rule is None:
        raise OperatorCommandChecklistError("Command execution rule is missing.")
    return rule


def _load_json_object(path: Path) -> dict[str, Any]:
    """Load JSON object.

    Args:
        path: JSON path.

    Returns:
        JSON object.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise OperatorCommandChecklistError("Expected JSON object input.")
    return payload


def _required_input(input_paths: Mapping[str, Path], key: str) -> Path:
    """Return required input path.

    Args:
        input_paths: Input path mapping.
        key: Required key.

    Returns:
        Existing input path.
    """
    path = input_paths.get(key)
    if path is None:
        raise OperatorCommandChecklistError(f"Missing required input: {key}")
    if not path.exists():
        raise OperatorCommandChecklistError(f"Input does not exist: {key}")
    return path


def _require_schema(payload: Mapping[str, Any], expected: str) -> None:
    """Validate schema version.

    Args:
        payload: Payload.
        expected: Expected schema.
    """
    if payload.get("schema_version") != expected:
        raise OperatorCommandChecklistError("Unsupported schema version.")


def _reject_unsafe_payload(payload: Any) -> None:
    """Reject local paths and raw payload markers.

    Args:
        payload: Payload to scan.
    """
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if key in {
                "api_key",
                "authorization",
                "image_bytes",
                "ocr_text",
                "owner_hash",
                "provider_payload",
                "raw_image",
                "raw_ocr_text",
                "raw_provider_payload",
                "request_headers",
                "service_key",
            }:
                raise OperatorCommandChecklistError("Unsafe key found.")
            _reject_unsafe_payload(value)
    elif isinstance(payload, list):
        for item in payload:
            _reject_unsafe_payload(item)
    elif isinstance(payload, str) and any(marker in payload for marker in LOCAL_PATH_MARKERS):
        raise OperatorCommandChecklistError("Unsafe local path marker found.")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write JSON payload.

    Args:
        path: Destination path.
        payload: Payload.
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
    """Build redacted failure summary.

    Args:
        input_paths: Input paths.
        output_path: Output path.
        error: Raised exception.

    Returns:
        Failure payload.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "failed",
        "error_type": type(error).__name__,
        "input_names": {key: path.name for key, path in sorted(input_paths.items())},
        "output_name": output_path.name,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def _cli_summary(checklist: Mapping[str, Any]) -> dict[str, Any]:
    """Return compact CLI summary.

    Args:
        checklist: Checklist payload.

    Returns:
        CLI summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": checklist.get("status"),
        "queue_key": checklist.get("queue_key"),
        "batch_key": checklist.get("batch_key"),
        "command_count": checklist.get("command_count"),
    }


def _source_doc_urls(post_plan: Mapping[str, Any]) -> list[str]:
    """Return source docs.

    Args:
        post_plan: Post-completion plan payload.

    Returns:
        Source doc URLs.
    """
    urls = []
    for url in _safe_string_list(post_plan.get("source_doc_urls")):
        if url.startswith("https://") and url not in urls:
            urls.append(url)
    if not urls:
        urls = [
            "https://docs.python.org/3/library/argparse.html",
            "https://docs.python.org/3/library/json.html",
            "https://www.postgresql.org/docs/current/ddl-constraints.html",
            "https://supabase.com/docs/guides/database/postgres/row-level-security",
        ]
    return urls


def _rel(repo_root: Path, path: Path) -> str:
    """Return repo-relative POSIX path.

    Args:
        repo_root: Repository root.
        path: Target path.

    Returns:
        Repo-relative path.
    """
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
    except ValueError as exc:
        raise OperatorCommandChecklistError("Path is outside repo root.") from exc
    return rel.as_posix()


def _taxonomy_staging_path(todo_dir: Path) -> Path:
    """Return the active supplement taxonomy staging artifact.

    Args:
        todo_dir: Date-specific todo artifact directory.

    Returns:
        Existing staging path when available, otherwise the expected path for
        ``todo_dir``.
    """
    expected = todo_dir / f"{todo_dir.name}-supplement-taxonomy-db-staging.jsonl"
    if expected.exists():
        return expected
    candidates = sorted(todo_dir.parent.glob("*/*-supplement-taxonomy-db-staging.jsonl"))
    return candidates[-1] if candidates else expected


def _batch_suffix(batch_file_name: str) -> str:
    """Return the batch number suffix used by contact sheet directories.

    Args:
        batch_file_name: Safe batch file name.

    Returns:
        Safe suffix token.
    """
    stem = batch_file_name.removesuffix(".jsonl")
    suffix = stem.rsplit("-", 1)[-1]
    safe_suffix = _safe_token(suffix)
    if not safe_suffix:
        raise OperatorCommandChecklistError("Batch file name does not contain a safe suffix.")
    return safe_suffix


def _safe_batch_key(value: Any) -> str:
    """Return safe batch key.

    Args:
        value: Candidate value.

    Returns:
        Batch key.
    """
    token = _safe_token(value)
    if ":" not in token:
        return token
    left, right = token.split(":", 1)
    if not left or not right:
        return ""
    return token


def _safe_token(value: Any) -> str:
    """Return safe token.

    Args:
        value: Candidate value.

    Returns:
        Safe token.
    """
    if not isinstance(value, str):
        return ""
    text = value.strip()[:200]
    allowed = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz가-힣_.:-")
    return text if text and all(char in allowed for char in text) else ""


def _safe_file_name(value: Any) -> str:
    """Return safe file name.

    Args:
        value: Candidate value.

    Returns:
        Safe file name.
    """
    if not isinstance(value, str):
        return ""
    text = value.strip()[:200]
    if "/" in text or "\\" in text or not text:
        return ""
    allowed = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz가-힣_.:-")
    return text if all(char in allowed for char in text) else ""


def _safe_sentence(value: Any) -> str:
    """Return bounded sentence.

    Args:
        value: Candidate value.

    Returns:
        Safe sentence.
    """
    if not isinstance(value, str):
        return ""
    text = value.strip()[:320]
    _reject_unsafe_payload(text)
    return text


def _safe_command(value: Any) -> str:
    """Return bounded repo-relative command.

    Args:
        value: Candidate command.

    Returns:
        Safe command.
    """
    if not isinstance(value, str):
        return ""
    text = value.strip()[:COMMAND_MAX_LENGTH]
    _reject_unsafe_payload(text)
    return text


def _safe_bool(value: Any) -> bool:
    """Return strict boolean values for Markdown display.

    Args:
        value: Candidate value.

    Returns:
        Boolean value only when the candidate is already a bool.
    """
    return value if isinstance(value, bool) else False


def _safe_string_list(value: Any) -> list[str]:
    """Return bounded safe string list.

    Args:
        value: Candidate list.

    Returns:
        Safe strings.
    """
    if not isinstance(value, list):
        return []
    result = []
    for item in value[:40]:
        if isinstance(item, str):
            text = item.strip()[:320]
            _reject_unsafe_payload(text)
            result.append(text)
    return result


def _mapping_rows(value: Any) -> list[Mapping[str, Any]]:
    """Return mapping rows.

    Args:
        value: Candidate list.

    Returns:
        Mapping rows.
    """
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _non_negative_int(value: Any) -> int:
    """Return non-negative integer.

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


if __name__ == "__main__":
    main()
