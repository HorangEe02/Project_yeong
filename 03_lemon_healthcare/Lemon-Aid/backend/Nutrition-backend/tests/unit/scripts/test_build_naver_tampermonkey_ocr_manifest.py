"""Tests for Naver Tampermonkey OCR manifest generation."""

from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

import pytest
from PIL import Image

from scripts import build_naver_tampermonkey_ocr_manifest as builder


def _write_image(path: Path, *, size: tuple[int, int] = (640, 480)) -> None:
    """Write a deterministic test image.

    Args:
        path: Destination path.
        size: Image size.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, "white").save(path, format="JPEG")


def _jsonl_rows(path: Path) -> list[dict[str, object]]:
    """Read JSONL rows from a test artifact."""
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def test_build_detail_manifest_normalizes_korean_paths(tmp_path: Path) -> None:
    """Verify detail images are classified through NFC-normalized path parts."""
    source_root = tmp_path / "naver"
    detail_marker = unicodedata.normalize("NFD", "상세페이지")
    review_marker = unicodedata.normalize("NFD", "리뷰")
    detail_image = (
        source_root
        / unicodedata.normalize("NFD", "[오메가3]")
        / unicodedata.normalize("NFD", "제품A_123456789")
        / detail_marker
        / "d_1.jpg"
    )
    review_image = (
        source_root
        / unicodedata.normalize("NFD", "[오메가3]")
        / unicodedata.normalize("NFD", "제품A_123456789")
        / review_marker
        / "r_1.jpg"
    )
    _write_image(detail_image)
    _write_image(review_image)

    output_dir = tmp_path / "out"
    summary = builder.build_naver_tampermonkey_manifest(
        source_root=source_root,
        output_dir=output_dir,
        manifest_name="manifest-detail.jsonl",
        inventory_name="inventory.json",
        section="detail",
        sample_size=10,
        scan_limit=20,
        seed=7,
        min_width=100,
        min_height=100,
        max_bytes=1_000_000,
    )

    assert summary["manifest_row_count"] == 1
    assert summary["manifest_name"] == "manifest-detail.jsonl"
    assert summary["inventory_name"] == "inventory.json"
    assert summary["category_labels_name"] == builder.DEFAULT_CATEGORY_LABELS_NAME
    serialized_summary = json.dumps(summary, ensure_ascii=False)
    assert str(tmp_path) not in serialized_summary
    assert "manifest" not in summary
    assert "inventory" not in summary
    assert "category_labels" not in summary
    rows = _jsonl_rows(output_dir / "manifest-detail.jsonl")
    assert len(rows) == 1
    row = rows[0]
    assert row["fixture_id"] == "naver-tm-detail-000001"
    assert row["section"] == "detail"
    assert row["category"] == "[오메가3]"
    assert row["product_id"] == "123456789"
    assert str(row["image_path"]).startswith("$NAVER_TAMPERMONKEY_SOURCE_ROOT/")
    assert str(source_root) not in str(row["image_path"])
    assert row["contains_personal_data"] is False
    assert row["external_transfer_allowed"] is True
    assert row["fixture_labels"]["supplement_category"]["category_key"] == "omega_3"
    assert row["fixture_labels"]["language_targets"] == ["en", "ko"]
    assert "cardiovascular" in row["db_labeling"]["chronic_fixture_tags"]
    assert row["db_labeling"]["status"] == "pending_human_review"
    assert row["expected"] == {}
    dumped = json.dumps(row, ensure_ascii=False)
    assert "raw_ocr_text" not in dumped
    assert "provider_payload" not in dumped

    inventory = json.loads((output_dir / "inventory.json").read_text(encoding="utf-8"))
    assert inventory["section_counts"]["detail"] == 1
    assert inventory["section_counts"]["review"] == 1
    assert inventory["category_count"] == 1
    assert inventory["product_dir_count"] == 1
    assert inventory["category_label_count"] == 1
    assert inventory["category_label_key_counts"] == {"omega_3": 1}
    assert inventory["raw_ocr_text_stored"] is False

    category_labels = json.loads((output_dir / "category-labels.json").read_text(encoding="utf-8"))
    assert category_labels["label_source"] == "tampermonkey_folder_name"
    assert category_labels["labels"][0]["category_key"] == "omega_3"
    assert category_labels["labels"][0]["candidate_count"] == 2


def test_review_manifest_defaults_to_local_pii_screening(tmp_path: Path) -> None:
    """Verify review images can be emitted for local-only PII screening."""
    source_root = tmp_path / "naver"
    review_image = source_root / "[비타민C]" / "제품B_99999" / "리뷰" / "r_1.jpg"
    _write_image(review_image)
    output_dir = tmp_path / "out"

    builder.build_naver_tampermonkey_manifest(
        source_root=source_root,
        output_dir=output_dir,
        manifest_name="manifest-review.jsonl",
        inventory_name="inventory.json",
        section="review",
        sample_size=1,
        scan_limit=10,
        seed=1,
        min_width=100,
        min_height=100,
        max_bytes=1_000_000,
    )

    rows = _jsonl_rows(output_dir / "manifest-review.jsonl")
    assert rows[0]["section"] == "review"
    assert rows[0]["contains_personal_data"] is None
    assert rows[0]["pii_screening_status"] == "pending_local_screening"
    assert rows[0]["external_transfer_allowed"] is False
    assert rows[0]["local_processing_allowed"] is True


def test_review_manifest_marks_external_transfer_disallowed_when_cleared(
    tmp_path: Path,
) -> None:
    """Verify cleared review rows are local-only by default."""
    source_root = tmp_path / "naver"
    review_image = source_root / "[비타민C]" / "제품B_99999" / "리뷰" / "r_1.jpg"
    _write_image(review_image)
    output_dir = tmp_path / "out"

    builder.build_naver_tampermonkey_manifest(
        source_root=source_root,
        output_dir=output_dir,
        manifest_name="manifest-review.jsonl",
        inventory_name="inventory.json",
        section="review",
        sample_size=1,
        scan_limit=10,
        seed=1,
        min_width=100,
        min_height=100,
        max_bytes=1_000_000,
        review_personal_data_cleared=True,
    )

    rows = _jsonl_rows(output_dir / "manifest-review.jsonl")
    assert rows[0]["section"] == "review"
    assert rows[0]["contains_personal_data"] is False
    assert rows[0]["pii_screening_status"] == "operator_cleared_review_local_only"
    assert rows[0]["external_transfer_allowed"] is False


def test_reject_raw_fields_blocks_forbidden_keys() -> None:
    """Verify generated helper rejects forbidden raw payload fields."""
    with pytest.raises(ValueError, match="raw_ocr_text"):
        builder._reject_raw_fields({"nested": {"raw_ocr_text": "do not store"}})
    with pytest.raises(ValueError, match="local path"):
        builder._reject_unsafe_payload({"image_path": "/private/tmp/raw.jpg"})


def test_output_names_must_be_filenames(tmp_path: Path) -> None:
    """Verify output names cannot escape the requested output directory."""
    source_root = tmp_path / "naver"
    detail_image = source_root / "[오메가3]" / "제품A_123456789" / "상세페이지" / "d_1.jpg"
    _write_image(detail_image)

    with pytest.raises(ValueError, match="manifest_name"):
        builder.build_naver_tampermonkey_manifest(
            source_root=source_root,
            output_dir=tmp_path / "out",
            manifest_name="../manifest-detail.jsonl",
            inventory_name="inventory.json",
            section="detail",
            sample_size=1,
            scan_limit=10,
            seed=1,
            min_width=100,
            min_height=100,
            max_bytes=1_000_000,
        )

    with pytest.raises(ValueError, match="inventory_name"):
        builder.build_naver_tampermonkey_manifest(
            source_root=source_root,
            output_dir=tmp_path / "out",
            manifest_name="manifest-detail.jsonl",
            inventory_name="nested/inventory.json",
            section="detail",
            sample_size=1,
            scan_limit=10,
            seed=1,
            min_width=100,
            min_height=100,
            max_bytes=1_000_000,
        )

    with pytest.raises(ValueError, match="category_labels_name"):
        builder.build_naver_tampermonkey_manifest(
            source_root=source_root,
            output_dir=tmp_path / "out",
            manifest_name="manifest-detail.jsonl",
            inventory_name="inventory.json",
            category_labels_name="nested/category-labels.json",
            section="detail",
            sample_size=1,
            scan_limit=10,
            seed=1,
            min_width=100,
            min_height=100,
            max_bytes=1_000_000,
        )


def test_missing_source_root_error_does_not_include_path(tmp_path: Path) -> None:
    """Verify direct validation errors avoid local source path literals."""
    source_root = tmp_path / "missing-source"

    with pytest.raises(ValueError) as exc_info:
        builder.build_naver_tampermonkey_manifest(
            source_root=source_root,
            output_dir=tmp_path / "out",
            manifest_name="manifest-detail.jsonl",
            inventory_name="inventory.json",
            section="detail",
            sample_size=1,
            scan_limit=10,
            seed=1,
            min_width=100,
            min_height=100,
            max_bytes=1_000_000,
        )

    assert str(tmp_path) not in str(exc_info.value)


def test_main_error_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI failures write redacted inventory without traceback or local paths."""
    source_root = tmp_path / "missing-source"
    output_dir = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_naver_tampermonkey_ocr_manifest.py",
            "--source-root",
            str(source_root),
            "--output-dir",
            str(output_dir),
            "--inventory-name",
            "../unsafe-inventory.json",
            "--manifest-name",
            "manifest-detail.jsonl",
            "--section",
            "detail",
            "--sample-size",
            "1",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        builder.main()

    printed = capsys.readouterr().out
    summary_path = output_dir / builder.DEFAULT_INVENTORY_NAME
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert exc_info.value.code == 1
    assert "Traceback" not in printed
    assert str(tmp_path) not in printed
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)
    assert summary["status"] == "error"
    assert summary["error_code"] == "validation_error"
    assert summary["inventory_name"] == builder.DEFAULT_INVENTORY_NAME
    assert summary["raw_ocr_text_stored"] is False
    assert summary["local_path_literals_stored"] is False


def test_unknown_category_gets_stable_folder_only_db_label(tmp_path: Path) -> None:
    """Verify unmapped folders still become DB-labelable fixture categories."""
    source_root = tmp_path / "naver"
    detail_image = source_root / "[미확인_성분]" / "제품C_12345" / "상세페이지" / "d_1.jpg"
    _write_image(detail_image)
    output_dir = tmp_path / "out"

    summary = builder.build_naver_tampermonkey_manifest(
        source_root=source_root,
        output_dir=output_dir,
        manifest_name="manifest-detail.jsonl",
        inventory_name="inventory.json",
        section="detail",
        sample_size=1,
        scan_limit=10,
        seed=1,
        min_width=100,
        min_height=100,
        max_bytes=1_000_000,
    )

    rows = _jsonl_rows(output_dir / "manifest-detail.jsonl")
    label = rows[0]["fixture_labels"]["supplement_category"]
    assert str(label["category_key"]).startswith("unmapped_tampermonkey_")
    assert label["display_name_ko"] == "미확인_성분"
    assert label["requires_human_review"] is True
    assert rows[0]["db_labeling"]["normalized_folder_label"] == "미확인_성분"
    assert summary["unmapped_category_count"] == 1


def test_custom_category_taxonomy_path_maps_folder_alias(tmp_path: Path) -> None:
    """Verify operator-provided taxonomy can add new category fixtures."""
    source_root = tmp_path / "naver"
    detail_image = source_root / "[크롬_혈당]" / "제품D_12345" / "상세페이지" / "d_1.jpg"
    _write_image(detail_image)
    taxonomy_path = tmp_path / "taxonomy.json"
    taxonomy_path.write_text(
        json.dumps(
            {
                "schema_version": "test-taxonomy-v1",
                "categories": {
                    "chromium": {
                        "display_name_ko": "크롬",
                        "display_name_en": "Chromium",
                        "folder_aliases": ["크롬_혈당"],
                        "condition_tags": ["diabetes"],
                        "caution_tags": ["kidney_disease_review"],
                        "source_urls": [
                            "https://ods.od.nih.gov/factsheets/Chromium-HealthProfessional/"
                        ],
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    builder.build_naver_tampermonkey_manifest(
        source_root=source_root,
        output_dir=tmp_path / "out",
        manifest_name="manifest-detail.jsonl",
        inventory_name="inventory.json",
        category_taxonomy_path=taxonomy_path,
        section="detail",
        sample_size=1,
        scan_limit=10,
        seed=1,
        min_width=100,
        min_height=100,
        max_bytes=1_000_000,
    )

    rows = _jsonl_rows(tmp_path / "out" / "manifest-detail.jsonl")
    assert rows[0]["db_labeling"]["category_key"] == "chromium"
    assert rows[0]["db_labeling"]["chronic_fixture_tags"] == ["diabetes"]


def test_invalid_image_root_env_var_is_rejected(tmp_path: Path) -> None:
    """Verify image root token names must not be arbitrary shell text."""
    source_root = tmp_path / "naver"
    detail_image = source_root / "[오메가3]" / "제품A_123456789" / "상세페이지" / "d_1.jpg"
    _write_image(detail_image)

    with pytest.raises(ValueError, match="image_root_env_var"):
        builder.build_naver_tampermonkey_manifest(
            source_root=source_root,
            output_dir=tmp_path / "out",
            manifest_name="manifest-detail.jsonl",
            inventory_name="inventory.json",
            image_root_env_var="bad/value",
            section="detail",
            sample_size=1,
            scan_limit=10,
            seed=1,
            min_width=100,
            min_height=100,
            max_bytes=1_000_000,
        )
