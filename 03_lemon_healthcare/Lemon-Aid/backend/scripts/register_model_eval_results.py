"""Register sanitized model evaluation metrics for promotion gates."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import UUID, uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.db.session import get_sessionmaker  # noqa: E402
from src.learning.retraining import RetrainingSecurityError  # noqa: E402
from src.models.db.retraining import ModelEvalResult, ModelRegistryEntry  # noqa: E402

SUMMARY_SCHEMA_VERSION = "model-eval-results-registration-summary-v1"
METRIC_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
STABLE_CODE_PATTERN = re.compile(r"^[a-z0-9_.:-]{1,120}$")
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
    parser.add_argument("--model-id", required=True, type=UUID)
    parser.add_argument("--eval-dataset-version-id", required=True, type=UUID)
    parser.add_argument(
        "--metric",
        action="append",
        default=[],
        nargs=2,
        metavar=("NAME", "VALUE"),
        help="Evaluation metric row, for example: --metric cer 0.081",
    )
    parser.add_argument("--subgroup-key", default=None)
    parser.add_argument("--failure-bucket", default=None)
    return parser.parse_args(argv)


async def run_cli(argv: list[str] | None = None) -> int:
    """Parse arguments, register metric rows, and print a redacted summary.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        summary = await register_model_eval_results(
            model_id=args.model_id,
            eval_dataset_version_id=args.eval_dataset_version_id,
            metrics=_parse_metric_pairs(args.metric),
            subgroup_key=args.subgroup_key,
            failure_bucket=args.failure_bucket,
        )
    except (InvalidOperation, RetrainingSecurityError, ValueError) as exc:
        summary = _error_summary(error=exc)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 1

    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


async def register_model_eval_results(
    *,
    model_id: UUID,
    eval_dataset_version_id: UUID,
    metrics: dict[str, Decimal],
    subgroup_key: str | None = None,
    failure_bucket: str | None = None,
) -> dict[str, object]:
    """Persist sanitized evaluation metric rows for one model.

    Args:
        model_id: Model registry row being evaluated.
        eval_dataset_version_id: Dataset version used for evaluation.
        metrics: Metric name to nonnegative Decimal value mapping.
        subgroup_key: Optional stable subgroup key.
        failure_bucket: Optional stable failure bucket key.

    Returns:
        Sanitized registration summary.

    Raises:
        RetrainingSecurityError: If metric names, values, or optional codes are unsafe.
        ValueError: If the model row is missing or no metrics are supplied.
    """
    _validate_metrics(metrics)
    _validate_optional_code(subgroup_key, "subgroup_key")
    _validate_optional_code(failure_bucket, "failure_bucket")

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        model = await session.get(ModelRegistryEntry, model_id)
        if model is None:
            raise ValueError("Model registry entry was not found.")
        rows = [
            ModelEvalResult(
                id=uuid4(),
                model_id=model_id,
                eval_dataset_version_id=eval_dataset_version_id,
                metric_name=metric_name,
                metric_value=metric_value,
                subgroup_key=subgroup_key,
                failure_bucket=failure_bucket,
            )
            for metric_name, metric_value in sorted(metrics.items())
        ]
        for row in rows:
            session.add(row)
        await session.commit()

    return _success_summary(
        model_id=model_id,
        eval_dataset_version_id=eval_dataset_version_id,
        row_count=len(rows),
        subgroup_key=subgroup_key,
        failure_bucket=failure_bucket,
    )


def _parse_metric_pairs(raw_metrics: list[list[str]]) -> dict[str, Decimal]:
    """Parse repeated CLI metric pairs into a validated mapping.

    Args:
        raw_metrics: Repeated ``[name, value]`` argument pairs.

    Returns:
        Metric mapping.

    Raises:
        ValueError: If no metric exists or a metric name is repeated.
        InvalidOperation: If a metric value is not Decimal-compatible.
    """
    if not raw_metrics:
        raise ValueError("At least one metric is required.")
    metrics: dict[str, Decimal] = {}
    for metric_name, raw_value in raw_metrics:
        if metric_name in metrics:
            raise ValueError("Duplicate metric names are not allowed.")
        metrics[metric_name] = Decimal(raw_value)
    _validate_metrics(metrics)
    return metrics


def _validate_metrics(metrics: dict[str, Decimal]) -> None:
    """Validate metric names and values.

    Args:
        metrics: Metric mapping.

    Raises:
        RetrainingSecurityError: If a name or value is unsafe.
        ValueError: If no metric is supplied.
    """
    if not metrics:
        raise ValueError("At least one metric is required.")
    for metric_name, metric_value in metrics.items():
        _validate_metric_name(metric_name)
        if not math.isfinite(float(metric_value)) or metric_value < 0:
            raise RetrainingSecurityError("Metric values must be finite and nonnegative.")


def _validate_metric_name(metric_name: str) -> None:
    """Validate a stable metric name.

    Args:
        metric_name: Candidate metric name.

    Raises:
        RetrainingSecurityError: If the name is unsafe.
    """
    if not METRIC_NAME_PATTERN.fullmatch(metric_name):
        raise RetrainingSecurityError("Metric name must use stable safe characters.")
    _reject_path_url_or_secret(metric_name, "Metric name")


def _validate_optional_code(value: str | None, label: str) -> None:
    """Validate optional subgroup/failure bucket codes.

    Args:
        value: Optional stable code.
        label: Error label.

    Raises:
        RetrainingSecurityError: If the code is unsafe.
    """
    if value is None:
        return
    if not STABLE_CODE_PATTERN.fullmatch(value):
        raise RetrainingSecurityError(f"{label} must use stable safe characters.")
    _reject_path_url_or_secret(value, label)


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
        raise RetrainingSecurityError(f"{label} must not be a path or URL.")
    if any(marker in folded for marker in SECRET_LIKE_MARKERS):
        raise RetrainingSecurityError(f"{label} contains a secret-like value.")


def _success_summary(
    *,
    model_id: UUID,
    eval_dataset_version_id: UUID,
    row_count: int,
    subgroup_key: str | None,
    failure_bucket: str | None,
) -> dict[str, object]:
    """Return a redacted success summary.

    Args:
        model_id: Evaluated model id.
        eval_dataset_version_id: Eval dataset version id.
        row_count: Number of metric rows stored.
        subgroup_key: Optional subgroup key.
        failure_bucket: Optional failure bucket.

    Returns:
        Summary without metric names, values, raw payloads, or paths.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "ok",
        "model_id": str(model_id),
        "eval_dataset_version_id": str(eval_dataset_version_id),
        "eval_result_count": row_count,
        "subgroup_key_present": subgroup_key is not None,
        "failure_bucket_present": failure_bucket is not None,
        "metric_names_printed": False,
        "metric_values_printed": False,
        "raw_eval_payload_stored": False,
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
        "metric_names_printed": False,
        "metric_values_printed": False,
        "raw_eval_payload_stored": False,
    }


def main() -> None:
    """Run the CLI entrypoint."""
    raise SystemExit(asyncio.run(run_cli()))


if __name__ == "__main__":
    main()
