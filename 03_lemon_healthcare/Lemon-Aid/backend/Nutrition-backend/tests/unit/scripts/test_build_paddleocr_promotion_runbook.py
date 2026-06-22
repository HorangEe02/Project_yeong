"""Tests for PaddleOCR promotion operator runbook generation."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

runbook = importlib.import_module("scripts.build_paddleocr_promotion_runbook")


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    """Write one JSON fixture.

    Args:
        path: Destination path.
        payload: JSON payload.

    Returns:
        Written path.
    """
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _plan(*, task: str = "recognition") -> dict[str, Any]:
    """Build a fine-tune plan fixture.

    Args:
        task: PaddleOCR task.

    Returns:
        Plan payload.
    """
    return {
        "schema_version": "paddleocr-finetune-run-plan-v1",
        "task": task,
        "training_execution_performed": False,
    }


def _finetune_eval(*, task: str = "recognition") -> dict[str, Any]:
    """Build a fine-tuned eval fixture.

    Args:
        task: PaddleOCR task.

    Returns:
        Eval payload.
    """
    return {
        "schema_version": "paddleocr-finetune-eval-result-v1",
        "task": task,
        "process_status": "metrics_verified",
        "metrics_json_ready_for_registration": True,
        "stdout_raw_stored": False,
        "stderr_raw_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def _baseline_eval(*, task: str = "recognition") -> dict[str, Any]:
    """Build a baseline eval fixture.

    Args:
        task: PaddleOCR task.

    Returns:
        Eval payload.
    """
    return {
        "schema_version": "paddleocr-baseline-eval-result-v1",
        "task": task,
        "process_status": "metrics_verified",
        "metrics_json_ready_for_comparison": True,
        "stdout_raw_stored": False,
        "stderr_raw_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def _baseline_gate(*, task: str = "recognition") -> dict[str, Any]:
    """Build a baseline gate fixture.

    Args:
        task: PaddleOCR task.

    Returns:
        Gate payload.
    """
    return {
        "schema_version": "paddleocr-baseline-comparison-gate-v1",
        "task": task,
        "allowed": True,
        "rule_count": 2,
        "passed_rule_count": 2,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def _promotion_rules(*, task: str = "recognition") -> dict[str, Any]:
    """Build a promotion rules fixture.

    Args:
        task: PaddleOCR task.

    Returns:
        Promotion rules payload.
    """
    return {
        "schema_version": "paddleocr-promotion-metric-rules-v1",
        "task": task,
        "allowed_by_baseline_gate": True,
        "metric_rules": [
            {"metric_name": "acc", "comparator": ">=", "threshold": "0.92"},
            {"metric_name": "norm_edit_dis", "comparator": ">=", "threshold": "0.90"},
        ],
        "artifact_ref_printed": False,
    }


def _readiness(*, task: str = "recognition", ready: bool = True) -> dict[str, Any]:
    """Build a readiness fixture.

    Args:
        task: PaddleOCR task.
        ready: Whether the readiness artifact is promotion-ready.

    Returns:
        Readiness payload.
    """
    return {
        "schema_version": "paddleocr-promotion-readiness-v1",
        "task": task,
        "ready_for_promotion": ready,
        "artifact_count": 5,
        "metric_names_printed": False,
        "metric_values_printed": False,
        "source_path_printed": False,
        "checkpoint_ref_printed": False,
        "artifact_ref_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def _write_artifacts(tmp_path: Path, **overrides: dict[str, Any]) -> dict[str, Path]:
    """Write a complete artifact chain.

    Args:
        tmp_path: Temporary directory.
        overrides: Payload overrides by fixture key.

    Returns:
        Artifact path mapping.
    """
    payloads = {
        "plan": _plan(),
        "finetune_eval": _finetune_eval(),
        "baseline_eval": _baseline_eval(),
        "baseline_gate": _baseline_gate(),
        "promotion_rules": _promotion_rules(),
        "readiness": _readiness(),
    }
    payloads.update(overrides)
    return {
        key: _write_json(tmp_path / f"{key}.json", payload) for key, payload in payloads.items()
    }


def test_runbook_allows_ready_artifact_chain(
    tmp_path: Path,
    capsys: Any,
) -> None:
    """Verify a consistent artifact chain creates a redacted runbook."""
    paths = _write_artifacts(tmp_path)
    output_path = tmp_path / "runbook.json"

    exit_code = runbook.run_cli(
        [
            "--task",
            "recognition",
            "--plan",
            str(paths["plan"]),
            "--finetune-eval",
            str(paths["finetune_eval"]),
            "--baseline-eval",
            str(paths["baseline_eval"]),
            "--baseline-gate",
            str(paths["baseline_gate"]),
            "--promotion-rules",
            str(paths["promotion_rules"]),
            "--readiness",
            str(paths["readiness"]),
            "--output",
            str(output_path),
        ]
    )

    stdout = capsys.readouterr().out
    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert artifact["schema_version"] == "paddleocr-promotion-operator-runbook-v1"
    assert artifact["ready_for_operator_review"] is True
    assert artifact["task"] == "recognition"
    assert artifact["stage_count"] == 7
    assert artifact["artifact_count"] == 6
    assert artifact["artifact_inputs"][0]["role"] == "plan"
    assert artifact["artifact_inputs"][0]["file_name"] == "plan.json"
    assert "content_sha256" in artifact["artifact_inputs"][0]
    assert "path_hash" in artifact["artifact_inputs"][0]
    assert str(tmp_path) not in stdout
    assert "acc" not in stdout
    assert "0.92" not in stdout


def test_runbook_rejects_not_ready_readiness_artifact(tmp_path: Path) -> None:
    """Verify stored readiness must be promotion-ready."""
    paths = _write_artifacts(tmp_path, readiness=_readiness(ready=False))

    exit_code = runbook.run_cli(
        [
            "--task",
            "recognition",
            "--plan",
            str(paths["plan"]),
            "--finetune-eval",
            str(paths["finetune_eval"]),
            "--baseline-eval",
            str(paths["baseline_eval"]),
            "--baseline-gate",
            str(paths["baseline_gate"]),
            "--promotion-rules",
            str(paths["promotion_rules"]),
            "--readiness",
            str(paths["readiness"]),
            "--output",
            str(tmp_path / "runbook.json"),
        ]
    )

    assert exit_code == 1


def test_runbook_rejects_task_mismatch(tmp_path: Path) -> None:
    """Verify every artifact must match the requested task."""
    paths = _write_artifacts(tmp_path, baseline_eval=_baseline_eval(task="detection"))

    exit_code = runbook.run_cli(
        [
            "--task",
            "recognition",
            "--plan",
            str(paths["plan"]),
            "--finetune-eval",
            str(paths["finetune_eval"]),
            "--baseline-eval",
            str(paths["baseline_eval"]),
            "--baseline-gate",
            str(paths["baseline_gate"]),
            "--promotion-rules",
            str(paths["promotion_rules"]),
            "--readiness",
            str(paths["readiness"]),
            "--output",
            str(tmp_path / "runbook.json"),
        ]
    )

    assert exit_code == 1


def test_runbook_rejects_unsafe_readiness_flags(tmp_path: Path) -> None:
    """Verify readiness redaction flags must remain fail-closed."""
    unsafe_readiness = _readiness()
    unsafe_readiness["metric_values_printed"] = True
    paths = _write_artifacts(tmp_path, readiness=unsafe_readiness)

    exit_code = runbook.run_cli(
        [
            "--task",
            "recognition",
            "--plan",
            str(paths["plan"]),
            "--finetune-eval",
            str(paths["finetune_eval"]),
            "--baseline-eval",
            str(paths["baseline_eval"]),
            "--baseline-gate",
            str(paths["baseline_gate"]),
            "--promotion-rules",
            str(paths["promotion_rules"]),
            "--readiness",
            str(paths["readiness"]),
            "--output",
            str(tmp_path / "runbook.json"),
        ]
    )

    assert exit_code == 1


def test_runbook_error_summary_is_redacted(
    tmp_path: Path,
    capsys: Any,
) -> None:
    """Verify CLI errors do not print artifact paths or metric details."""
    paths = _write_artifacts(tmp_path)
    missing = tmp_path / "missing.json"
    output_path = tmp_path / "runbook.json"

    exit_code = runbook.run_cli(
        [
            "--task",
            "recognition",
            "--plan",
            str(missing),
            "--finetune-eval",
            str(paths["finetune_eval"]),
            "--baseline-eval",
            str(paths["baseline_eval"]),
            "--baseline-gate",
            str(paths["baseline_gate"]),
            "--promotion-rules",
            str(paths["promotion_rules"]),
            "--readiness",
            str(paths["readiness"]),
            "--output",
            str(output_path),
        ]
    )

    stdout = capsys.readouterr().out
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert summary["status"] == "error"
    assert str(tmp_path) not in stdout
    assert "missing.json" not in stdout
    assert "acc" not in stdout
