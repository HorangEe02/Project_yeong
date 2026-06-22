"""Tests for PaddleOCR text extraction target gate."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

gate_module = importlib.import_module("scripts.gate_paddleocr_text_extraction_target")


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


def _eval_summary(**overrides: Any) -> dict[str, Any]:
    """Build a trusted PaddleOCR target eval summary fixture.

    Args:
        overrides: Field overrides.

    Returns:
        Evaluation summary fixture.
    """
    payload: dict[str, Any] = {
        "schema_version": "supplement-paddleocr-text-extraction-eval-summary-v1",
        "provider": "paddleocr_local",
        "eval_split": "holdout",
        "fixture_count": 40,
        "human_reviewed_fixture_count": 40,
        "leakage_check_passed": True,
        "privacy_review_cleared": True,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "metrics": {
            "normalized_text_precision": 0.97,
            "normalized_text_recall": 0.96,
            "normalized_text_f1": 0.965,
        },
    }
    payload.update(overrides)
    return payload


def test_gate_allows_target_reached_on_trusted_holdout_eval(tmp_path: Path) -> None:
    """Verify held-out human-reviewed 95 percent metrics stop the loop."""
    summary_path = _write_json(tmp_path / "eval.json", _eval_summary())

    gate = gate_module.build_paddleocr_text_extraction_target_gate(
        eval_summary_path=summary_path,
    )

    assert gate["status"] == "target_reached"
    assert gate["paddleocr_target_reached"] is True
    assert gate["continue_training_loop"] is False
    assert gate["trust_checks"]["eval_split_is_heldout"] is True
    assert gate["privacy_review_cleared"] is True
    assert gate["training_loop_stop_allowed"] is True
    assert gate["metric_checks"] == {
        "normalized_text_f1": True,
        "normalized_text_precision": True,
        "normalized_text_recall": True,
    }


def test_gate_continues_when_any_required_metric_is_below_target(tmp_path: Path) -> None:
    """Verify a single low metric keeps PaddleOCR training open."""
    summary_path = _write_json(
        tmp_path / "eval.json",
        _eval_summary(
            metrics={
                "normalized_text_precision": 0.97,
                "normalized_text_recall": 0.94,
                "normalized_text_f1": 0.955,
            }
        ),
    )

    gate = gate_module.build_paddleocr_text_extraction_target_gate(
        eval_summary_path=summary_path,
    )

    assert gate["status"] == "continue_training_loop"
    assert gate["paddleocr_target_reached"] is False
    assert gate["metric_checks"]["normalized_text_recall"] is False


def test_gate_blocks_untrusted_train_split(tmp_path: Path) -> None:
    """Verify train split metrics cannot stop the learning loop."""
    summary_path = _write_json(tmp_path / "eval.json", _eval_summary(eval_split="train"))

    gate = gate_module.build_paddleocr_text_extraction_target_gate(
        eval_summary_path=summary_path,
    )

    assert gate["status"] == "blocked_by_untrusted_eval"
    assert gate["paddleocr_target_reached"] is False
    assert gate["trust_checks"]["eval_split_is_heldout"] is False


def test_gate_blocks_when_leakage_check_did_not_pass(tmp_path: Path) -> None:
    """Verify leakage uncertainty fails closed."""
    summary_path = _write_json(
        tmp_path / "eval.json",
        _eval_summary(leakage_check_passed=False),
    )

    gate = gate_module.build_paddleocr_text_extraction_target_gate(
        eval_summary_path=summary_path,
    )

    assert gate["status"] == "blocked_by_untrusted_eval"
    assert gate["trust_checks"]["leakage_check_passed"] is False


def test_gate_blocks_when_privacy_review_is_not_cleared(tmp_path: Path) -> None:
    """Verify human GT privacy review is required before stopping training."""
    summary_path = _write_json(
        tmp_path / "eval.json",
        _eval_summary(privacy_review_cleared=False),
    )

    gate = gate_module.build_paddleocr_text_extraction_target_gate(
        eval_summary_path=summary_path,
    )

    assert gate["status"] == "blocked_by_untrusted_eval"
    assert gate["paddleocr_target_reached"] is False
    assert gate["trust_checks"]["privacy_review_cleared"] is False
    assert gate["training_loop_stop_allowed"] is False


def test_gate_rejects_raw_ocr_text_key(tmp_path: Path) -> None:
    """Verify raw OCR text cannot enter target gate input."""
    summary_path = _write_json(tmp_path / "eval.json", _eval_summary(raw_ocr_text="secret"))

    try:
        gate_module.build_paddleocr_text_extraction_target_gate(eval_summary_path=summary_path)
    except ValueError as exc:
        assert "raw_ocr_text" in str(exc)
    else:
        raise AssertionError("Expected raw OCR text rejection.")


def test_cli_writes_gate_and_redacted_markdown(
    tmp_path: Path,
    capsys: Any,
) -> None:
    """Verify CLI writes artifacts without printing metric values or paths."""
    summary_path = _write_json(tmp_path / "eval.json", _eval_summary())
    output_path = tmp_path / "gate.json"
    markdown_path = tmp_path / "gate.md"

    exit_code = gate_module.run_cli(
        [
            "--eval-summary",
            str(summary_path),
            "--output",
            str(output_path),
            "--markdown-output",
            str(markdown_path),
            "--min-fixtures",
            "30",
        ]
    )

    stdout = capsys.readouterr().out
    written = json.loads(output_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert exit_code == 0
    assert written["paddleocr_target_reached"] is True
    assert "0.97" not in stdout
    assert str(tmp_path) not in stdout
    assert "PaddleOCR Text Extraction Target Gate" in markdown
    assert "normalized_text_precision" in markdown
