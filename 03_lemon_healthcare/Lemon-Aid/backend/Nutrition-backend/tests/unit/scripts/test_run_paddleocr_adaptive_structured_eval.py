"""Tests for adaptive PaddleOCR structured evaluation."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

adaptive_eval = importlib.import_module("scripts.run_paddleocr_adaptive_structured_eval")


def _write_bundle(bundle_dir: Path) -> None:
    """Write a minimal two-ingredient benchmark bundle."""
    bundle_dir.mkdir()
    (bundle_dir / "ground-truth.todo.jsonl").write_text(
        json.dumps(
            {
                "fixture_id": "fixture-1",
                "image_path": "image.jpg",
                "ready_for_benchmark_after_review": True,
                "expected": {
                    "ingredients": [
                        {"display_name": "Vitamin C", "amount": "100", "unit": "mg"},
                        {"display_name": "Vitamin D", "amount": "200", "unit": "mcg"},
                    ]
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _ready_row(fixture_id: str) -> dict[str, Any]:
    """Build one ready benchmark row for selector tests."""
    return {
        "fixture_id": fixture_id,
        "image_path": f"{fixture_id}.jpg",
        "ready_for_benchmark_after_review": True,
        "expected": {"ingredients": []},
    }


def test_selected_ready_rows_filters_fixture_ids_before_limit() -> None:
    """Verify explicit fixture selection is deterministic and limit applies last."""
    rows = [_ready_row(f"fixture-{index}") for index in range(5)]

    selected = adaptive_eval._selected_ready_rows(
        rows,
        fixture_ids=["fixture-3", "fixture-1"],
        shard_index=None,
        num_shards=None,
        limit=1,
    )

    assert [row["fixture_id"] for row in selected] == ["fixture-1"]


def test_selected_ready_rows_shards_by_stable_fixture_hash() -> None:
    """Verify shard selection is stable and covers each fixture once."""
    rows = [_ready_row(f"fixture-{index}") for index in range(12)]

    shards = [
        adaptive_eval._selected_ready_rows(
            rows,
            fixture_ids=None,
            shard_index=shard_index,
            num_shards=4,
            limit=None,
        )
        for shard_index in range(4)
    ]

    flattened = [row["fixture_id"] for shard in shards for row in shard]
    assert set(flattened) == {row["fixture_id"] for row in rows}
    assert len(flattened) == len(set(flattened))


def test_selected_ready_rows_rejects_inconsistent_shard_args() -> None:
    """Verify invalid shard options fail before a long A100 job starts."""
    rows = [_ready_row("fixture-1")]

    try:
        adaptive_eval._selected_ready_rows(
            rows,
            fixture_ids=None,
            shard_index=0,
            num_shards=None,
            limit=None,
        )
    except ValueError as exc:
        assert "provided together" in str(exc)
    else:  # pragma: no cover - explicit assertion branch
        raise AssertionError("expected ValueError")


def test_adaptive_union_improves_ingredient_recall_without_raw_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Verify union merge can lift recall and keeps normal artifacts redacted."""
    bundle_dir = tmp_path / "bundle"
    output_dir = tmp_path / "out"
    splits = tmp_path / "splits.jsonl"
    _write_bundle(bundle_dir)
    splits.write_text(
        json.dumps({"fixture_id": "fixture-1", "split": "holdout"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    def fake_build_ocr(**kwargs: Any) -> dict[str, Any]:
        return {"rec_model_dir": kwargs["rec_model_dir"]}

    def fake_predict_lines(ocr: dict[str, Any], _: Path) -> list[str]:
        if ocr["rec_model_dir"] == "primary-dir":
            return ["Vitamin C 100 mg"]
        return ["Vitamin D 200 mcg"]

    monkeypatch.setattr(adaptive_eval, "_build_ocr", fake_build_ocr)
    monkeypatch.setattr(adaptive_eval, "_predict_lines", fake_predict_lines)
    args = argparse.Namespace(
        bundle_dir=bundle_dir,
        splits=splits,
        output_dir=output_dir,
        profile="server_detection",
        primary_name="b128",
        primary_rec_model_dir="primary-dir",
        secondary_name="b64",
        secondary_rec_model_dir="secondary-dir",
        det_model=None,
        rec_model=None,
        max_side=None,
        det_box_thresh=None,
        det_thresh=None,
        det_unclip_ratio=2.5,
        roi_crop_preset="none",
        ocr_pass_preset="single",
        post_pass="ingredient_alias_amount_unit",
        eval_split="holdout",
        provider="paddleocr_local",
        target_threshold="0.90",
        min_ingredient_recall="0.85",
        min_fixtures=1,
        limit=None,
        raw_debug_dir=None,
        apply=True,
    )

    result = adaptive_eval.run_adaptive_eval(args)

    by_strategy = {item["strategy"]: item for item in result["strategy_summaries"]}
    assert by_strategy["b128"]["metrics"]["ingredient_recall"] == 0.5
    assert by_strategy["union"]["metrics"]["ingredient_recall"] == 1.0
    assert by_strategy["evidence_union"]["metrics"]["ingredient_recall"] == 1.0
    assert result["ingredient_recall_improved_by_union"] is True
    assert result["ingredient_recall_improved_by_evidence_union"] is True
    assert (output_dir / "line-comparison-hardcases.redacted.json").is_file()
    assert "Vitamin C" not in json.dumps(result, ensure_ascii=False)
    assert "Vitamin D" not in (output_dir / "paddleocr-adaptive-eval.union.json").read_text(
        encoding="utf-8"
    )


def test_section_aware_roi_crop_preset_creates_temporary_variants(tmp_path: Path) -> None:
    """Verify section-aware ROI creates only temporary crop candidates."""
    image_path = tmp_path / "label.jpg"
    temp_dir = tmp_path / "temp-crops"
    temp_dir.mkdir()
    Image.new("RGB", (320, 640), color="white").save(image_path)

    variants = adaptive_eval._crop_variants(
        image_path,
        fixture_id="fixture/with unsafe chars",
        temp_dir=temp_dir,
        preset="section_aware",
    )

    assert variants[0] == image_path
    assert len(variants) > len(
        adaptive_eval._crop_variants(
            image_path, fixture_id="fixture", temp_dir=temp_dir, preset="vertical3_lr2"
        )
    )
    assert all(path == image_path or path.parent == temp_dir for path in variants)
    assert all("/" not in path.name for path in variants[1:])


def test_section_aware_v2_roi_crop_preset_adds_recall_variants(tmp_path: Path) -> None:
    """Verify section-aware v2 adds recall-first crops without persisting them."""
    image_path = tmp_path / "label.jpg"
    temp_dir = tmp_path / "temp-crops"
    temp_dir.mkdir()
    Image.new("RGB", (360, 720), color="white").save(image_path)

    section_aware = adaptive_eval._crop_variants(
        image_path,
        fixture_id="fixture",
        temp_dir=temp_dir,
        preset="section_aware",
    )
    section_aware_v2 = adaptive_eval._crop_variants(
        image_path,
        fixture_id="fixture",
        temp_dir=temp_dir,
        preset="section_aware_v2",
    )

    assert section_aware_v2[0] == image_path
    assert len(section_aware_v2) > len(section_aware)
    assert all(path == image_path or path.parent == temp_dir for path in section_aware_v2)


def test_section_aware_v3_roi_crop_preset_adds_detector_led_candidates(tmp_path: Path) -> None:
    """Verify section-aware v3 adds more section-targeted crop candidates."""
    image_path = tmp_path / "label.jpg"
    temp_dir = tmp_path / "temp-crops"
    temp_dir.mkdir()
    Image.new("RGB", (420, 840), color="white").save(image_path)

    section_aware_v2 = adaptive_eval._crop_variants(
        image_path,
        fixture_id="fixture",
        temp_dir=temp_dir,
        preset="section_aware_v2",
    )
    section_aware_v3 = adaptive_eval._crop_variants(
        image_path,
        fixture_id="fixture",
        temp_dir=temp_dir,
        preset="section_aware_v3",
    )

    assert section_aware_v3[0] == image_path
    assert len(section_aware_v3) > len(section_aware_v2)
    assert any(path.name.endswith(".facts_core_table.jpg") for path in section_aware_v3)
    assert any(path.name.endswith(".other_ingredients_band.jpg") for path in section_aware_v3)


def test_section_aware_v4_roi_crop_preset_adds_table_row_candidates(tmp_path: Path) -> None:
    """Verify section-aware v4 adds dense facts-table crop candidates."""
    image_path = tmp_path / "label.jpg"
    temp_dir = tmp_path / "temp-crops"
    temp_dir.mkdir()
    Image.new("RGB", (420, 840), color="white").save(image_path)

    vertical3_lr2 = adaptive_eval._crop_variants(
        image_path,
        fixture_id="fixture",
        temp_dir=temp_dir,
        preset="vertical3_lr2",
    )
    section_aware_v4 = adaptive_eval._crop_variants(
        image_path,
        fixture_id="fixture",
        temp_dir=temp_dir,
        preset="section_aware_v4",
    )

    assert section_aware_v4[0] == image_path
    assert len(section_aware_v4) > len(vertical3_lr2)
    assert any(path.name.endswith(".facts_row_strip_upper.jpg") for path in section_aware_v4)
    assert any(path.name.endswith(".facts_amount_right_column.jpg") for path in section_aware_v4)


def test_section_aware_v5_roi_crop_preset_adds_pairing_candidates(tmp_path: Path) -> None:
    """Verify section-aware v5 adds row/column pairing crops beyond v4."""
    image_path = tmp_path / "label.jpg"
    temp_dir = tmp_path / "temp-crops"
    temp_dir.mkdir()
    Image.new("RGB", (420, 840), color="white").save(image_path)

    section_aware_v4 = adaptive_eval._crop_variants(
        image_path,
        fixture_id="fixture",
        temp_dir=temp_dir,
        preset="section_aware_v4",
    )
    section_aware_v5 = adaptive_eval._crop_variants(
        image_path,
        fixture_id="fixture",
        temp_dir=temp_dir,
        preset="section_aware_v5",
    )

    assert section_aware_v5[0] == image_path
    assert len(section_aware_v5) > len(section_aware_v4)
    assert any(path.name.endswith(".facts_table_name_amount_pair.jpg") for path in section_aware_v5)
    assert any(path.name.endswith(".facts_table_right_dv_col.jpg") for path in section_aware_v5)


def test_section_aware_v6_roi_crop_preset_adds_micro_row_candidates(tmp_path: Path) -> None:
    """Verify section-aware v6 adds narrow row-pairing candidates beyond v5."""
    image_path = tmp_path / "label.jpg"
    temp_dir = tmp_path / "temp-crops"
    temp_dir.mkdir()
    Image.new("RGB", (420, 840), color="white").save(image_path)

    section_aware_v5 = adaptive_eval._crop_variants(
        image_path,
        fixture_id="fixture",
        temp_dir=temp_dir,
        preset="section_aware_v5",
    )
    section_aware_v6 = adaptive_eval._crop_variants(
        image_path,
        fixture_id="fixture",
        temp_dir=temp_dir,
        preset="section_aware_v6",
    )

    assert section_aware_v6[0] == image_path
    assert len(section_aware_v6) > len(section_aware_v5)
    assert any(path.name.endswith(".facts_row_micro_03.jpg") for path in section_aware_v6)
    assert any(
        path.name.endswith(".facts_name_amount_center_pair.jpg") for path in section_aware_v6
    )


def test_section_aware_v7_roi_crop_preset_adds_dense_hardcase_candidates(tmp_path: Path) -> None:
    """Verify section-aware v7 adds dense row and declaration crops beyond v6."""
    image_path = tmp_path / "label.jpg"
    temp_dir = tmp_path / "temp-crops"
    temp_dir.mkdir()
    Image.new("RGB", (420, 840), color="white").save(image_path)

    section_aware_v6 = adaptive_eval._crop_variants(
        image_path,
        fixture_id="fixture",
        temp_dir=temp_dir,
        preset="section_aware_v6",
    )
    section_aware_v7 = adaptive_eval._crop_variants(
        image_path,
        fixture_id="fixture",
        temp_dir=temp_dir,
        preset="section_aware_v7",
    )

    assert section_aware_v7[0] == image_path
    assert len(section_aware_v7) > len(section_aware_v6)
    assert any(path.name.endswith(".facts_ultra_row_03.jpg") for path in section_aware_v7)
    assert any(
        path.name.endswith(".other_ingredients_low_band_dense.jpg") for path in section_aware_v7
    )


def test_recall_precision_ocr_pass_preset_builds_multi_pass_configs() -> None:
    """Verify OCR multi-pass config keeps default pass plus recall/precision probes."""
    args = argparse.Namespace(
        det_box_thresh=0.4,
        det_thresh=0.3,
        det_unclip_ratio=3.0,
        ocr_pass_preset="recall_precision_v1",
    )

    pass_configs = adaptive_eval._ocr_pass_configs(args)

    assert [item.name for item in pass_configs] == ["base", "recall_low_box", "precision_high_box"]
    assert pass_configs[1].det_box_thresh == 0.25
    assert pass_configs[1].det_thresh == 0.15
    assert pass_configs[1].det_unclip_ratio == 3.5
    assert pass_configs[2].det_box_thresh == 0.65


def test_ingredient_evidence_lines_fuses_split_amount_unit_windows() -> None:
    """Verify evidence merge joins visible split ingredient and amount lines."""
    evidence = adaptive_eval._ingredient_evidence_lines(
        [
            "Supplement Facts",
            "Vitamin C",
            "1OO",
            "m g",
            "100 %",
        ]
    )

    normalized = [adaptive_eval._normalize_for_metric(line) for line in evidence]
    assert any("vitaminc1oomg" in line for line in normalized)


def test_ingredient_evidence_lines_fuses_nearby_name_and_amount_rows() -> None:
    """Verify evidence merge handles table headers between name and amount."""
    evidence = adaptive_eval._ingredient_evidence_lines(
        [
            "Supplement Facts",
            "Vitamin",
            "C",
            "% Daily Value",
            "100 mg",
            "Zinc",
            "15 mg",
        ]
    )

    normalized = [adaptive_eval._normalize_for_metric(line) for line in evidence]
    assert any("vitaminc" in line for line in normalized)
    assert any("vitamincdailyvalue100mg" in line for line in normalized)
    assert any("zinc15mg" in line for line in normalized)


def test_ingredient_evidence_lines_fuses_nearby_name_amount_and_daily_value_rows() -> None:
    """Verify evidence merge keeps visible %DV with split facts-table rows."""
    evidence = adaptive_eval._ingredient_evidence_lines(
        [
            "Supplement Facts",
            "Vitamin B6",
            "Amount Per Serving",
            "10.5 mg",
            "618%",
            "Magnesium",
            "450 mg",
            "107%",
        ]
    )

    normalized = [adaptive_eval._normalize_for_metric(line) for line in evidence]
    assert any("vitaminb6105mg618" in line for line in normalized)
    assert any("magnesium450mg107" in line for line in normalized)


def test_ingredient_evidence_lines_strips_headers_from_split_compound_rows() -> None:
    """Verify evidence merge can remove table headers from split compound rows."""
    evidence = adaptive_eval._ingredient_evidence_lines(
        [
            "Supplement Facts",
            "Pyridoxine",
            "HCI",
            "% Daily Value",
            "10.5",
            "mg",
        ]
    )

    normalized = [adaptive_eval._normalize_for_metric(line) for line in evidence]
    assert any("pyridoxinehci105mg" in line for line in normalized)


def test_ingredient_evidence_lines_fuses_amount_only_and_unit_only_rows() -> None:
    """Verify evidence merge pairs nearby names with split amount/unit rows."""
    evidence = adaptive_eval._ingredient_evidence_lines(
        [
            "Supplement Facts",
            "Pantothenic Acid",
            "10",
            "mg",
            "Choline",
            "55",
            "mg",
        ]
    )

    normalized = [adaptive_eval._normalize_for_metric(line) for line in evidence]
    assert any("pantothenicacid10mg" in line for line in normalized)
    assert any("choline55mg" in line for line in normalized)


def test_ingredient_evidence_lines_fuses_unit_then_amount_rows() -> None:
    """Verify evidence merge pairs split amount/unit rows even when OCR order flips."""
    evidence = adaptive_eval._ingredient_evidence_lines(
        [
            "Supplement Facts",
            "Magnesium",
            "mg",
            "450",
            "Vitamin B6",
            "mg",
            "10.5",
        ]
    )

    normalized = [adaptive_eval._normalize_for_metric(line) for line in evidence]
    assert any("magnesium450mg" in line or "magnesiummg450" in line for line in normalized)
    assert any("vitaminb6105mg" in line or "vitaminb6mg105" in line for line in normalized)


def test_declaration_evidence_fuses_wrapped_korean_ingredient_names() -> None:
    """Verify declaration headers recover wrapped name-only ingredient evidence."""
    evidence, records = adaptive_eval._ingredient_evidence_lines_with_records(
        [
            "원재료명",
            "비타민",
            "D",
            "구연산",
            "아연",
            "섭취 방법",
            "1일 1회",
        ]
    )

    normalized = [adaptive_eval._normalize_for_metric(line) for line in evidence]
    assert any("비타민d구연산아연" in line for line in normalized)
    assert any(
        record["accept_reason"] == "declaration_header_continuation_window" for record in records
    )


def test_declaration_evidence_stops_before_next_english_section() -> None:
    """Verify declaration evidence does not merge directions/warnings text."""
    windows = adaptive_eval._declaration_continuation_windows(
        [
            "Other Ingredients: Gelatin",
            "Capsule",
            "Rice flour",
            "Directions",
            "Take one capsule daily",
        ],
        0,
    )

    normalized = [adaptive_eval._normalize_for_metric(line) for line in windows]
    assert any("gelatincapsulericeflour" in line for line in normalized)
    assert not any("directions" in line for line in normalized)
    assert not any("takeonecapsule" in line for line in normalized)


def test_ingredient_evidence_records_are_redacted() -> None:
    """Verify evidence-level merge emits hashes and reasons, not raw OCR text."""
    evidence, records = adaptive_eval._ingredient_evidence_lines_with_records(
        [
            "Supplement Facts",
            "Magnesium",
            "200",
            "mg",
        ]
    )

    assert any("Magnesium" in line for line in evidence)
    assert records
    assert all(record["raw_text_stored"] is False for record in records)
    assert "Magnesium" not in json.dumps(records, ensure_ascii=False)
    assert {record["accept_reason"] for record in records}


def test_raw_debug_uses_roi_variants_and_evidence_only_when_requested(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Verify raw hard-case debug includes ROI evidence only in debug output."""
    bundle_dir = tmp_path / "bundle"
    output_dir = tmp_path / "out"
    raw_debug_dir = tmp_path / "raw-debug"
    splits = tmp_path / "splits.jsonl"
    bundle_dir.mkdir()
    Image.new("RGB", (360, 720), color="white").save(bundle_dir / "image.jpg")
    bundle_row = {
        "fixture_id": "fixture-debug",
        "image_path": "image.jpg",
        "ready_for_benchmark_after_review": True,
        "expected": {
            "ingredients": [
                {"display_name": "Vitamin C", "amount": "100", "unit": "mg"},
            ]
        },
    }
    (bundle_dir / "ground-truth.todo.jsonl").write_text(
        json.dumps(bundle_row, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    splits.write_text(
        json.dumps({"fixture_id": "fixture-debug", "split": "holdout"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    def fake_build_ocr(**kwargs: Any) -> dict[str, Any]:
        return {"rec_model_dir": kwargs["rec_model_dir"]}

    def fake_predict_lines(ocr: dict[str, Any], image_path: Path) -> list[str]:
        if ocr["rec_model_dir"] == "primary-dir":
            return []
        if image_path.name.endswith(".facts_left_column60.jpg"):
            return ["Supplement Facts", "Vitamin", "C", "100 mg"]
        return []

    monkeypatch.setattr(adaptive_eval, "_build_ocr", fake_build_ocr)
    monkeypatch.setattr(adaptive_eval, "_predict_lines", fake_predict_lines)
    args = argparse.Namespace(
        bundle_dir=bundle_dir,
        splits=splits,
        output_dir=output_dir,
        profile="server_detection",
        primary_name="b128",
        primary_rec_model_dir="primary-dir",
        secondary_name="b64",
        secondary_rec_model_dir="secondary-dir",
        det_model=None,
        rec_model=None,
        max_side=None,
        det_box_thresh=None,
        det_thresh=None,
        det_unclip_ratio=3.0,
        roi_crop_preset="section_aware_v2",
        ocr_pass_preset="single",
        post_pass="ingredient_alias_amount_unit",
        eval_split="holdout",
        provider="paddleocr_local",
        target_threshold="0.90",
        min_ingredient_recall="0.85",
        min_fixtures=1,
        limit=None,
        raw_debug_dir=raw_debug_dir,
        apply=True,
    )

    result = adaptive_eval.run_adaptive_eval(args)

    debug_payload = json.loads((raw_debug_dir / "fixture-debug.json").read_text(encoding="utf-8"))
    assert result["raw_debug_dir_written"] is True
    assert debug_payload["schema_version"] == "paddleocr-raw-line-debug-v2"
    assert (
        debug_payload["warning"] == "temporary operator-only raw OCR debug artifact; do not commit"
    )
    assert debug_payload["variant_line_counts"][1]["candidate"] == "b64"
    assert any(
        variant["variant_name"].endswith(".facts_left_column60.jpg") and variant["line_count"] == 4
        for variant in debug_payload["variant_line_counts"][1]["variants"]
    )
    assert any(
        "Vitamin C" in line or "Vitamin C 100 mg" in line
        for line in debug_payload["evidence_union_lines"]
    )
    assert "Vitamin C" not in (output_dir / "line-comparison-hardcases.redacted.json").read_text(
        encoding="utf-8"
    )
