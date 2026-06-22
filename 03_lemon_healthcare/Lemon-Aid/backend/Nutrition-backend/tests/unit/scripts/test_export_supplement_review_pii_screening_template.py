"""Tests for supplement review-image PII screening template export."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

candidate_builder = importlib.import_module("scripts.build_supplement_learning_candidate_manifests")
template_exporter = importlib.import_module(
    "scripts.export_supplement_review_pii_screening_template"
)


def _touch_image(path: Path, content: bytes = b"review-image") -> None:
    """Create an image-like fixture file.

    Args:
        path: Target image path.
        content: File bytes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write JSONL rows.

    Args:
        path: Destination path.
        rows: Rows to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _candidate_rows(
    tmp_path: Path, *, pii_cleared: bool = False
) -> tuple[Path, list[dict[str, Any]]]:
    """Build supplement review OCR candidate rows.

    Args:
        tmp_path: Test temp directory.
        pii_cleared: Whether candidates are already PII-cleared.

    Returns:
        Source root and OCR candidate rows.
    """
    root = tmp_path / "crawling-image"
    _touch_image(root / "[오메가3]" / "나우푸드 오메가3_123456" / "리뷰" / "review.jpg")
    rows, _, _ = candidate_builder.build_learning_candidate_manifests(
        root=root,
        review_personal_data_cleared=pii_cleared,
        max_detail_per_category=0,
    )
    return root, rows


def test_export_pii_template_includes_pending_review_candidates(tmp_path: Path) -> None:
    """Verify pending review OCR candidates become local-only screening rows."""
    _, candidates = _candidate_rows(tmp_path)
    candidate_manifest = tmp_path / "candidates.jsonl"
    _write_jsonl(candidate_manifest, candidates)

    rows, summary = template_exporter.export_pii_screening_template(
        candidate_manifest=candidate_manifest,
        source_run_id="pii-template-test",
    )

    assert len(rows) == 1
    assert summary["template_row_count"] == 1
    assert summary["external_transfer_allowed_rows"] == 0
    assert summary["teacher_ocr_allowed_rows"] == 0
    row = rows[0]
    assert row["schema_version"] == template_exporter.ROW_SCHEMA_VERSION
    assert row["source_run_id"] == "pii-template-test"
    assert row["fixture_id"] == candidates[0]["fixture_id"]
    assert row["contains_personal_data"] is None
    assert row["pii_screening_status"] == "pending_local_screening"
    assert row["external_transfer_allowed"] is False
    assert row["teacher_ocr_allowed"] is False
    assert row["operator_decision_required"] is True
    assert row["decision_stub"]["pii_screening_decision"]["decision"] == ""
    assert (
        row["decision_stub"]["pii_screening_decision"]["attest_no_personal_data_visible"] is False
    )


def test_export_pii_template_materializes_relative_private_image_path(
    tmp_path: Path,
) -> None:
    """Verify optional materialization writes only relative hashed image paths."""
    source_root, candidates = _candidate_rows(tmp_path)
    candidate_manifest = tmp_path / "candidates.jsonl"
    output_path = tmp_path / "out" / "pii-template.jsonl"
    image_dir = tmp_path / "out" / "images"
    _write_jsonl(candidate_manifest, candidates)

    rows, summary = template_exporter.export_pii_screening_template(
        candidate_manifest=candidate_manifest,
        source_root=source_root,
        materialized_image_dir=image_dir,
        output_manifest_path=output_path,
    )

    assert len(rows) == 1
    assert summary["image_materialization_requested"] is True
    assert summary["image_materialized_count"] == 1
    image_path = rows[0]["image_path"]
    assert isinstance(image_path, str)
    assert image_path.startswith("images/review-ocr-gt-")
    assert "나우푸드 오메가3_123456" not in image_path
    assert str(tmp_path) not in image_path
    assert (output_path.parent / image_path).read_bytes() == b"review-image"
    assert rows[0]["image_materialization_policy"] == "private_hashed_fixture_copy_materialized"


def test_export_pii_template_skips_already_cleared_candidates(tmp_path: Path) -> None:
    """Verify already-cleared candidates are not exported for screening again."""
    _, candidates = _candidate_rows(tmp_path, pii_cleared=True)
    candidate_manifest = tmp_path / "candidates.jsonl"
    _write_jsonl(candidate_manifest, candidates)

    rows, summary = template_exporter.export_pii_screening_template(
        candidate_manifest=candidate_manifest,
    )

    assert rows == []
    assert summary["skip_reason_counts"] == {"candidate_not_pending_pii_screening": 1}


def test_export_pii_template_omits_paths_product_literals_and_raw_payloads(
    tmp_path: Path,
) -> None:
    """Verify PII screening templates stay redacted."""
    _, candidates = _candidate_rows(tmp_path)
    product_literal = "나우푸드 오메가3_123456"
    candidate_manifest = tmp_path / "candidates.jsonl"
    _write_jsonl(candidate_manifest, candidates)

    rows, summary = template_exporter.export_pii_screening_template(
        candidate_manifest=candidate_manifest,
    )
    dumped = json.dumps({"rows": rows, "summary": summary}, ensure_ascii=False)

    assert product_literal not in dumped
    assert str(tmp_path) not in dumped
    assert "/private/" not in dumped
    assert "/Volumes/" not in dumped
    assert '"raw_ocr_text":' not in dumped
    assert '"provider_payload":' not in dumped
    assert rows[0]["absolute_paths_stored"] is False
    assert rows[0]["product_dir_literals_stored"] is False
    assert summary["raw_ocr_text_stored"] is False
    assert summary["raw_provider_payload_stored"] is False


def test_export_pii_template_rejects_raw_candidate_keys(tmp_path: Path) -> None:
    """Verify raw OCR text cannot be smuggled through candidate rows."""
    _, candidates = _candidate_rows(tmp_path)
    candidates[0]["raw_ocr_text"] = "do not store"
    candidate_manifest = tmp_path / "candidates.jsonl"
    _write_jsonl(candidate_manifest, candidates)

    with pytest.raises(ValueError, match="raw_ocr_text"):
        template_exporter.export_pii_screening_template(candidate_manifest=candidate_manifest)


def test_main_writes_pii_template_and_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI writes PII screening template JSONL and summary."""
    _, candidates = _candidate_rows(tmp_path)
    candidate_manifest = tmp_path / "candidates.jsonl"
    output_path = tmp_path / "out" / "pii-template.jsonl"
    summary_path = tmp_path / "out" / "summary.json"
    _write_jsonl(candidate_manifest, candidates)

    template_exporter.main(
        [
            "--candidate-manifest",
            str(candidate_manifest),
            "--output",
            str(output_path),
            "--summary",
            str(summary_path),
            "--source-run-id",
            "pii-template-cli",
        ]
    )

    printed = capsys.readouterr().out
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert json.loads(printed)["template_row_count"] == 1
    assert summary["source_run_id"] == "pii-template-cli"
    assert summary["ocr_provider_call_performed"] is False
    assert rows[0]["operator_decision_required"] is True
    assert str(tmp_path) not in printed
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)
