"""Build a redacted readiness report for the supplement learning pipeline.

This report connects the review-gated taxonomy, OCR benchmark, YOLO section
annotation, and PaddleOCR fine-tuning artifacts into one operator checkpoint.
It never reads source images, never calls OCR providers or LLMs, never writes to
the database, and never emits local paths, raw OCR text, or provider payloads.

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
import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "supplement-learning-pipeline-readiness-v1"
SUMMARY_SCHEMA_VERSION = "supplement-learning-pipeline-readiness-summary-v1"
PADDLEOCR_HUMAN_GT_EARLY_STOP_THRESHOLD = 0.95
PADDLEOCR_TEXT_REQUIRED_METRICS = (
    "normalized_text_precision",
    "normalized_text_recall",
    "normalized_text_f1",
)
MAX_REDACTED_STRING_LIST_ITEMS = 20
MAX_REDACTED_STRING_LENGTH = 160
SOURCE_DOC_URLS = (
    "https://docs.ultralytics.com/datasets/detect/",
    "https://docs.ultralytics.com/tasks/detect/",
    "https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html",
    "https://cloud.google.com/vision/docs/ocr",
    "https://api.ncloud-docs.com/docs/en/ai-application-service-ocr",
    "https://docs.sqlalchemy.org/en/21/orm/queryguide/select.html",
)

RAW_FORBIDDEN_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "image_bytes",
        "ocr_text",
        "owner_hash",
        "provider_payload",
        "raw_image",
        "raw_model_response",
        "raw_ocr_text",
        "raw_provider_payload",
        "request_headers",
        "service_key",
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


@dataclass(frozen=True)
class ArtifactSpec:
    """Expected artifact metadata for one pipeline role.

    Args:
        role: Stable operator-facing artifact role.
        expected_schema_versions: Accepted top-level or row schema versions.
        description: Short reason this artifact exists in the pipeline.
    """

    role: str
    expected_schema_versions: frozenset[str]
    description: str


@dataclass(frozen=True)
class StageSpec:
    """Pipeline stage definition.

    Args:
        stage_key: Stable stage identifier.
        phase: High-level pipeline phase.
        required_roles: Artifact roles that prove stage completion.
        pending_roles: Artifact roles that prove the stage is waiting for a
            human decision instead of missing entirely.
        next_operator_action: Safe next action label for the operator.
    """

    stage_key: str
    phase: str
    required_roles: tuple[str, ...]
    pending_roles: tuple[str, ...]
    next_operator_action: str


class PipelineReadinessError(ValueError):
    """Raised when a readiness report cannot be trusted."""


ARTIFACT_SPECS: dict[str, ArtifactSpec] = {
    "taxonomy_audit": ArtifactSpec(
        role="taxonomy_audit",
        expected_schema_versions=frozenset({"supplement-crawling-image-taxonomy-audit-v1"}),
        description="read-only crawling-image structure audit",
    ),
    "taxonomy_staging": ArtifactSpec(
        role="taxonomy_staging",
        expected_schema_versions=frozenset({"supplement-taxonomy-db-staging-v1"}),
        description="category seed and brand-candidate DB staging rows",
    ),
    "brand_review_template": ArtifactSpec(
        role="brand_review_template",
        expected_schema_versions=frozenset({"supplement-brand-review-template-v1"}),
        description="operator template for brand and product review",
    ),
    "brand_review_bundle": ArtifactSpec(
        role="brand_review_bundle",
        expected_schema_versions=frozenset({"supplement-brand-review-bundle-v1"}),
        description="local HTML and decision-template bundle for brand and product review",
    ),
    "brand_review_decision_preflight": ArtifactSpec(
        role="brand_review_decision_preflight",
        expected_schema_versions=frozenset({"supplement-brand-review-decision-preflight-v1"}),
        description="redacted preflight summary for brand/product review decisions",
    ),
    "approved_product_import": ArtifactSpec(
        role="approved_product_import",
        expected_schema_versions=frozenset({"supplement-product-import-manifest-row-v1"}),
        description="approved product/category DB import manifest rows",
    ),
    "category_only_import_dry_run": ArtifactSpec(
        role="category_only_import_dry_run",
        expected_schema_versions=frozenset({"supplement-taxonomy-approved-db-import-v1"}),
        description="dry-run proof that category seed rows plan only category upserts",
    ),
    "category_seed_apply_gate": ArtifactSpec(
        role="category_seed_apply_gate",
        expected_schema_versions=frozenset({"supplement-category-seed-db-apply-gate-v1"}),
        description="category seed DB apply gate after dry-run and product-write blocking checks",
    ),
    "category_seed_target_preflight": ArtifactSpec(
        role="category_seed_target_preflight",
        expected_schema_versions=frozenset({"supplement-category-seed-db-target-preflight-v1"}),
        description="local development DB target preflight before category seed apply",
    ),
    "category_seed_db_verification": ArtifactSpec(
        role="category_seed_db_verification",
        expected_schema_versions=frozenset({"supplement-taxonomy-db-import-verification-v1"}),
        description="read-only DB verification for category seed rows only",
    ),
    "category_seed_cleanup_preflight": ArtifactSpec(
        role="category_seed_cleanup_preflight",
        expected_schema_versions=frozenset({"supplement-category-seed-cleanup-preflight-v1"}),
        description="redacted cleanup preflight for extra active category seed rows",
    ),
    "category_seed_cleanup_apply": ArtifactSpec(
        role="category_seed_cleanup_apply",
        expected_schema_versions=frozenset({"supplement-category-seed-cleanup-apply-v1"}),
        description="redacted dry-run/apply summary for extra active category seed cleanup",
    ),
    "taxonomy_db_verification": ArtifactSpec(
        role="taxonomy_db_verification",
        expected_schema_versions=frozenset({"supplement-taxonomy-db-import-verification-v1"}),
        description="read-only DB import verification for reviewed product/category rows",
    ),
    "auto_brand_product_import_dry_run": ArtifactSpec(
        role="auto_brand_product_import_dry_run",
        expected_schema_versions=frozenset({"supplement-brand-products-auto-import-v1"}),
        description=(
            "dry-run proof for provisional auto brand products and product-category mappings"
        ),
    ),
    "auto_brand_product_db_verification": ArtifactSpec(
        role="auto_brand_product_db_verification",
        expected_schema_versions=frozenset({"supplement-brand-products-auto-db-verification-v1"}),
        description="read-only DB verification for provisional auto brand product mappings",
    ),
    "learning_candidate_summary": ArtifactSpec(
        role="learning_candidate_summary",
        expected_schema_versions=frozenset({"supplement-learning-candidate-manifests-v1"}),
        description="review OCR and detail-page YOLO candidate summary",
    ),
    "private_image_tracking_check": ArtifactSpec(
        role="private_image_tracking_check",
        expected_schema_versions=frozenset({"private-image-tracking-check-v1"}),
        description="git tracking gate for source and materialized private images",
    ),
    "pii_screening_template": ArtifactSpec(
        role="pii_screening_template",
        expected_schema_versions=frozenset({"supplement-review-pii-screening-template-v1"}),
        description="operator PII screening template for review OCR images",
    ),
    "pii_screening_review_bundle": ArtifactSpec(
        role="pii_screening_review_bundle",
        expected_schema_versions=frozenset({"supplement-review-pii-screening-review-bundle-v1"}),
        description="local HTML and decision-template bundle for review-image PII screening",
    ),
    "pii_screening_decision_preflight": ArtifactSpec(
        role="pii_screening_decision_preflight",
        expected_schema_versions=frozenset(
            {"supplement-review-pii-screening-decision-preflight-v1"}
        ),
        description="redacted preflight summary for operator PII screening decisions",
    ),
    "pii_screening_apply": ArtifactSpec(
        role="pii_screening_apply",
        expected_schema_versions=frozenset({"supplement-review-pii-screening-apply-v1"}),
        description="PII screening decision application summary",
    ),
    "ocr_ground_truth_template": ArtifactSpec(
        role="ocr_ground_truth_template",
        expected_schema_versions=frozenset({"supplement-ocr-ground-truth-template-v1"}),
        description="manual OCR ground-truth template",
    ),
    "ocr_ground_truth_review_bundle": ArtifactSpec(
        role="ocr_ground_truth_review_bundle",
        expected_schema_versions=frozenset({"supplement-ocr-ground-truth-review-bundle-v1"}),
        description="local HTML and editable JSONL bundle for manual OCR ground truth",
    ),
    "ocr_ground_truth_preflight": ArtifactSpec(
        role="ocr_ground_truth_preflight",
        expected_schema_versions=frozenset({"supplement-ocr-ground-truth-preflight-v1"}),
        description="redacted preflight summary for manual OCR ground truth benchmark readiness",
    ),
    "ocr_benchmark_manifest": ArtifactSpec(
        role="ocr_benchmark_manifest",
        expected_schema_versions=frozenset(
            {
                "supplement-ocr-provider-benchmark-manifest-v1",
                "supplement-ocr-provider-benchmark-fixture-v1",
            }
        ),
        description="human-reviewed OCR provider benchmark fixtures",
    ),
    "ocr_benchmark_gate": ArtifactSpec(
        role="ocr_benchmark_gate",
        expected_schema_versions=frozenset({"supplement-ocr-benchmark-gate-v1"}),
        description="redacted gate for PII, manual GT, benchmark, and teacher OCR readiness",
    ),
    "benchmark_split_summary": ArtifactSpec(
        role="benchmark_split_summary",
        expected_schema_versions=frozenset({"paddleocr-benchmark-split-assignment-v1"}),
        description="product-group-safe benchmark split assignment summary",
    ),
    "ocr_three_tier_eval": ArtifactSpec(
        role="ocr_three_tier_eval",
        expected_schema_versions=frozenset({"ocr-kpi-gate-v1"}),
        description="CLOVA, Google Vision, and PaddleOCR comparison result",
    ),
    "yolo_annotation_template": ArtifactSpec(
        role="yolo_annotation_template",
        expected_schema_versions=frozenset({"supplement-yolo-annotation-template-summary-v1"}),
        description="operator template for supplement-section bbox labels",
    ),
    "yolo_annotation_review_bundle": ArtifactSpec(
        role="yolo_annotation_review_bundle",
        expected_schema_versions=frozenset({"supplement-yolo-annotation-review-bundle-v1"}),
        description="local HTML/task bundle for supplement-section bbox annotation",
    ),
    "yolo_annotation_decision_preflight": ArtifactSpec(
        role="yolo_annotation_decision_preflight",
        expected_schema_versions=frozenset({"supplement-yolo-annotation-decision-preflight-v1"}),
        description="redacted preflight summary for operator bbox annotation decisions",
    ),
    "yolo_template_promotion": ArtifactSpec(
        role="yolo_template_promotion",
        expected_schema_versions=frozenset({"supplement-yolo-template-promotion-summary-v1"}),
        description="approved bbox template promotion summary",
    ),
    "yolo_dataset": ArtifactSpec(
        role="yolo_dataset",
        expected_schema_versions=frozenset({"supplement-section-yolo-materialize-summary-v1"}),
        description="materialized YOLO section dataset summary",
    ),
    "yolo_section_dataset_gate": ArtifactSpec(
        role="yolo_section_dataset_gate",
        expected_schema_versions=frozenset({"supplement-yolo-section-dataset-gate-v1"}),
        description="redacted gate for supplement-section YOLO training readiness",
    ),
    "paddleocr_improvement_candidates": ArtifactSpec(
        role="paddleocr_improvement_candidates",
        expected_schema_versions=frozenset({"supplement-paddleocr-improvement-manifest-v1"}),
        description="PaddleOCR improvement candidate manifest",
    ),
    "paddleocr_text_target_chain_preflight": ArtifactSpec(
        role="paddleocr_text_target_chain_preflight",
        expected_schema_versions=frozenset({"paddleocr-text-target-chain-preflight-v1"}),
        description="PaddleOCR 95 percent text target gate preflight",
    ),
    "paddleocr_annotation_tasks": ArtifactSpec(
        role="paddleocr_annotation_tasks",
        expected_schema_versions=frozenset(
            {"paddleocr-improvement-annotation-task-create-summary-v1"}
        ),
        description="created OCR annotation tasks for PaddleOCR improvement",
    ),
    "paddleocr_dataset": ArtifactSpec(
        role="paddleocr_dataset",
        expected_schema_versions=frozenset({"paddleocr-dataset-materialize-summary-v1"}),
        description="materialized PaddleOCR training dataset summary",
    ),
    "paddleocr_finetune_plan": ArtifactSpec(
        role="paddleocr_finetune_plan",
        expected_schema_versions=frozenset({"paddleocr-finetune-run-plan-v1"}),
        description="PaddleOCR fine-tune execution plan",
    ),
    "paddleocr_finetune_eval": ArtifactSpec(
        role="paddleocr_finetune_eval",
        expected_schema_versions=frozenset({"paddleocr-finetune-eval-result-v1"}),
        description="fine-tuned PaddleOCR metric verification result",
    ),
    "paddleocr_baseline_eval": ArtifactSpec(
        role="paddleocr_baseline_eval",
        expected_schema_versions=frozenset({"paddleocr-baseline-eval-result-v1"}),
        description="baseline PaddleOCR metric verification result",
    ),
    "paddleocr_baseline_gate": ArtifactSpec(
        role="paddleocr_baseline_gate",
        expected_schema_versions=frozenset({"paddleocr-baseline-comparison-gate-v1"}),
        description="baseline comparison and promotion threshold gate",
    ),
    "paddleocr_promotion_runbook": ArtifactSpec(
        role="paddleocr_promotion_runbook",
        expected_schema_versions=frozenset({"paddleocr-promotion-operator-runbook-v1"}),
        description="operator runbook before model promotion",
    ),
    "paddleocr_accuracy_stop_gate": ArtifactSpec(
        role="paddleocr_accuracy_stop_gate",
        expected_schema_versions=frozenset(
            {
                "paddleocr-human-gt-accuracy-stop-gate-v1",
                "paddleocr-text-extraction-target-gate-v1",
            }
        ),
        description="human-ground-truth PaddleOCR accuracy gate for stopping further training",
    ),
    "operator_review_workpack": ArtifactSpec(
        role="operator_review_workpack",
        expected_schema_versions=frozenset({"supplement-operator-review-workpack-v1"}),
        description="redacted batch-by-batch operator workpack for pending human review",
    ),
    "operator_review_batch_progress": ArtifactSpec(
        role="operator_review_batch_progress",
        expected_schema_versions=frozenset(
            {"supplement-operator-review-batch-progress-preflight-v1"}
        ),
        description="redacted aggregate progress preflight for operator review batches",
    ),
    "operator_post_completion_command_plan": ArtifactSpec(
        role="operator_post_completion_command_plan",
        expected_schema_versions=frozenset({"supplement-operator-post-completion-command-plan-v1"}),
        description="redacted queue-specific gate order after an operator batch is completed",
    ),
}

STAGE_SPECS: tuple[StageSpec, ...] = (
    StageSpec(
        stage_key="taxonomy_structure_audit",
        phase="taxonomy_db",
        required_roles=("taxonomy_audit",),
        pending_roles=(),
        next_operator_action="inspect_structure_issues_before_staging",
    ),
    StageSpec(
        stage_key="taxonomy_db_staging",
        phase="taxonomy_db",
        required_roles=("taxonomy_staging",),
        pending_roles=(),
        next_operator_action="export_brand_review_template",
    ),
    StageSpec(
        stage_key="brand_product_review",
        phase="taxonomy_db",
        required_roles=("approved_product_import",),
        pending_roles=(
            "brand_review_template",
            "brand_review_bundle",
            "brand_review_decision_preflight",
            "operator_review_workpack",
            "operator_review_batch_progress",
            "operator_post_completion_command_plan",
        ),
        next_operator_action="complete_brand_product_human_review",
    ),
    StageSpec(
        stage_key="category_seed_db_apply_preflight",
        phase="taxonomy_db",
        required_roles=(
            "category_only_import_dry_run",
            "category_seed_apply_gate",
            "category_seed_target_preflight",
        ),
        pending_roles=("taxonomy_staging",),
        next_operator_action="run_category_seed_apply_against_local_database_then_read_only_verification",
    ),
    StageSpec(
        stage_key="category_seed_db_verification",
        phase="taxonomy_db",
        required_roles=("category_seed_db_verification",),
        pending_roles=(
            "category_seed_target_preflight",
            "taxonomy_staging",
            "category_seed_cleanup_preflight",
            "category_seed_cleanup_apply",
        ),
        next_operator_action="run_category_seed_db_apply_and_read_only_verification",
    ),
    StageSpec(
        stage_key="taxonomy_db_import_verification",
        phase="taxonomy_db",
        required_roles=("approved_product_import", "taxonomy_db_verification"),
        pending_roles=("approved_product_import",),
        next_operator_action="run_read_only_db_import_verification",
    ),
    StageSpec(
        stage_key="learning_candidate_split",
        phase="ocr_yolo_candidates",
        required_roles=("learning_candidate_summary",),
        pending_roles=(),
        next_operator_action="screen_review_images_for_pii_and_prepare_yolo_templates",
    ),
    StageSpec(
        stage_key="private_image_tracking_check",
        phase="security_privacy",
        required_roles=("private_image_tracking_check",),
        pending_roles=(),
        next_operator_action="remove_private_image_files_from_git_tracking_before_review",
    ),
    StageSpec(
        stage_key="review_pii_screening",
        phase="ocr_ground_truth",
        required_roles=("pii_screening_apply",),
        pending_roles=(
            "pii_screening_template",
            "pii_screening_review_bundle",
            "pii_screening_decision_preflight",
            "operator_review_workpack",
            "operator_review_batch_progress",
            "operator_post_completion_command_plan",
        ),
        next_operator_action="apply_pii_screening_decisions",
    ),
    StageSpec(
        stage_key="manual_ocr_ground_truth",
        phase="ocr_ground_truth",
        required_roles=("ocr_benchmark_manifest",),
        pending_roles=(
            "ocr_benchmark_gate",
            "ocr_ground_truth_template",
            "ocr_ground_truth_review_bundle",
            "ocr_ground_truth_preflight",
        ),
        next_operator_action="complete_human_reviewed_ocr_ground_truth",
    ),
    StageSpec(
        stage_key="teacher_ocr_comparison",
        phase="ocr_provider_eval",
        required_roles=(
            "ocr_benchmark_manifest",
            "benchmark_split_summary",
            "ocr_three_tier_eval",
        ),
        pending_roles=("ocr_benchmark_gate", "ocr_benchmark_manifest", "benchmark_split_summary"),
        next_operator_action="run_clova_google_vision_paddleocr_comparison",
    ),
    StageSpec(
        stage_key="yolo_section_annotation",
        phase="supplement_section_yolo",
        required_roles=("yolo_template_promotion",),
        pending_roles=(
            "yolo_annotation_template",
            "yolo_annotation_review_bundle",
            "yolo_annotation_decision_preflight",
            "operator_review_workpack",
            "operator_review_batch_progress",
            "operator_post_completion_command_plan",
        ),
        next_operator_action="complete_supplement_section_bbox_review",
    ),
    StageSpec(
        stage_key="yolo_section_dataset",
        phase="supplement_section_yolo",
        required_roles=("yolo_dataset",),
        pending_roles=("yolo_template_promotion", "yolo_section_dataset_gate"),
        next_operator_action="materialize_section_yolo_dataset",
    ),
    StageSpec(
        stage_key="paddleocr_text_target_chain_preflight",
        phase="paddleocr_training",
        required_roles=("paddleocr_text_target_chain_preflight",),
        pending_roles=("ocr_benchmark_manifest", "benchmark_split_summary", "ocr_three_tier_eval"),
        next_operator_action="prepare_paddleocr_text_target_gate",
    ),
    StageSpec(
        stage_key="paddleocr_improvement_triage",
        phase="paddleocr_training",
        required_roles=("paddleocr_improvement_candidates",),
        pending_roles=("ocr_three_tier_eval",),
        next_operator_action="create_or_review_paddleocr_annotation_tasks",
    ),
    StageSpec(
        stage_key="paddleocr_annotation_tasks",
        phase="paddleocr_training",
        required_roles=("paddleocr_dataset",),
        pending_roles=("paddleocr_annotation_tasks",),
        next_operator_action="accept_annotation_tasks_and_materialize_dataset",
    ),
    StageSpec(
        stage_key="paddleocr_finetune_plan",
        phase="paddleocr_training",
        required_roles=("paddleocr_finetune_plan",),
        pending_roles=("paddleocr_dataset",),
        next_operator_action="review_finetune_plan_before_trusted_worker_execution",
    ),
    StageSpec(
        stage_key="paddleocr_metric_gate",
        phase="paddleocr_training",
        required_roles=(
            "paddleocr_finetune_eval",
            "paddleocr_baseline_eval",
            "paddleocr_baseline_gate",
        ),
        pending_roles=("paddleocr_finetune_plan",),
        next_operator_action="run_finetune_and_baseline_metric_gate",
    ),
    StageSpec(
        stage_key="paddleocr_promotion_runbook",
        phase="paddleocr_training",
        required_roles=("paddleocr_promotion_runbook",),
        pending_roles=("paddleocr_baseline_gate",),
        next_operator_action="operator_review_before_model_promotion",
    ),
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        metavar="ROLE=PATH",
        help="Artifact role and JSON/JSONL path. Can be provided multiple times.",
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None) -> int:
    """Build a readiness report and print a redacted summary.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        artifact_paths = _parse_artifact_args(args.artifact)
        report = build_readiness_report(artifact_paths=artifact_paths)
    except (OSError, json.JSONDecodeError, PipelineReadinessError) as exc:
        summary = _error_summary(exc)
        _write_json(args.output, summary)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 1

    _write_json(args.output, report)
    print(json.dumps(_summary_from_report(report), ensure_ascii=False, sort_keys=True))
    return 0


def build_readiness_report(*, artifact_paths: Mapping[str, Path]) -> dict[str, Any]:
    """Build a redacted stage-by-stage readiness report.

    Args:
        artifact_paths: Artifact role to path mapping.

    Returns:
        Redacted readiness report.

    Raises:
        PipelineReadinessError: If an unknown, malformed, or unsafe artifact is provided.
    """
    unknown_roles = sorted(set(artifact_paths) - set(ARTIFACT_SPECS))
    if unknown_roles:
        raise PipelineReadinessError("Unknown artifact role was provided.")

    artifacts = {
        role: _load_artifact(role=role, path=path) for role, path in sorted(artifact_paths.items())
    }
    stages = [_stage_readiness(stage, artifacts=artifacts) for stage in STAGE_SPECS]
    status_counts = _status_counts(stage["status"] for stage in stages)
    blocked_count = sum(
        1
        for stage in stages
        if stage["status"] in {"blocked_missing_artifact", "blocked_invalid_artifact"}
    )
    pending_count = sum(1 for stage in stages if stage["status"] == "pending_operator_review")
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "overall_status": _overall_status(
            blocked_count=blocked_count,
            pending_count=pending_count,
            stages=stages,
        ),
        "stage_count": len(stages),
        "status_counts": status_counts,
        "provided_artifact_count": len(artifacts),
        "provided_artifact_roles": sorted(artifacts),
        "blocked_stage_count": blocked_count,
        "pending_operator_review_stage_count": pending_count,
        "verified_stage_count": status_counts.get("verified", 0),
        "source_doc_urls": list(SOURCE_DOC_URLS),
        "stages": stages,
        "artifact_summaries": list(artifacts.values()),
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_image_read_performed": False,
        "local_absolute_path_printed": False,
        "product_literal_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }
    _reject_unsafe_payload(report)
    return report


def _parse_artifact_args(values: Sequence[str]) -> dict[str, Path]:
    """Parse repeated ``ROLE=PATH`` arguments.

    Args:
        values: Raw artifact CLI arguments.

    Returns:
        Mapping from role to path.

    Raises:
        PipelineReadinessError: If a value is malformed or duplicated.
    """
    parsed: dict[str, Path] = {}
    for value in values:
        role, separator, raw_path = value.partition("=")
        if not separator or not role or not raw_path:
            raise PipelineReadinessError("Artifact arguments must use ROLE=PATH.")
        if role in parsed:
            raise PipelineReadinessError("Duplicate artifact role was provided.")
        parsed[role] = Path(raw_path).expanduser().resolve()
    return parsed


def _load_artifact(*, role: str, path: Path) -> dict[str, Any]:
    """Load and summarize one JSON or JSONL artifact without exposing contents.

    Args:
        role: Artifact role.
        path: Artifact path.

    Returns:
        Redacted artifact summary.

    Raises:
        PipelineReadinessError: If the artifact is missing, unsafe, or has an
            unexpected schema version.
    """
    if not path.is_file():
        raise PipelineReadinessError("Required artifact is missing.")
    content = path.read_bytes()
    payload, row_count, schema_versions = _parse_artifact_content(content)
    _reject_unsafe_payload(payload)
    expected = ARTIFACT_SPECS[role].expected_schema_versions
    if not schema_versions or not set(schema_versions).issubset(expected):
        raise PipelineReadinessError("Artifact schema version does not match role.")
    return {
        "role": role,
        "schema_versions": sorted(schema_versions),
        "record_count": row_count,
        "content_fingerprint": _fingerprint_bytes(content),
        "path_fingerprint": _fingerprint_text(str(path.expanduser())),
        "description": ARTIFACT_SPECS[role].description,
        **_artifact_state_flags(role=role, payload=payload),
    }


def _fingerprint_bytes(value: bytes) -> str:
    """Return a short non-secret fingerprint for artifact identity.

    Args:
        value: Raw artifact bytes.

    Returns:
        Public fingerprint string.
    """
    return f"fp-{hashlib.sha256(value).hexdigest()[:8]}"


def _fingerprint_text(value: str) -> str:
    """Return a short non-secret fingerprint for artifact path identity.

    Args:
        value: Text to fingerprint.

    Returns:
        Public fingerprint string.
    """
    return _fingerprint_bytes(value.encode("utf-8"))


def _parse_artifact_content(content: bytes) -> tuple[Any, int, frozenset[str]]:
    """Parse JSON or JSONL content and collect schema versions.

    Args:
        content: Raw artifact bytes.

    Returns:
        Parsed payload, record count, and schema versions.

    Raises:
        PipelineReadinessError: If the artifact is empty or malformed.
    """
    text = content.decode("utf-8")
    stripped = text.strip()
    if not stripped:
        raise PipelineReadinessError("Artifact is empty.")
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        payload = None
    if payload is not None:
        if isinstance(payload, dict):
            schema = payload.get("schema_version")
            if not isinstance(schema, str):
                raise PipelineReadinessError("JSON artifact is missing schema_version.")
            return payload, 1, frozenset({schema})
        raise PipelineReadinessError("JSON artifact must be an object.")

    rows = []
    schema_versions: set[str] = set()
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    for line in lines:
        row = json.loads(line)
        if not isinstance(row, dict):
            raise PipelineReadinessError("JSONL artifact rows must be objects.")
        schema = row.get("schema_version")
        if not isinstance(schema, str):
            raise PipelineReadinessError("JSONL artifact row is missing schema_version.")
        rows.append(row)
        schema_versions.add(schema)
    if not rows:
        raise PipelineReadinessError("JSONL artifact contains no rows.")
    return rows, len(rows), frozenset(schema_versions)


def _artifact_state_flags(*, role: str, payload: Any) -> dict[str, Any]:
    """Extract safe aggregate readiness flags from a parsed artifact.

    Args:
        role: Artifact role.
        payload: Parsed JSON or JSONL payload.

    Returns:
        Redacted aggregate flags only.
    """
    if not isinstance(payload, dict):
        return {}
    flags: dict[str, Any] = {}
    for key in (
        "status",
        "process_status",
        "db_import_verified",
        "ready_for_operator_review",
        "ready_for_promotion",
        "allowed",
        "ready_for_db_write",
        "preflight_only",
        "apply_requested",
        "category_seed_db_apply_allowed",
        "category_seed_db_apply_target_allowed",
        "product_db_apply_allowed",
        "product_category_db_apply_allowed",
        "database_connection_opened",
        "db_connection_opened",
    ):
        value = payload.get(key)
        if isinstance(value, bool | int | str):
            flags[key] = value
    flags.update(_category_seed_preflight_state_flags(role=role, payload=payload))
    flags.update(_category_seed_cleanup_state_flags(role=role, payload=payload))
    flags.update(_db_verification_state_flags(role=role, payload=payload))
    flags.update(_auto_brand_product_state_flags(role=role, payload=payload))
    flags.update(_private_image_tracking_state_flags(role=role, payload=payload))
    flags.update(_benchmark_split_state_flags(role=role, payload=payload))
    flags.update(_ocr_benchmark_gate_state_flags(role=role, payload=payload))
    flags.update(_ocr_ground_truth_preflight_state_flags(role=role, payload=payload))
    flags.update(_paddleocr_text_target_preflight_state_flags(role=role, payload=payload))
    flags.update(_paddleocr_accuracy_stop_state_flags(role=role, payload=payload))
    if role == "paddleocr_baseline_gate" and payload.get("allowed") is not True:
        flags["artifact_warning"] = "baseline_gate_not_allowed"
    if role == "operator_review_workpack":
        for key in ("batch_count", "workpack_file_count", "next_batch_key"):
            value = payload.get(key)
            if isinstance(value, bool | int | str) or value is None:
                flags[key] = value
    if role == "operator_review_batch_progress":
        for key in (
            "batch_count",
            "complete_batch_count",
            "pending_batch_count",
            "invalid_batch_count",
            "all_batches_complete",
            "next_incomplete_batch_key",
            "total_expected_row_count",
            "total_valid_row_count",
            "total_blank_row_count",
            "total_pending_row_count",
            "total_invalid_row_count",
            "total_missing_row_count",
        ):
            value = payload.get(key)
            if isinstance(value, bool | int | str) or value is None:
                flags[key] = value
    return flags


def _ocr_ground_truth_preflight_state_flags(
    *,
    role: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract safe aggregate fields for manual OCR ground-truth preflight.

    Args:
        role: Artifact role.
        payload: Parsed JSON payload.

    Returns:
        Safe readiness fields without OCR text, provider payloads, or paths.
    """
    if role != "ocr_ground_truth_preflight":
        return {}
    flags: dict[str, Any] = {}
    for key in (
        "status",
        "ready_for_benchmark_build",
        "row_count",
        "human_reviewed_row_count",
        "explicit_ready_flag_count",
        "benchmark_ready_row_count",
        "min_ready_rows",
    ):
        value = payload.get(key)
        if isinstance(value, bool | int | str) or value is None:
            flags[key] = value
    if payload.get("ready_for_benchmark_build") is not True:
        flags["artifact_warning"] = "ocr_ground_truth_preflight_not_ready"
    return flags


def _paddleocr_text_target_preflight_state_flags(
    *,
    role: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract safe aggregate fields for the PaddleOCR text target preflight.

    Args:
        role: Artifact role.
        payload: Parsed JSON payload.

    Returns:
        Safe readiness fields without row text, provider payloads, or paths.
    """
    if role != "paddleocr_text_target_chain_preflight":
        return {}
    flags: dict[str, Any] = {}
    for key in (
        "status",
        "ready_for_target_gate",
        "continue_training_loop",
        "row_count",
        "scoreable_fixture_count",
        "candidate_schema_count",
        "eval_split",
        "min_fixture_count",
        "benchmark_manifest_role",
    ):
        value = payload.get(key)
        if isinstance(value, bool | int | str) or value is None:
            flags[key] = value
    if payload.get("ready_for_target_gate") is not True:
        flags["artifact_warning"] = "paddleocr_text_target_chain_preflight_not_ready"
    return flags


def _benchmark_split_state_flags(
    *,
    role: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract safe aggregate benchmark split fields.

    Args:
        role: Artifact role.
        payload: Parsed JSON payload.

    Returns:
        Product-group split readiness fields without row contents.
    """
    if role != "benchmark_split_summary":
        return {}
    flags: dict[str, Any] = {}
    for key in (
        "row_count",
        "product_group_count",
        "ready_for_holdout_eval",
        "leakage_check_passed",
        "split_assignment_method",
        "min_holdout_fixtures",
        "min_test_fixtures",
    ):
        value = payload.get(key)
        if isinstance(value, bool | int | str) or value is None:
            flags[key] = value
    split_counts = payload.get("split_counts")
    if isinstance(split_counts, dict):
        flags["split_counts"] = {
            str(key): value
            for key, value in sorted(split_counts.items())
            if isinstance(value, int) and value >= 0
        }
    if payload.get("leakage_check_passed") is not True:
        flags["artifact_warning"] = "benchmark_split_leakage_check_not_passed"
    elif payload.get("ready_for_holdout_eval") is not True:
        flags["artifact_warning"] = "benchmark_split_not_ready_for_holdout_eval"
    return flags


def _ocr_benchmark_gate_state_flags(
    *,
    role: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract safe aggregate OCR benchmark gate fields.

    Args:
        role: Artifact role.
        payload: Parsed JSON payload.

    Returns:
        Redacted gate fields without OCR text or row payloads.
    """
    if role != "ocr_benchmark_gate":
        return {}
    flags: dict[str, Any] = {}
    for key in (
        "status",
        "candidate_row_count",
        "cleared_no_personal_data_count",
        "pii_blank_decision_count",
        "pii_pending_operator_action_count",
        "ground_truth_template_allowed",
        "ready_for_benchmark_rows",
        "benchmark_fixture_count",
        "scoreable_fixture_count",
        "benchmark_required_sections_ready",
        "benchmark_split_row_count",
        "benchmark_split_leakage_check_passed",
        "teacher_ocr_benchmark_allowed",
        "external_teacher_ocr_eval_allowed",
        "paddleocr_training_allowed_now",
    ):
        value = payload.get(key)
        if isinstance(value, bool | int | str) or value is None:
            flags[key] = value
    for key in (
        "benchmark_required_expected_sections",
        "benchmark_required_expected_section_policy",
        "benchmark_missing_required_expected_sections",
    ):
        value = payload.get(key)
        if _is_safe_string_list(value):
            flags[key] = value
    if payload.get("status") != "ready_for_teacher_ocr_eval":
        flags["artifact_warning"] = "ocr_benchmark_gate_not_ready"
    return flags


def _paddleocr_accuracy_stop_state_flags(
    *,
    role: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract derived flags for the PaddleOCR 95 percent stop gate.

    Args:
        role: Artifact role.
        payload: Parsed JSON payload.

    Returns:
        Redacted stop-gate flags. The exact metric value is intentionally not
        propagated to the operator report; only the policy threshold result is
        exposed.
    """
    if role != "paddleocr_accuracy_stop_gate":
        return {}
    if payload.get("schema_version") == "paddleocr-text-extraction-target-gate-v1":
        trust_checks = payload.get("trust_checks")
        metric_checks = payload.get("metric_checks")
        if not isinstance(trust_checks, Mapping):
            trust_checks = {}
        if not isinstance(metric_checks, Mapping):
            metric_checks = {}
        human_gt_compared = (
            payload.get("human_ground_truth_compared") is True
            or trust_checks.get("all_fixtures_human_reviewed") is True
        )
        privacy_review_cleared = (
            payload.get("privacy_review_cleared") is True
            or trust_checks.get("privacy_review_cleared") is True
        )
        threshold_met = payload.get("text_extraction_accuracy_meets_95_percent") is True or all(
            metric_checks.get(metric_name) is True
            for metric_name in PADDLEOCR_TEXT_REQUIRED_METRICS
        )
        stop_allowed = (
            threshold_met
            and human_gt_compared
            and privacy_review_cleared
            and payload.get("training_loop_stop_allowed") is True
            and payload.get("paddleocr_target_reached") is True
        )
        flags: dict[str, Any] = {
            "human_ground_truth_compared": human_gt_compared,
            "privacy_review_cleared": privacy_review_cleared,
            "text_extraction_accuracy_meets_95_percent": threshold_met,
            "minimum_required_accuracy": "0.95",
            "training_loop_stop_allowed": stop_allowed,
            "metric_values_printed": False,
        }
        if not stop_allowed:
            flags["artifact_warning"] = "paddleocr_accuracy_stop_gate_not_allowed"
        return flags
    accuracy = _float_payload_field(payload, "text_extraction_accuracy")
    threshold_met = accuracy is not None and accuracy >= PADDLEOCR_HUMAN_GT_EARLY_STOP_THRESHOLD
    human_gt_compared = payload.get("human_ground_truth_compared") is True
    privacy_review_cleared = payload.get("privacy_review_cleared") is True
    stop_allowed = (
        threshold_met
        and human_gt_compared
        and privacy_review_cleared
        and payload.get("accuracy_threshold_met") is True
        and payload.get("training_loop_stop_allowed") is True
    )
    flags: dict[str, Any] = {
        "human_ground_truth_compared": human_gt_compared,
        "privacy_review_cleared": privacy_review_cleared,
        "text_extraction_accuracy_meets_95_percent": threshold_met,
        "minimum_required_accuracy": "0.95",
        "training_loop_stop_allowed": stop_allowed,
        "metric_values_printed": False,
    }
    if not stop_allowed:
        flags["artifact_warning"] = "paddleocr_accuracy_stop_gate_not_allowed"
    return flags


def _float_payload_field(payload: Mapping[str, Any], key: str) -> float | None:
    """Return a finite float payload field.

    Args:
        payload: Parsed artifact payload.
        key: Field name to read.

    Returns:
        Float value, or None if the field is missing or invalid.
    """
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    if parsed < 0 or not math.isfinite(parsed):
        return None
    return parsed


def _private_image_tracking_state_flags(
    *,
    role: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract private-image tracking aggregate fields.

    Args:
        role: Artifact role.
        payload: Parsed JSON payload.

    Returns:
        Safe aggregate fields for Git tracking evidence.
    """
    if role != "private_image_tracking_check":
        return {}
    flags: dict[str, Any] = {}
    for key in (
        "passed",
        "tracked_private_image_count",
        "protected_path_count",
        "git_ls_files_checked",
    ):
        value = payload.get(key)
        if isinstance(value, bool | int | str) or value is None:
            flags[key] = value
    return flags


def _db_verification_state_flags(*, role: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Extract safe DB verification fields from category/product verifier artifacts.

    Args:
        role: Artifact role.
        payload: Parsed JSON payload.

    Returns:
        Safe aggregate verification fields.
    """
    if role not in {
        "category_seed_db_verification",
        "taxonomy_db_verification",
        "auto_brand_product_db_verification",
    }:
        return {}
    flags: dict[str, Any] = {}
    if payload.get("db_import_verified") is not True:
        flags["artifact_warning"] = "db_import_not_verified"
    for key in (
        "status",
        "verification_scope",
        "product_import_manifest_present",
        "approved_product_rows_required",
        "approved_product_rows_available",
        "category_import_verified",
        "product_import_verified",
        "expected_category_count",
        "active_db_category_count",
        "matched_category_count",
        "missing_category_count",
        "extra_active_category_count",
        "expected_product_count",
        "matched_product_count",
        "expected_product_category_count",
        "matched_product_category_count",
        "missing_product_category_count",
        "db_write_performed",
    ):
        value = payload.get(key)
        if isinstance(value, bool | int | str) or value is None:
            flags[key] = value
    blocked_reason_codes = payload.get("blocked_reason_codes")
    if isinstance(blocked_reason_codes, list):
        flags["blocked_reason_codes"] = [
            item for item in blocked_reason_codes if isinstance(item, str)
        ]
    return flags


def _auto_brand_product_state_flags(
    *,
    role: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract safe aggregate fields for provisional auto brand product artifacts.

    Args:
        role: Artifact role.
        payload: Parsed JSON payload.

    Returns:
        Safe aggregate counts for auto import dry-run and verification artifacts.
    """
    if role not in {
        "auto_brand_product_import_dry_run",
        "auto_brand_product_db_verification",
    }:
        return {}
    flags: dict[str, Any] = {}
    for key in (
        "product_row_count",
        "with_manufacturer",
        "manufacturer_null_needs_review",
        "distinct_categories",
        "distinct_brands",
        "product_category_mapping_planned_count",
        "product_category_mapping_write_enabled",
        "expected_product_count",
        "matched_product_count",
        "expected_product_category_count",
        "matched_product_category_count",
        "missing_product_category_count",
        "db_write_performed",
    ):
        value = payload.get(key)
        if isinstance(value, bool | int | str) or value is None:
            flags[key] = value
    return flags


def _category_seed_preflight_state_flags(
    *,
    role: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract safe category seed dry-run/gate/preflight fields.

    Args:
        role: Artifact role.
        payload: Parsed JSON payload.

    Returns:
        Safe aggregate fields that prove only category seed apply was prepared.
    """
    if role not in {
        "category_only_import_dry_run",
        "category_seed_apply_gate",
        "category_seed_target_preflight",
    }:
        return {}
    flags: dict[str, Any] = {}
    for key in (
        "category_seed_row_count",
        "approved_product_import_row_count",
        "planned_category_upsert_count",
        "planned_product_upsert_count",
        "planned_product_category_upsert_count",
        "approved_for_db_write_row_count",
        "brand_candidate_row_count",
        "database_host_class",
        "runtime_environment",
        "database_driver",
    ):
        value = payload.get(key)
        if isinstance(value, bool | int | str) or value is None:
            flags[key] = value
    return flags


def _category_seed_cleanup_state_flags(
    *,
    role: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract safe cleanup-preflight fields for category seed drift.

    Args:
        role: Artifact role.
        payload: Parsed JSON payload.

    Returns:
        Safe aggregate cleanup fields without category literals.
    """
    if role not in {"category_seed_cleanup_preflight", "category_seed_cleanup_apply"}:
        return {}
    flags: dict[str, Any] = {}
    for key in (
        "status",
        "expected_category_count",
        "active_db_category_count",
        "matched_category_count",
        "missing_category_count",
        "extra_active_category_count",
        "category_seed_exact_match",
        "cleanup_required",
        "cleanup_requires_manual_approval",
        "planned_category_deactivation_count",
        "manual_cleanup_confirmation_provided",
        "deactivated_category_count",
        "db_write_performed",
        "db_delete_performed",
        "db_update_performed",
    ):
        value = payload.get(key)
        if isinstance(value, bool | int | str) or value is None:
            flags[key] = value
    if role == "category_seed_cleanup_preflight" and payload.get("cleanup_required") is True:
        flags["artifact_warning"] = "category_seed_cleanup_requires_manual_approval"
    if (
        role == "category_seed_cleanup_apply"
        and payload.get("status") == "ready_for_manual_category_seed_cleanup"
    ):
        flags["artifact_warning"] = "category_seed_cleanup_apply_waiting_for_approval"
    return flags


def _stage_readiness(
    stage: StageSpec,
    *,
    artifacts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Return readiness status for one pipeline stage.

    Args:
        stage: Stage definition.
        artifacts: Loaded artifact summaries keyed by role.

    Returns:
        Redacted stage readiness row.
    """
    present_required = [role for role in stage.required_roles if role in artifacts]
    missing_required = [role for role in stage.required_roles if role not in artifacts]
    present_pending = [role for role in stage.pending_roles if role in artifacts]
    invalid_blockers = _semantic_blockers(stage=stage, artifacts=artifacts)

    if invalid_blockers:
        status = "blocked_invalid_artifact"
        blocker_codes = invalid_blockers
    elif not missing_required:
        status = "verified"
        blocker_codes = []
    elif present_pending:
        status = "pending_operator_review"
        blocker_codes = [f"missing_required:{role}" for role in missing_required]
    else:
        status = "blocked_missing_artifact"
        blocker_codes = [f"missing_required:{role}" for role in missing_required]

    return {
        "stage_key": stage.stage_key,
        "phase": stage.phase,
        "status": status,
        "required_roles": list(stage.required_roles),
        "pending_roles": list(stage.pending_roles),
        "present_required_roles": present_required,
        "present_pending_roles": present_pending,
        "missing_required_roles": missing_required,
        "blocker_codes": blocker_codes,
        "next_operator_action": stage.next_operator_action,
        "next_steps": _stage_next_steps(
            stage=stage,
            status=status,
            missing_required_roles=missing_required,
            blocker_codes=blocker_codes,
        ),
    }


def _stage_next_steps(
    *,
    stage: StageSpec,
    status: str,
    missing_required_roles: Sequence[str],
    blocker_codes: Sequence[str],
) -> list[str]:
    """Return redacted next-step labels for one readiness stage.

    Args:
        stage: Stage definition.
        status: Computed readiness status.
        missing_required_roles: Required artifact roles not present.
        blocker_codes: Semantic blocker codes for invalid artifacts.

    Returns:
        Stable action labels safe for operator-facing reports.
    """
    if status == "verified":
        return []
    steps = [stage.next_operator_action]
    steps.extend(f"provide_required_artifact:{role}" for role in missing_required_roles)
    steps.extend(f"resolve_blocker:{code}" for code in blocker_codes)
    return _dedupe_preserve_order(steps)


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    """Return unique strings without changing their first-seen order.

    Args:
        values: Candidate values.

    Returns:
        Deduplicated strings.
    """
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        safe_value = str(value)
        if safe_value in seen:
            continue
        seen.add(safe_value)
        output.append(safe_value)
    return output


def _semantic_blockers(
    *,
    stage: StageSpec,
    artifacts: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Return aggregate semantic blocker codes for provided artifacts.

    Args:
        stage: Stage definition.
        artifacts: Loaded artifact summaries keyed by role.

    Returns:
        Blocker code list.
    """
    blockers = _stage_semantic_blockers(
        stage_key=stage.stage_key,
        artifacts=artifacts,
    )
    blockers.extend(
        _private_image_tracking_stage_blockers(stage=stage, artifacts=artifacts),
    )
    return blockers


def _stage_semantic_blockers(
    *,
    stage_key: str,
    artifacts: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Return semantic blockers for stages with aggregate readiness rules.

    Args:
        stage_key: Stable stage identifier.
        artifacts: Loaded artifact summaries keyed by role.

    Returns:
        Blocker code list for the stage.
    """
    blocker_builders = {
        "category_seed_db_apply_preflight": _category_seed_apply_preflight_blockers,
        "category_seed_db_verification": _category_seed_verification_stage_blockers,
        "taxonomy_db_import_verification": _taxonomy_db_verification_blockers,
        "manual_ocr_ground_truth": _manual_ocr_ground_truth_blockers,
        "teacher_ocr_comparison": _teacher_ocr_comparison_stage_blockers,
        "paddleocr_text_target_chain_preflight": _paddleocr_text_target_preflight_blockers,
        "paddleocr_metric_gate": _paddleocr_metric_gate_blockers,
        "paddleocr_promotion_runbook": _paddleocr_promotion_runbook_blockers,
    }
    build_blockers = blocker_builders.get(stage_key)
    if build_blockers is None:
        return []
    return build_blockers(artifacts)


def _category_seed_verification_stage_blockers(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Return category seed verification and cleanup blockers.

    Args:
        artifacts: Loaded artifact summaries keyed by role.

    Returns:
        Stable blocker codes for category seed verification.
    """
    verification = artifacts.get("category_seed_db_verification")
    if verification is None:
        return []
    blockers = _category_seed_verification_blockers(verification)
    blockers.extend(_category_seed_cleanup_preflight_blockers(artifacts))
    blockers.extend(_category_seed_cleanup_apply_blockers(artifacts))
    return blockers


def _teacher_ocr_comparison_stage_blockers(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Return OCR benchmark gate and provider comparison blockers.

    Args:
        artifacts: Loaded artifact summaries keyed by role.

    Returns:
        Stable blocker codes for teacher OCR comparison readiness.
    """
    blockers = _ocr_benchmark_gate_blockers(artifacts)
    blockers.extend(_teacher_ocr_comparison_blockers(artifacts))
    return blockers


def _paddleocr_metric_gate_blockers(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Return blockers for PaddleOCR metric gate artifacts.

    Args:
        artifacts: Loaded artifact summaries keyed by role.

    Returns:
        Stable blocker codes for PaddleOCR metric verification.
    """
    blockers: list[str] = []
    for role in ("paddleocr_finetune_eval", "paddleocr_baseline_eval"):
        artifact = artifacts.get(role)
        if artifact is not None and artifact.get("process_status") != "metrics_verified":
            blockers.append(f"{role}:metrics_not_verified")
    gate = artifacts.get("paddleocr_baseline_gate")
    if gate is not None and gate.get("allowed") is not True:
        blockers.append("paddleocr_baseline_gate:not_allowed")
    return blockers


def _paddleocr_promotion_runbook_blockers(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Return blockers for PaddleOCR promotion runbook readiness.

    Args:
        artifacts: Loaded artifact summaries keyed by role.

    Returns:
        Stable blocker codes for promotion runbook operator review readiness.
    """
    runbook = artifacts.get("paddleocr_promotion_runbook")
    if runbook is None or runbook.get("ready_for_operator_review") is True:
        return []
    return ["promotion_runbook:not_ready_for_operator_review"]


def _paddleocr_text_target_preflight_blockers(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Return blockers for the PaddleOCR 95 percent text target preflight.

    Args:
        artifacts: Loaded artifact summaries keyed by role.

    Returns:
        Stable blocker codes for candidate-manifest and fixture-readiness gaps.
    """
    preflight = artifacts.get("paddleocr_text_target_chain_preflight")
    if preflight is None:
        return []
    blockers: list[str] = []
    if preflight.get("ready_for_target_gate") is not True:
        blockers.append("paddleocr_text_target_chain_preflight:not_ready")
    if preflight.get("status") == "blocked_by_candidate_manifest":
        blockers.append(
            "paddleocr_text_target_chain_preflight:candidate_manifest_needs_benchmark_build"
        )
    scoreable_count = preflight.get("scoreable_fixture_count")
    if not isinstance(scoreable_count, int) or scoreable_count <= 0:
        blockers.append("paddleocr_text_target_chain_preflight:no_scoreable_fixtures")
    return blockers


def _manual_ocr_ground_truth_blockers(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Return blockers explaining why manual OCR GT cannot become benchmark rows.

    Args:
        artifacts: Loaded artifact summaries keyed by role.

    Returns:
        Stable blocker codes for PII and manual ground-truth readiness.
    """
    blockers: list[str] = []
    preflight = artifacts.get("ocr_ground_truth_preflight")
    if preflight is not None and preflight.get("ready_for_benchmark_build") is not True:
        blockers.append("ocr_ground_truth_preflight:not_ready_for_benchmark_build")
    gate = artifacts.get("ocr_benchmark_gate")
    if gate is None:
        return blockers
    status = gate.get("status")
    if status == "blocked_by_pii_screening":
        blockers.append("ocr_benchmark_gate:blocked_by_pii_screening")
    if gate.get("ground_truth_template_allowed") is not True:
        blockers.append("ocr_benchmark_gate:ground_truth_template_not_allowed")
    ready_rows = gate.get("ready_for_benchmark_rows")
    if not isinstance(ready_rows, int) or ready_rows <= 0:
        blockers.append("ocr_benchmark_gate:no_human_reviewed_ground_truth_rows")
    return blockers


def _ocr_benchmark_gate_blockers(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Return blockers for teacher OCR comparison readiness from the benchmark gate.

    Args:
        artifacts: Loaded artifact summaries keyed by role.

    Returns:
        Stable blocker codes for OCR benchmark and split readiness.
    """
    gate = artifacts.get("ocr_benchmark_gate")
    if gate is None:
        return []
    blockers: list[str] = []
    if gate.get("status") != "ready_for_teacher_ocr_eval":
        blockers.append("ocr_benchmark_gate:not_ready_for_teacher_ocr_eval")
    if gate.get("teacher_ocr_benchmark_allowed") is not True:
        blockers.append("ocr_benchmark_gate:teacher_ocr_benchmark_not_allowed")
    if gate.get("external_teacher_ocr_eval_allowed") is not True:
        blockers.append("ocr_benchmark_gate:external_teacher_ocr_eval_not_allowed")
    if gate.get("paddleocr_training_allowed_now") is True:
        blockers.append("ocr_benchmark_gate:paddleocr_training_must_remain_blocked")
    return blockers


def _teacher_ocr_comparison_blockers(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Return blockers for teacher OCR evaluation prerequisites.

    Args:
        artifacts: Loaded artifact summaries keyed by role.

    Returns:
        Stable blocker codes for missing or invalid split safety evidence.
    """
    blockers: list[str] = []
    if "ocr_three_tier_eval" in artifacts and "benchmark_split_summary" not in artifacts:
        blockers.append("benchmark_split_summary:missing_before_teacher_ocr_eval")
    split = artifacts.get("benchmark_split_summary")
    if split is None:
        return blockers
    if split.get("leakage_check_passed") is not True:
        blockers.append("benchmark_split_summary:leakage_check_not_passed")
    if split.get("ready_for_holdout_eval") is not True:
        blockers.append("benchmark_split_summary:not_ready_for_holdout_eval")
    row_count = split.get("row_count")
    if not isinstance(row_count, int) or row_count <= 0:
        blockers.append("benchmark_split_summary:row_count_not_positive")
    split_counts = split.get("split_counts")
    if not isinstance(split_counts, dict) or split_counts.get("holdout", 0) <= 0:
        blockers.append("benchmark_split_summary:holdout_split_missing")
    return blockers


def _taxonomy_db_verification_blockers(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Return blockers for reviewed taxonomy DB verification.

    Args:
        artifacts: Loaded artifact summaries keyed by role.

    Returns:
        Stable blocker codes for invalid reviewed-product DB verification.
    """
    verification = artifacts.get("taxonomy_db_verification")
    if verification is None or verification.get("db_import_verified") is True:
        return []
    blocker_codes = verification.get("blocked_reason_codes")
    if not isinstance(blocker_codes, list):
        return ["taxonomy_db_verification:db_import_not_verified"]
    if "approved_product_import" not in artifacts:
        blocker_codes = [
            code for code in blocker_codes if code != "missing_required:approved_product_import"
        ]
    return [f"taxonomy_db_verification:{code}" for code in blocker_codes if isinstance(code, str)]


def _private_image_tracking_stage_blockers(
    *,
    stage: StageSpec,
    artifacts: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Return private image tracking blockers for the matching stage.

    Args:
        stage: Stage definition.
        artifacts: Loaded artifact summaries keyed by role.

    Returns:
        Empty list for unrelated stages, or private tracking blocker codes.
    """
    if stage.stage_key != "private_image_tracking_check":
        return []
    tracking = artifacts.get("private_image_tracking_check")
    if tracking is None:
        return []
    return _private_image_tracking_blockers(tracking)


def _private_image_tracking_blockers(tracking: Mapping[str, Any]) -> list[str]:
    """Return blockers for private image Git tracking evidence.

    Args:
        tracking: Redacted private-image tracking report summary.

    Returns:
        Stable blocker codes for unsafe tracked image evidence.
    """
    blockers: list[str] = []
    if tracking.get("passed") is not True:
        blockers.append("private_image_tracking:not_passed")
    if tracking.get("git_ls_files_checked") is not True:
        blockers.append("private_image_tracking:git_ls_files_not_checked")
    tracked_count = _int_summary_field(tracking, "tracked_private_image_count")
    if tracked_count is None or tracked_count != 0:
        blockers.append("private_image_tracking:tracked_image_count_not_zero")
    protected_count = _int_summary_field(tracking, "protected_path_count")
    if protected_count is None or protected_count == 0:
        blockers.append("private_image_tracking:protected_path_count_missing")
    return blockers


def _category_seed_apply_preflight_blockers(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Return semantic blockers for category seed apply preflight artifacts.

    Args:
        artifacts: Loaded artifact summaries keyed by role.

    Returns:
        Stable blocker codes for unsafe or incomplete category seed preflight evidence.
    """
    blockers: list[str] = []
    dry_run = artifacts.get("category_only_import_dry_run")
    apply_gate = artifacts.get("category_seed_apply_gate")
    target = artifacts.get("category_seed_target_preflight")

    if dry_run is not None:
        blockers.extend(_category_seed_dry_run_blockers(dry_run))

    if apply_gate is not None:
        blockers.extend(_category_seed_apply_gate_blockers(apply_gate))

    if target is not None:
        blockers.extend(_category_seed_target_preflight_blockers(target))

    return blockers


def _category_seed_dry_run_blockers(dry_run: Mapping[str, Any]) -> list[str]:
    """Return blockers for the category-only importer dry-run.

    Args:
        dry_run: Redacted category-only importer dry-run summary.

    Returns:
        Stable blocker codes for unsafe dry-run evidence.
    """
    blockers: list[str] = []
    if dry_run.get("ready_for_db_write") is not True:
        blockers.append("category_seed_dry_run:not_ready_for_db_write")
    if dry_run.get("preflight_only") is not True:
        blockers.append("category_seed_dry_run:not_preflight_only")
    if dry_run.get("apply_requested") is True or dry_run.get("db_write_performed") is True:
        blockers.append("category_seed_dry_run:db_write_must_not_run")
    if _int_summary_field(dry_run, "category_seed_row_count") in {None, 0}:
        blockers.append("category_seed_dry_run:category_seed_count_missing")
    if _int_summary_field(dry_run, "planned_category_upsert_count") in {None, 0}:
        blockers.append("category_seed_dry_run:planned_category_upsert_missing")
    for key in (
        "approved_product_import_row_count",
        "planned_product_upsert_count",
        "planned_product_category_upsert_count",
    ):
        value = _int_summary_field(dry_run, key)
        if value is None or value != 0:
            blockers.append(f"category_seed_dry_run:{key}_must_be_zero")
    return blockers


def _category_seed_apply_gate_blockers(apply_gate: Mapping[str, Any]) -> list[str]:
    """Return blockers for the category seed apply gate.

    Args:
        apply_gate: Redacted category seed apply gate summary.

    Returns:
        Stable blocker codes for unsafe apply-gate evidence.
    """
    blockers: list[str] = []
    if apply_gate.get("status") != "ready_for_category_seed_db_apply":
        blockers.append("category_seed_apply_gate:not_ready")
    if apply_gate.get("category_seed_db_apply_allowed") is not True:
        blockers.append("category_seed_apply_gate:apply_not_allowed")
    if apply_gate.get("product_db_apply_allowed") is not False:
        blockers.append("category_seed_apply_gate:product_apply_must_be_blocked")
    if apply_gate.get("product_category_db_apply_allowed") is not False:
        blockers.append("category_seed_apply_gate:product_category_apply_must_be_blocked")
    if (
        apply_gate.get("db_write_performed") is True
        or apply_gate.get("database_connection_opened") is True
    ):
        blockers.append("category_seed_apply_gate:db_side_effect_must_not_run")
    return blockers


def _category_seed_target_preflight_blockers(target: Mapping[str, Any]) -> list[str]:
    """Return blockers for the local DB target preflight.

    Args:
        target: Redacted local DB target preflight summary.

    Returns:
        Stable blocker codes for unsafe DB target evidence.
    """
    blockers: list[str] = []
    if target.get("status") != "ready_for_local_category_seed_apply":
        blockers.append("category_seed_target_preflight:not_ready")
    if target.get("category_seed_db_apply_target_allowed") is not True:
        blockers.append("category_seed_target_preflight:target_not_allowed")
    if target.get("runtime_environment") != "development":
        blockers.append("category_seed_target_preflight:not_development")
    if target.get("database_host_class") != "local":
        blockers.append("category_seed_target_preflight:not_local_database")
    if target.get("product_db_apply_allowed") is not False:
        blockers.append("category_seed_target_preflight:product_apply_must_be_blocked")
    if target.get("product_category_db_apply_allowed") is not False:
        blockers.append("category_seed_target_preflight:product_category_apply_must_be_blocked")
    if target.get("db_connection_opened") is True or target.get("db_write_performed") is True:
        blockers.append("category_seed_target_preflight:db_side_effect_must_not_run")
    return blockers


def _category_seed_verification_blockers(verification: Mapping[str, Any]) -> list[str]:
    """Return semantic blockers for category-only DB verification.

    Args:
        verification: Redacted artifact summary from the read-only verifier.

    Returns:
        Stable blocker codes explaining why the category seed proof is invalid.
    """
    blockers: list[str] = []
    if verification.get("db_import_verified") is not True:
        blockers.append("db_import_not_verified")
    expected_category_count = _int_summary_field(verification, "expected_category_count")
    extra_active_category_count = _int_summary_field(
        verification,
        "extra_active_category_count",
    )
    matched_category_count = _int_summary_field(verification, "matched_category_count")
    missing_category_count = _int_summary_field(verification, "missing_category_count")
    expected_product_count = _int_summary_field(verification, "expected_product_count")
    expected_product_category_count = _int_summary_field(
        verification,
        "expected_product_category_count",
    )
    if expected_category_count is None or expected_category_count <= 0:
        blockers.append("category_seed:expected_category_count_missing")
    if (
        expected_category_count is not None
        and matched_category_count is not None
        and matched_category_count != expected_category_count
    ):
        blockers.append("category_seed:matched_category_count_mismatch")
    if missing_category_count is None or missing_category_count != 0:
        blockers.append("category_seed:missing_category_count_not_zero")
    if extra_active_category_count is None or extra_active_category_count != 0:
        blockers.append("category_seed:extra_active_category_count_not_zero")
    if expected_product_count is None or expected_product_count != 0:
        blockers.append("category_seed:expected_product_count_not_zero")
    if expected_product_category_count is None or expected_product_category_count != 0:
        blockers.append("category_seed:expected_product_category_count_not_zero")
    if verification.get("db_write_performed") is True:
        blockers.append("category_seed:verification_must_be_read_only")
    return blockers


def _category_seed_cleanup_preflight_blockers(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Return blockers for missing or unsafe cleanup preflight evidence.

    Args:
        artifacts: Loaded artifact summaries keyed by role.

    Returns:
        Stable blocker codes for category seed cleanup drift.
    """
    verification = artifacts.get("category_seed_db_verification")
    if verification is None:
        return []
    extra_count = _int_summary_field(verification, "extra_active_category_count")
    if extra_count is None or extra_count <= 0:
        return []

    cleanup = artifacts.get("category_seed_cleanup_preflight")
    if cleanup is None:
        return ["category_seed_cleanup_preflight:missing_for_extra_active_categories"]

    blockers: list[str] = []
    if cleanup.get("status") != "manual_cleanup_required":
        blockers.append("category_seed_cleanup_preflight:not_manual_cleanup_required")
    cleanup_extra_count = _int_summary_field(cleanup, "extra_active_category_count")
    if cleanup_extra_count != extra_count:
        blockers.append("category_seed_cleanup_preflight:extra_count_mismatch")
    if cleanup.get("cleanup_required") is not True:
        blockers.append("category_seed_cleanup_preflight:cleanup_not_marked_required")
    if cleanup.get("cleanup_requires_manual_approval") is not True:
        blockers.append("category_seed_cleanup_preflight:manual_approval_not_required")
    if (
        cleanup.get("db_write_performed") is True
        or cleanup.get("db_delete_performed") is True
        or cleanup.get("db_update_performed") is True
    ):
        blockers.append("category_seed_cleanup_preflight:db_side_effect_must_not_run")
    return blockers


def _category_seed_cleanup_apply_blockers(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Return blockers for missing or unsafe cleanup dry-run/apply evidence.

    Args:
        artifacts: Loaded artifact summaries keyed by role.

    Returns:
        Stable blocker codes for category seed cleanup execution planning.
    """
    verification = artifacts.get("category_seed_db_verification")
    if verification is None:
        return []
    extra_count = _int_summary_field(verification, "extra_active_category_count")
    if extra_count is None or extra_count <= 0:
        return []

    preflight_blockers = _category_seed_cleanup_preflight_blockers(artifacts)
    if preflight_blockers:
        return []

    cleanup_apply = artifacts.get("category_seed_cleanup_apply")
    if cleanup_apply is None:
        return ["category_seed_cleanup_apply:missing_manual_cleanup_dry_run"]

    blockers: list[str] = []
    status = cleanup_apply.get("status")
    if status not in {
        "ready_for_manual_category_seed_cleanup",
        "manual_category_seed_cleanup_applied",
    }:
        blockers.append("category_seed_cleanup_apply:status_not_ready_or_applied")
    cleanup_extra_count = _int_summary_field(cleanup_apply, "extra_active_category_count")
    if cleanup_extra_count != extra_count:
        blockers.append("category_seed_cleanup_apply:extra_count_mismatch")
    planned_count = _int_summary_field(cleanup_apply, "planned_category_deactivation_count")
    if planned_count != extra_count:
        blockers.append("category_seed_cleanup_apply:planned_count_mismatch")
    if cleanup_apply.get("db_delete_performed") is True:
        blockers.append("category_seed_cleanup_apply:db_delete_must_not_run")
    if status == "ready_for_manual_category_seed_cleanup":
        blockers.extend(_category_seed_cleanup_dry_run_blockers(cleanup_apply))
    if status == "manual_category_seed_cleanup_applied":
        blockers.extend(
            _category_seed_cleanup_applied_blockers(
                cleanup_apply=cleanup_apply,
                extra_count=extra_count,
            )
        )
    return blockers


def _category_seed_cleanup_dry_run_blockers(
    cleanup_apply: Mapping[str, Any],
) -> list[str]:
    """Return dry-run-specific cleanup apply blockers.

    Args:
        cleanup_apply: Cleanup apply summary.

    Returns:
        Stable blocker codes.
    """
    blockers: list[str] = []
    if cleanup_apply.get("apply_requested") is not False:
        blockers.append("category_seed_cleanup_apply:dry_run_apply_requested")
    if (
        cleanup_apply.get("db_write_performed") is True
        or cleanup_apply.get("db_update_performed") is True
    ):
        blockers.append("category_seed_cleanup_apply:dry_run_db_side_effect")
    return blockers


def _category_seed_cleanup_applied_blockers(
    *,
    cleanup_apply: Mapping[str, Any],
    extra_count: int,
) -> list[str]:
    """Return apply-mode cleanup blockers that require fresh DB verification.

    Args:
        cleanup_apply: Cleanup apply summary.
        extra_count: Extra active category count from the verification artifact.

    Returns:
        Stable blocker codes.
    """
    blockers: list[str] = []
    if cleanup_apply.get("db_write_performed") is not True:
        blockers.append("category_seed_cleanup_apply:applied_without_db_write_flag")
    if cleanup_apply.get("db_update_performed") is not True:
        blockers.append("category_seed_cleanup_apply:applied_without_db_update_flag")
    deactivated_count = _int_summary_field(cleanup_apply, "deactivated_category_count")
    if deactivated_count != extra_count:
        blockers.append("category_seed_cleanup_apply:deactivated_count_mismatch")
    blockers.append("category_seed_cleanup_apply:rerun_db_verification_after_apply")
    return blockers


def _int_summary_field(value: Mapping[str, Any], key: str) -> int | None:
    """Return an integer summary field when it is safely encoded.

    Args:
        value: Artifact summary mapping.
        key: Summary key to read.

    Returns:
        Integer value, or None when missing or not an integer string/value.
    """
    item = value.get(key)
    if isinstance(item, bool):
        return None
    if isinstance(item, int):
        return item
    if isinstance(item, str) and item.isdecimal():
        return int(item)
    return None


def _overall_status(
    *,
    blocked_count: int,
    pending_count: int,
    stages: Sequence[Mapping[str, Any]],
) -> str:
    """Return aggregate pipeline status.

    Args:
        blocked_count: Number of blocked stages.
        pending_count: Number of human-review pending stages.
        stages: Stage rows.

    Returns:
        Stable overall status token.
    """
    if blocked_count:
        return "in_progress_blocked_by_missing_or_invalid_artifacts"
    if pending_count:
        return "in_progress_pending_operator_review"
    if all(stage["status"] == "verified" for stage in stages):
        return "ready_for_operator_model_promotion_review"
    return "in_progress"


def _status_counts(statuses: Iterable[str]) -> dict[str, int]:
    """Count stage statuses.

    Args:
        statuses: Stage status values.

    Returns:
        Sorted status count mapping.
    """
    counts: dict[str, int] = {}
    for status in statuses:
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _is_safe_string_list(value: Any) -> bool:
    """Return whether a value is a small list of non-path strings.

    Args:
        value: Candidate artifact field.

    Returns:
        True when ``value`` is a bounded list of strings safe for redacted
        operator summaries.
    """
    if not isinstance(value, list) or len(value) > MAX_REDACTED_STRING_LIST_ITEMS:
        return False
    for item in value:
        if not isinstance(item, str) or len(item) > MAX_REDACTED_STRING_LENGTH:
            return False
        if any(marker in item for marker in LOCAL_PATH_MARKERS):
            return False
    return True


def _reject_unsafe_payload(value: Any) -> None:
    """Reject payloads that contain raw provider data or local paths.

    Args:
        value: Parsed payload or generated report.

    Raises:
        PipelineReadinessError: If unsafe keys or local path markers are found.
    """
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in RAW_FORBIDDEN_KEYS:
                raise PipelineReadinessError("Unsafe raw/provider key found in artifact.")
            _reject_unsafe_payload(item)
        return
    if isinstance(value, list | tuple):
        for item in value:
            _reject_unsafe_payload(item)
        return
    if isinstance(value, str) and any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise PipelineReadinessError("Unsafe local path marker found in artifact.")


def _summary_from_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Build a compact redacted CLI summary.

    Args:
        report: Full readiness report.

    Returns:
        Summary JSON object.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "ok",
        "overall_status": report["overall_status"],
        "stage_count": report["stage_count"],
        "provided_artifact_count": report["provided_artifact_count"],
        "blocked_stage_count": report["blocked_stage_count"],
        "pending_operator_review_stage_count": report["pending_operator_review_stage_count"],
        "verified_stage_count": report["verified_stage_count"],
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_image_read_performed": False,
        "local_absolute_path_printed": False,
        "product_literal_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def _error_summary(error: Exception) -> dict[str, Any]:
    """Return a redacted error summary.

    Args:
        error: Raised exception. The message is intentionally not included.

    Returns:
        Summary JSON object.
    """
    _ = error
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "error",
        "overall_status": "blocked_invalid_artifact",
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_image_read_performed": False,
        "local_absolute_path_printed": False,
        "product_literal_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write JSON to disk.

    Args:
        path: Destination path.
        payload: JSON object to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    """Run the CLI entrypoint."""
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
