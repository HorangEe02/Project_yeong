"""Tests for PaddleOCR baseline comparison gate."""

from __future__ import annotations

import importlib
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

baseline_gate = importlib.import_module("scripts.gate_paddleocr_finetune_against_baseline")


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


def test_recognition_gate_allows_metrics_above_baseline_and_thresholds(
    tmp_path: Path,
) -> None:
    """Verify recognition metrics must beat baseline and absolute thresholds."""
    finetuned_path = _write_json(
        tmp_path / "finetuned.json",
        {"acc": 0.93, "norm_edit_dis": 0.91},
    )
    baseline_path = _write_json(
        tmp_path / "baseline.json",
        {"acc": 0.90, "norm_edit_dis": 0.88},
    )

    gate, summary, promotion_rules = baseline_gate.gate_paddleocr_finetune_against_baseline(
        task="recognition",
        finetuned_metrics_path=finetuned_path,
        baseline_metrics_path=baseline_path,
        min_metric_thresholds={
            "acc": Decimal("0.92"),
            "norm_edit_dis": Decimal("0.90"),
        },
        min_improvements={
            "acc": Decimal("0.01"),
            "norm_edit_dis": Decimal("0.01"),
        },
    )

    assert gate["allowed"] is True
    assert gate["passed_rule_count"] == 2
    assert summary["allowed"] is True
    assert promotion_rules["allowed_by_baseline_gate"] is True
    assert promotion_rules["metric_rules"] == [
        {"metric_name": "acc", "comparator": ">=", "threshold": "0.92"},
        {"metric_name": "norm_edit_dis", "comparator": ">=", "threshold": "0.9"},
    ]


def test_detection_gate_blocks_baseline_regression(tmp_path: Path) -> None:
    """Verify detection metrics cannot regress below baseline plus delta."""
    finetuned_path = _write_json(
        tmp_path / "finetuned.json",
        {"precision": 0.80, "recall": 0.78, "hmean": 0.79},
    )
    baseline_path = _write_json(
        tmp_path / "baseline.json",
        {"precision": 0.79, "recall": 0.78, "hmean": 0.80},
    )

    gate, summary, promotion_rules = baseline_gate.gate_paddleocr_finetune_against_baseline(
        task="detection",
        finetuned_metrics_path=finetuned_path,
        baseline_metrics_path=baseline_path,
        min_metric_thresholds={
            "precision": Decimal("0.75"),
            "recall": Decimal("0.75"),
            "hmean": Decimal("0.75"),
        },
        min_improvements={
            "precision": Decimal("0.00"),
            "recall": Decimal("0.00"),
            "hmean": Decimal("0.01"),
        },
    )

    assert gate["allowed"] is False
    assert gate["reason"] == "metric_gate_failed"
    assert gate["passed_rule_count"] == 2
    assert summary["allowed"] is False
    assert promotion_rules["allowed_by_baseline_gate"] is False
    hmean_rule = promotion_rules["metric_rules"][2]
    assert hmean_rule == {"metric_name": "hmean", "comparator": ">=", "threshold": "0.81"}


def test_gate_requires_all_task_metric_thresholds(tmp_path: Path) -> None:
    """Verify explicit absolute thresholds are required for every task metric."""
    finetuned_path = _write_json(
        tmp_path / "finetuned.json",
        {"acc": 0.93, "norm_edit_dis": 0.91},
    )
    baseline_path = _write_json(
        tmp_path / "baseline.json",
        {"acc": 0.90, "norm_edit_dis": 0.88},
    )

    with pytest.raises(
        baseline_gate.PaddleOCRBaselineGateError,
        match="thresholds must cover",
    ):
        baseline_gate.gate_paddleocr_finetune_against_baseline(
            task="recognition",
            finetuned_metrics_path=finetuned_path,
            baseline_metrics_path=baseline_path,
            min_metric_thresholds={"acc": Decimal("0.92")},
            min_improvements={},
        )


def test_gate_rejects_missing_required_metrics(tmp_path: Path) -> None:
    """Verify missing task-required metric values fail closed."""
    finetuned_path = _write_json(tmp_path / "finetuned.json", {"acc": 0.93})
    baseline_path = _write_json(
        tmp_path / "baseline.json",
        {"acc": 0.90, "norm_edit_dis": 0.88},
    )

    with pytest.raises(
        baseline_gate.PaddleOCRBaselineGateError,
        match="missing required",
    ):
        baseline_gate.gate_paddleocr_finetune_against_baseline(
            task="recognition",
            finetuned_metrics_path=finetuned_path,
            baseline_metrics_path=baseline_path,
            min_metric_thresholds={
                "acc": Decimal("0.92"),
                "norm_edit_dis": Decimal("0.90"),
            },
            min_improvements={},
        )


def test_gate_rejects_unsafe_metric_names(tmp_path: Path) -> None:
    """Verify metric JSON cannot contain path-like metric keys."""
    finetuned_path = _write_json(
        tmp_path / "finetuned.json",
        {"../acc": 0.93, "norm_edit_dis": 0.91},
    )
    baseline_path = _write_json(
        tmp_path / "baseline.json",
        {"acc": 0.90, "norm_edit_dis": 0.88},
    )

    with pytest.raises(
        baseline_gate.PaddleOCRBaselineGateError,
        match=r"stable safe|paths",
    ):
        baseline_gate.gate_paddleocr_finetune_against_baseline(
            task="recognition",
            finetuned_metrics_path=finetuned_path,
            baseline_metrics_path=baseline_path,
            min_metric_thresholds={
                "acc": Decimal("0.92"),
                "norm_edit_dis": Decimal("0.90"),
            },
            min_improvements={},
        )


def test_cli_writes_gate_and_redacted_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI output hides metric names, values, and local paths."""
    finetuned_path = _write_json(
        tmp_path / "finetuned.json",
        {"acc": 0.93, "norm_edit_dis": 0.91},
    )
    baseline_path = _write_json(
        tmp_path / "baseline.json",
        {"acc": 0.90, "norm_edit_dis": 0.88},
    )
    output_path = tmp_path / "gate.json"
    promotion_rules_path = tmp_path / "promotion-rules.json"

    exit_code = baseline_gate.run_cli(
        [
            "--task",
            "recognition",
            "--finetuned-metrics",
            str(finetuned_path),
            "--baseline-metrics",
            str(baseline_path),
            "--output",
            str(output_path),
            "--promotion-rules-output",
            str(promotion_rules_path),
            "--min-metric",
            "acc",
            "0.92",
            "--min-metric",
            "norm_edit_dis",
            "0.90",
            "--min-improvement",
            "acc",
            "0.01",
            "--min-improvement",
            "norm_edit_dis",
            "0.01",
        ]
    )

    stdout = capsys.readouterr().out
    gate = json.loads(output_path.read_text(encoding="utf-8"))
    rules = json.loads(promotion_rules_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert gate["allowed"] is True
    assert rules["allowed_by_baseline_gate"] is True
    assert "acc" not in stdout
    assert "0.93" not in stdout
    assert "0.92" not in stdout
    assert str(tmp_path) not in stdout


def test_cli_error_summary_is_redacted(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI error output hides paths and metric values."""
    finetuned_path = _write_json(tmp_path / "finetuned.json", {"acc": 0.93})
    baseline_path = _write_json(
        tmp_path / "baseline.json",
        {"acc": 0.90, "norm_edit_dis": 0.88},
    )
    output_path = tmp_path / "gate.json"

    exit_code = baseline_gate.run_cli(
        [
            "--task",
            "recognition",
            "--finetuned-metrics",
            str(finetuned_path),
            "--baseline-metrics",
            str(baseline_path),
            "--output",
            str(output_path),
            "--min-metric",
            "acc",
            "0.92",
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == 1
    assert "PaddleOCRBaselineGateError" in stdout
    assert "acc" not in stdout
    assert "0.93" not in stdout
    assert str(tmp_path) not in stdout
