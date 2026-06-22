"""Build a redacted operator runbook for PaddleOCR model promotion.

The runbook is the final non-mutating checkpoint before a trained PaddleOCR
candidate is promoted through ``promote_model_candidate.py``. It reuses the
promotion readiness preflight, verifies the readiness artifact that an operator
will review, and emits an ordered runbook without local paths, metric names,
metric values, checkpoint refs, artifact refs, raw OCR text, or provider
payloads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from scripts import validate_paddleocr_promotion_artifacts as preflight

RUNBOOK_SCHEMA_VERSION = "paddleocr-promotion-operator-runbook-v1"
SUMMARY_SCHEMA_VERSION = "paddleocr-promotion-operator-runbook-summary-v1"
READINESS_SCHEMA_VERSION = "paddleocr-promotion-readiness-v1"
TASK_CHOICES = ("detection", "recognition")
EXPECTED_READINESS_ARTIFACT_COUNT = 5


class PaddleOCRPromotionRunbookError(ValueError):
    """Raised when a promotion runbook cannot be trusted."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, choices=TASK_CHOICES)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--finetune-eval", required=True, type=Path)
    parser.add_argument("--baseline-eval", required=True, type=Path)
    parser.add_argument("--baseline-gate", required=True, type=Path)
    parser.add_argument("--promotion-rules", required=True, type=Path)
    parser.add_argument("--readiness", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None) -> int:
    """Build the promotion runbook and print a redacted summary.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        runbook, summary = build_paddleocr_promotion_runbook(
            task=args.task,
            plan_path=args.plan,
            finetune_eval_path=args.finetune_eval,
            baseline_eval_path=args.baseline_eval,
            baseline_gate_path=args.baseline_gate,
            promotion_rules_path=args.promotion_rules,
            readiness_path=args.readiness,
        )
    except (OSError, PaddleOCRPromotionRunbookError, preflight.PaddleOCRPromotionReadinessError):
        summary = _error_summary()
        _write_json(args.output, summary)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 1

    _write_json(args.output, runbook)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def build_paddleocr_promotion_runbook(
    *,
    task: str,
    plan_path: Path,
    finetune_eval_path: Path,
    baseline_eval_path: Path,
    baseline_gate_path: Path,
    promotion_rules_path: Path,
    readiness_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a redacted promotion runbook after artifact verification.

    Args:
        task: PaddleOCR task, either ``detection`` or ``recognition``.
        plan_path: Fine-tune run plan artifact.
        finetune_eval_path: Fine-tuned eval artifact.
        baseline_eval_path: Baseline eval artifact.
        baseline_gate_path: Baseline comparison gate artifact.
        promotion_rules_path: Promotion metric rules artifact.
        readiness_path: Readiness preflight artifact.

    Returns:
        Runbook artifact and redacted operator summary.

    Raises:
        PaddleOCRPromotionRunbookError: If the readiness artifact or task is unsafe.
        PaddleOCRPromotionReadinessError: If the artifact chain fails preflight.
    """
    if task not in TASK_CHOICES:
        raise PaddleOCRPromotionRunbookError("Unsupported PaddleOCR promotion task.")

    readiness, _summary = preflight.validate_paddleocr_promotion_artifacts(
        plan_path=plan_path,
        finetune_eval_path=finetune_eval_path,
        baseline_eval_path=baseline_eval_path,
        baseline_gate_path=baseline_gate_path,
        promotion_rules_path=promotion_rules_path,
    )
    if readiness["task"] != task:
        raise PaddleOCRPromotionRunbookError("Verified artifact task does not match request.")

    stored_readiness = _load_json_object(readiness_path)
    _validate_stored_readiness(stored_readiness, expected_task=task)

    artifact_inputs = [
        _artifact_summary("plan", plan_path),
        _artifact_summary("finetune_eval", finetune_eval_path),
        _artifact_summary("baseline_eval", baseline_eval_path),
        _artifact_summary("baseline_gate", baseline_gate_path),
        _artifact_summary("promotion_rules", promotion_rules_path),
        _artifact_summary("readiness", readiness_path),
    ]
    stages = _runbook_stages(task=task)
    runbook = {
        "schema_version": RUNBOOK_SCHEMA_VERSION,
        "task": task,
        "ready_for_operator_review": True,
        "stage_count": len(stages),
        "stages": stages,
        "artifact_count": len(artifact_inputs),
        "artifact_inputs": artifact_inputs,
        "preflight_revalidated": True,
        "stored_readiness_checked": True,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "training_execution_performed_by_script": False,
        "metric_names_printed": False,
        "metric_values_printed": False,
        "source_path_printed": False,
        "checkpoint_ref_printed": False,
        "artifact_ref_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }
    return runbook, _success_summary(runbook=runbook)


def _validate_stored_readiness(payload: Mapping[str, Any], *, expected_task: str) -> None:
    """Validate the persisted readiness artifact reviewed by an operator.

    Args:
        payload: Stored readiness artifact.
        expected_task: Expected PaddleOCR task.

    Raises:
        PaddleOCRPromotionRunbookError: If readiness is missing or unsafe.
    """
    if payload.get("schema_version") != READINESS_SCHEMA_VERSION:
        raise PaddleOCRPromotionRunbookError("Unsupported readiness schema.")
    if payload.get("task") != expected_task:
        raise PaddleOCRPromotionRunbookError("Readiness task does not match request.")
    if payload.get("ready_for_promotion") is not True:
        raise PaddleOCRPromotionRunbookError("Readiness artifact is not promotion-ready.")
    if payload.get("artifact_count") != EXPECTED_READINESS_ARTIFACT_COUNT:
        raise PaddleOCRPromotionRunbookError("Readiness artifact count is unexpected.")
    for key in (
        "metric_names_printed",
        "metric_values_printed",
        "source_path_printed",
        "checkpoint_ref_printed",
        "artifact_ref_printed",
        "raw_ocr_text_stored",
        "raw_provider_payload_stored",
    ):
        if payload.get(key) is not False:
            raise PaddleOCRPromotionRunbookError("Readiness artifact redaction flag is unsafe.")


def _runbook_stages(*, task: str) -> list[dict[str, Any]]:
    """Return ordered promotion stages without executable local paths.

    Args:
        task: PaddleOCR task.

    Returns:
        Ordered stage descriptors.
    """
    return [
        {
            "stage_key": "verify_finetune_plan",
            "required_artifact_role": "plan",
            "expected_schema": preflight.PLAN_SCHEMA_VERSION,
            "status_gate": "training_execution_performed=false",
            "operator_action": "confirm_dataset_config_and_private_artifact_refs",
        },
        {
            "stage_key": "verify_finetuned_eval",
            "required_artifact_role": "finetune_eval",
            "expected_schema": preflight.FINETUNE_EVAL_SCHEMA_VERSION,
            "status_gate": "process_status=metrics_verified",
            "operator_action": "confirm_finetuned_metrics_json_exists",
        },
        {
            "stage_key": "verify_baseline_eval",
            "required_artifact_role": "baseline_eval",
            "expected_schema": preflight.BASELINE_EVAL_SCHEMA_VERSION,
            "status_gate": "process_status=metrics_verified",
            "operator_action": "confirm_baseline_metrics_json_exists",
        },
        {
            "stage_key": "verify_baseline_gate",
            "required_artifact_role": "baseline_gate",
            "expected_schema": preflight.BASELINE_GATE_SCHEMA_VERSION,
            "status_gate": "allowed=true",
            "operator_action": "confirm_absolute_threshold_and_baseline_improvement_passed",
        },
        {
            "stage_key": "verify_promotion_rules",
            "required_artifact_role": "promotion_rules",
            "expected_schema": preflight.PROMOTION_RULES_SCHEMA_VERSION,
            "status_gate": "allowed_by_baseline_gate=true",
            "operator_action": "use_rules_for_model_promotion_only_after_preflight",
        },
        {
            "stage_key": "verify_readiness_preflight",
            "required_artifact_role": "readiness",
            "expected_schema": READINESS_SCHEMA_VERSION,
            "status_gate": "ready_for_promotion=true",
            "operator_action": "run_model_promotion_with_db_apply_only_after_review",
        },
        {
            "stage_key": "operator_promotion_boundary",
            "required_artifact_role": "operator_review",
            "expected_schema": RUNBOOK_SCHEMA_VERSION,
            "status_gate": f"task={task}",
            "operator_action": "record_human_approval_before_db_write",
        },
    ]


def _artifact_summary(role: str, path: Path) -> dict[str, Any]:
    """Return a path-redacted artifact summary.

    Args:
        role: Artifact role in the promotion chain.
        path: Artifact path.

    Returns:
        Redacted artifact summary with file name and content digest only.

    Raises:
        PaddleOCRPromotionRunbookError: If the artifact cannot be read safely.
    """
    if not path.is_file():
        raise PaddleOCRPromotionRunbookError("Required artifact is missing.")
    content = path.read_bytes()
    return {
        "role": role,
        "file_name": path.name,
        "content_sha256": hashlib.sha256(content).hexdigest(),
        "path_hash": hashlib.sha256(str(path.expanduser()).encode("utf-8")).hexdigest(),
    }


def _load_json_object(path: Path) -> dict[str, Any]:
    """Load a JSON object without retaining path text in error messages.

    Args:
        path: JSON artifact path.

    Returns:
        Parsed JSON object.

    Raises:
        PaddleOCRPromotionRunbookError: If the file is missing or malformed.
    """
    if not path.is_file():
        raise PaddleOCRPromotionRunbookError("Required artifact is missing.")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaddleOCRPromotionRunbookError("Required artifact JSON is malformed.") from exc
    if not isinstance(parsed, dict):
        raise PaddleOCRPromotionRunbookError("Required artifact must be an object.")
    return parsed


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write a JSON object.

    Args:
        path: Destination path.
        payload: JSON payload.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _success_summary(*, runbook: Mapping[str, Any]) -> dict[str, Any]:
    """Return an aggregate-only success summary.

    Args:
        runbook: Generated runbook artifact.

    Returns:
        Redacted operator summary.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "ok",
        "task": runbook["task"],
        "ready_for_operator_review": runbook["ready_for_operator_review"],
        "stage_count": runbook["stage_count"],
        "artifact_count": runbook["artifact_count"],
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "training_execution_performed_by_script": False,
        "metric_names_printed": False,
        "metric_values_printed": False,
        "source_path_printed": False,
        "checkpoint_ref_printed": False,
        "artifact_ref_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def _error_summary() -> dict[str, Any]:
    """Return an aggregate-only error summary."""
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "error",
        "ready_for_operator_review": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "training_execution_performed_by_script": False,
        "metric_names_printed": False,
        "metric_values_printed": False,
        "source_path_printed": False,
        "checkpoint_ref_printed": False,
        "artifact_ref_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def main() -> None:
    """Run the CLI entrypoint."""
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
