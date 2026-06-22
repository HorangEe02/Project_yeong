"""Build a sanitized PaddleOCR fine-tuning run plan.

This operator script validates a materialized PaddleOCR dataset directory and
writes a private run-plan artifact that can be used before calling
``register_model_training_run.py``. It does not execute PaddleOCR training and
does not print labels, source refs, local paths, OCR provider payloads, or image
paths.

References:
    https://www.paddleocr.ai/v3.3.2/en/version2.x/ppocr/model_train/finetune.html
    https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppocr/blog/config.html
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.learning.retraining import RetrainingSecurityError  # noqa: E402

PLAN_SCHEMA_VERSION = "paddleocr-finetune-run-plan-v1"
SUMMARY_SCHEMA_VERSION = "paddleocr-finetune-run-plan-summary-v1"
TASK_CHOICES = ("detection", "recognition")
TASK_TO_MODEL_FAMILY = {
    "detection": "paddleocr_det",
    "recognition": "paddleocr_rec",
}
TASK_TO_LABEL_PREFIX = {
    "detection": ("det", "det_gt"),
    "recognition": ("rec", "rec_gt"),
}
SUPPORTED_SPLITS = ("train", "val", "test")
SECRET_LIKE_MARKERS = (
    "bearer ",
    "ngrok-free.dev",
    "sb_secret_",
    "service_role",
    "aws_secret_access_key",
    "-----begin",
)
SOURCE_DOC_URLS = (
    "https://www.paddleocr.ai/v3.3.2/en/version2.x/ppocr/model_train/finetune.html",
    "https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppocr/blog/config.html",
)
GPU_LIST_PATTERN = re.compile(r"^\d+(,\d+)*$")
LABEL_LINE_FIELD_COUNT = 2
DETECTION_BOX_POINT_COUNT = 4
MAX_EPOCHS = 1000
MAX_BATCH_SIZE_PER_CARD = 4096


class PaddleOCRFinetunePlanError(ValueError):
    """Raised when a PaddleOCR fine-tuning plan input is invalid."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", required=True, type=Path)
    parser.add_argument("--task", required=True, choices=TASK_CHOICES)
    parser.add_argument("--dataset-version-id", required=True, type=UUID)
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--config-ref", required=True)
    parser.add_argument("--pretrained-model-ref", required=True)
    parser.add_argument("--save-model-ref", required=True)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--learning-rate", type=float, default=0.0001)
    parser.add_argument("--batch-size-per-card", type=int, default=8)
    parser.add_argument("--gpus", default="0")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summary", type=Path)
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None) -> int:
    """Build the plan artifact and print a sanitized summary.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        plan, summary = build_paddleocr_finetune_run_plan(
            dataset_dir=args.dataset_dir,
            task=args.task,
            dataset_version_id=args.dataset_version_id,
            base_model=args.base_model,
            config_ref=args.config_ref,
            pretrained_model_ref=args.pretrained_model_ref,
            save_model_ref=args.save_model_ref,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            batch_size_per_card=args.batch_size_per_card,
            gpus=args.gpus,
        )
        _write_json(args.output, plan)
        if args.summary is not None:
            _write_json(args.summary, summary)
    except (PaddleOCRFinetunePlanError, RetrainingSecurityError, ValueError) as exc:
        summary = _error_summary(error=exc)
        if args.summary is not None:
            _write_json(args.summary, summary)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 1

    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def build_paddleocr_finetune_run_plan(
    *,
    dataset_dir: Path,
    task: str,
    dataset_version_id: UUID,
    base_model: str,
    config_ref: str,
    pretrained_model_ref: str,
    save_model_ref: str,
    epochs: int,
    learning_rate: float,
    batch_size_per_card: int,
    gpus: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build a sanitized PaddleOCR fine-tuning run plan.

    Args:
        dataset_dir: Materialized PaddleOCR dataset directory.
        task: PaddleOCR task, either detection or recognition.
        dataset_version_id: Dataset version that produced the materialized files.
        base_model: Sanitized base model tag used for model registry linkage.
        config_ref: Private relative PaddleOCR config reference.
        pretrained_model_ref: Private relative pre-trained model reference.
        save_model_ref: Private relative model output reference.
        epochs: Planned epoch count.
        learning_rate: Planned optimizer learning rate.
        batch_size_per_card: Planned single-card batch size.
        gpus: Comma-separated GPU ids for the official PaddleOCR launch command.

    Returns:
        Tuple of private plan artifact and sanitized operator summary.

    Raises:
        PaddleOCRFinetunePlanError: If dataset or hyperparameter inputs are invalid.
        RetrainingSecurityError: If refs or model tags contain unsafe data.
        ValueError: If enum-like inputs are unsupported.
    """
    if task not in TASK_CHOICES:
        raise ValueError("Unsupported PaddleOCR task.")
    _validate_private_ref(base_model, "base model")
    _validate_private_ref(config_ref, "config ref")
    _validate_private_ref(pretrained_model_ref, "pretrained model ref")
    _validate_private_ref(save_model_ref, "save model ref")
    _validate_hyperparams(
        epochs=epochs,
        learning_rate=learning_rate,
        batch_size_per_card=batch_size_per_card,
        gpus=gpus,
    )
    dataset_summary = _scan_materialized_dataset(dataset_dir=dataset_dir, task=task)
    model_family = TASK_TO_MODEL_FAMILY[task]
    hyperparams = {
        "epochs": epochs,
        "learning_rate": learning_rate,
        "batch_size_per_card": batch_size_per_card,
        "gpus": gpus,
    }
    plan = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "training_execution_performed": False,
        "dataset_version_id": str(dataset_version_id),
        "task": task,
        "model_family": model_family,
        "base_model": base_model,
        "dataset": dataset_summary,
        "paddleocr": {
            "config_ref": config_ref,
            "pretrained_model_ref": pretrained_model_ref,
            "save_model_ref": save_model_ref,
            "source_doc_urls": list(SOURCE_DOC_URLS),
        },
        "hyperparams": hyperparams,
        "suggested_command_tokens": _suggested_command_tokens(
            gpus=gpus,
            config_ref=config_ref,
            pretrained_model_ref=pretrained_model_ref,
            save_model_ref=save_model_ref,
            epochs=epochs,
            learning_rate=learning_rate,
            batch_size_per_card=batch_size_per_card,
        ),
        "register_model_training_run": {
            "model_family": model_family,
            "base_model": base_model,
            "dataset_version_id": str(dataset_version_id),
            "status_after_execution": "succeeded_or_failed_after_verified_training",
            "artifact_ref": save_model_ref,
        },
        "source_ref_printed": False,
        "source_path_printed": False,
        "label_text_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }
    summary = _success_summary(
        task=task,
        model_family=model_family,
        dataset_version_id=dataset_version_id,
        dataset_summary=dataset_summary,
        hyperparams=hyperparams,
    )
    return plan, summary


def _scan_materialized_dataset(*, dataset_dir: Path, task: str) -> dict[str, Any]:
    """Scan materialized PaddleOCR split label files.

    Args:
        dataset_dir: Materialized dataset directory.
        task: PaddleOCR task.

    Returns:
        Safe dataset summary with counts and label file refs only.

    Raises:
        PaddleOCRFinetunePlanError: If required labels or image refs are invalid.
    """
    if not dataset_dir.is_dir():
        raise PaddleOCRFinetunePlanError("Materialized dataset directory does not exist.")
    label_dir_name, label_prefix = TASK_TO_LABEL_PREFIX[task]
    split_counts: dict[str, int] = {}
    label_files: list[str] = []
    image_count = 0
    for split in SUPPORTED_SPLITS:
        relative_label_path = Path(label_dir_name) / f"{label_prefix}_{split}.txt"
        label_path = dataset_dir / relative_label_path
        if not label_path.exists():
            split_counts[split] = 0
            continue
        split_count = _scan_label_file(
            dataset_dir=dataset_dir,
            label_path=label_path,
            task=task,
        )
        split_counts[split] = split_count
        image_count += split_count
        label_files.append(relative_label_path.as_posix())
    if split_counts.get("train", 0) <= 0:
        raise PaddleOCRFinetunePlanError(
            "PaddleOCR training labels require at least one train row."
        )
    return {
        "task": task,
        "split_counts": split_counts,
        "image_count": image_count,
        "label_files": label_files,
        "dataset_root_printed": False,
        "image_paths_printed": False,
        "label_text_printed": False,
    }


def _scan_label_file(*, dataset_dir: Path, label_path: Path, task: str) -> int:
    """Validate one PaddleOCR split label file.

    Args:
        dataset_dir: Materialized dataset directory.
        label_path: Split label file.
        task: PaddleOCR task.

    Returns:
        Number of valid rows.

    Raises:
        PaddleOCRFinetunePlanError: If a row can corrupt training input.
    """
    row_count = 0
    for raw_line in label_path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        image_ref, label_payload = _split_label_line(raw_line)
        _validate_relative_image_ref(image_ref)
        if not (dataset_dir / image_ref).is_file():
            raise PaddleOCRFinetunePlanError("PaddleOCR label image ref does not resolve.")
        if task == "detection":
            _validate_detection_payload(label_payload)
        row_count += 1
    return row_count


def _split_label_line(raw_line: str) -> tuple[Path, str]:
    """Split a PaddleOCR label line into relative image ref and payload.

    Args:
        raw_line: One tab-separated PaddleOCR label row.

    Returns:
        Relative image reference and label payload.

    Raises:
        PaddleOCRFinetunePlanError: If the row is malformed.
    """
    parts = raw_line.split("\t", maxsplit=1)
    if len(parts) != LABEL_LINE_FIELD_COUNT or not parts[0].strip() or not parts[1].strip():
        raise PaddleOCRFinetunePlanError("PaddleOCR label rows must be tab-separated.")
    return Path(parts[0]), parts[1]


def _validate_relative_image_ref(image_ref: Path) -> None:
    """Validate one materialized relative image reference.

    Args:
        image_ref: Candidate image reference from a PaddleOCR label file.

    Raises:
        PaddleOCRFinetunePlanError: If the image ref is unsafe.
    """
    ref_text = image_ref.as_posix()
    if image_ref.is_absolute() or ".." in image_ref.parts or "://" in ref_text:
        raise PaddleOCRFinetunePlanError(
            "PaddleOCR label image refs must be private relative paths."
        )


def _validate_detection_payload(label_payload: str) -> None:
    """Validate PaddleOCR text detection JSON payload shape.

    Args:
        label_payload: JSON payload from one detection label row.

    Raises:
        PaddleOCRFinetunePlanError: If the payload is not a list of boxes.
    """
    try:
        parsed = json.loads(label_payload)
    except json.JSONDecodeError as exc:
        raise PaddleOCRFinetunePlanError("PaddleOCR detection labels must be JSON.") from exc
    if not isinstance(parsed, list) or not parsed:
        raise PaddleOCRFinetunePlanError("PaddleOCR detection labels must contain boxes.")
    for box in parsed:
        if not isinstance(box, dict):
            raise PaddleOCRFinetunePlanError("PaddleOCR detection boxes must be objects.")
        points = box.get("points")
        if not isinstance(points, list) or len(points) != DETECTION_BOX_POINT_COUNT:
            raise PaddleOCRFinetunePlanError("PaddleOCR detection boxes require four points.")


def _suggested_command_tokens(
    *,
    gpus: str,
    config_ref: str,
    pretrained_model_ref: str,
    save_model_ref: str,
    epochs: int,
    learning_rate: float,
    batch_size_per_card: int,
) -> list[str]:
    """Return official-style PaddleOCR training command tokens.

    Args:
        gpus: Comma-separated GPU ids.
        config_ref: Relative PaddleOCR config reference.
        pretrained_model_ref: Relative pre-trained model reference.
        save_model_ref: Relative model output reference.
        epochs: Epoch count.
        learning_rate: Learning rate.
        batch_size_per_card: Single-card batch size.

    Returns:
        Command token list using only sanitized relative refs.
    """
    return [
        "python3",
        "-m",
        "paddle.distributed.launch",
        "--gpus",
        gpus,
        "tools/train.py",
        "-c",
        config_ref,
        "-o",
        f"Global.pretrained_model={pretrained_model_ref}",
        f"Global.save_model_dir={save_model_ref}",
        f"Global.epoch_num={epochs}",
        f"Optimizer.lr.learning_rate={learning_rate}",
        f"Train.loader.batch_size_per_card={batch_size_per_card}",
    ]


def _validate_hyperparams(
    *,
    epochs: int,
    learning_rate: float,
    batch_size_per_card: int,
    gpus: str,
) -> None:
    """Validate bounded PaddleOCR fine-tune hyperparameters.

    Args:
        epochs: Epoch count.
        learning_rate: Learning rate.
        batch_size_per_card: Single-card batch size.
        gpus: Comma-separated GPU ids.

    Raises:
        PaddleOCRFinetunePlanError: If a hyperparameter is out of bounds.
    """
    if epochs <= 0 or epochs > MAX_EPOCHS:
        raise PaddleOCRFinetunePlanError("PaddleOCR epochs must be in 1..1000.")
    if learning_rate <= 0 or learning_rate > 1:
        raise PaddleOCRFinetunePlanError("PaddleOCR learning rate must be in (0, 1].")
    if batch_size_per_card <= 0 or batch_size_per_card > MAX_BATCH_SIZE_PER_CARD:
        raise PaddleOCRFinetunePlanError("PaddleOCR batch size must be in 1..4096.")
    if not GPU_LIST_PATTERN.fullmatch(gpus):
        raise PaddleOCRFinetunePlanError("PaddleOCR gpus must be a comma-separated id list.")


def _validate_private_ref(value: str, label: str) -> None:
    """Reject URL, absolute path, traversal, and secret-like refs.

    Args:
        value: Candidate reference.
        label: Error label.

    Raises:
        RetrainingSecurityError: If the reference is unsafe.
    """
    if not value.strip():
        raise RetrainingSecurityError(f"{label} cannot be empty.")
    folded = value.casefold()
    if "://" in value or value.startswith("/") or ".." in Path(value).parts:
        raise RetrainingSecurityError(f"{label} must be a private relative reference.")
    if any(marker in folded for marker in SECRET_LIKE_MARKERS):
        raise RetrainingSecurityError(f"{label} contains a secret-like value.")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON object to disk.

    Args:
        path: Destination path.
        payload: JSON payload.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _success_summary(
    *,
    task: str,
    model_family: str,
    dataset_version_id: UUID,
    dataset_summary: dict[str, Any],
    hyperparams: dict[str, Any],
) -> dict[str, Any]:
    """Return a redacted success summary.

    Args:
        task: PaddleOCR task.
        model_family: Model family key.
        dataset_version_id: Dataset version identifier.
        dataset_summary: Safe dataset counts.
        hyperparams: Sanitized hyperparameters.

    Returns:
        Summary without paths, label text, or private refs.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "ok",
        "task": task,
        "model_family": model_family,
        "dataset_version_id": str(dataset_version_id),
        "split_counts": dataset_summary["split_counts"],
        "image_count": dataset_summary["image_count"],
        "hyperparam_key_count": len(hyperparams),
        "training_execution_performed": False,
        "dataset_root_printed": False,
        "image_paths_printed": False,
        "label_text_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


def _error_summary(*, error: BaseException) -> dict[str, Any]:
    """Return a redacted error summary.

    Args:
        error: Raised exception.

    Returns:
        Error summary without input paths or secret-bearing values.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "error",
        "error_type": type(error).__name__,
        "training_execution_performed": False,
        "dataset_root_printed": False,
        "image_paths_printed": False,
        "label_text_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def main() -> None:
    """Run the CLI entrypoint."""
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
