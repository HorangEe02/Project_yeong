"""Tests for trusted PaddleOCR eval metric extraction."""

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

eval_runner = importlib.import_module("scripts.run_paddleocr_eval_from_finetune_plan")


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


def _plan(
    *, task: str = "recognition", save_model_ref: str = "models/paddleocr/run"
) -> dict[str, Any]:
    """Build a fine-tune plan fixture.

    Args:
        task: PaddleOCR task.
        save_model_ref: Private model output ref.

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
            "save_model_ref": save_model_ref,
        },
        "hyperparams": {
            "epochs": 3,
            "learning_rate": 0.0001,
            "batch_size_per_card": 8,
            "gpus": "0",
        },
    }


def _finetune_execution(*, process_status: str = "succeeded") -> dict[str, Any]:
    """Build a fine-tune execution result fixture.

    Args:
        process_status: Training process status.

    Returns:
        Execution result payload.
    """
    return {
        "schema_version": "paddleocr-finetune-execution-result-v1",
        "process_status": process_status,
        "metrics_json_required_for_registration": process_status == "succeeded",
        "stdout_raw_stored": False,
        "stderr_raw_stored": False,
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


def test_dry_run_builds_eval_command_without_execution_or_path_leak(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify dry-run validates eval preconditions without training logs."""
    plan_path = _write_json(tmp_path / "plan.json", _plan())
    paddleocr_root = _write_fake_paddleocr_root(tmp_path / "PaddleOCR")
    output_path = tmp_path / "eval-result.json"

    exit_code = eval_runner.run_cli(
        [
            "--plan",
            str(plan_path),
            "--paddleocr-root",
            str(paddleocr_root),
            "--output",
            str(output_path),
        ]
    )

    stdout = capsys.readouterr().out
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert result["process_status"] == "validated_not_executed"
    assert result["eval_execution_performed"] is False
    assert result["metrics_json_ready_for_registration"] is False
    assert str(tmp_path) not in stdout
    assert "models/paddleocr" not in stdout
    assert "configs/rec" not in stdout


def test_execute_recognition_eval_writes_flat_verified_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify recognition eval parses acc and norm_edit_dis only."""
    plan_path = _write_json(tmp_path / "plan.json", _plan(task="recognition"))
    execution_path = _write_json(tmp_path / "train.json", _finetune_execution())
    paddleocr_root = _write_fake_paddleocr_root(tmp_path / "PaddleOCR")
    output_path = tmp_path / "eval-result.json"
    metrics_output = tmp_path / "metrics.json"
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
            Fake completed process with metric text.
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
                "ppocr INFO: metric eval ***************\n"
                "{'acc': 0.91, 'norm_edit_dis': 0.87, 'fps': 12.3}\n"
                "/private/tmp/raw-log-should-not-store\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(eval_runner.subprocess, "run", fake_run)

    exit_code = eval_runner.run_cli(
        [
            "--plan",
            str(plan_path),
            "--finetune-execution",
            str(execution_path),
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
    assert captured["capture_output"] is True
    assert captured["text"] is True
    assert captured["timeout"] == 10
    assert captured["check"] is False
    assert result["process_status"] == "metrics_verified"
    assert result["metric_key_count"] == 2
    assert result["metrics_json_ready_for_registration"] is True
    assert metrics == {"acc": 0.91, "norm_edit_dis": 0.87}
    assert "/private/tmp/raw-log-should-not-store" not in json.dumps(result, ensure_ascii=False)
    assert "/private/tmp/raw-log-should-not-store" not in stdout
    assert "acc" not in stdout
    assert "0.91" not in stdout
    assert str(tmp_path) not in stdout


def test_execute_detection_eval_requires_precision_recall_hmean(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify detection eval extracts the official detection metrics."""
    plan_path = _write_json(tmp_path / "plan.json", _plan(task="detection"))
    execution_path = _write_json(tmp_path / "train.json", _finetune_execution())
    paddleocr_root = _write_fake_paddleocr_root(tmp_path / "PaddleOCR")

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
            stdout="{'precision': 0.8, 'recall': 0.75, 'hmean': 0.774}\n",
            stderr="",
        )

    monkeypatch.setattr(eval_runner.subprocess, "run", fake_run)

    result, summary, metrics = eval_runner.run_paddleocr_eval_from_finetune_plan(
        plan_path=plan_path,
        finetune_execution_path=execution_path,
        paddleocr_root=paddleocr_root,
        execute=True,
        timeout_seconds=10,
        metrics_output_path=tmp_path / "metrics.json",
    )

    assert result["task"] == "detection"
    assert result["process_status"] == "metrics_verified"
    assert summary["metric_key_count"] == 3
    assert metrics == {"precision": 0.8, "recall": 0.75, "hmean": 0.774}


def test_successful_eval_without_required_metrics_is_not_registration_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify return code 0 is insufficient without task-required metrics."""
    plan_path = _write_json(tmp_path / "plan.json", _plan(task="recognition"))
    execution_path = _write_json(tmp_path / "train.json", _finetune_execution())
    paddleocr_root = _write_fake_paddleocr_root(tmp_path / "PaddleOCR")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Return logs without required metric keys.

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
            stdout="{'fps': 12.0}\n",
            stderr="",
        )

    monkeypatch.setattr(eval_runner.subprocess, "run", fake_run)

    result, _, metrics = eval_runner.run_paddleocr_eval_from_finetune_plan(
        plan_path=plan_path,
        finetune_execution_path=execution_path,
        paddleocr_root=paddleocr_root,
        execute=True,
        timeout_seconds=10,
        metrics_output_path=tmp_path / "metrics.json",
    )

    assert result["process_status"] == "metrics_missing"
    assert result["metrics_json_ready_for_registration"] is False
    assert metrics is None


def test_timeout_redacts_partial_eval_logs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify timeout partial logs are summarized, not stored raw."""
    plan_path = _write_json(tmp_path / "plan.json", _plan())
    execution_path = _write_json(tmp_path / "train.json", _finetune_execution())
    paddleocr_root = _write_fake_paddleocr_root(tmp_path / "PaddleOCR")

    def fake_timeout(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Raise a timeout with raw partial output.

        Args:
            args: Positional subprocess arguments.
            kwargs: Keyword subprocess arguments.

        Returns:
            Never returns.

        Raises:
            subprocess.TimeoutExpired: Always raised.
        """
        _ = (args, kwargs)
        raise subprocess.TimeoutExpired(
            cmd=["python3"],
            timeout=1,
            output="partial\n/private/tmp/should-not-store\n",
            stderr="traceback detail\n",
        )

    monkeypatch.setattr(eval_runner.subprocess, "run", fake_timeout)

    result, summary, metrics = eval_runner.run_paddleocr_eval_from_finetune_plan(
        plan_path=plan_path,
        finetune_execution_path=execution_path,
        paddleocr_root=paddleocr_root,
        execute=True,
        timeout_seconds=1,
        metrics_output_path=tmp_path / "metrics.json",
    )

    serialized = json.dumps({"result": result, "summary": summary}, ensure_ascii=False)
    assert result["process_status"] == "timeout"
    assert result["stdout_sha256"]
    assert result["metrics_json_ready_for_registration"] is False
    assert metrics is None
    assert "/private/tmp/should-not-store" not in serialized
    assert "traceback detail" not in serialized
    assert str(tmp_path) not in serialized


def test_execute_rejects_failed_finetune_execution_result(tmp_path: Path) -> None:
    """Verify eval cannot run when training did not succeed."""
    plan_path = _write_json(tmp_path / "plan.json", _plan())
    execution_path = _write_json(
        tmp_path / "train.json", _finetune_execution(process_status="failed")
    )
    paddleocr_root = _write_fake_paddleocr_root(tmp_path / "PaddleOCR")

    with pytest.raises(
        eval_runner.PaddleOCREvalExecutionError,
        match="must succeed",
    ):
        eval_runner.run_paddleocr_eval_from_finetune_plan(
            plan_path=plan_path,
            finetune_execution_path=execution_path,
            paddleocr_root=paddleocr_root,
            execute=True,
            timeout_seconds=10,
            metrics_output_path=tmp_path / "metrics.json",
        )


def test_cli_error_summary_is_redacted_for_unsafe_plan(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI errors do not print local paths or unsafe refs."""
    plan_path = _write_json(
        tmp_path / "plan.json",
        _plan(save_model_ref="/private/tmp/model"),
    )
    output_path = tmp_path / "eval-result.json"

    exit_code = eval_runner.run_cli(
        [
            "--plan",
            str(plan_path),
            "--paddleocr-root",
            str(tmp_path / "missing"),
            "--output",
            str(output_path),
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == 1
    assert "PaddleOCREvalExecutionError" in stdout
    assert str(tmp_path) not in stdout
    assert "/private/tmp/model" not in stdout
    assert "models/paddleocr" not in stdout
