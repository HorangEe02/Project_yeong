"""Tests for Tampermonkey OCR image-quality diagnostics."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

from scripts import export_naver_tampermonkey_ocr_image_quality_diagnostics as diagnostics


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL rows for tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_image(
    path: Path,
    *,
    size: tuple[int, int] = (420, 320),
    color: tuple[int, int, int] = (40, 40, 40),
) -> str:
    """Write a deterministic local test image and return its SHA-256 digest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, format="PNG")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_row(image_sha256: str) -> dict[str, object]:
    """Return a safe manifest row with a tokenized image reference."""
    return {
        "fixture_id": "naver-tm-detail-000001",
        "source": "naver_tampermonkey",
        "section": "detail",
        "image_path": "$NAVER_TAMPERMONKEY_SOURCE_ROOT/[오메가3]/제품A_12345/상세페이지/d_1.png",
        "image_sha256": image_sha256,
        "product_dir": "제품A_12345",
        "width": 420,
        "height": 320,
        "size_bucket": "small",
        "db_labeling": {
            "category_key": "omega_3",
            "language_targets": ["ko", "en"],
            "chronic_fixture_tags": ["cardiovascular"],
        },
    }


def _observation(**overrides: object) -> dict[str, object]:
    """Return a redacted failed OCR observation."""
    row: dict[str, object] = {
        "fixture_id": "naver-tm-detail-000001",
        "provider": "paddleocr_local",
        "status": "error",
        "error_code": "ocr_low_confidence",
        "text_non_empty": False,
        "parser_success": False,
    }
    row.update(overrides)
    return row


def test_export_image_quality_diagnostics_emits_redacted_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify low-confidence failures get image metadata without local paths."""
    source_root = tmp_path / "source"
    image_path = source_root / "[오메가3]" / "제품A_12345" / "상세페이지" / "d_1.png"
    image_sha256 = _write_image(image_path)
    monkeypatch.setenv("NAVER_TAMPERMONKEY_SOURCE_ROOT", str(source_root))
    _write_jsonl(tmp_path / "manifest.jsonl", [_manifest_row(image_sha256)])
    _write_jsonl(tmp_path / "observations.jsonl", [_observation()])

    rows, summary = diagnostics.export_image_quality_diagnostics(
        manifest_path=tmp_path / "manifest.jsonl",
        observations_path=tmp_path / "observations.jsonl",
        output_dir=tmp_path / "out",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["diagnostic_status"] == "completed"
    assert row["fixture_id"] == "naver-tm-detail-000001"
    assert row["category_key"] == "omega_3"
    assert row["image_sha256"] == image_sha256
    assert row["brightness_bucket"] == "dark"
    assert row["contrast_bucket"] == "low"
    assert "try_brightness_normalization" in row["suggested_preprocess_actions"]
    assert "try_contrast_autocontrast" in row["suggested_preprocess_actions"]
    assert summary["diagnostic_row_count"] == 1
    assert summary["suggested_preprocess_action_counts"]["try_contrast_autocontrast"] == 1
    serialized = json.dumps({"rows": rows, "summary": summary}, ensure_ascii=False)
    assert "image_path" not in serialized
    assert "product_dir" not in serialized
    assert str(tmp_path) not in serialized
    assert "/private/" not in serialized


def test_export_image_quality_diagnostics_filters_non_low_confidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify default diagnostics only include low-confidence OCR errors."""
    source_root = tmp_path / "source"
    image_sha256 = _write_image(
        source_root / "[오메가3]" / "제품A_12345" / "상세페이지" / "d_1.png"
    )
    monkeypatch.setenv("NAVER_TAMPERMONKEY_SOURCE_ROOT", str(source_root))
    _write_jsonl(tmp_path / "manifest.jsonl", [_manifest_row(image_sha256)])
    _write_jsonl(tmp_path / "observations.jsonl", [_observation(error_code="ocr_empty_text")])

    rows, summary = diagnostics.export_image_quality_diagnostics(
        manifest_path=tmp_path / "manifest.jsonl",
        observations_path=tmp_path / "observations.jsonl",
        output_dir=tmp_path / "out",
    )

    assert rows == []
    assert summary["target_observation_count"] == 0


def test_export_image_quality_diagnostics_rejects_raw_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify raw OCR text cannot enter diagnostic artifacts."""
    source_root = tmp_path / "source"
    image_sha256 = _write_image(
        source_root / "[오메가3]" / "제품A_12345" / "상세페이지" / "d_1.png"
    )
    monkeypatch.setenv("NAVER_TAMPERMONKEY_SOURCE_ROOT", str(source_root))
    _write_jsonl(tmp_path / "manifest.jsonl", [_manifest_row(image_sha256)])
    _write_jsonl(tmp_path / "observations.jsonl", [_observation(raw_ocr_text="do not store")])

    with pytest.raises(ValueError, match="raw_ocr_text"):
        diagnostics.export_image_quality_diagnostics(
            manifest_path=tmp_path / "manifest.jsonl",
            observations_path=tmp_path / "observations.jsonl",
            output_dir=tmp_path / "out",
        )


def test_export_image_quality_diagnostics_rejects_unsafe_manifest_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify local paths and path traversal are rejected from manifest input."""
    source_root = tmp_path / "source"
    image_sha256 = _write_image(
        source_root / "[오메가3]" / "제품A_12345" / "상세페이지" / "d_1.png"
    )
    monkeypatch.setenv("NAVER_TAMPERMONKEY_SOURCE_ROOT", str(source_root))
    row = _manifest_row(image_sha256)
    row["image_path"] = "$NAVER_TAMPERMONKEY_SOURCE_ROOT/../escape.png"
    _write_jsonl(tmp_path / "manifest.jsonl", [row])
    _write_jsonl(tmp_path / "observations.jsonl", [_observation()])

    rows, summary = diagnostics.export_image_quality_diagnostics(
        manifest_path=tmp_path / "manifest.jsonl",
        observations_path=tmp_path / "observations.jsonl",
        output_dir=tmp_path / "out",
    )

    assert rows[0]["diagnostic_status"] == "decode_error"
    assert summary["decode_error_count"] == 1
    serialized = json.dumps({"rows": rows, "summary": summary}, ensure_ascii=False)
    assert str(tmp_path) not in serialized


def test_write_outputs_writes_redacted_diagnostics(tmp_path: Path) -> None:
    """Verify output writer keeps diagnostic artifacts privacy-scannable."""
    rows = [
        {
            "schema_version": diagnostics.SCHEMA_VERSION,
            "fixture_id": "naver-tm-detail-000001",
            "provider": "paddleocr_local",
            "status": "error",
            "error_code": "ocr_low_confidence",
            "section": "detail",
            "category_key": "omega_3",
            "language_targets": ["ko"],
            "chronic_fixture_tags": [],
            "image_sha256": "a" * 64,
            "diagnostic_status": "completed",
            "suggested_preprocess_actions": ["try_ppocrv5_server_or_layout_model"],
            "raw_artifacts_stored": False,
            "raw_ocr_text_stored": False,
            "raw_provider_payload_stored": False,
            "raw_model_response_stored": False,
            "local_path_literals_stored": False,
        }
    ]
    summary = {
        "schema_version": diagnostics.SUMMARY_SCHEMA_VERSION,
        "diagnostic_row_count": 1,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }

    diagnostics._write_outputs(
        rows=rows,
        summary=summary,
        output_dir=tmp_path / "out",
        diagnostics_name=diagnostics.DEFAULT_DIAGNOSTICS_NAME,
        summary_name=diagnostics.DEFAULT_SUMMARY_NAME,
    )

    diagnostics_text = (tmp_path / "out" / diagnostics.DEFAULT_DIAGNOSTICS_NAME).read_text(
        encoding="utf-8"
    )
    summary_text = (tmp_path / "out" / diagnostics.DEFAULT_SUMMARY_NAME).read_text(encoding="utf-8")
    assert "naver-tm-detail-000001" in diagnostics_text
    assert "image_path" not in diagnostics_text
    assert str(tmp_path) not in summary_text


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
            "export_naver_tampermonkey_ocr_image_quality_diagnostics.py",
            "--manifest",
            str(tmp_path / "missing-manifest.jsonl"),
            "--observations",
            str(tmp_path / "missing-observations.jsonl"),
            "--output-dir",
            str(tmp_path / "out"),
            "--diagnostics-name",
            "../unsafe.jsonl",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        diagnostics.main()

    printed = capsys.readouterr().out
    payload = json.loads(printed)
    assert exc_info.value.code == 1
    assert payload["status"] == "error"
    assert "Traceback" not in printed
    assert str(tmp_path) not in printed
    assert "/private/" not in printed
