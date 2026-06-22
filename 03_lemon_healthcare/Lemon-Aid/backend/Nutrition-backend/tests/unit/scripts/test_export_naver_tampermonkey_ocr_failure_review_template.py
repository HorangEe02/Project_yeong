"""Tests for exporting Tampermonkey OCR failure review queues."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts import export_naver_tampermonkey_ocr_failure_review_template as exporter


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL rows for tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _manifest_row(fixture_id: str = "naver-tm-detail-000001") -> dict[str, object]:
    """Return a safe batch manifest row."""
    return {
        "fixture_id": fixture_id,
        "section": "detail",
        "image_path": "$NAVER_TAMPERMONKEY_SOURCE_ROOT/[오메가3]/sample/detail.jpg",
        "contains_personal_data": False,
        "external_transfer_allowed": True,
        "db_labeling": {
            "category_key": "omega_3",
            "language_targets": ["ko", "en"],
            "chronic_fixture_tags": ["cardiovascular"],
        },
    }


def _write_batch_report(batch_dir: Path, manifest_name: str = "tm-batch-001.jsonl") -> None:
    """Write a minimal provider comparison report."""
    payload = {
        "manifest_name": manifest_name,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    batch_dir.mkdir(parents=True, exist_ok=True)
    (batch_dir / "naver-ocr-provider-comparison.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def test_export_failure_review_template_joins_manifest_metadata(tmp_path: Path) -> None:
    """Verify OCR and LLM failures become redacted review rows."""
    batch_dir = tmp_path / "batches"
    _write_jsonl(
        batch_dir / "tm-batch-001.jsonl",
        [
            _manifest_row("naver-tm-detail-000001"),
            _manifest_row("naver-tm-detail-000002"),
            _manifest_row("naver-tm-detail-000003"),
        ],
    )
    runner_root = tmp_path / "runner"
    batch_output = runner_root / "batch-run-001"
    _write_batch_report(batch_output)
    _write_jsonl(
        batch_output / exporter.OBSERVATION_RELATIVE_PATH,
        [
            {
                "fixture_id": "naver-tm-detail-000001",
                "provider": "paddleocr_local",
                "status": "error",
                "error_code": "ocr_low_confidence",
            },
            {
                "fixture_id": "naver-tm-detail-000002",
                "provider": "paddleocr_local",
                "status": "completed",
                "llm_parse_status": "error",
                "llm_parse_error_code": "ollama_structured_output",
            },
            {
                "fixture_id": "naver-tm-detail-000003",
                "provider": "paddleocr_local",
                "status": "completed",
                "llm_parse_status": "completed",
            },
        ],
    )

    rows, summary = exporter.export_failure_review_template(
        batch_dir=batch_dir,
        runner_output_root=runner_root,
        output_dir=tmp_path / "out",
    )

    assert len(rows) == 2
    assert rows[0]["failure_kind"] == "ocr_error"
    assert rows[0]["category_key"] == "omega_3"
    assert rows[0]["suggested_next_action"] == "inspect_image_quality_or_preprocess"
    assert rows[1]["failure_kind"] == "llm_parse_error"
    assert rows[1]["suggested_next_action"] == "retry_structured_parser_or_schema_prompt"
    assert summary["review_row_count"] == 2
    assert summary["failure_kind_counts"] == {"llm_parse_error": 1, "ocr_error": 1}
    serialized = json.dumps({"rows": rows, "summary": summary}, ensure_ascii=False)
    assert str(tmp_path) not in serialized
    assert "/private/" not in serialized
    assert "do not store" not in serialized


def test_export_failure_review_template_rejects_raw_observation(tmp_path: Path) -> None:
    """Verify raw OCR fields are rejected before review export."""
    batch_dir = tmp_path / "batches"
    _write_jsonl(batch_dir / "tm-batch-001.jsonl", [_manifest_row()])
    batch_output = tmp_path / "runner" / "batch-run-001"
    _write_batch_report(batch_output)
    _write_jsonl(
        batch_output / exporter.OBSERVATION_RELATIVE_PATH,
        [
            {
                "fixture_id": "naver-tm-detail-000001",
                "provider": "paddleocr_local",
                "status": "error",
                "raw_ocr_text": "do not store",
            }
        ],
    )

    with pytest.raises(ValueError, match="raw_ocr_text"):
        exporter.export_failure_review_template(
            batch_dir=batch_dir,
            runner_output_root=tmp_path / "runner",
            output_dir=tmp_path / "out",
        )


def test_export_failure_review_template_rejects_local_path_manifest(tmp_path: Path) -> None:
    """Verify local path literals are rejected from manifest metadata."""
    batch_dir = tmp_path / "batches"
    row = _manifest_row()
    row["image_path"] = "/Volumes/private/detail.jpg"
    _write_jsonl(batch_dir / "tm-batch-001.jsonl", [row])

    with pytest.raises(ValueError, match="local path"):
        exporter.export_failure_review_template(
            batch_dir=batch_dir,
            runner_output_root=tmp_path / "runner",
            output_dir=tmp_path / "out",
        )


def test_write_outputs_writes_redacted_files(tmp_path: Path) -> None:
    """Verify output JSONL and summary are written without path literals."""
    rows = [
        {
            "schema_version": exporter.SCHEMA_VERSION,
            "review_task_id": "a" * 64,
            "fixture_id": "naver-tm-detail-000001",
            "batch_name": "tm-batch-001.jsonl",
            "batch_output_name": "batch-run-001",
            "provider": "paddleocr_local",
            "section": "detail",
            "category_key": "omega_3",
            "language_targets": ["ko"],
            "chronic_fixture_tags": [],
            "failure_kind": "ocr_error",
            "status": "error",
            "error_code": "ocr_low_confidence",
            "llm_parse_status": None,
            "llm_parse_error_code": None,
            "suggested_next_action": "inspect_image_quality_or_preprocess",
            "requires_human_review": True,
            "raw_artifacts_stored": False,
            "raw_ocr_text_stored": False,
            "raw_provider_payload_stored": False,
            "raw_model_response_stored": False,
            "local_path_literals_stored": False,
        }
    ]
    summary = {
        "schema_version": exporter.SUMMARY_SCHEMA_VERSION,
        "review_row_count": 1,
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
        review_name=exporter.DEFAULT_REVIEW_NAME,
        summary_name=exporter.DEFAULT_SUMMARY_NAME,
    )

    review_text = (tmp_path / "out" / exporter.DEFAULT_REVIEW_NAME).read_text(encoding="utf-8")
    summary_text = (tmp_path / "out" / exporter.DEFAULT_SUMMARY_NAME).read_text(encoding="utf-8")
    assert "naver-tm-detail-000001" in review_text
    assert str(tmp_path) not in review_text
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
            "export_naver_tampermonkey_ocr_failure_review_template.py",
            "--batch-dir",
            str(tmp_path / "missing-batches"),
            "--runner-output-root",
            str(tmp_path / "missing-runner"),
            "--output-dir",
            str(tmp_path / "out"),
            "--review-name",
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
