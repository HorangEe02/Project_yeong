"""Tests for applying human-reviewed chronic ingredient decisions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import apply_chronic_ingredient_review_decisions as applier
from scripts import validate_ground_truth


def _write_json(path: Path, payload: dict[str, object]) -> None:
    """Write one JSON object for tests."""
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL rows for tests."""
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _snapshot(**overrides: object) -> dict[str, object]:
    """Return a minimal valid V3 snapshot."""
    snapshot: dict[str, object] = {
        "schema_version": "supplement-parsed-snapshot-v3",
        "requires_user_confirmation": True,
        "source": {
            "analysis_id": None,
            "parser_schema_version": "supplement-parser-output-v2",
            "ocr_provider": "manual",
            "ocr_confidence": None,
            "layout_available": False,
            "raw_image_stored": False,
            "raw_ocr_text_stored": False,
            "raw_provider_payload_stored": False,
            "raw_model_response_stored": False,
        },
        "product": {
            "product_name": "test product",
            "manufacturer": None,
            "barcode_candidates": [],
            "evidence_refs": [],
        },
        "serving": {
            "serving_size_text": None,
            "serving_amount": None,
            "serving_unit": None,
            "daily_servings": None,
            "total_amount": None,
            "total_unit": None,
            "evidence_refs": [],
        },
        "ingredients": [
            {
                "display_name": "정x 3개입(",
                "normalized_name": "정x 3개입(",
                "amount": None,
                "unit": None,
                "nutrient_code_candidates": [],
                "confidence": 0.2,
                "source": "ocr_llm_preview",
                "evidence_refs": [],
            }
        ],
        "label_sections": [],
        "intake_method": {
            "text": None,
            "structured": {
                "frequency": "unknown",
                "times_per_day": None,
                "amount_per_time": None,
                "amount_unit": None,
                "time_of_day": [],
                "with_food": "unknown",
            },
            "evidence_refs": [],
        },
        "precautions": [],
        "functional_claims": [],
        "evidence_spans": [],
        "domain_correction_audit": [],
        "low_confidence_fields": [],
        "warnings": [
            "ground_truth_pending_human_review",
            "auto_expected_requires_human_verification",
            "category:vitamin_d",
        ],
        "chronic_disease_indications": ["osteoporosis"],
    }
    snapshot.update(overrides)
    return snapshot


def _decision(**overrides: object) -> dict[str, object]:
    """Return a valid verified chronic ingredient decision."""
    row: dict[str, object] = {
        "schema_version": "chronic-ingredient-review-decision-v1",
        "fixture_id": "naver-chronic-0001",
        "reviewer_id": "operator_1",
        "reviewed_at": "2026-05-24T14:30:00+09:00",
        "verification_status": "verified",
        "verified_ingredients": [
            {
                "display_name": "비타민 D",
                "normalized_name": "비타민 d",
                "amount": 1000,
                "unit": "IU",
            }
        ],
        "attestations": {
            "human_verified_from_local_fixture": True,
            "no_raw_ocr_text_copied": True,
            "no_provider_payload_copied": True,
            "no_secret_or_local_path_copied": True,
        },
    }
    row.update(overrides)
    return row


def test_apply_verified_decision_replaces_ingredients_and_clears_pending(
    tmp_path: Path,
) -> None:
    """Verify a human decision creates a human-labeled V3 snapshot copy."""
    expected_dir = tmp_path / "expected"
    expected_dir.mkdir()
    _write_json(expected_dir / "naver-chronic-0001.snapshot_v3.json", _snapshot())
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(decisions_path, [_decision()])

    outputs, summary = applier.apply_chronic_ingredient_review_decisions(
        expected_dir=expected_dir,
        decisions_path=decisions_path,
        output_dir=tmp_path / "verified-expected",
    )

    updated = outputs["naver-chronic-0001.snapshot_v3.json"]
    assert summary["verified_count"] == 1
    assert summary["pending_count"] == 0
    assert updated["ingredients"] == [
        {
            "display_name": "비타민 D",
            "normalized_name": "비타민 d",
            "amount": 1000,
            "unit": "IU",
            "nutrient_code_candidates": [],
            "confidence": 1.0,
            "source": "manual",
            "evidence_refs": [],
        }
    ]
    assert updated["warnings"] == ["category:vitamin_d"]
    assert validate_ground_truth._is_human_labeled(updated) is True
    serialized = json.dumps({"outputs": outputs, "summary": summary}, ensure_ascii=False).lower()
    assert '"raw_ocr_text"' not in serialized
    assert "/volumes/" not in serialized


def test_apply_rejects_review_template_rows_used_as_decisions(tmp_path: Path) -> None:
    """Verify the non-importable review template cannot be applied directly."""
    expected_dir = tmp_path / "expected"
    expected_dir.mkdir()
    _write_json(expected_dir / "naver-chronic-0001.snapshot_v3.json", _snapshot())
    decisions_path = tmp_path / "template.jsonl"
    _write_jsonl(
        decisions_path,
        [
            {
                "schema_version": "chronic-ingredient-review-template-v1",
                "fixture_id": "naver-chronic-0001",
                "requires_human_review": True,
            }
        ],
    )

    with pytest.raises(ValueError, match="chronic decision schema"):
        applier.apply_chronic_ingredient_review_decisions(
            expected_dir=expected_dir,
            decisions_path=decisions_path,
            output_dir=tmp_path / "verified-expected",
        )


@pytest.mark.parametrize(
    ("unsafe_patch", "match"),
    [
        ({"raw_ocr_text": "do not persist"}, "raw_ocr_text"),
        ({"provider_payload": {"text": "do not persist"}}, "provider_payload"),
        ({"review_note": "free text is not allowed"}, "review_note"),
        ({"fixture_id": "/Volumes/private/path"}, "local path"),
    ],
)
def test_apply_rejects_raw_fields_notes_and_local_paths(
    tmp_path: Path,
    unsafe_patch: dict[str, object],
    match: str,
) -> None:
    """Verify unsafe decision payloads fail before snapshot output."""
    expected_dir = tmp_path / "expected"
    expected_dir.mkdir()
    _write_json(expected_dir / "naver-chronic-0001.snapshot_v3.json", _snapshot())
    decisions_path = tmp_path / "unsafe.jsonl"
    _write_jsonl(decisions_path, [_decision(**unsafe_patch)])

    with pytest.raises(ValueError, match=match):
        applier.apply_chronic_ingredient_review_decisions(
            expected_dir=expected_dir,
            decisions_path=decisions_path,
            output_dir=tmp_path / "verified-expected",
        )


@pytest.mark.parametrize("reviewer_id", ["ollama_gemma4", "gemma4", "operator/secret"])
def test_apply_rejects_non_operator_reviewer_ids(
    tmp_path: Path,
    reviewer_id: str,
) -> None:
    """Verify model-only or unsafe reviewer ids are rejected."""
    expected_dir = tmp_path / "expected"
    expected_dir.mkdir()
    _write_json(expected_dir / "naver-chronic-0001.snapshot_v3.json", _snapshot())
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(decisions_path, [_decision(reviewer_id=reviewer_id)])

    with pytest.raises(ValueError, match="operator-prefixed"):
        applier.apply_chronic_ingredient_review_decisions(
            expected_dir=expected_dir,
            decisions_path=decisions_path,
            output_dir=tmp_path / "verified-expected",
        )


@pytest.mark.parametrize(
    ("status", "expected_warning"),
    [
        ("needs_changes", "human_review_needs_changes"),
        ("not_scoreable", "human_review_not_scoreable"),
    ],
)
def test_apply_non_verified_decisions_keep_snapshot_pending(
    tmp_path: Path,
    status: str,
    expected_warning: str,
) -> None:
    """Verify non-verified decisions do not become scoreable ground truth."""
    expected_dir = tmp_path / "expected"
    expected_dir.mkdir()
    _write_json(expected_dir / "naver-chronic-0001.snapshot_v3.json", _snapshot())
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(
        decisions_path,
        [
            _decision(
                verification_status=status,
                verified_ingredients=[],
                attestations={},
            )
        ],
    )

    outputs, summary = applier.apply_chronic_ingredient_review_decisions(
        expected_dir=expected_dir,
        decisions_path=decisions_path,
        output_dir=tmp_path / "verified-expected",
    )

    updated = outputs["naver-chronic-0001.snapshot_v3.json"]
    assert summary[f"{status}_count"] == 1
    assert summary["pending_count"] == 1
    assert expected_warning in updated["warnings"]
    assert validate_ground_truth._is_human_labeled(updated) is False


def test_apply_rejects_unmatched_decision_by_default(tmp_path: Path) -> None:
    """Verify fixture id mismatches fail closed."""
    expected_dir = tmp_path / "expected"
    expected_dir.mkdir()
    _write_json(expected_dir / "naver-chronic-0001.snapshot_v3.json", _snapshot())
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(decisions_path, [_decision(fixture_id="naver-chronic-9999")])

    with pytest.raises(ValueError, match="not in expected snapshots"):
        applier.apply_chronic_ingredient_review_decisions(
            expected_dir=expected_dir,
            decisions_path=decisions_path,
            output_dir=tmp_path / "verified-expected",
        )
