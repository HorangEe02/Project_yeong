"""Tests for supplement brand review template export."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

staging = importlib.import_module("scripts.build_supplement_taxonomy_db_staging")
exporter = importlib.import_module("scripts.export_supplement_brand_review_template")


def _touch(path: Path) -> None:
    """Create a placeholder image-like file.

    Args:
        path: File path to create.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"placeholder")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSON object rows as JSONL.

    Args:
        path: Destination path.
        rows: JSON object rows.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _staging_rows(tmp_path: Path) -> list[dict[str, object]]:
    """Build taxonomy staging rows for tests.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Staging rows.
    """
    root = tmp_path / "crawling-image"
    _touch(root / "[오메가3]" / "나우푸드 오메가3_123456" / "리뷰" / "review.jpg")
    _touch(root / "[비타민C]" / "고려은단 비타민C_789012" / "상세페이지" / "detail.png")
    return staging.build_taxonomy_staging_rows(root=root, source_run_id="brand-review-test")


def test_export_brand_review_template_filters_brand_candidates(tmp_path: Path) -> None:
    """Verify only review-gated brand candidates are exported."""
    staging_path = tmp_path / "taxonomy.jsonl"
    _write_jsonl(staging_path, _staging_rows(tmp_path))

    rows, summary = exporter.export_brand_review_template(
        taxonomy_staging=staging_path,
        source_run_id="brand-review-test",
    )

    assert len(rows) == 2
    assert summary["template_row_count"] == 2
    assert summary["skip_reason_counts"] == {"not_product_brand_candidate": 2}
    assert {row["category_key"] for row in rows} == {"비타민c", "오메가3"}
    assert all(row["schema_version"] == exporter.ROW_SCHEMA_VERSION for row in rows)
    assert all(row["approved_for_db_write"] is False for row in rows)
    assert all(row["operator_decision_required"] is True for row in rows)
    assert all(
        row["decision_stub"]["schema_version"] == exporter.DECISION_SCHEMA_VERSION for row in rows
    )


def test_export_brand_review_template_omits_product_literals_and_paths(tmp_path: Path) -> None:
    """Verify template output does not expose product folder literals or paths."""
    product_literal = "나우푸드 오메가3_123456"
    staging_path = tmp_path / "taxonomy.jsonl"
    _write_jsonl(staging_path, _staging_rows(tmp_path))

    rows, summary = exporter.export_brand_review_template(taxonomy_staging=staging_path)
    dumped = json.dumps({"rows": rows, "summary": summary}, ensure_ascii=False)

    assert product_literal not in dumped
    assert str(tmp_path) not in dumped
    assert "/private/" not in dumped
    assert "/Volumes/" not in dumped
    assert '"raw_ocr_text":' not in dumped
    assert '"provider_payload":' not in dumped
    assert summary["product_dir_literals_stored"] is False
    assert summary["absolute_paths_stored"] is False


def test_export_brand_review_template_rejects_raw_keys(tmp_path: Path) -> None:
    """Verify raw OCR/provider fields cannot enter the template."""
    staging_path = tmp_path / "taxonomy.jsonl"
    rows = _staging_rows(tmp_path)
    rows[1]["raw_ocr_text"] = "do not emit"
    _write_jsonl(staging_path, rows)

    with pytest.raises(ValueError, match="raw_ocr_text"):
        exporter.export_brand_review_template(taxonomy_staging=staging_path)


def test_main_writes_jsonl_and_redacted_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI writes safe template rows and summary."""
    staging_path = tmp_path / "taxonomy.jsonl"
    output_path = tmp_path / "out" / "brand-review.jsonl"
    _write_jsonl(staging_path, _staging_rows(tmp_path))

    exporter.main(["--taxonomy-staging", str(staging_path), "--output", str(output_path)])

    stdout = capsys.readouterr().out
    summary = json.loads(stdout)
    assert summary["template_row_count"] == 2
    assert output_path.exists()
    assert output_path.with_suffix(".jsonl.summary.json").exists()
    assert str(tmp_path) not in stdout
    assert "/private/" not in stdout
