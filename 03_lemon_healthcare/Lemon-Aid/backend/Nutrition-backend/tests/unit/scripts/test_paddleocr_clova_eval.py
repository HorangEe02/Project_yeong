"""Tests for PaddleOCR structured metric post-processing."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

paddle_eval = importlib.import_module("scripts.paddleocr_clova_eval")


def test_postprocess_adds_visible_ingredient_and_unit_aliases() -> None:
    """Verify aliases are added only from visible OCR text."""
    processed, applied = paddle_eval._postprocess_hypothesis_text(
        "Supplement Facts Vitamin C 1000 mcg",
        mode=paddle_eval.POST_PASS_INGREDIENT_ALIAS_AMOUNT_UNIT,
    )

    normalized = paddle_eval._normalize_for_metric(processed)
    assert applied is True
    assert paddle_eval._normalize_for_metric("비타민 C") in normalized
    assert paddle_eval._normalize_for_metric("아스코르브산") in normalized
    assert paddle_eval._normalize_for_metric("1000 μg") in normalized
    assert paddle_eval._normalize_for_metric("1000 마이크로그램") in normalized


def test_postprocess_adds_aliases_for_glyph_confused_long_alias() -> None:
    """Verify long visible aliases tolerate bounded OCR glyph confusion before scoring."""
    processed, applied = paddle_eval._postprocess_hypothesis_text(
        "Supplement Facts Vitamln C 1000 mg",
        mode=paddle_eval.POST_PASS_INGREDIENT_ALIAS_AMOUNT_UNIT,
    )

    normalized = paddle_eval._normalize_for_metric(processed)
    assert applied is True
    assert paddle_eval._normalize_for_metric("Vitamin C") in normalized
    assert paddle_eval._normalize_for_metric("비타민 C") in normalized


def test_postprocess_does_not_confusion_expand_short_aliases() -> None:
    """Verify short aliases still require exact visibility to avoid false positives."""
    processed, applied = paddle_eval._postprocess_hypothesis_text(
        "Supplement Facts aryeon 8 mg",
        mode=paddle_eval.POST_PASS_INGREDIENT_ALIAS_AMOUNT_UNIT,
    )

    normalized = paddle_eval._normalize_for_metric(processed)
    assert applied is True
    assert paddle_eval._normalize_for_metric("아연") not in normalized


def test_ingredient_recall_accepts_bounded_hcl_hci_confusion() -> None:
    """Verify ingredient recall tolerates common HCl/HCI OCR glyph confusion."""
    expected = {"ingredients": [{"display_name": "pyridoxine HCl"}]}
    hypothesis = paddle_eval._normalize_for_metric("Supplement Facts pyridoxineHCI 10.5 mg")

    found, total = paddle_eval._ingredient_recall(expected, hypothesis)

    assert (found, total) == (1, 1)


def test_ingredient_recall_accepts_precise_compound_aliases() -> None:
    """Verify exact compound aliases recover bilingual ingredient mentions."""
    expected = {"ingredients": [{"display_name": "Magnesium Oxide"}]}
    hypothesis = paddle_eval._normalize_for_metric("성분 및 함량 산화마그네슘 450 mg")

    found, total = paddle_eval._ingredient_recall(expected, hypothesis)

    assert (found, total) == (1, 1)


def test_ingredient_recall_accepts_expanded_b_vitamin_aliases() -> None:
    """Verify expanded supplement aliases recover visible B-vitamin compounds."""
    expected = {"ingredients": [{"display_name": "Pantothenic Acid"}]}
    hypothesis = paddle_eval._normalize_for_metric("Supplement Facts calcium pantothenate 10 mg")

    found, total = paddle_eval._ingredient_recall(expected, hypothesis)

    assert (found, total) == (1, 1)


def test_postprocess_adds_visible_excipient_aliases() -> None:
    """Verify common excipient aliases are added only when source text is visible."""
    processed, applied = paddle_eval._postprocess_hypothesis_text(
        "Other Ingredients: gelatin capsule rice flour",
        mode=paddle_eval.POST_PASS_INGREDIENT_ALIAS_AMOUNT_UNIT,
    )

    normalized = paddle_eval._normalize_for_metric(processed)
    assert applied is True
    assert paddle_eval._normalize_for_metric("젤라틴 캡슐") in normalized
    assert paddle_eval._normalize_for_metric("쌀가루") in normalized
    assert paddle_eval._normalize_for_metric("마그네슘 스테아레이트") not in normalized


def test_evaluate_reports_post_pass_without_storing_raw_text(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Verify metric post-pass improves field counts without raw OCR persistence."""
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "ground-truth.todo.jsonl").write_text(
        json.dumps(
            {
                "fixture_id": "fixture-1",
                "image_path": "image.jpg",
                "ready_for_benchmark_after_review": True,
                "expected": {
                    "ingredients": [
                        {
                            "display_name": "비타민 C",
                            "amount": "1000",
                            "unit": "μg",
                        }
                    ]
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(paddle_eval, "_build_ocr", lambda **_: object())
    monkeypatch.setattr(paddle_eval, "_predict_text", lambda *_: "Vitamin C 1000 mcg")

    result = paddle_eval.evaluate(
        bundle_dir=bundle_dir,
        limit=None,
        det_model="PP-OCRv5_mobile_det",
        rec_model="korean_PP-OCRv5_mobile_rec",
        max_side=2048,
        post_pass=paddle_eval.POST_PASS_INGREDIENT_ALIAS_AMOUNT_UNIT,
    )

    assert result["field_match_ratio_macro"] == 1.0
    assert result["field_match_ratio_micro"] == 1.0
    assert result["ingredient_recall"] == 1.0
    assert result["post_pass_applied_total"] == 1
    assert "Vitamin C 1000 mcg" not in json.dumps(result, ensure_ascii=False)
