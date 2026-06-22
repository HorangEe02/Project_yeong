"""Validate PaddleOCR promotion artifacts before DB-backed promotion.

This preflight checks that fine-tuned eval metrics, baseline eval metrics,
baseline comparison gate output, and promotion rules all agree on task and
status before an operator calls ``promote_model_candidate.py``. It does not
mutate DB state and does not print paths, metric names, metric values,
checkpoint refs, raw OCR text, provider payloads, or model artifact refs.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

PLAN_SCHEMA_VERSION = "paddleocr-finetune-run-plan-v1"
FINETUNE_EVAL_SCHEMA_VERSION = "paddleocr-finetune-eval-result-v1"
BASELINE_EVAL_SCHEMA_VERSION = "paddleocr-baseline-eval-result-v1"
BASELINE_GATE_SCHEMA_VERSION = "paddleocr-baseline-comparison-gate-v1"
PROMOTION_RULES_SCHEMA_VERSION = "paddleocr-promotion-metric-rules-v1"
READINESS_SCHEMA_VERSION = "paddleocr-promotion-readiness-v1"
SUMMARY_SCHEMA_VERSION = "paddleocr-promotion-readiness-summary-v1"
TASK_CHOICES = ("detection", "recognition")


class PaddleOCRPromotionReadinessError(ValueError):
    """Raised when promotion artifacts are incomplete or inconsistent."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--finetune-eval", required=True, type=Path)
    parser.add_argument("--baseline-eval", required=True, type=Path)
    parser.add_argument("--baseline-gate", required=True, type=Path)
    parser.add_argument("--promotion-rules", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None) -> int:
    """Validate promotion artifacts and print a redacted summary.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        readiness, summary = validate_paddleocr_promotion_artifacts(
            plan_path=args.plan,
            finetune_eval_path=args.finetune_eval,
            baseline_eval_path=args.baseline_eval,
            baseline_gate_path=args.baseline_gate,
            promotion_rules_path=args.promotion_rules,
        )
    except PaddleOCRPromotionReadinessError as exc:
        summary = _error_summary(error=exc)
        _write_json(args.output, summary)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 1

    _write_json(args.output, readiness)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def validate_paddleocr_promotion_artifacts(
    *,
    plan_path: Path,
    finetune_eval_path: Path,
    baseline_eval_path: Path,
    baseline_gate_path: Path,
    promotion_rules_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate the artifact chain needed before model promotion.

    Args:
        plan_path: PaddleOCR fine-tune run plan artifact.
        finetune_eval_path: Fine-tuned eval result artifact.
        baseline_eval_path: Baseline eval result artifact.
        baseline_gate_path: Baseline comparison gate artifact.
        promotion_rules_path: Promotion metric rules artifact.

    Returns:
        Redacted readiness artifact and redacted operator summary.

    Raises:
        PaddleOCRPromotionReadinessError: If any artifact is unsafe or inconsistent.
    """
    plan = _load_json_object(plan_path)
    finetune_eval = _load_json_object(finetune_eval_path)
    baseline_eval = _load_json_object(baseline_eval_path)
    baseline_gate = _load_json_object(baseline_gate_path)
    promotion_rules = _load_json_object(promotion_rules_path)

    task = _validated_plan_task(plan)
    _validate_finetune_eval(finetune_eval, task=task)
    _validate_baseline_eval(baseline_eval, task=task)
    gate_rule_count = _validate_baseline_gate(baseline_gate, task=task)
    promotion_rule_count = _validate_promotion_rules(
        promotion_rules,
        task=task,
        expected_rule_count=gate_rule_count,
    )

    readiness = {
        "schema_version": READINESS_SCHEMA_VERSION,
        "ready_for_promotion": True,
        "task": task,
        "artifact_count": 5,
        "gate_rule_count": gate_rule_count,
        "promotion_rule_count": promotion_rule_count,
        "finetune_metrics_ready": True,
        "baseline_metrics_ready": True,
        "baseline_gate_allowed": True,
        "promotion_rules_allowed": True,
        "db_write_performed": False,
        "metric_names_printed": False,
        "metric_values_printed": False,
        "source_path_printed": False,
        "checkpoint_ref_printed": False,
        "artifact_ref_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }
    return readiness, _success_summary(readiness=readiness)


def _load_json_object(path: Path) -> dict[str, Any]:
    """Load a JSON object without retaining path details in errors.

    Args:
        path: Artifact path.

    Returns:
        Parsed JSON object.

    Raises:
        PaddleOCRPromotionReadinessError: If the file is missing or malformed.
    """
    if not path.is_file():
        raise PaddleOCRPromotionReadinessError("Required artifact is missing.")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaddleOCRPromotionReadinessError("Required artifact JSON is malformed.") from exc
    if not isinstance(parsed, dict):
        raise PaddleOCRPromotionReadinessError("Required artifact must be an object.")
    return parsed


def _validated_plan_task(plan: Mapping[str, Any]) -> str:
    """Validate plan schema and return its task.

    Args:
        plan: Plan artifact.

    Returns:
        Task key.

    Raises:
        PaddleOCRPromotionReadinessError: If the plan is unsupported.
    """
    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise PaddleOCRPromotionReadinessError("Unsupported plan schema.")
    if plan.get("training_execution_performed") is not False:
        raise PaddleOCRPromotionReadinessError("Plan must be pre-execution metadata.")
    task = plan.get("task")
    if task not in TASK_CHOICES:
        raise PaddleOCRPromotionReadinessError("Unsupported plan task.")
    return str(task)


def _validate_finetune_eval(payload: Mapping[str, Any], *, task: str) -> None:
    """Validate a fine-tuned eval result artifact.

    Args:
        payload: Fine-tuned eval artifact.
        task: Expected task.

    Raises:
        PaddleOCRPromotionReadinessError: If the artifact is not comparison-ready.
    """
    if payload.get("schema_version") != FINETUNE_EVAL_SCHEMA_VERSION:
        raise PaddleOCRPromotionReadinessError("Unsupported fine-tuned eval schema.")
    if payload.get("task") != task:
        raise PaddleOCRPromotionReadinessError("Fine-tuned eval task does not match plan.")
    if payload.get("process_status") != "metrics_verified":
        raise PaddleOCRPromotionReadinessError("Fine-tuned eval metrics are not verified.")
    if payload.get("metrics_json_ready_for_registration") is not True:
        raise PaddleOCRPromotionReadinessError("Fine-tuned metrics are not registration-ready.")
    _validate_no_raw_eval_payload(payload)


def _validate_baseline_eval(payload: Mapping[str, Any], *, task: str) -> None:
    """Validate a baseline eval result artifact.

    Args:
        payload: Baseline eval artifact.
        task: Expected task.

    Raises:
        PaddleOCRPromotionReadinessError: If the artifact is not comparison-ready.
    """
    if payload.get("schema_version") != BASELINE_EVAL_SCHEMA_VERSION:
        raise PaddleOCRPromotionReadinessError("Unsupported baseline eval schema.")
    if payload.get("task") != task:
        raise PaddleOCRPromotionReadinessError("Baseline eval task does not match plan.")
    if payload.get("process_status") != "metrics_verified":
        raise PaddleOCRPromotionReadinessError("Baseline eval metrics are not verified.")
    if payload.get("metrics_json_ready_for_comparison") is not True:
        raise PaddleOCRPromotionReadinessError("Baseline metrics are not comparison-ready.")
    _validate_no_raw_eval_payload(payload)


def _validate_baseline_gate(payload: Mapping[str, Any], *, task: str) -> int:
    """Validate a baseline comparison gate artifact.

    Args:
        payload: Gate artifact.
        task: Expected task.

    Returns:
        Gate rule count.

    Raises:
        PaddleOCRPromotionReadinessError: If the gate did not pass.
    """
    if payload.get("schema_version") != BASELINE_GATE_SCHEMA_VERSION:
        raise PaddleOCRPromotionReadinessError("Unsupported baseline gate schema.")
    if payload.get("task") != task:
        raise PaddleOCRPromotionReadinessError("Baseline gate task does not match plan.")
    if payload.get("allowed") is not True:
        raise PaddleOCRPromotionReadinessError("Baseline gate did not allow promotion.")
    rule_count = payload.get("rule_count")
    passed_rule_count = payload.get("passed_rule_count")
    if not isinstance(rule_count, int) or rule_count <= 0:
        raise PaddleOCRPromotionReadinessError("Baseline gate has no metric rules.")
    if passed_rule_count != rule_count:
        raise PaddleOCRPromotionReadinessError("Baseline gate did not pass every metric rule.")
    if payload.get("raw_ocr_text_stored") is not False:
        raise PaddleOCRPromotionReadinessError("Baseline gate contains raw OCR data.")
    if payload.get("raw_provider_payload_stored") is not False:
        raise PaddleOCRPromotionReadinessError("Baseline gate contains raw provider data.")
    return rule_count


def _validate_promotion_rules(
    payload: Mapping[str, Any],
    *,
    task: str,
    expected_rule_count: int,
) -> int:
    """Validate promotion rules generated by baseline comparison.

    Args:
        payload: Promotion rules artifact.
        task: Expected task.
        expected_rule_count: Rule count expected from the baseline gate.

    Returns:
        Promotion rule count.

    Raises:
        PaddleOCRPromotionReadinessError: If rules are not safe to use.
    """
    if payload.get("schema_version") != PROMOTION_RULES_SCHEMA_VERSION:
        raise PaddleOCRPromotionReadinessError("Unsupported promotion rules schema.")
    if payload.get("task") != task:
        raise PaddleOCRPromotionReadinessError("Promotion rules task does not match plan.")
    if payload.get("allowed_by_baseline_gate") is not True:
        raise PaddleOCRPromotionReadinessError("Promotion rules were not allowed by gate.")
    raw_rules = payload.get("metric_rules")
    if not isinstance(raw_rules, list) or len(raw_rules) != expected_rule_count:
        raise PaddleOCRPromotionReadinessError("Promotion rule count does not match gate.")
    if payload.get("artifact_ref_printed") is not False:
        raise PaddleOCRPromotionReadinessError("Promotion rules expose artifact refs.")
    return len(raw_rules)


def _validate_no_raw_eval_payload(payload: Mapping[str, Any]) -> None:
    """Validate eval result redaction flags.

    Args:
        payload: Eval artifact.

    Raises:
        PaddleOCRPromotionReadinessError: If raw data flags are unsafe.
    """
    if payload.get("stdout_raw_stored") is not False:
        raise PaddleOCRPromotionReadinessError("Eval artifact contains raw stdout.")
    if payload.get("stderr_raw_stored") is not False:
        raise PaddleOCRPromotionReadinessError("Eval artifact contains raw stderr.")
    if payload.get("raw_ocr_text_stored") is not False:
        raise PaddleOCRPromotionReadinessError("Eval artifact contains raw OCR text.")
    if payload.get("raw_provider_payload_stored") is not False:
        raise PaddleOCRPromotionReadinessError("Eval artifact contains raw provider data.")


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


def _success_summary(*, readiness: Mapping[str, Any]) -> dict[str, Any]:
    """Return a redacted success summary.

    Args:
        readiness: Readiness artifact.

    Returns:
        Aggregate-only operator summary.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "ok",
        "ready_for_promotion": readiness["ready_for_promotion"],
        "task": readiness["task"],
        "artifact_count": readiness["artifact_count"],
        "gate_rule_count": readiness["gate_rule_count"],
        "promotion_rule_count": readiness["promotion_rule_count"],
        "db_write_performed": False,
        "metric_names_printed": False,
        "metric_values_printed": False,
        "source_path_printed": False,
        "checkpoint_ref_printed": False,
        "artifact_ref_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def _error_summary(*, error: BaseException) -> dict[str, Any]:
    """Return a redacted error summary.

    Args:
        error: Raised exception.

    Returns:
        Error summary without artifact paths or metric details.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "error",
        "error_type": type(error).__name__,
        "ready_for_promotion": False,
        "db_write_performed": False,
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
