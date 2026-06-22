"""Tests for exporting retry manifests from reconciled OCR failures."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts import export_naver_tampermonkey_reconciled_failure_retry_manifest as exporter


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL rows for tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _manifest_row(fixture_id: str = "naver-tm-detail-000001") -> dict[str, object]:
    """Return a safe Tampermonkey manifest row."""
    return {
        "fixture_id": fixture_id,
        "source": "naver_tampermonkey",
        "section": "detail",
        "image_path": "$NAVER_TAMPERMONKEY_SOURCE_ROOT/[오메가3]/sample/detail.jpg",
        "contains_personal_data": False,
        "external_transfer_allowed": True,
        "db_labeling": {
            "category_key": "omega_3",
            "language_targets": ["ko", "en"],
            "chronic_fixture_tags": ["cardiovascular"],
            "source_urls": ["https://ods.od.nih.gov/factsheets/list-all/"],
        },
    }


def _observation(
    fixture_id: str = "naver-tm-detail-000001",
    *,
    status: str = "error",
    error_code: str | None = "ocr_low_confidence",
    llm_parse_status: str | None = None,
    llm_parse_error_code: str | None = None,
) -> dict[str, object]:
    """Return a redacted reconciled observation row."""
    row: dict[str, object] = {
        "fixture_id": fixture_id,
        "provider": "paddleocr_local",
        "status": status,
        "text_non_empty": status == "completed",
        "parser_success": status == "completed",
    }
    if error_code is not None:
        row["error_code"] = error_code
    if llm_parse_status is not None:
        row["llm_parse_status"] = llm_parse_status
    if llm_parse_error_code is not None:
        row["llm_parse_error_code"] = llm_parse_error_code
    return row


def test_export_retry_manifest_from_reconciled_ocr_errors(tmp_path: Path) -> None:
    """Verify remaining OCR errors become collector-compatible retry rows."""
    manifest = tmp_path / "manifest.jsonl"
    observations = tmp_path / "reconciled.jsonl"
    _write_jsonl(
        manifest,
        [
            _manifest_row("naver-tm-detail-000001"),
            _manifest_row("naver-tm-detail-000002"),
        ],
    )
    _write_jsonl(
        observations,
        [
            _observation("naver-tm-detail-000001"),
            _observation("naver-tm-detail-000002", status="completed", error_code=None),
        ],
    )

    rows, summary = exporter.export_retry_manifest(
        manifest_path=manifest,
        observations_path=observations,
        output_dir=tmp_path / "out",
        failure_kind="ocr_error",
    )

    assert [row["fixture_id"] for row in rows] == ["naver-tm-detail-000001"]
    assert rows[0]["image_path"] == "$NAVER_TAMPERMONKEY_SOURCE_ROOT/[오메가3]/sample/detail.jpg"
    retry_metadata = rows[0]["retry_metadata"]
    assert isinstance(retry_metadata, dict)
    assert retry_metadata["failure_kind"] == "ocr_error"
    assert retry_metadata["source_error_code"] == "ocr_low_confidence"
    assert retry_metadata["suggested_next_action"] == "inspect_image_quality_or_layout_model"
    assert summary["retry_row_count"] == 1
    assert summary["failure_kind_counts"] == {"ocr_error": 1}
    assert summary["error_code_counts"] == {"ocr_low_confidence": 1}
    assert summary["category_key_counts"] == {"omega_3": 1}
    serialized = json.dumps({"rows": rows, "summary": summary}, ensure_ascii=False)
    assert str(tmp_path) not in serialized
    assert "/private/" not in serialized


def test_export_retry_manifest_from_reconciled_llm_errors(tmp_path: Path) -> None:
    """Verify LLM parse failures can be isolated after reconciliation."""
    manifest = tmp_path / "manifest.jsonl"
    observations = tmp_path / "reconciled.jsonl"
    _write_jsonl(manifest, [_manifest_row()])
    _write_jsonl(
        observations,
        [
            _observation(
                status="completed",
                error_code=None,
                llm_parse_status="error",
                llm_parse_error_code="ollama_structured_output",
            )
        ],
    )

    rows, summary = exporter.export_retry_manifest(
        manifest_path=manifest,
        observations_path=observations,
        output_dir=tmp_path / "out",
        failure_kind="llm_parse_error",
    )

    assert len(rows) == 1
    retry_metadata = rows[0]["retry_metadata"]
    assert isinstance(retry_metadata, dict)
    assert retry_metadata["failure_kind"] == "llm_parse_error"
    assert retry_metadata["source_llm_parse_error_code"] == "ollama_structured_output"
    assert retry_metadata["suggested_next_action"] == "retry_structured_parser_or_schema_prompt"
    assert summary["llm_parse_error_code_counts"] == {"ollama_structured_output": 1}


def test_export_retry_manifest_skips_missing_source_rows(tmp_path: Path) -> None:
    """Verify observations without source manifest rows are counted and skipped."""
    manifest = tmp_path / "manifest.jsonl"
    observations = tmp_path / "reconciled.jsonl"
    _write_jsonl(manifest, [_manifest_row("naver-tm-detail-000001")])
    _write_jsonl(observations, [_observation("naver-tm-detail-999999")])

    rows, summary = exporter.export_retry_manifest(
        manifest_path=manifest,
        observations_path=observations,
        output_dir=tmp_path / "out",
    )

    assert rows == []
    assert summary["retry_row_count"] == 0
    assert summary["skipped_missing_fixture_count"] == 1


def test_export_retry_manifest_rejects_raw_observation_field(tmp_path: Path) -> None:
    """Verify raw OCR fields cannot enter retry manifests."""
    manifest = tmp_path / "manifest.jsonl"
    observations = tmp_path / "reconciled.jsonl"
    _write_jsonl(manifest, [_manifest_row()])
    row = _observation()
    row["raw_ocr_text"] = "do not persist"
    _write_jsonl(observations, [row])

    with pytest.raises(ValueError, match="raw_ocr_text"):
        exporter.export_retry_manifest(
            manifest_path=manifest,
            observations_path=observations,
            output_dir=tmp_path / "out",
        )


def test_export_retry_manifest_rejects_local_path_manifest(tmp_path: Path) -> None:
    """Verify local path literals cannot enter retry manifests."""
    manifest = tmp_path / "manifest.jsonl"
    observations = tmp_path / "reconciled.jsonl"
    row = _manifest_row()
    row["image_path"] = "/Volumes/private/detail.jpg"
    _write_jsonl(manifest, [row])
    _write_jsonl(observations, [_observation()])

    with pytest.raises(ValueError, match="local path"):
        exporter.export_retry_manifest(
            manifest_path=manifest,
            observations_path=observations,
            output_dir=tmp_path / "out",
        )


def test_write_outputs_writes_redacted_files(tmp_path: Path) -> None:
    """Verify retry manifest and summary files are written safely."""
    rows = [
        {
            **_manifest_row(),
            "retry_metadata": {
                "schema_version": exporter.SCHEMA_VERSION,
                "source_fixture_id": "naver-tm-detail-000001",
                "failure_kind": "ocr_error",
                "source_status": "error",
                "source_error_code": "ocr_low_confidence",
                "source_llm_parse_status": None,
                "source_llm_parse_error_code": None,
                "suggested_next_action": "inspect_image_quality_or_layout_model",
                "raw_artifacts_stored": False,
                "raw_ocr_text_stored": False,
                "raw_provider_payload_stored": False,
                "raw_model_response_stored": False,
                "local_path_literals_stored": False,
            },
        }
    ]
    summary = {
        "schema_version": exporter.SUMMARY_SCHEMA_VERSION,
        "retry_row_count": 1,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }

    exporter._write_outputs(
        rows=rows,
        summary=summary,
        output_dir=tmp_path / "out",
        manifest_name=exporter.DEFAULT_MANIFEST_NAME,
        summary_name=exporter.DEFAULT_SUMMARY_NAME,
    )

    manifest_text = (tmp_path / "out" / exporter.DEFAULT_MANIFEST_NAME).read_text(encoding="utf-8")
    summary_text = (tmp_path / "out" / exporter.DEFAULT_SUMMARY_NAME).read_text(encoding="utf-8")
    assert "naver-tm-detail-000001" in manifest_text
    assert str(tmp_path) not in manifest_text
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
            "export_naver_tampermonkey_reconciled_failure_retry_manifest.py",
            "--manifest",
            str(tmp_path / "missing-manifest.jsonl"),
            "--observations",
            str(tmp_path / "missing-observations.jsonl"),
            "--output-dir",
            str(tmp_path / "out"),
            "--manifest-name",
            "../unsafe.jsonl",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        exporter.main()

    printed = capsys.readouterr().out
    payload = json.loads(printed)
    assert exc_info.value.code == 1
    assert payload["status"] == "error"
    assert "Traceback" not in printed
    assert str(tmp_path) not in printed
    assert "/private/" not in printed
