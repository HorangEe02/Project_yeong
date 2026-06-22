"""Tests for PaddleOCR fine-tuning run plan generation."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from src.learning.retraining import RetrainingSecurityError

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

planner = importlib.import_module("scripts.build_paddleocr_finetune_run_plan")


def _write_file(path: Path, payload: bytes = b"image") -> None:
    """Write a tiny fixture file.

    Args:
        path: Destination path.
        payload: File payload.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _write_recognition_dataset(dataset_dir: Path) -> None:
    """Write a materialized PaddleOCR recognition dataset fixture.

    Args:
        dataset_dir: Dataset root.
    """
    _write_file(dataset_dir / "rec" / "train" / "word.jpg")
    (dataset_dir / "rec").mkdir(parents=True, exist_ok=True)
    (dataset_dir / "rec" / "rec_gt_train.txt").write_text(
        "rec/train/word.jpg\tUbiquinol 200 mg\n",
        encoding="utf-8",
    )


def _write_detection_dataset(dataset_dir: Path) -> None:
    """Write a materialized PaddleOCR detection dataset fixture.

    Args:
        dataset_dir: Dataset root.
    """
    _write_file(dataset_dir / "det" / "images" / "train" / "label.jpg")
    annotation = json.dumps(
        [{"transcription": "text", "points": [[0, 0], [10, 0], [10, 10], [0, 10]]}],
        ensure_ascii=False,
    )
    (dataset_dir / "det").mkdir(parents=True, exist_ok=True)
    (dataset_dir / "det" / "det_gt_train.txt").write_text(
        f"det/images/train/label.jpg\t{annotation}\n",
        encoding="utf-8",
    )


def _build_plan(dataset_dir: Path, *, task: str) -> tuple[dict[str, object], dict[str, object]]:
    """Build a test plan with safe relative refs.

    Args:
        dataset_dir: Dataset root.
        task: PaddleOCR task.

    Returns:
        Plan and summary.
    """
    return planner.build_paddleocr_finetune_run_plan(
        dataset_dir=dataset_dir,
        task=task,
        dataset_version_id=uuid4(),
        base_model="PP-OCRv5-rec" if task == "recognition" else "PP-OCRv5-det",
        config_ref=(
            "configs/rec/supplement_rec.yml"
            if task == "recognition"
            else "configs/det/supplement_det.yml"
        ),
        pretrained_model_ref="pretrain_models/ppocr/best_accuracy",
        save_model_ref="models/paddleocr/supplement-labels",
        epochs=3,
        learning_rate=0.0001,
        batch_size_per_card=8,
        gpus="0",
    )


def test_build_recognition_plan_without_label_or_path_leak(tmp_path: Path) -> None:
    """Verify recognition plan stores counts and safe refs, not label text."""
    dataset_dir = tmp_path / "paddleocr"
    _write_recognition_dataset(dataset_dir)

    plan, summary = _build_plan(dataset_dir, task="recognition")

    assert plan["schema_version"] == "paddleocr-finetune-run-plan-v1"
    assert plan["model_family"] == "paddleocr_rec"
    assert plan["training_execution_performed"] is False
    assert summary["split_counts"] == {"train": 1, "val": 0, "test": 0}
    serialized = json.dumps({"plan": plan, "summary": summary}, ensure_ascii=False)
    assert "Ubiquinol" not in serialized
    assert str(tmp_path) not in serialized
    assert plan["raw_ocr_text_stored"] is False
    assert plan["raw_provider_payload_stored"] is False


def test_build_detection_plan_validates_paddleocr_json_labels(tmp_path: Path) -> None:
    """Verify detection plan accepts valid PaddleOCR box JSON labels."""
    dataset_dir = tmp_path / "paddleocr"
    _write_detection_dataset(dataset_dir)

    plan, summary = _build_plan(dataset_dir, task="detection")

    assert plan["model_family"] == "paddleocr_det"
    assert summary["image_count"] == 1
    assert "Optimizer.lr.learning_rate=0.0001" in plan["suggested_command_tokens"]


def test_plan_rejects_missing_train_rows(tmp_path: Path) -> None:
    """Verify fine-tuning cannot be planned without train rows."""
    dataset_dir = tmp_path / "paddleocr"
    (dataset_dir / "rec").mkdir(parents=True)
    (dataset_dir / "rec" / "rec_gt_val.txt").write_text("", encoding="utf-8")

    with pytest.raises(
        planner.PaddleOCRFinetunePlanError,
        match="at least one train row",
    ):
        _build_plan(dataset_dir, task="recognition")


def test_plan_rejects_unsafe_image_refs(tmp_path: Path) -> None:
    """Verify label files cannot contain absolute or traversing image refs."""
    dataset_dir = tmp_path / "paddleocr"
    (dataset_dir / "rec").mkdir(parents=True)
    (dataset_dir / "rec" / "rec_gt_train.txt").write_text(
        "/private/tmp/word.jpg\tVitamin C\n",
        encoding="utf-8",
    )

    with pytest.raises(planner.PaddleOCRFinetunePlanError, match="relative paths"):
        _build_plan(dataset_dir, task="recognition")


def test_plan_rejects_secret_like_refs(tmp_path: Path) -> None:
    """Verify config and artifact refs cannot carry secret-like values."""
    dataset_dir = tmp_path / "paddleocr"
    _write_recognition_dataset(dataset_dir)

    with pytest.raises(RetrainingSecurityError, match="secret-like"):
        planner.build_paddleocr_finetune_run_plan(
            dataset_dir=dataset_dir,
            task="recognition",
            dataset_version_id=uuid4(),
            base_model="PP-OCRv5-rec",
            config_ref="configs/rec/supplement_rec.yml",
            pretrained_model_ref="pretrain_models/ppocr/best_accuracy",
            save_model_ref="models/service_role/supplement-labels",
            epochs=3,
            learning_rate=0.0001,
            batch_size_per_card=8,
            gpus="0",
        )


def test_cli_writes_plan_and_safe_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI writes plan while stdout remains aggregate-only."""
    dataset_dir = tmp_path / "paddleocr"
    output_path = tmp_path / "plan.json"
    summary_path = tmp_path / "summary.json"
    _write_recognition_dataset(dataset_dir)

    exit_code = planner.run_cli(
        [
            "--dataset-dir",
            str(dataset_dir),
            "--task",
            "recognition",
            "--dataset-version-id",
            str(uuid4()),
            "--base-model",
            "PP-OCRv5-rec",
            "--config-ref",
            "configs/rec/supplement_rec.yml",
            "--pretrained-model-ref",
            "pretrain_models/ppocr/best_accuracy",
            "--save-model-ref",
            "models/paddleocr/supplement-labels",
            "--output",
            str(output_path),
            "--summary",
            str(summary_path),
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == 0
    assert output_path.is_file()
    assert summary_path.is_file()
    assert "Ubiquinol" not in stdout
    assert str(tmp_path) not in stdout
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["training_execution_performed"] is False
