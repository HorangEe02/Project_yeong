"""Register a PaddleOCR training run from a sanitized fine-tune plan.

This bridge consumes ``paddleocr-finetune-run-plan-v1`` and persists a
``ModelTrainingRun`` using the existing sanitized registration boundary. It is
intended for trusted operators after a PaddleOCR training command has completed
and verified metrics are available. It does not execute training and does not
print config refs, model artifact refs, metric names, metric values, labels,
image paths, OCR text, provider payloads, or local filesystem paths.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import UUID

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.learning.retraining import RetrainingSecurityError  # noqa: E402

from scripts import register_model_training_run as training_registration  # noqa: E402

PLAN_SCHEMA_VERSION = "paddleocr-finetune-run-plan-v1"
SUMMARY_SCHEMA_VERSION = "paddleocr-finetune-run-registration-summary-v1"
STATUS_CHOICES = ("succeeded", "failed")
MODEL_FAMILY_BY_TASK = {
    "detection": "paddleocr_det",
    "recognition": "paddleocr_rec",
}


class PaddleOCRFinetuneRegistrationError(ValueError):
    """Raised when a fine-tune plan cannot be registered safely."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--metrics-json", default="{}")
    parser.add_argument("--status", required=True, choices=STATUS_CHOICES)
    return parser.parse_args(argv)


async def run_cli(argv: list[str] | None = None) -> int:
    """Register the run and print a sanitized summary.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        summary = await register_paddleocr_finetune_run_from_plan(
            plan_path=args.plan,
            metrics_snapshot=_parse_metrics_json(args.metrics_json),
            status=args.status,
        )
    except (PaddleOCRFinetuneRegistrationError, RetrainingSecurityError, ValueError) as exc:
        summary = _error_summary(error=exc)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 1

    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


async def register_paddleocr_finetune_run_from_plan(
    *,
    plan_path: Path,
    metrics_snapshot: Mapping[str, Any],
    status: str,
) -> dict[str, Any]:
    """Register one PaddleOCR training run from a sanitized run plan.

    Args:
        plan_path: Fine-tune run plan artifact path.
        metrics_snapshot: Verified numeric metrics from the completed run.
        status: Completed run status, either succeeded or failed.

    Returns:
        Sanitized registration summary.

    Raises:
        PaddleOCRFinetuneRegistrationError: If the plan/status contract is invalid.
        RetrainingSecurityError: If delegated model registration rejects input.
        ValueError: If metric or enum-like input is invalid.
    """
    if status not in STATUS_CHOICES:
        raise ValueError("Unsupported PaddleOCR fine-tune registration status.")
    plan = _load_plan(plan_path)
    plan_view = _validated_plan_view(plan)
    metrics = dict(metrics_snapshot)
    _validate_metrics_for_status(metrics, status=status)

    registration_summary = await training_registration.register_model_training_run(
        model_family=plan_view["model_family"],
        base_model=plan_view["base_model"],
        dataset_version_id=UUID(plan_view["dataset_version_id"]),
        hyperparam_snapshot=_hyperparam_snapshot_from_plan(plan),
        metrics_snapshot=metrics,
        artifact_ref=plan_view["artifact_ref"] if status == "succeeded" else None,
        status=status,
    )
    return _success_summary(
        registration_summary=registration_summary,
        task=plan_view["task"],
        status=status,
        metrics=metrics,
    )


def _load_plan(path: Path) -> dict[str, Any]:
    """Load a fine-tune run plan from disk without leaking the path.

    Args:
        path: Plan file path.

    Returns:
        Parsed plan object.

    Raises:
        PaddleOCRFinetuneRegistrationError: If the plan is missing or malformed.
    """
    if not path.is_file():
        raise PaddleOCRFinetuneRegistrationError("Fine-tune run plan does not exist.")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaddleOCRFinetuneRegistrationError("Fine-tune run plan JSON is malformed.") from exc
    if not isinstance(parsed, dict):
        raise PaddleOCRFinetuneRegistrationError("Fine-tune run plan must be an object.")
    return parsed


def _validated_plan_view(plan: Mapping[str, Any]) -> dict[str, str]:
    """Extract and cross-check the fields needed for DB registration.

    Args:
        plan: Parsed fine-tune plan.

    Returns:
        Minimal safe string view for model training registration.

    Raises:
        PaddleOCRFinetuneRegistrationError: If required fields are inconsistent.
    """
    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise PaddleOCRFinetuneRegistrationError("Unsupported PaddleOCR fine-tune plan schema.")
    if plan.get("training_execution_performed") is not False:
        raise PaddleOCRFinetuneRegistrationError("Fine-tune plan must be pre-execution metadata.")
    task = _string_field(plan, "task")
    expected_family = MODEL_FAMILY_BY_TASK.get(task)
    if expected_family is None:
        raise PaddleOCRFinetuneRegistrationError("Unsupported PaddleOCR fine-tune task.")
    model_family = _string_field(plan, "model_family")
    if model_family != expected_family:
        raise PaddleOCRFinetuneRegistrationError("Fine-tune plan model family does not match task.")
    dataset_version_id = _string_field(plan, "dataset_version_id")
    UUID(dataset_version_id)
    base_model = _string_field(plan, "base_model")

    paddleocr = plan.get("paddleocr")
    if not isinstance(paddleocr, Mapping):
        raise PaddleOCRFinetuneRegistrationError("Fine-tune plan paddleocr block is missing.")
    save_model_ref = _string_field(paddleocr, "save_model_ref")

    registration = plan.get("register_model_training_run")
    if not isinstance(registration, Mapping):
        raise PaddleOCRFinetuneRegistrationError("Fine-tune plan registration block is missing.")
    if _string_field(registration, "model_family") != model_family:
        raise PaddleOCRFinetuneRegistrationError("Registration model family is inconsistent.")
    if _string_field(registration, "base_model") != base_model:
        raise PaddleOCRFinetuneRegistrationError("Registration base model is inconsistent.")
    if _string_field(registration, "dataset_version_id") != dataset_version_id:
        raise PaddleOCRFinetuneRegistrationError("Registration dataset version is inconsistent.")
    if _string_field(registration, "artifact_ref") != save_model_ref:
        raise PaddleOCRFinetuneRegistrationError("Registration artifact ref is inconsistent.")

    return {
        "task": task,
        "model_family": model_family,
        "dataset_version_id": dataset_version_id,
        "base_model": base_model,
        "artifact_ref": save_model_ref,
    }


def _hyperparam_snapshot_from_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Build the sanitized hyperparameter snapshot to persist.

    Args:
        plan: Parsed fine-tune plan.

    Returns:
        Hyperparameter snapshot without docs URLs, labels, local paths, or metrics.

    Raises:
        PaddleOCRFinetuneRegistrationError: If required plan blocks are malformed.
    """
    hyperparams = plan.get("hyperparams")
    paddleocr = plan.get("paddleocr")
    if not isinstance(hyperparams, Mapping) or not isinstance(paddleocr, Mapping):
        raise PaddleOCRFinetuneRegistrationError(
            "Fine-tune plan hyperparameter blocks are invalid."
        )
    return {
        "plan_schema_version": PLAN_SCHEMA_VERSION,
        "task": _string_field(plan, "task"),
        "config_ref": _string_field(paddleocr, "config_ref"),
        "pretrained_model_ref": _string_field(paddleocr, "pretrained_model_ref"),
        "save_model_ref": _string_field(paddleocr, "save_model_ref"),
        "epochs": _numeric_field(hyperparams, "epochs"),
        "learning_rate": _numeric_field(hyperparams, "learning_rate"),
        "batch_size_per_card": _numeric_field(hyperparams, "batch_size_per_card"),
        "gpus": _string_field(hyperparams, "gpus"),
    }


def _string_field(mapping: Mapping[str, Any], key: str) -> str:
    """Return a required non-empty string field.

    Args:
        mapping: Source mapping.
        key: Field name.

    Returns:
        Field value.

    Raises:
        PaddleOCRFinetuneRegistrationError: If the field is missing.
    """
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PaddleOCRFinetuneRegistrationError("Fine-tune plan is missing required metadata.")
    return value


def _numeric_field(mapping: Mapping[str, Any], key: str) -> int | float:
    """Return a required finite numeric field.

    Args:
        mapping: Source mapping.
        key: Field name.

    Returns:
        Numeric field value.

    Raises:
        PaddleOCRFinetuneRegistrationError: If the field is missing or invalid.
    """
    value = mapping.get(key)
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(float(value))
    ):
        raise PaddleOCRFinetuneRegistrationError("Fine-tune plan has invalid numeric metadata.")
    return value


def _parse_metrics_json(raw_json: str) -> dict[str, Any]:
    """Parse CLI metrics JSON.

    Args:
        raw_json: Raw JSON object string.

    Returns:
        Parsed metrics object.

    Raises:
        ValueError: If metrics JSON is not an object.
    """
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError("metrics-json must be valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("metrics-json must be a JSON object.")
    return parsed


def _validate_metrics_for_status(metrics: Mapping[str, Any], *, status: str) -> None:
    """Validate metric presence before delegated registration.

    Args:
        metrics: Metric snapshot.
        status: Registration status.

    Raises:
        ValueError: If a successful run has no metrics.
    """
    if status == "succeeded" and not metrics:
        raise ValueError("Succeeded PaddleOCR fine-tune runs require verified metrics.")


def _success_summary(
    *,
    registration_summary: Mapping[str, Any],
    task: str,
    status: str,
    metrics: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a redacted registration summary.

    Args:
        registration_summary: Summary from the delegated registration script.
        task: PaddleOCR task.
        status: Training status.
        metrics: Metric snapshot.

    Returns:
        Aggregate-only summary without config refs, artifact refs, metric names, or values.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "ok",
        "training_run_id": registration_summary["training_run_id"],
        "task": task,
        "model_family": registration_summary["model_family"],
        "dataset_version_id": registration_summary["dataset_version_id"],
        "training_status": status,
        "metric_key_count": len(metrics),
        "artifact_ref_registered": registration_summary["artifact_ref_registered"],
        "registered_from_plan": True,
        "training_execution_performed_by_script": False,
        "config_ref_printed": False,
        "artifact_ref_printed": False,
        "metric_names_printed": False,
        "metric_values_printed": False,
        "label_text_printed": False,
        "source_path_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def _error_summary(*, error: BaseException) -> dict[str, Any]:
    """Return a redacted error summary.

    Args:
        error: Raised exception.

    Returns:
        Error summary without input path or raw values.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "error",
        "error_type": type(error).__name__,
        "registered_from_plan": False,
        "training_execution_performed_by_script": False,
        "config_ref_printed": False,
        "artifact_ref_printed": False,
        "metric_names_printed": False,
        "metric_values_printed": False,
        "label_text_printed": False,
        "source_path_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def main() -> None:
    """Run the CLI entrypoint."""
    raise SystemExit(asyncio.run(run_cli()))


if __name__ == "__main__":
    main()
