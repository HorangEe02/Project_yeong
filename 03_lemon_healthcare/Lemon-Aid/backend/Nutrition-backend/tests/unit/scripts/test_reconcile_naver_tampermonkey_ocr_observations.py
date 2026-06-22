"""Tests for reconciling Tampermonkey OCR observations."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts import reconcile_naver_tampermonkey_ocr_observations as reconciler


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL rows for tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _observation(
    fixture_id: str,
    *,
    status: str = "completed",
    llm_status: str | None = "completed",
    ingredient_count: int = 1,
    error_code: str | None = None,
) -> dict[str, object]:
    """Return a redacted observation row."""
    row: dict[str, object] = {
        "fixture_id": fixture_id,
        "provider": "paddleocr_local",
        "status": status,
        "text_non_empty": status == "completed",
        "parser_success": status == "completed",
    }
    if error_code is not None:
        row["error_code"] = error_code
    if llm_status is not None:
        row["llm_parse_status"] = llm_status
        row["llm_parse_attempt_count"] = 1
        if llm_status == "completed":
            row["llm_parsed_ingredient_count"] = ingredient_count
            row["llm_parsed_ingredients"] = [
                {
                    "display_name": f"성분-{index}",
                    "amount": float(index),
                    "unit": "mg",
                    "confidence": 0.5,
                    "source": "ollama_structured",
                }
                for index in range(ingredient_count)
            ]
    return row


def test_reconcile_observations_prefers_retry_success(tmp_path: Path) -> None:
    """Verify retry successes replace base errors without double-counting."""
    base = tmp_path / "base.jsonl"
    retry = tmp_path / "retry.jsonl"
    _write_jsonl(
        base,
        [
            _observation(
                "fixture-1", status="error", llm_status=None, error_code="ocr_low_confidence"
            ),
            _observation("fixture-2", status="completed", llm_status="error", ingredient_count=0),
        ],
    )
    _write_jsonl(
        retry,
        [
            _observation(
                "fixture-1", status="completed", llm_status="completed", ingredient_count=3
            ),
            _observation(
                "fixture-2", status="completed", llm_status="completed", ingredient_count=2
            ),
        ],
    )

    rows, summary = reconciler.reconcile_observations(observation_paths=[base, retry])

    assert [row["fixture_id"] for row in rows] == ["fixture-1", "fixture-2"]
    assert [row["status"] for row in rows] == ["completed", "completed"]
    assert [row["llm_parse_status"] for row in rows] == ["completed", "completed"]
    assert summary["input_observation_count"] == 4
    assert summary["output_observation_count"] == 2
    assert summary["duplicate_group_count"] == 2
    assert summary["status_counts"] == {"completed": 2}
    assert summary["llm_parse_status_counts"] == {"completed": 2}
    serialized = json.dumps({"rows": rows, "summary": summary}, ensure_ascii=False)
    assert str(tmp_path) not in serialized
    assert "/private/" not in serialized


def test_reconcile_observations_keeps_better_ingredient_count_on_tie(tmp_path: Path) -> None:
    """Verify higher structured ingredient count wins when status ties."""
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    _write_jsonl(first, [_observation("fixture-1", ingredient_count=1)])
    _write_jsonl(second, [_observation("fixture-1", ingredient_count=4)])

    rows, summary = reconciler.reconcile_observations(observation_paths=[first, second])

    assert len(rows) == 1
    assert rows[0]["llm_parsed_ingredient_count"] == 4
    assert list(summary["selected_source_counts"].values()) == [1]  # type: ignore[union-attr]
    assert next(iter(summary["selected_source_counts"])).endswith(":second.jsonl")  # type: ignore[arg-type]


def test_reconcile_observations_hashes_long_source_labels(tmp_path: Path) -> None:
    """Verify long retry output paths do not break redacted source accounting."""
    long_dir = (
        tmp_path
        / "retry-runs-gemma4-e4b-live"
        / "ocr-low-confidence-reconciled-4-server-detection-gemma4-escalated"
        / "paddleocr-observations"
    )
    path = long_dir / "supplement-ocr-observations.jsonl"
    _write_jsonl(path, [_observation("fixture-1")])

    rows, summary = reconciler.reconcile_observations(observation_paths=[path])

    assert len(rows) == 1
    source_counts = summary["selected_source_counts"]
    assert isinstance(source_counts, dict)
    assert list(source_counts.values()) == [1]
    source_label = next(iter(source_counts))
    assert source_label.startswith("source-")
    assert len(source_label) <= 120
    serialized = json.dumps(summary, ensure_ascii=False)
    assert str(tmp_path) not in serialized


def test_reconcile_observations_rejects_raw_fields(tmp_path: Path) -> None:
    """Verify raw OCR text cannot enter reconciled artifacts."""
    path = tmp_path / "observations.jsonl"
    row = _observation("fixture-1")
    row["raw_ocr_text"] = "do not persist"
    _write_jsonl(path, [row])

    with pytest.raises(ValueError, match="raw_ocr_text"):
        reconciler.reconcile_observations(observation_paths=[path])


def test_reconcile_observations_rejects_local_path_literal(tmp_path: Path) -> None:
    """Verify local path literals are rejected."""
    path = tmp_path / "observations.jsonl"
    row = _observation("fixture-1")
    row["debug"] = "/Volumes/private/image.jpg"
    _write_jsonl(path, [row])

    with pytest.raises(ValueError, match="local path"):
        reconciler.reconcile_observations(observation_paths=[path])


def test_write_outputs_writes_redacted_files(tmp_path: Path) -> None:
    """Verify CLI writes reconciled JSONL and summary without local paths."""
    input_path = tmp_path / "input.jsonl"
    output_path = tmp_path / "out" / "reconciled.jsonl"
    summary_path = tmp_path / "out" / "summary.json"
    _write_jsonl(input_path, [_observation("fixture-1")])

    rows, summary = reconciler.reconcile_observations(observation_paths=[input_path])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    assert "fixture-1" in output_path.read_text(encoding="utf-8")
    assert str(tmp_path) not in summary_path.read_text(encoding="utf-8")


def test_main_error_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI errors avoid tracebacks and local paths."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reconcile_naver_tampermonkey_ocr_observations.py",
            "--observations",
            str(tmp_path / "missing.jsonl"),
            "--output",
            str(tmp_path / "out.jsonl"),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        reconciler.main()

    printed = capsys.readouterr().out
    payload = json.loads(printed)
    assert exc_info.value.code == 1
    assert payload["status"] == "error"
    assert "Traceback" not in printed
    assert str(tmp_path) not in printed
    assert "/private/" not in printed
