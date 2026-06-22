"""Register a sanitized model training run for operator workflows."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.db.session import get_sessionmaker  # noqa: E402
from src.learning.retraining import (  # noqa: E402
    RetrainingSecurityError,
    validate_sanitized_label_snapshot,
)
from src.models.db.retraining import ModelTrainingRun  # noqa: E402

SUMMARY_SCHEMA_VERSION = "model-training-run-registration-summary-v1"
MODEL_FAMILY_CHOICES = (
    "yolo",
    "paddleocr_det",
    "paddleocr_rec",
    "food_classifier",
    "image_embedding",
)
STATUS_CHOICES = (
    "queued",
    "running",
    "succeeded",
    "failed",
)
SECRET_LIKE_MARKERS = (
    "bearer ",
    "ngrok-free.dev",
    "sb_secret_",
    "service_role",
    "aws_secret_access_key",
    "-----begin",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-family", required=True, choices=MODEL_FAMILY_CHOICES)
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--dataset-version-id", required=True, type=UUID)
    parser.add_argument("--hyperparams-json", default="{}")
    parser.add_argument("--metrics-json", default="{}")
    parser.add_argument("--artifact-ref", default=None)
    parser.add_argument("--status", default="queued", choices=STATUS_CHOICES)
    return parser.parse_args(argv)


async def run_cli(argv: list[str] | None = None) -> int:
    """Parse arguments, register the training run, and print a summary.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        summary = await register_model_training_run(
            model_family=args.model_family,
            base_model=args.base_model,
            dataset_version_id=args.dataset_version_id,
            hyperparam_snapshot=_parse_json_object(args.hyperparams_json, "hyperparams-json"),
            metrics_snapshot=_parse_json_object(args.metrics_json, "metrics-json"),
            artifact_ref=args.artifact_ref,
            status=args.status,
        )
    except (RetrainingSecurityError, ValueError) as exc:
        summary = _error_summary(error=exc)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 1

    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


async def register_model_training_run(
    *,
    model_family: str,
    base_model: str,
    dataset_version_id: UUID,
    hyperparam_snapshot: Mapping[str, Any],
    metrics_snapshot: Mapping[str, Any],
    artifact_ref: str | None,
    status: str,
) -> dict[str, object]:
    """Persist one sanitized model training run.

    Args:
        model_family: Model family key.
        base_model: Base model tag.
        dataset_version_id: Training dataset version id.
        hyperparam_snapshot: Sanitized training config.
        metrics_snapshot: Verified numeric metric snapshot.
        artifact_ref: Optional private artifact reference.
        status: Initial training lifecycle status.

    Returns:
        Sanitized registration summary.

    Raises:
        RetrainingSecurityError: If config, metrics, or artifact ref is unsafe.
        ValueError: If enum-like input is invalid.
    """
    if model_family not in MODEL_FAMILY_CHOICES:
        raise ValueError("Unsupported model family.")
    if status not in STATUS_CHOICES:
        raise ValueError("Unsupported training run status.")
    _validate_base_model(base_model)
    validate_sanitized_label_snapshot(hyperparam_snapshot)
    _validate_metric_snapshot(metrics_snapshot)
    _validate_artifact_ref(artifact_ref)

    training_run = ModelTrainingRun(
        id=uuid4(),
        model_family=model_family,
        base_model=base_model,
        dataset_version_id=dataset_version_id,
        hyperparam_snapshot=dict(hyperparam_snapshot),
        metrics_snapshot=dict(metrics_snapshot),
        artifact_ref=artifact_ref,
        status=status,
        started_at=datetime.now(UTC) if status == "running" else None,
    )
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        session.add(training_run)
        await session.commit()

    return _success_summary(training_run=training_run)


def _parse_json_object(raw_json: str, argument_name: str) -> dict[str, Any]:
    """Parse a CLI JSON object argument.

    Args:
        raw_json: Raw JSON text.
        argument_name: Argument name used in error messages.

    Returns:
        Parsed JSON object.

    Raises:
        ValueError: If the input is not a JSON object.
    """
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{argument_name} must be valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{argument_name} must be a JSON object.")
    return parsed


def _validate_base_model(base_model: str) -> None:
    """Reject unsafe base model tags.

    Args:
        base_model: Candidate base model tag.

    Raises:
        RetrainingSecurityError: If the tag looks like a path, URL, or secret.
    """
    if not base_model.strip():
        raise RetrainingSecurityError("Base model is required.")
    _reject_path_url_or_secret(base_model, "Base model")


def _validate_metric_snapshot(metrics_snapshot: Mapping[str, Any]) -> None:
    """Validate a flat numeric metric snapshot.

    Args:
        metrics_snapshot: Candidate metric snapshot.

    Raises:
        RetrainingSecurityError: If a key or value is unsafe.
    """
    for key, value in metrics_snapshot.items():
        if not isinstance(key, str) or not key.strip():
            raise RetrainingSecurityError("Metric keys must be non-empty strings.")
        _reject_path_url_or_secret(key, "Metric key")
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise RetrainingSecurityError("Metric values must be numeric.")
        numeric_value = float(value)
        if not math.isfinite(numeric_value) or numeric_value < 0:
            raise RetrainingSecurityError("Metric values must be finite and nonnegative.")


def _validate_artifact_ref(artifact_ref: str | None) -> None:
    """Validate a private model artifact reference.

    Args:
        artifact_ref: Optional artifact reference.

    Raises:
        RetrainingSecurityError: If the ref is empty, public, absolute, traversing, or secret-like.
    """
    if artifact_ref is None:
        return
    if not artifact_ref.strip():
        raise RetrainingSecurityError("Artifact ref cannot be empty.")
    _reject_path_url_or_secret(artifact_ref, "Artifact ref")


def _reject_path_url_or_secret(value: str, label: str) -> None:
    """Reject URL, absolute path, traversal, and secret-like values.

    Args:
        value: Candidate string.
        label: Error label.

    Raises:
        RetrainingSecurityError: If the value is unsafe.
    """
    folded = value.casefold()
    if "://" in value or value.startswith("/") or ".." in value:
        raise RetrainingSecurityError(f"{label} must be a private relative reference.")
    if any(marker in folded for marker in SECRET_LIKE_MARKERS):
        raise RetrainingSecurityError(f"{label} contains a secret-like value.")


def _success_summary(*, training_run: ModelTrainingRun) -> dict[str, object]:
    """Return a redacted success summary.

    Args:
        training_run: Persisted training run.

    Returns:
        Summary without artifact ref, hyperparams, metrics, or paths.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "ok",
        "training_run_id": str(training_run.id),
        "model_family": training_run.model_family,
        "dataset_version_id": str(training_run.dataset_version_id),
        "training_status": training_run.status,
        "hyperparam_key_count": len(training_run.hyperparam_snapshot),
        "metric_key_count": len(training_run.metrics_snapshot),
        "artifact_ref_registered": training_run.artifact_ref is not None,
        "artifact_ref_printed": False,
        "raw_config_printed": False,
        "raw_metrics_printed": False,
    }


def _error_summary(*, error: BaseException) -> dict[str, object]:
    """Return a redacted error summary.

    Args:
        error: Raised exception.

    Returns:
        Summary with only the exception class.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "error",
        "error_type": type(error).__name__,
        "artifact_ref_printed": False,
        "raw_config_printed": False,
        "raw_metrics_printed": False,
    }


def main() -> None:
    """Run the CLI entrypoint."""
    raise SystemExit(asyncio.run(run_cli()))


if __name__ == "__main__":
    main()
