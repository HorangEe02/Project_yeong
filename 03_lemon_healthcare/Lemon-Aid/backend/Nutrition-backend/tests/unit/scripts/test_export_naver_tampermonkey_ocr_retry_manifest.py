"""Tests for exporting Tampermonkey OCR retry manifests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts import export_naver_tampermonkey_ocr_retry_manifest as exporter


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


def _review_row(
    *,
    fixture_id: str = "naver-tm-detail-000001",
    review_task_id: str = "a" * 64,
    failure_kind: str = "ocr_error",
    error_code: str | None = "ocr_low_confidence",
    llm_parse_error_code: str | None = None,
    suggested_next_action: str = "inspect_image_quality_or_preprocess",
) -> dict[str, object]:
    """Return a redacted failure review row."""
    return {
        "schema_version": exporter.EXPECTED_REVIEW_SCHEMA_VERSION,
        "review_task_id": review_task_id,
        "fixture_id": fixture_id,
        "batch_name": "tm-batch-001.jsonl",
        "batch_output_name": "batch-run-001",
        "provider": "paddleocr_local",
        "section": "detail",
        "category_key": "omega_3",
        "language_targets": ["ko", "en"],
        "chronic_fixture_tags": ["cardiovascular"],
        "failure_kind": failure_kind,
        "status": "error" if failure_kind == "ocr_error" else "completed",
        "error_code": error_code,
        "llm_parse_status": "error" if failure_kind == "llm_parse_error" else None,
        "llm_parse_error_code": llm_parse_error_code,
        "suggested_next_action": suggested_next_action,
        "requires_human_review": True,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }


def test_export_retry_manifest_filters_ocr_failures(tmp_path: Path) -> None:
    """Verify OCR failures are exported as collector-compatible retry rows."""
    batch_dir = tmp_path / "batches"
    _write_jsonl(
        batch_dir / "tm-batch-001.jsonl",
        [
            _manifest_row("naver-tm-detail-000001"),
            _manifest_row("naver-tm-detail-000002"),
        ],
    )
    _write_jsonl(
        tmp_path / "review.jsonl",
        [
            _review_row(fixture_id="naver-tm-detail-000001"),
            _review_row(
                fixture_id="naver-tm-detail-000002",
                review_task_id="b" * 64,
                failure_kind="llm_parse_error",
                error_code=None,
                llm_parse_error_code="ollama_structured_output",
                suggested_next_action="retry_structured_parser_or_schema_prompt",
            ),
        ],
    )

    rows, summary = exporter.export_retry_manifest(
        batch_dir=batch_dir,
        failure_review_path=tmp_path / "review.jsonl",
        output_dir=tmp_path / "out",
        failure_kind="ocr_error",
    )

    assert [row["fixture_id"] for row in rows] == ["naver-tm-detail-000001"]
    assert rows[0]["image_path"] == "$NAVER_TAMPERMONKEY_SOURCE_ROOT/[오메가3]/sample/detail.jpg"
    assert rows[0]["retry_metadata"] == {
        "schema_version": exporter.SCHEMA_VERSION,
        "source_review_task_id": "a" * 64,
        "failure_kind": "ocr_error",
        "source_error_code": "ocr_low_confidence",
        "source_llm_parse_error_code": None,
        "suggested_next_action": "inspect_image_quality_or_preprocess",
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    assert summary["retry_row_count"] == 1
    assert summary["failure_kind_counts"] == {"ocr_error": 1}
    assert summary["category_key_counts"] == {"omega_3": 1}
    serialized = json.dumps({"rows": rows, "summary": summary}, ensure_ascii=False)
    assert str(tmp_path) not in serialized
    assert "/private/" not in serialized


def test_export_retry_manifest_filters_suggested_next_action(tmp_path: Path) -> None:
    """Verify parser retries can be separated from OCR retries."""
    batch_dir = tmp_path / "batches"
    _write_jsonl(
        batch_dir / "tm-batch-001.jsonl",
        [
            _manifest_row("naver-tm-detail-000001"),
            _manifest_row("naver-tm-detail-000002"),
        ],
    )
    _write_jsonl(
        tmp_path / "review.jsonl",
        [
            _review_row(fixture_id="naver-tm-detail-000001"),
            _review_row(
                fixture_id="naver-tm-detail-000002",
                review_task_id="b" * 64,
                failure_kind="llm_parse_error",
                error_code=None,
                llm_parse_error_code="ollama_structured_output",
                suggested_next_action="retry_structured_parser_or_schema_prompt",
            ),
        ],
    )

    rows, summary = exporter.export_retry_manifest(
        batch_dir=batch_dir,
        failure_review_path=tmp_path / "review.jsonl",
        output_dir=tmp_path / "out",
        suggested_next_actions=("retry_structured_parser_or_schema_prompt",),
    )

    assert [row["fixture_id"] for row in rows] == ["naver-tm-detail-000002"]
    retry_metadata = rows[0]["retry_metadata"]
    assert isinstance(retry_metadata, dict)
    assert retry_metadata["failure_kind"] == "llm_parse_error"
    assert retry_metadata["source_error_code"] is None
    assert retry_metadata["source_llm_parse_error_code"] == "ollama_structured_output"
    assert summary["suggested_next_action_counts"] == {
        "retry_structured_parser_or_schema_prompt": 1
    }


def test_export_retry_manifest_skips_missing_source_rows(tmp_path: Path) -> None:
    """Verify review rows without original manifest rows are counted and skipped."""
    batch_dir = tmp_path / "batches"
    _write_jsonl(batch_dir / "tm-batch-001.jsonl", [_manifest_row("naver-tm-detail-000001")])
    _write_jsonl(
        tmp_path / "review.jsonl",
        [_review_row(fixture_id="naver-tm-detail-999999")],
    )

    rows, summary = exporter.export_retry_manifest(
        batch_dir=batch_dir,
        failure_review_path=tmp_path / "review.jsonl",
        output_dir=tmp_path / "out",
    )

    assert rows == []
    assert summary["retry_row_count"] == 0
    assert summary["skipped_missing_fixture_count"] == 1


def test_export_retry_manifest_rejects_raw_review_field(tmp_path: Path) -> None:
    """Verify raw OCR fields cannot enter retry manifests."""
    batch_dir = tmp_path / "batches"
    _write_jsonl(batch_dir / "tm-batch-001.jsonl", [_manifest_row()])
    review = _review_row()
    review["raw_ocr_text"] = "do not persist"
    _write_jsonl(tmp_path / "review.jsonl", [review])

    with pytest.raises(ValueError, match="raw_ocr_text"):
        exporter.export_retry_manifest(
            batch_dir=batch_dir,
            failure_review_path=tmp_path / "review.jsonl",
            output_dir=tmp_path / "out",
        )


def test_export_retry_manifest_rejects_local_path_manifest(tmp_path: Path) -> None:
    """Verify local path literals cannot enter retry manifests."""
    batch_dir = tmp_path / "batches"
    row = _manifest_row()
    row["image_path"] = "/Volumes/private/detail.jpg"
    _write_jsonl(batch_dir / "tm-batch-001.jsonl", [row])
    _write_jsonl(tmp_path / "review.jsonl", [_review_row()])

    with pytest.raises(ValueError, match="local path"):
        exporter.export_retry_manifest(
            batch_dir=batch_dir,
            failure_review_path=tmp_path / "review.jsonl",
            output_dir=tmp_path / "out",
        )


def test_write_outputs_writes_redacted_files(tmp_path: Path) -> None:
    """Verify retry manifest and summary files are written safely."""
    rows = [
        {
            **_manifest_row(),
            "retry_metadata": {
                "schema_version": exporter.SCHEMA_VERSION,
                "source_review_task_id": "a" * 64,
                "failure_kind": "ocr_error",
                "source_error_code": "ocr_low_confidence",
                "source_llm_parse_error_code": None,
                "suggested_next_action": "inspect_image_quality_or_preprocess",
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
            "export_naver_tampermonkey_ocr_retry_manifest.py",
            "--batch-dir",
            str(tmp_path / "missing-batches"),
            "--failure-review",
            str(tmp_path / "missing-review.jsonl"),
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
