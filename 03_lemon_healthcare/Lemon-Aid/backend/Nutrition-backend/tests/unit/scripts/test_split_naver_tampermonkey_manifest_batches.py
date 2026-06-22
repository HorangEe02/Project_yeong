"""Tests for splitting Naver Tampermonkey OCR manifests into batches."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts import split_naver_tampermonkey_manifest_batches as splitter


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL rows for tests."""
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _manifest_row(index: int, *, category_key: str = "omega_3") -> dict[str, object]:
    """Return a minimal safe Tampermonkey manifest row."""
    return {
        "fixture_id": f"naver-tm-detail-{index:06d}",
        "source": "naver_tampermonkey",
        "section": "detail",
        "image_path": (
            "$NAVER_TAMPERMONKEY_SOURCE_ROOT/[오메가3]/" f"sample_{index}/상세페이지/d_{index}.jpg"
        ),
        "image_sha256": f"{index:064x}"[-64:],
        "contains_personal_data": False,
        "external_transfer_allowed": True,
        "db_labeling": {
            "category_key": category_key,
            "language_targets": ["ko", "en"],
            "chronic_fixture_tags": ["cardiovascular"],
            "caution_tags": [],
            "source_urls": ["https://ods.od.nih.gov/factsheets/list-all/"],
        },
    }


def test_split_manifest_batches_preserves_rows_and_writes_summary(tmp_path: Path) -> None:
    """Verify rows are split into deterministic resume-friendly JSONL files."""
    manifest_path = tmp_path / "manifest.jsonl"
    rows = [
        _manifest_row(1, category_key="omega_3"),
        _manifest_row(2, category_key="vitamin_d"),
        _manifest_row(3, category_key="omega_3"),
        _manifest_row(4, category_key="magnesium"),
        _manifest_row(5, category_key="vitamin_d"),
    ]
    _write_jsonl(manifest_path, rows)

    batches, summary = splitter.split_manifest_batches(
        manifest_path=manifest_path,
        output_dir=tmp_path / "batches",
        batch_size=2,
        batch_prefix="tm-batch",
    )

    assert [batch["name"] for batch in batches] == [
        "tm-batch-001.jsonl",
        "tm-batch-002.jsonl",
        "tm-batch-003.jsonl",
    ]
    assert batches[0]["rows"] == rows[:2]
    assert batches[2]["rows"] == rows[4:]
    assert summary["input_row_count"] == 5
    assert summary["batch_count"] == 3
    assert summary["category_key_counts"] == {
        "magnesium": 1,
        "omega_3": 2,
        "vitamin_d": 2,
    }
    assert summary["batches"][0]["row_index_start"] == 0  # type: ignore[index]
    assert summary["batches"][2]["row_index_end"] == 4  # type: ignore[index]

    splitter._write_batches(
        batches=batches,
        summary=summary,
        output_dir=tmp_path / "batches",
        summary_path=tmp_path / "batches" / "manifest-batches.summary.json",
        overwrite=False,
    )

    written = (tmp_path / "batches" / "tm-batch-001.jsonl").read_text(encoding="utf-8")
    assert "naver-tm-detail-000001" in written
    summary_text = (tmp_path / "batches" / "manifest-batches.summary.json").read_text(
        encoding="utf-8"
    )
    assert str(tmp_path) not in summary_text
    assert "/Volumes/" not in summary_text


def test_split_manifest_batches_rejects_raw_ocr_text(tmp_path: Path) -> None:
    """Verify raw OCR text cannot enter batch artifacts."""
    manifest_path = tmp_path / "manifest.jsonl"
    row = _manifest_row(1)
    row["raw_ocr_text"] = "do not persist"
    _write_jsonl(manifest_path, [row])

    with pytest.raises(ValueError, match="raw_ocr_text"):
        splitter.split_manifest_batches(
            manifest_path=manifest_path,
            output_dir=tmp_path / "batches",
        )


def test_split_manifest_batches_rejects_local_path_literal(tmp_path: Path) -> None:
    """Verify local absolute paths are rejected."""
    manifest_path = tmp_path / "manifest.jsonl"
    row = _manifest_row(1)
    row["image_path"] = "/Volumes/private/detail.jpg"
    _write_jsonl(manifest_path, [row])

    with pytest.raises(ValueError, match="local path"):
        splitter.split_manifest_batches(
            manifest_path=manifest_path,
            output_dir=tmp_path / "batches",
        )


def test_split_manifest_batches_rejects_unsafe_batch_prefix(tmp_path: Path) -> None:
    """Verify generated file names cannot contain path separators."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_jsonl(manifest_path, [_manifest_row(1)])

    with pytest.raises(ValueError, match="batch_prefix"):
        splitter.split_manifest_batches(
            manifest_path=manifest_path,
            output_dir=tmp_path / "batches",
            batch_prefix="../unsafe",
        )


def test_main_error_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI failures do not expose local paths or tracebacks."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "split_naver_tampermonkey_manifest_batches.py",
            "--manifest",
            str(tmp_path / "missing.jsonl"),
            "--output-dir",
            str(tmp_path / "batches"),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        splitter.main()

    printed = capsys.readouterr().out
    payload = json.loads(printed)
    assert exc_info.value.code == 1
    assert payload["status"] == "error"
    assert payload["manifest_name"] == "missing.jsonl"
    assert "Traceback" not in printed
    assert str(tmp_path) not in printed
    assert "/private/" not in printed
