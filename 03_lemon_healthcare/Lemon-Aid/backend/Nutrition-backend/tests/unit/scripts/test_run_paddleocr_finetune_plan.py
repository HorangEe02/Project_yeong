"""Tests for trusted PaddleOCR fine-tune plan execution."""

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

runner = importlib.import_module("scripts.run_paddleocr_finetune_plan")


def _write_fake_paddleocr_root(root: Path) -> Path:
    """Write a minimal PaddleOCR checkout fixture.

    Args:
        root: Destination root.

    Returns:
        Root path.
    """
    train_path = root / "tools" / "train.py"
    train_path.parent.mkdir(parents=True, exist_ok=True)
    train_path.write_text("print('train')\n", encoding="utf-8")
    return root


def _plan(*, command_tokens: list[str] | None = None) -> dict[str, Any]:
    """Build a sanitized fine-tune run plan fixture.

    Args:
        command_tokens: Optional command tokens override.

    Returns:
        Plan payload.
    """
    return {
        "schema_version": "paddleocr-finetune-run-plan-v1",
        "training_execution_performed": False,
        "dataset_version_id": str(uuid4()),
        "task": "recognition",
        "model_family": "paddleocr_rec",
        "base_model": "PP-OCRv5-rec",
        "suggested_command_tokens": command_tokens
        or [
            "python3",
            "-m",
            "paddle.distributed.launch",
            "--gpus",
            "0",
            "tools/train.py",
            "-c",
            "configs/rec/supplement_rec.yml",
            "-o",
            "Global.pretrained_model=pretrain_models/ppocr/best_accuracy",
            "Global.save_model_dir=models/paddleocr/supplement-labels",
            "Global.epoch_num=3",
            "Optimizer.lr.learning_rate=0.0001",
            "Train.loader.batch_size_per_card=8",
        ],
        "paddleocr": {
            "config_ref": "configs/rec/supplement_rec.yml",
            "pretrained_model_ref": "pretrain_models/ppocr/best_accuracy",
            "save_model_ref": "models/paddleocr/supplement-labels",
        },
        "hyperparams": {
            "epochs": 3,
            "learning_rate": 0.0001,
            "batch_size_per_card": 8,
            "gpus": "0",
        },
    }


def _write_plan(path: Path, payload: dict[str, Any]) -> Path:
    """Write a plan fixture.

    Args:
        path: Destination path.
        payload: Plan payload.

    Returns:
        Plan path.
    """
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_dry_run_validates_plan_without_training_or_path_leak(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify dry-run validates the root and writes only redacted metadata."""
    plan_path = _write_plan(tmp_path / "plan.json", _plan())
    paddleocr_root = _write_fake_paddleocr_root(tmp_path / "PaddleOCR")
    output_path = tmp_path / "execution.json"

    exit_code = runner.run_cli(
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
    assert result["training_execution_performed"] is False
    assert result["command_printed"] is False
    assert str(tmp_path) not in stdout
    assert "models/paddleocr" not in stdout
    assert "configs/rec" not in stdout


def test_execute_hashes_logs_without_storing_raw_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify successful execution stores only log digests and line counts."""
    plan_path = _write_plan(tmp_path / "plan.json", _plan())
    paddleocr_root = _write_fake_paddleocr_root(tmp_path / "PaddleOCR")
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
        """Capture subprocess arguments while avoiding real training.

        Args:
            tokens: Command tokens.
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
            stdout="epoch 1\n/private/tmp/should-not-store\n",
            stderr="warning: should-not-store\n",
        )

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result, summary = runner.run_paddleocr_finetune_plan(
        plan_path=plan_path,
        paddleocr_root=paddleocr_root,
        output_path=tmp_path / "execution.json",
        execute=True,
        timeout_seconds=10,
    )

    assert captured["cwd"] == paddleocr_root
    assert "tools/train.py" in captured["tokens"]
    assert captured["capture_output"] is True
    assert captured["text"] is True
    assert captured["timeout"] == 10
    assert captured["check"] is False
    assert result["process_status"] == "succeeded"
    assert result["return_code"] == 0
    assert result["stdout_sha256"]
    assert result["stderr_sha256"]
    assert result["stdout_line_count"] == 2
    assert result["stderr_line_count"] == 1
    assert result["metrics_json_required_for_registration"] is True
    serialized = json.dumps({"result": result, "summary": summary}, ensure_ascii=False)
    assert "/private/tmp/should-not-store" not in serialized
    assert "warning: should-not-store" not in serialized
    assert "models/paddleocr" not in serialized
    assert str(tmp_path) not in serialized


def test_timeout_records_status_without_raw_partial_logs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify timeout status keeps only partial stream digests."""
    plan_path = _write_plan(tmp_path / "plan.json", _plan())
    paddleocr_root = _write_fake_paddleocr_root(tmp_path / "PaddleOCR")

    def fake_timeout(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Raise a fake timeout with raw partial output.

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
            stderr="timeout detail\n",
        )

    monkeypatch.setattr(runner.subprocess, "run", fake_timeout)

    result, summary = runner.run_paddleocr_finetune_plan(
        plan_path=plan_path,
        paddleocr_root=paddleocr_root,
        output_path=tmp_path / "execution.json",
        execute=True,
        timeout_seconds=1,
    )

    assert result["process_status"] == "timeout"
    assert result["return_code"] is None
    assert result["metrics_json_required_for_registration"] is False
    serialized = json.dumps({"result": result, "summary": summary}, ensure_ascii=False)
    assert "/private/tmp/should-not-store" not in serialized
    assert "timeout detail" not in serialized
    assert str(tmp_path) not in serialized


def test_rejects_unsafe_command_token(tmp_path: Path) -> None:
    """Verify command override refs cannot escape the trusted checkout."""
    plan_path = _write_plan(
        tmp_path / "plan.json",
        _plan(
            command_tokens=[
                "python3",
                "tools/train.py",
                "-o",
                "Global.save_model_dir=/private/tmp/model",
            ]
        ),
    )
    paddleocr_root = _write_fake_paddleocr_root(tmp_path / "PaddleOCR")

    with pytest.raises(
        runner.PaddleOCRFinetuneExecutionError,
        match="private refs",
    ):
        runner.run_paddleocr_finetune_plan(
            plan_path=plan_path,
            paddleocr_root=paddleocr_root,
            output_path=tmp_path / "execution.json",
            execute=False,
            timeout_seconds=10,
        )


def test_rejects_missing_train_entrypoint(tmp_path: Path) -> None:
    """Verify a non-PaddleOCR checkout cannot be used for execution."""
    plan_path = _write_plan(tmp_path / "plan.json", _plan())
    paddleocr_root = tmp_path / "PaddleOCR"
    paddleocr_root.mkdir(parents=True)

    with pytest.raises(
        runner.PaddleOCRFinetuneExecutionError,
        match="entrypoint is missing",
    ):
        runner.run_paddleocr_finetune_plan(
            plan_path=plan_path,
            paddleocr_root=paddleocr_root,
            output_path=tmp_path / "execution.json",
            execute=False,
            timeout_seconds=10,
        )


def test_cli_error_summary_is_redacted(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI errors do not print local input paths or command refs."""
    plan_path = _write_plan(tmp_path / "plan.json", _plan(command_tokens=["/bin/python"]))
    output_path = tmp_path / "execution.json"

    exit_code = runner.run_cli(
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
    assert "PaddleOCRFinetuneExecutionError" in stdout
    assert str(tmp_path) not in stdout
    assert "/bin/python" not in stdout
    assert "models/paddleocr" not in stdout
