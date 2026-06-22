"""Register a sanitized model registry candidate for operator workflows."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from uuid import UUID, uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.db.session import get_sessionmaker  # noqa: E402
from src.learning.retraining import RetrainingSecurityError  # noqa: E402
from src.models.db.retraining import ModelRegistryEntry, ModelTrainingRun  # noqa: E402

SUMMARY_SCHEMA_VERSION = "model-candidate-registration-summary-v1"
TASK_TYPE_CHOICES = (
    "supplement_roi_detection",
    "supplement_ocr_detection",
    "supplement_ocr_recognition",
    "food_detection",
    "food_classification",
    "image_embedding",
)
MODEL_FAMILY_TASK_TYPES = {
    "yolo": frozenset({"supplement_roi_detection", "food_detection"}),
    "paddleocr_det": frozenset({"supplement_ocr_detection"}),
    "paddleocr_rec": frozenset({"supplement_ocr_recognition"}),
    "food_classifier": frozenset({"food_classification"}),
    "image_embedding": frozenset({"image_embedding"}),
}
MODEL_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,120}$")
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
    parser.add_argument("--training-run-id", required=True, type=UUID)
    parser.add_argument("--task-type", required=True, choices=TASK_TYPE_CHOICES)
    parser.add_argument("--model-version", required=True)
    parser.add_argument(
        "--artifact-ref",
        default=None,
        help="Optional private model artifact ref; defaults to the training run artifact ref.",
    )
    return parser.parse_args(argv)


async def run_cli(argv: list[str] | None = None) -> int:
    """Parse arguments, register the candidate, and print a redacted summary.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        summary = await register_model_candidate(
            training_run_id=args.training_run_id,
            task_type=args.task_type,
            model_version=args.model_version,
            artifact_ref=args.artifact_ref,
        )
    except (RetrainingSecurityError, ValueError) as exc:
        summary = _error_summary(error=exc)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 1

    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


async def register_model_candidate(
    *,
    training_run_id: UUID,
    task_type: str,
    model_version: str,
    artifact_ref: str | None,
) -> dict[str, object]:
    """Persist one candidate model registry entry.

    Args:
        training_run_id: Successful training run that produced the candidate.
        task_type: Deployable task type aligned with the training run family.
        model_version: Safe operator-assigned model version label.
        artifact_ref: Optional private model artifact reference.

    Returns:
        Sanitized registration summary.

    Raises:
        RetrainingSecurityError: If model version or artifact ref is unsafe.
        ValueError: If the training run is missing, incomplete, or task-incompatible.
    """
    _validate_model_version(model_version)
    _validate_artifact_ref(artifact_ref)

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        training_run = await session.get(ModelTrainingRun, training_run_id)
        if training_run is None:
            raise ValueError("Model training run was not found.")
        if training_run.status != "succeeded":
            raise ValueError("Model training run must be succeeded before candidate registration.")
        _validate_task_type_for_training_run(task_type=task_type, training_run=training_run)

        resolved_artifact_ref = artifact_ref or training_run.artifact_ref
        _validate_artifact_ref(resolved_artifact_ref)
        if resolved_artifact_ref is None:
            raise ValueError("A private artifact ref is required.")

        model = ModelRegistryEntry(
            id=uuid4(),
            task_type=task_type,
            model_version=model_version,
            training_run_id=training_run_id,
            artifact_ref=resolved_artifact_ref,
            deployment_status="candidate",
            metric_gate_snapshot={},
        )
        session.add(model)
        await session.commit()

    return _success_summary(model=model)


def _validate_task_type_for_training_run(
    *,
    task_type: str,
    training_run: ModelTrainingRun,
) -> None:
    """Verify the candidate task type matches the training family.

    Args:
        task_type: Candidate deployable task type.
        training_run: Source model training run.

    Raises:
        ValueError: If the model family or task type is unsupported.
    """
    allowed_task_types = MODEL_FAMILY_TASK_TYPES.get(training_run.model_family)
    if allowed_task_types is None:
        raise ValueError("Unsupported model family.")
    if task_type not in allowed_task_types:
        raise ValueError("Task type does not match model family.")


def _validate_model_version(model_version: str) -> None:
    """Validate a safe model version label.

    Args:
        model_version: Operator-assigned model version.

    Raises:
        RetrainingSecurityError: If the version is empty, path-like, URL-like, or secret-like.
    """
    if not MODEL_VERSION_PATTERN.fullmatch(model_version):
        raise RetrainingSecurityError("Model version must use safe tag characters.")
    _reject_path_url_or_secret(model_version, "Model version")


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


def _success_summary(*, model: ModelRegistryEntry) -> dict[str, object]:
    """Return a redacted success summary.

    Args:
        model: Persisted model registry row.

    Returns:
        Summary without artifact ref, operator hash, metrics, or paths.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "ok",
        "model_id": str(model.id),
        "training_run_id": str(model.training_run_id),
        "task_type": model.task_type,
        "model_version": model.model_version,
        "deployment_status": model.deployment_status,
        "artifact_ref_registered": True,
        "artifact_ref_printed": False,
        "metric_gate_empty": model.metric_gate_snapshot == {},
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
        "metric_gate_empty": True,
    }


def main() -> None:
    """Run the CLI entrypoint."""
    raise SystemExit(asyncio.run(run_cli()))


if __name__ == "__main__":
    main()
