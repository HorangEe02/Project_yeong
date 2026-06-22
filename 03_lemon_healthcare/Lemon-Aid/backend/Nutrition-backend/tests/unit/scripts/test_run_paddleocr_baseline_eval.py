"""Tests for trusted PaddleOCR baseline eval metric extraction."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

baseline_eval = importlib.import_module("scripts.run_paddleocr_baseline_eval")


def _write_fake_paddleocr_root(root: Path) -> Path:
    """Write a minimal PaddleOCR checkout fixture.

    Args:
        root: Destination root.

    Returns:
        Root path.
    """
    eval_path = root / "tools" / "eval.py"
    eval_path.parent.mkdir(parents=True, exist_ok=True)
    eval_path.write_text("print('eval')\n", encoding="utf-8")
    return root


def _plan(*, task: str = "recognition") -> dict[str, Any]:
    """Build a fine-tune plan fixture.

    Args:
        task: PaddleOCR task.

    Returns:
        Plan payload.
    """
    model_family = "paddleocr_rec" if task == "recognition" else "paddleocr_det"
    base_model = "PP-OCRv5-rec" if task == "recognition" else "PP-OCRv5-det"
    config_ref = (
        "configs/rec/supplement_rec.yml"
        if task == "recognition"
        else "configs/det/supplement_det.yml"
    )
    return {
        "schema_version": "paddleocr-finetune-run-plan-v1",
        "training_execution_performed": False,
        "dataset_version_id": str(uuid4()),
        "task": task,
        "model_family": model_family,
        "base_model": base_model,
        "paddleocr": {
            "config_ref": config_ref,
            "pretrained_model_ref": "pretrain_models/ppocr/best_accuracy",
            "save_model_ref": "models/paddleocr/fine-tuned",
        },
        "hyperparams": {
            "epochs": 3,
            "learning_rate": 0.0001,
            "batch_size_per_card": 8,
            "gpus": "0",
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    """Write a JSON fixture.

    Args:
        path: Destination path.
        payload: JSON payload.

    Returns:
        Written path.
    """
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_dry_run_validates_baseline_without_execution_or_path_leak(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify dry-run validates baseline eval preconditions without raw refs."""
    plan_path = _write_json(tmp_path / "plan.json", _plan())
    paddleocr_root = _write_fake_paddleocr_root(tmp_path / "PaddleOCR")
    output_path = tmp_path / "baseline-result.json"

    exit_code = baseline_eval.run_cli(
        [
            "--plan",
            str(plan_path),
            "--baseline-checkpoint-ref",
            "models/baseline/rec/best_accuracy",
            "--paddleocr-root",
            str(paddleocr_root),
            "--output",
            str(output_path),
        ]
    )

    stdout = capsys.readouterr().out
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert result["schema_version"] == "paddleocr-baseline-eval-result-v1"
    assert result["process_status"] == "validated_not_executed"
    assert result["metrics_json_ready_for_comparison"] is False
    assert str(tmp_path) not in stdout
    assert "models/baseline" not in stdout
    assert "configs/rec" not in stdout


def test_execute_recognition_baseline_writes_flat_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify recognition baseline eval parses only required metrics."""
    plan_path = _write_json(tmp_path / "plan.json", _plan(task="recognition"))
    paddleocr_root = _write_fake_paddleocr_root(tmp_path / "PaddleOCR")
    output_path = tmp_path / "baseline-result.json"
    metrics_output = tmp_path / "baseline-metrics.json"
    captured: dict[str, Any] = {}

    def fake_run(
        tokens: list[str],
        *,
        cwd: Path,
        capture_output: bool,
        text: bool,
        timeout: int,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        """Return fake recognition metric logs.

        Args:
            tokens: Eval command tokens.
            cwd: Subprocess working directory.
            capture_output: Whether output is captured.
            text: Whether text mode is enabled.
            timeout: Timeout seconds.
            check: Whether subprocess should raise on nonzero exit.

        Returns:
            Fake completed process.
        """
        captured.update(
            {
                "tokens": tokens,
                "cwd": cwd,
                "capture_output": capture_output,
                "text": text,
                "timeout": timeout,
                "check": check,
            }
        )
        return subprocess.CompletedProcess(
            args=tokens,
            returncode=0,
            stdout=(
                "ppocr INFO: baseline metric\n"
                "{'acc': 0.89, 'norm_edit_dis': 0.84, 'fps': 10.1}\n"
                "/private/tmp/raw-log-should-not-store\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(baseline_eval.subprocess, "run", fake_run)

    exit_code = baseline_eval.run_cli(
        [
            "--plan",
            str(plan_path),
            "--baseline-checkpoint-ref",
            "models/baseline/rec/best_accuracy",
            "--paddleocr-root",
            str(paddleocr_root),
            "--output",
            str(output_path),
            "--metrics-output",
            str(metrics_output),
            "--execute",
            "--timeout-seconds",
            "10",
        ]
    )

    stdout = capsys.readouterr().out
    result = json.loads(output_path.read_text(encoding="utf-8"))
    metrics = json.loads(metrics_output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert captured["cwd"] == paddleocr_root
    assert "tools/eval.py" in captured["tokens"]
    assert "tools/train.py" not in captured["tokens"]
    assert "Global.checkpoints=models/baseline/rec/best_accuracy" in captured["tokens"]
    assert captured["capture_output"] is True
    assert captured["text"] is True
    assert captured["timeout"] == 10
    assert captured["check"] is False
    assert result["process_status"] == "metrics_verified"
    assert result["metric_key_count"] == 2
    assert result["metrics_json_ready_for_comparison"] is True
    assert metrics == {"acc": 0.89, "norm_edit_dis": 0.84}
    assert "/private/tmp/raw-log-should-not-store" not in json.dumps(result, ensure_ascii=False)
    assert "/private/tmp/raw-log-should-not-store" not in stdout
    assert "acc" not in stdout
    assert "0.89" not in stdout
    assert str(tmp_path) not in stdout


def test_execute_detection_baseline_requires_precision_recall_hmean(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify detection baseline eval extracts the required detection metrics."""
    plan_path = _write_json(tmp_path / "plan.json", _plan(task="detection"))
    paddleocr_root = _write_fake_paddleocr_root(tmp_path / "PaddleOCR")
    output_path = tmp_path / "baseline-result.json"
    metrics_output = tmp_path / "baseline-metrics.json"

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Return fake detection metrics.

        Args:
            args: Positional subprocess arguments.
            kwargs: Keyword subprocess arguments.

        Returns:
            Fake completed process.
        """
        _ = (args, kwargs)
        return subprocess.CompletedProcess(
            args=["python3"],
            returncode=0,
            stdout="{'precision': 0.78, 'recall': 0.74, 'hmean': 0.759}\n",
            stderr="",
        )

    monkeypatch.setattr(baseline_eval.subprocess, "run", fake_run)

    exit_code = baseline_eval.run_cli(
        [
            "--plan",
            str(plan_path),
            "--baseline-checkpoint-ref",
            "models/baseline/det/best_accuracy",
            "--paddleocr-root",
            str(paddleocr_root),
            "--output",
            str(output_path),
            "--metrics-output",
            str(metrics_output),
            "--execute",
        ]
    )

    result = json.loads(output_path.read_text(encoding="utf-8"))
    metrics = json.loads(metrics_output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert result["process_status"] == "metrics_verified"
    assert metrics == {"precision": 0.78, "recall": 0.74, "hmean": 0.759}


def test_execute_baseline_without_metrics_output_fails_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify executed baseline eval must write a comparison-ready metric JSON."""
    plan_path = _write_json(tmp_path / "plan.json", _plan())
    paddleocr_root = _write_fake_paddleocr_root(tmp_path / "PaddleOCR")
    output_path = tmp_path / "baseline-result.json"

    exit_code = baseline_eval.run_cli(
        [
            "--plan",
            str(plan_path),
            "--baseline-checkpoint-ref",
            "models/baseline/rec/best_accuracy",
            "--paddleocr-root",
            str(paddleocr_root),
            "--output",
            str(output_path),
            "--execute",
        ]
    )

    stdout = capsys.readouterr().out
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert result["status"] == "error"
    assert "PaddleOCRBaselineEvalError" in stdout
    assert "models/baseline" not in stdout
    assert str(tmp_path) not in stdout


def test_successful_baseline_eval_without_required_metrics_is_not_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify return code success is not enough without task-required metrics."""
    plan_path = _write_json(tmp_path / "plan.json", _plan(task="recognition"))
    paddleocr_root = _write_fake_paddleocr_root(tmp_path / "PaddleOCR")
    output_path = tmp_path / "baseline-result.json"
    metrics_output = tmp_path / "baseline-metrics.json"

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Return fake logs without all required metrics.

        Args:
            args: Positional subprocess arguments.
            kwargs: Keyword subprocess arguments.

        Returns:
            Fake completed process.
        """
        _ = (args, kwargs)
        return subprocess.CompletedProcess(
            args=["python3"],
            returncode=0,
            stdout="{'acc': 0.89}\n",
            stderr="",
        )

    monkeypatch.setattr(baseline_eval.subprocess, "run", fake_run)

    exit_code = baseline_eval.run_cli(
        [
            "--plan",
            str(plan_path),
            "--baseline-checkpoint-ref",
            "models/baseline/rec/best_accuracy",
            "--paddleocr-root",
            str(paddleocr_root),
            "--output",
            str(output_path),
            "--metrics-output",
            str(metrics_output),
            "--execute",
        ]
    )

    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert result["process_status"] == "metrics_missing"
    assert result["metrics_json_ready_for_comparison"] is False
    assert not metrics_output.exists()


def test_baseline_eval_rejects_unsafe_checkpoint_ref(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify baseline checkpoint refs cannot be paths, URLs, or traversal."""
    plan_path = _write_json(tmp_path / "plan.json", _plan())
    paddleocr_root = _write_fake_paddleocr_root(tmp_path / "PaddleOCR")
    output_path = tmp_path / "baseline-result.json"

    exit_code = baseline_eval.run_cli(
        [
            "--plan",
            str(plan_path),
            "--baseline-checkpoint-ref",
            "../models/baseline/rec/best_accuracy",
            "--paddleocr-root",
            str(paddleocr_root),
            "--output",
            str(output_path),
        ]
    )

    stdout = capsys.readouterr().out
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert result["status"] == "error"
    assert "../models" not in stdout
    assert str(tmp_path) not in stdout
