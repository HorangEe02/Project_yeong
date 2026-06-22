"""Tests for the redacted PP-StructureV3 Tampermonkey probe."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts import run_naver_tampermonkey_ppstructure_probe as probe


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL rows for tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _manifest_row(fixture_id: str = "naver-tm-detail-000001") -> dict[str, object]:
    """Return a safe manifest row."""
    return {
        "fixture_id": fixture_id,
        "section": "detail",
        "image_path": "$NAVER_TAMPERMONKEY_SOURCE_ROOT/[아연]/sample/detail.jpg",
        "image_sha256": "a" * 64,
        "db_labeling": {"category_key": "zinc"},
    }


class _FakePPStructureResult:
    """Fake PP-StructureV3 result exposing a json mapping."""

    def __init__(self, payload: dict[str, Any]) -> None:
        """Store fake payload."""
        self.json = payload


class _FakePPStructurePipeline:
    """Fake PP-StructureV3 pipeline for tests."""

    def predict(self, image_path: str) -> list[_FakePPStructureResult]:  # noqa: ARG002
        """Return one fake structured result containing raw text-like fields."""
        return [
            _FakePPStructureResult(
                {
                    "res": {
                        "layout_det_res": {
                            "boxes": [
                                {"label": "table", "score": 0.91, "coordinate": [0, 0, 10, 10]},
                                {"label": "text", "score": 0.81, "coordinate": [0, 11, 10, 20]},
                                {"label": "image", "score": 0.71, "coordinate": [0, 21, 10, 30]},
                            ],
                        },
                        "overall_ocr_res": {
                            "rec_texts": ["forbidden-placeholder-content"],
                            "dt_polys": [[[0, 0], [1, 1]]],
                        },
                        "table_res_list": [
                            {
                                "html": "<table><tr><td>placeholder</td></tr></table>",
                                "cell_box_list": [1, 2],
                            }
                        ],
                    }
                }
            )
        ]


def _pipeline_factory(**_kwargs: object) -> _FakePPStructurePipeline:
    """Return a fake PP-StructureV3 pipeline."""
    return _FakePPStructurePipeline()


def test_ppstructure_probe_writes_counts_without_raw_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the probe stores layout counts, not raw OCR/table text."""
    image_root = tmp_path / "source"
    image_path = image_root / "[아연]" / "sample" / "detail.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"fake")
    monkeypatch.setenv("NAVER_TAMPERMONKEY_SOURCE_ROOT", str(image_root))
    manifest = tmp_path / "manifest.jsonl"
    _write_jsonl(manifest, [_manifest_row()])

    rows, summary = probe.run_probe(
        manifest_path=manifest,
        output_dir=tmp_path / "out",
        pipeline_factory=_pipeline_factory,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["probe_status"] == "completed"
    assert row["layout_box_count"] == 3
    assert row["layout_table_region_count"] == 1
    assert row["layout_text_region_count"] == 1
    assert row["layout_figure_region_count"] == 1
    assert row["overall_ocr_rec_text_count"] == 1
    assert row["table_result_count"] >= 1
    assert summary["status_counts"] == {"completed": 1}
    serialized = json.dumps({"rows": rows, "summary": summary}, ensure_ascii=False)
    assert "forbidden-placeholder-content" not in serialized
    assert "<table>" not in serialized
    assert str(image_root) not in serialized
    assert "/private/" not in serialized


def test_ppstructure_probe_rejects_local_path_literal(tmp_path: Path) -> None:
    """Verify local path literals in manifests are rejected."""
    manifest = tmp_path / "manifest.jsonl"
    row = _manifest_row()
    row["image_path"] = "/Volumes/private/detail.jpg"
    _write_jsonl(manifest, [row])

    with pytest.raises(ValueError, match="local path"):
        probe.run_probe(
            manifest_path=manifest,
            output_dir=tmp_path / "out",
            pipeline_factory=_pipeline_factory,
        )


def test_ppstructure_probe_rejects_raw_manifest_field(tmp_path: Path) -> None:
    """Verify raw OCR fields cannot enter the probe input."""
    manifest = tmp_path / "manifest.jsonl"
    row = _manifest_row()
    row["raw_ocr_text"] = "do not persist"
    _write_jsonl(manifest, [row])

    with pytest.raises(ValueError, match="raw_ocr_text"):
        probe.run_probe(
            manifest_path=manifest,
            output_dir=tmp_path / "out",
            pipeline_factory=_pipeline_factory,
        )


def test_ppstructure_probe_write_outputs_are_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify output files do not contain local paths or raw text."""
    image_root = tmp_path / "source"
    image_path = image_root / "[아연]" / "sample" / "detail.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"fake")
    monkeypatch.setenv("NAVER_TAMPERMONKEY_SOURCE_ROOT", str(image_root))
    manifest = tmp_path / "manifest.jsonl"
    _write_jsonl(manifest, [_manifest_row()])
    rows, summary = probe.run_probe(
        manifest_path=manifest,
        output_dir=tmp_path / "out",
        pipeline_factory=_pipeline_factory,
    )

    probe._write_outputs(
        rows=rows,
        summary=summary,
        output_dir=tmp_path / "out",
        probe_name=probe.DEFAULT_PROBE_NAME,
        summary_name=probe.DEFAULT_SUMMARY_NAME,
    )

    output_text = (tmp_path / "out" / probe.DEFAULT_PROBE_NAME).read_text(encoding="utf-8")
    summary_text = (tmp_path / "out" / probe.DEFAULT_SUMMARY_NAME).read_text(encoding="utf-8")
    assert "forbidden-placeholder-content" not in output_text
    assert str(image_root) not in output_text
    assert str(image_root) not in summary_text


def test_ppstructure_probe_main_error_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI errors avoid tracebacks and local paths."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_naver_tampermonkey_ppstructure_probe.py",
            "--manifest",
            str(tmp_path / "missing.jsonl"),
            "--output-dir",
            str(tmp_path / "out"),
            "--probe-name",
            "../unsafe.jsonl",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        probe.main()

    printed = capsys.readouterr().out
    payload = json.loads(printed)
    assert exc_info.value.code == 1
    assert payload["status"] == "error"
    assert "Traceback" not in printed
    assert str(tmp_path) not in printed
    assert "/private/" not in printed


def test_ppstructure_probe_main_runtime_error_is_redacted_and_written(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify runtime dependency failures are captured as redacted summaries."""

    def _raise_runtime_error(**_kwargs: object) -> object:
        raise RuntimeError('install -e "/private/path/PaddleX[ocr]"')

    image_root = tmp_path / "source"
    image_path = image_root / "[아연]" / "sample" / "detail.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"fake")
    monkeypatch.setenv("NAVER_TAMPERMONKEY_SOURCE_ROOT", str(image_root))
    manifest = tmp_path / "manifest.jsonl"
    output_dir = tmp_path / "out"
    _write_jsonl(manifest, [_manifest_row()])
    monkeypatch.setattr(probe, "_build_pipeline", lambda **_kwargs: _raise_runtime_error())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_naver_tampermonkey_ppstructure_probe.py",
            "--manifest",
            str(manifest),
            "--output-dir",
            str(output_dir),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        probe.main()

    printed = capsys.readouterr().out
    payload = json.loads(printed)
    written = json.loads((output_dir / probe.DEFAULT_SUMMARY_NAME).read_text(encoding="utf-8"))
    assert exc_info.value.code == 1
    assert payload["status"] == "error"
    assert written["status"] == "error"
    assert payload["error_message"] == "Validation failed."
    assert str(tmp_path) not in printed
    assert "/private/" not in printed
