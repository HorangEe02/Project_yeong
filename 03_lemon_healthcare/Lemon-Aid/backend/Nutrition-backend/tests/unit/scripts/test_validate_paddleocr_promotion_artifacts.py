"""Tests for PaddleOCR promotion readiness preflight."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

preflight = importlib.import_module("scripts.validate_paddleocr_promotion_artifacts")


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


def _plan(*, task: str = "recognition") -> dict[str, Any]:
    """Build a plan fixture.

    Args:
        task: PaddleOCR task.

    Returns:
        Plan payload.
    """
    return {
        "schema_version": "paddleocr-finetune-run-plan-v1",
        "training_execution_performed": False,
        "dataset_version_id": str(uuid4()),
        "task": task,
    }


def _finetune_eval(
    *, task: str = "recognition", status: str = "metrics_verified"
) -> dict[str, Any]:
    """Build a fine-tuned eval fixture.

    Args:
        task: PaddleOCR task.
        status: Eval process status.

    Returns:
        Eval payload.
    """
    return {
        "schema_version": "paddleocr-finetune-eval-result-v1",
        "task": task,
        "process_status": status,
        "metrics_json_ready_for_registration": status == "metrics_verified",
        "stdout_raw_stored": False,
        "stderr_raw_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def _baseline_eval(
    *, task: str = "recognition", status: str = "metrics_verified"
) -> dict[str, Any]:
    """Build a baseline eval fixture.

    Args:
        task: PaddleOCR task.
        status: Eval process status.

    Returns:
        Eval payload.
    """
    return {
        "schema_version": "paddleocr-baseline-eval-result-v1",
        "task": task,
        "process_status": status,
        "metrics_json_ready_for_comparison": status == "metrics_verified",
        "stdout_raw_stored": False,
        "stderr_raw_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def _baseline_gate(
    *,
    task: str = "recognition",
    allowed: bool = True,
    rule_count: int = 2,
) -> dict[str, Any]:
    """Build a baseline comparison gate fixture.

    Args:
        task: PaddleOCR task.
        allowed: Whether gate allowed promotion.
        rule_count: Gate rule count.

    Returns:
        Gate payload.
    """
    passed_rule_count = rule_count if allowed else max(0, rule_count - 1)
    return {
        "schema_version": "paddleocr-baseline-comparison-gate-v1",
        "task": task,
        "allowed": allowed,
        "rule_count": rule_count,
        "passed_rule_count": passed_rule_count,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def _promotion_rules(
    *,
    task: str = "recognition",
    allowed: bool = True,
    rule_count: int = 2,
) -> dict[str, Any]:
    """Build a promotion rules fixture.

    Args:
        task: PaddleOCR task.
        allowed: Whether baseline gate allowed the rules.
        rule_count: Rule count.

    Returns:
        Promotion rules payload.
    """
    metric_names = ["acc", "norm_edit_dis", "precision", "recall", "hmean"]
    return {
        "schema_version": "paddleocr-promotion-metric-rules-v1",
        "task": task,
        "allowed_by_baseline_gate": allowed,
        "metric_rules": [
            {"metric_name": metric_names[index], "comparator": ">=", "threshold": "0.9"}
            for index in range(rule_count)
        ],
        "artifact_ref_printed": False,
    }


def _write_artifacts(tmp_path: Path, **overrides: dict[str, Any]) -> dict[str, Path]:
    """Write a complete preflight artifact set.

    Args:
        tmp_path: Temporary directory.
        overrides: Optional artifact payload overrides by key.

    Returns:
        Artifact path mapping.
    """
    payloads = {
        "plan": _plan(),
        "finetune_eval": _finetune_eval(),
        "baseline_eval": _baseline_eval(),
        "baseline_gate": _baseline_gate(),
        "promotion_rules": _promotion_rules(),
    }
    payloads.update(overrides)
    return {
        key: _write_json(tmp_path / f"{key}.json", payload) for key, payload in payloads.items()
    }


def test_preflight_allows_consistent_ready_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify a complete artifact chain produces a redacted readiness artifact."""
    paths = _write_artifacts(tmp_path)
    output_path = tmp_path / "readiness.json"

    exit_code = preflight.run_cli(
        [
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
            "--output",
            str(output_path),
        ]
    )

    stdout = capsys.readouterr().out
    readiness = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert readiness["schema_version"] == "paddleocr-promotion-readiness-v1"
    assert readiness["ready_for_promotion"] is True
    assert readiness["task"] == "recognition"
    assert readiness["gate_rule_count"] == 2
    assert readiness["promotion_rule_count"] == 2
    assert str(tmp_path) not in stdout
    assert "acc" not in stdout
    assert "0.9" not in stdout


def test_preflight_rejects_unverified_baseline_eval(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify baseline eval must be comparison-ready."""
    paths = _write_artifacts(
        tmp_path,
        baseline_eval=_baseline_eval(status="metrics_missing"),
    )
    output_path = tmp_path / "readiness.json"

    exit_code = preflight.run_cli(
        [
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
            "--output",
            str(output_path),
        ]
    )

    stdout = capsys.readouterr().out
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert summary["status"] == "error"
    assert "PaddleOCRPromotionReadinessError" in stdout
    assert str(tmp_path) not in stdout


def test_preflight_rejects_task_mismatch(tmp_path: Path) -> None:
    """Verify artifacts must all refer to the same task."""
    paths = _write_artifacts(
        tmp_path,
        baseline_gate=_baseline_gate(task="detection"),
    )

    with pytest.raises(
        preflight.PaddleOCRPromotionReadinessError,
        match="task does not match",
    ):
        preflight.validate_paddleocr_promotion_artifacts(
            plan_path=paths["plan"],
            finetune_eval_path=paths["finetune_eval"],
            baseline_eval_path=paths["baseline_eval"],
            baseline_gate_path=paths["baseline_gate"],
            promotion_rules_path=paths["promotion_rules"],
        )


def test_preflight_rejects_denied_baseline_gate(tmp_path: Path) -> None:
    """Verify a denied baseline gate cannot proceed to promotion."""
    paths = _write_artifacts(
        tmp_path,
        baseline_gate=_baseline_gate(allowed=False),
        promotion_rules=_promotion_rules(allowed=False),
    )

    with pytest.raises(
        preflight.PaddleOCRPromotionReadinessError,
        match="did not allow",
    ):
        preflight.validate_paddleocr_promotion_artifacts(
            plan_path=paths["plan"],
            finetune_eval_path=paths["finetune_eval"],
            baseline_eval_path=paths["baseline_eval"],
            baseline_gate_path=paths["baseline_gate"],
            promotion_rules_path=paths["promotion_rules"],
        )


def test_preflight_rejects_rule_count_mismatch(tmp_path: Path) -> None:
    """Verify promotion rule count must match the baseline gate."""
    paths = _write_artifacts(
        tmp_path,
        baseline_gate=_baseline_gate(rule_count=2),
        promotion_rules=_promotion_rules(rule_count=1),
    )

    with pytest.raises(
        preflight.PaddleOCRPromotionReadinessError,
        match="rule count",
    ):
        preflight.validate_paddleocr_promotion_artifacts(
            plan_path=paths["plan"],
            finetune_eval_path=paths["finetune_eval"],
            baseline_eval_path=paths["baseline_eval"],
            baseline_gate_path=paths["baseline_gate"],
            promotion_rules_path=paths["promotion_rules"],
        )


def test_preflight_rejects_raw_eval_payload_flags(tmp_path: Path) -> None:
    """Verify eval artifacts cannot claim raw logs were retained."""
    dirty_eval = _finetune_eval()
    dirty_eval["stdout_raw_stored"] = True
    paths = _write_artifacts(tmp_path, finetune_eval=dirty_eval)

    with pytest.raises(
        preflight.PaddleOCRPromotionReadinessError,
        match="raw stdout",
    ):
        preflight.validate_paddleocr_promotion_artifacts(
            plan_path=paths["plan"],
            finetune_eval_path=paths["finetune_eval"],
            baseline_eval_path=paths["baseline_eval"],
            baseline_gate_path=paths["baseline_gate"],
            promotion_rules_path=paths["promotion_rules"],
        )
