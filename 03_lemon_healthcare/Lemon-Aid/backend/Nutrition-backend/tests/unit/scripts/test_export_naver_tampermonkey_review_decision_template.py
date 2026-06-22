"""Tests for exporting Naver Tampermonkey review decision templates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import export_naver_tampermonkey_review_decision_template as exporter


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL test rows."""
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _review_row(**overrides: object) -> dict[str, object]:
    """Return a minimal review ingest row."""
    row: dict[str, object] = {
        "schema_version": "naver-tampermonkey-review-ingest-v1",
        "review_task_id": "d" * 64,
        "fixture_id": "naver-tm-detail-000001",
        "category_key": "omega_3",
        "category_display": {"ko": "오메가3", "en": "Omega-3"},
        "image": {"image_ref_hash": "b" * 64, "image_sha256": "a" * 64},
        "requires_human_review": True,
        "is_clinical_recommendation": False,
        "clinical_recommendation_forbidden": True,
        "ocr_observation_count": 1,
        "ingredient_candidate_count": 2,
        "ingredient_candidates": [
            {
                "display_name": "Omega-3",
                "nutrient_code": "omega_3",
                "amount": 1000.0,
                "unit": "mg",
                "confidence": 0.92,
                "source": "ollama_structured",
                "provider": "paddleocr_local",
            },
        ],
    }
    row.update(overrides)
    return row


def _gap_queue_row(**overrides: object) -> dict[str, object]:
    """Return a minimal manual-review gap queue row."""
    row: dict[str, object] = {
        "schema_version": "naver-tampermonkey-manual-review-gap-v1",
        "review_task_id": "d" * 64,
        "fixture_id": "naver-tm-detail-000001",
        "category_key": "omega_3",
        "gap_reasons": ["ingredient_candidate_count_zero"],
        "suggested_operator_actions": [
            "enter_manual_ingredients_or_mark_not_scoreable",
            "do_not_copy_ocr_output",
        ],
        "ingredient_candidate_count": 0,
        "ocr_observation_count": 1,
        "requires_human_review": True,
        "decision_batch_importable": False,
        "db_write_performed": False,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    row.update(overrides)
    return row


def test_export_review_decision_templates_with_safe_contract(
    tmp_path: Path,
) -> None:
    """Verify review templates expose required decision contract fields."""
    input_path = tmp_path / "review.jsonl"
    _write_jsonl(input_path, [_review_row()])

    rows, summary = exporter.export_review_decision_template_rows(input_path=input_path)

    assert summary["row_count"] == 1
    assert summary["rows_with_candidate_hints"] == 1
    assert summary["total_candidate_hints"] == 1
    assert summary["decision_batch_importable"] is False
    row = rows[0]
    assert row["schema_version"] == exporter.SCHEMA_VERSION
    assert "review_decision" not in row
    assert row["review_task_id"] == "d" * 64
    decision_entry_template = row["decision_entry_template"]
    assert isinstance(decision_entry_template, dict)
    assert decision_entry_template["schema_version"] == "naver-tampermonkey-review-decision-v1"
    assert decision_entry_template["review_task_id"] == "d" * 64
    assert decision_entry_template["fixture_id"] == "naver-tm-detail-000001"
    assert decision_entry_template["decision_batch_importable"] is False
    decision_stub = decision_entry_template["review_decision"]
    assert isinstance(decision_stub, dict)
    assert decision_stub["status"] is None
    assert decision_stub["reviewer_id"] is None
    assert decision_stub["reviewed_at"] is None
    assert decision_stub["display_name"] is None
    assert decision_stub["attest_pii_screening_completed"] is False
    assert decision_stub["attest_no_raw_ocr_text"] is False
    assert decision_stub["attest_not_clinical_recommendation"] is False
    assert decision_stub["ingredients"] == [
        {
            "display_name": None,
            "nutrient_code": None,
            "amount": None,
            "unit": None,
            "source": "human_reviewed",
        }
    ]
    contract = row["review_decision_contract"]
    assert isinstance(contract, dict)
    assert contract["decision_row_schema_version_required"] == (
        "naver-tampermonkey-review-decision-v1"
    )
    assert contract["reviewer_id_required_prefix"] == "operator_"
    assert contract["reviewed_at_required_format"] == "timezone_aware_iso8601"
    assert contract["approved_ingredient_display_name_max_length"] == 160
    assert contract["approved_ingredient_max_count"] == 128
    assert contract["approved_ingredient_identity_unique_by"] == [
        "normalized_display_name",
        "nutrient_code",
    ]
    assert contract["approved_ingredient_amount_type"] == "number_or_null"
    assert contract["approved_ingredient_source_required"] == "human_reviewed"
    assert contract["approved_ingredient_packaging_quantity_text_allowed"] is False
    assert contract["reviewed_text_executable_or_url_content_allowed"] is False
    assert contract["approved_attestations_required"] == [
        "attest_pii_screening_completed",
        "attest_no_raw_ocr_text",
        "attest_not_clinical_recommendation",
    ]
    assert contract["free_text_notes_allowed"] is False
    assert contract["local_path_literals_allowed"] is False
    candidates = row["candidate_context"]["ingredient_candidates"]  # type: ignore[index]
    assert candidates[0]["display_name"] == "Omega-3"
    assert candidates[0]["amount"] == 1000.0
    serialized = json.dumps(rows, ensure_ascii=False).lower()
    assert '"raw_ocr_text"' not in serialized
    assert '"provider_payload"' not in serialized
    assert "/volumes/" not in serialized


def test_export_review_decision_templates_caps_candidate_hints(
    tmp_path: Path,
) -> None:
    """Verify candidate hints are bounded and remain hints only."""
    input_path = tmp_path / "review.jsonl"
    row = _review_row(
        ingredient_candidates=[
            {"display_name": "Omega-3"},
            {"display_name": "Vitamin D"},
        ]
    )
    _write_jsonl(input_path, [row])

    rows, summary = exporter.export_review_decision_template_rows(
        input_path=input_path,
        max_candidates=1,
    )

    candidates = rows[0]["candidate_context"]["ingredient_candidates"]  # type: ignore[index]
    assert len(candidates) == 1
    assert summary["max_candidates_per_row"] == 1


def test_export_review_decision_templates_rejects_unsafe_input(
    tmp_path: Path,
) -> None:
    """Verify raw fields and local path literals cannot enter templates."""
    input_path = tmp_path / "raw.jsonl"
    _write_jsonl(input_path, [_review_row(raw_ocr_text="do not persist")])

    with pytest.raises(ValueError, match="raw_ocr_text"):
        exporter.export_review_decision_template_rows(input_path=input_path)

    local_path = tmp_path / "local.jsonl"
    _write_jsonl(
        local_path,
        [_review_row(ingredient_candidates=[{"display_name": "/Volumes/Corsair/a.jpg"}])],
    )

    with pytest.raises(ValueError, match="local path literal"):
        exporter.export_review_decision_template_rows(input_path=local_path)


@pytest.mark.parametrize(
    "display_name",
    [
        "<script>alert(1)</script>",
        "javascript:alert(1)",
        "https://example.test/product",
    ],
)
def test_export_review_decision_templates_rejects_executable_candidate_text(
    tmp_path: Path,
    display_name: str,
) -> None:
    """Verify unsafe candidate hints do not enter operator review templates."""
    input_path = tmp_path / "unsafe-candidate.jsonl"
    _write_jsonl(input_path, [_review_row(ingredient_candidates=[{"display_name": display_name}])])

    with pytest.raises(ValueError, match="executable or URL-like"):
        exporter.export_review_decision_template_rows(input_path=input_path)


def test_export_review_decision_templates_requires_human_review_rows(
    tmp_path: Path,
) -> None:
    """Verify non-reviewable or clinical rows fail closed."""
    input_path = tmp_path / "not-reviewable.jsonl"
    _write_jsonl(input_path, [_review_row(requires_human_review=False)])

    with pytest.raises(ValueError, match="require human review"):
        exporter.export_review_decision_template_rows(input_path=input_path)

    clinical_path = tmp_path / "clinical.jsonl"
    _write_jsonl(clinical_path, [_review_row(is_clinical_recommendation=True)])

    with pytest.raises(ValueError, match="clinical recommendations"):
        exporter.export_review_decision_template_rows(input_path=clinical_path)


def test_export_review_decision_templates_rejects_duplicate_review_ids(
    tmp_path: Path,
) -> None:
    """Verify duplicate review task ids fail before template export."""
    input_path = tmp_path / "review.jsonl"
    _write_jsonl(input_path, [_review_row(), _review_row()])

    with pytest.raises(ValueError, match="Duplicate review_task_id"):
        exporter.export_review_decision_template_rows(input_path=input_path)


def test_export_review_decision_templates_rejects_non_object_rows_without_path_leak(
    tmp_path: Path,
) -> None:
    """Verify direct template export errors do not include the input path."""
    input_path = tmp_path / "review.jsonl"
    input_path.write_text("[]\n", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        exporter.export_review_decision_template_rows(input_path=input_path)

    assert str(tmp_path) not in str(exc_info.value)
    assert str(input_path) not in str(exc_info.value)
    assert str(exc_info.value) == "JSONL rows must be objects."


def test_export_review_decision_templates_filters_manual_gap_queue(
    tmp_path: Path,
) -> None:
    """Verify gap queue filtering exports only manual-review gap rows."""
    input_path = tmp_path / "review.jsonl"
    gap_path = tmp_path / "gap.jsonl"
    _write_jsonl(
        input_path,
        [
            _review_row(),
            _review_row(
                review_task_id="e" * 64,
                fixture_id="naver-tm-detail-000002",
                ingredient_candidates=[{"display_name": "Vitamin D"}],
            ),
        ],
    )
    _write_jsonl(gap_path, [_gap_queue_row()])

    rows, summary = exporter.export_review_decision_template_rows(
        input_path=input_path,
        gap_queue_path=gap_path,
    )

    assert summary["row_count"] == 1
    assert summary["gap_queue_filter_applied"] is True
    assert summary["gap_queue_row_count"] == 1
    assert summary["gap_queue_name"] == "gap.jsonl"
    assert rows[0]["review_task_id"] == "d" * 64
    assert rows[0]["gap_context"] == {
        "gap_reasons": ["ingredient_candidate_count_zero"],
        "suggested_operator_actions": [
            "do_not_copy_ocr_output",
            "enter_manual_ingredients_or_mark_not_scoreable",
        ],
        "ingredient_candidate_count": 0,
        "ocr_observation_count": 1,
    }
    serialized = json.dumps(rows, ensure_ascii=False).lower()
    assert '"raw_ocr_text"' not in serialized
    assert "/volumes/" not in serialized


def test_export_review_decision_templates_rejects_unmatched_gap_queue(
    tmp_path: Path,
) -> None:
    """Verify gap queue rows must match review ingest ids."""
    input_path = tmp_path / "review.jsonl"
    gap_path = tmp_path / "gap.jsonl"
    _write_jsonl(input_path, [_review_row()])
    _write_jsonl(gap_path, [_gap_queue_row(review_task_id="e" * 64)])

    with pytest.raises(ValueError, match="not in review ingest"):
        exporter.export_review_decision_template_rows(
            input_path=input_path,
            gap_queue_path=gap_path,
        )


def test_export_review_decision_templates_rejects_unsafe_gap_queue(
    tmp_path: Path,
) -> None:
    """Verify unsafe manual gap queues cannot shape review templates."""
    input_path = tmp_path / "review.jsonl"
    gap_path = tmp_path / "gap.jsonl"
    _write_jsonl(input_path, [_review_row()])
    _write_jsonl(gap_path, [_gap_queue_row(raw_ocr_text="forbidden")])

    with pytest.raises(ValueError, match="raw_ocr_text"):
        exporter.export_review_decision_template_rows(
            input_path=input_path,
            gap_queue_path=gap_path,
        )


def test_export_review_decision_template_main_error_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI failures print a redacted JSON summary instead of traceback paths."""
    missing_input = tmp_path / "missing-review.jsonl"
    output_path = tmp_path / "template.jsonl"
    monkeypatch.setattr(
        "sys.argv",
        [
            "export_naver_tampermonkey_review_decision_template.py",
            "--input",
            str(missing_input),
            "--output",
            str(output_path),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        exporter.main()

    assert exc_info.value.code == 1
    stdout = capsys.readouterr().out
    summary = json.loads(stdout)
    assert summary["status"] == "error"
    assert summary["error_message"] == "Local file operation failed."
    assert str(tmp_path) not in stdout
    assert "/private/" not in stdout
