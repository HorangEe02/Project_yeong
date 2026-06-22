"""Tests for merging redacted OCR observations into DB-labeling staging rows."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import merge_naver_tampermonkey_ocr_observations_into_db_staging as merger


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL test rows."""
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _staging_row(**overrides: object) -> dict[str, object]:
    """Return a minimal DB-labeling staging row."""
    row: dict[str, object] = {
        "schema_version": "naver-tampermonkey-db-labeling-staging-v1",
        "fixture_id": "naver-tm-detail-000001",
        "source": "naver_tampermonkey",
        "section": "detail",
        "image_root_token": "$NAVER_TAMPERMONKEY_SOURCE_ROOT",
        "image_ref_hash": "b" * 64,
        "image_sha256": "a" * 64,
        "product_dir_hash": "c" * 64,
        "category_key": "omega_3",
        "language_targets": ["en", "ko"],
        "contains_personal_data": False,
        "pii_screening_status": "not_required_detail_page",
        "external_transfer_allowed": True,
        "local_processing_allowed": True,
        "requires_human_review": True,
    }
    row.update(overrides)
    return row


def _observation_row(**overrides: object) -> dict[str, object]:
    """Return a minimal redacted observation row."""
    row: dict[str, object] = {
        "fixture_id": "naver-tm-detail-000001",
        "provider": "paddleocr_local",
        "status": "completed",
        "text_non_empty": True,
        "parser_success": True,
        "char_count": 182,
        "line_count": 12,
        "latency_ms": 1234.5,
        "text_hash": "abc123",
        "llm_parse_status": "completed",
        "llm_parse_attempt_count": 2,
        "llm_parse_retry_count": 1,
        "llm_parsed_ingredients": [
            {
                "display_name": "오메가3",
                "nutrient_code": "omega_3",
                "amount": 1000,
                "unit": "mg",
                "confidence": 0.92,
                "source": "ollama_structured",
            }
        ],
    }
    row.update(overrides)
    return row


def test_merge_carries_only_redacted_ocr_and_llm_fields(tmp_path: Path) -> None:
    """Verify OCR/Ollama summaries are merged without raw text or path literals."""
    staging_path = tmp_path / "staging.jsonl"
    observations_path = tmp_path / "observations.jsonl"
    _write_jsonl(staging_path, [_staging_row()])
    _write_jsonl(observations_path, [_observation_row()])

    rows, summary = merger.merge_staging_with_observations(
        staging_path=staging_path,
        observation_paths=[observations_path],
    )

    assert summary["matched_observation_count"] == 1
    assert summary["rows_with_llm_ingredients"] == 1
    assert rows[0]["schema_version"] == merger.SCHEMA_VERSION
    assert rows[0]["ocr_observation_count"] == 1
    observation = rows[0]["ocr_observation_summaries"][0]  # type: ignore[index]
    assert observation["provider"] == "paddleocr_local"
    assert observation["llm_parse_attempt_count"] == 2
    assert observation["llm_parse_retry_count"] == 1
    assert observation["llm_parsed_ingredient_count"] == 1
    assert observation["llm_parsed_ingredients"] == [
        {
            "display_name": "오메가3",
            "nutrient_code": "omega_3",
            "amount": 1000.0,
            "unit": "mg",
            "confidence": 0.92,
            "source": "ollama_structured",
        }
    ]
    serialized = json.dumps(rows, ensure_ascii=False).lower()
    assert "raw_ocr_text" not in serialized
    assert "provider_payload" not in serialized
    assert "/volumes/" not in serialized


def test_merge_rejects_raw_observation_fields(tmp_path: Path) -> None:
    """Verify raw OCR fields cannot enter merged DB staging."""
    staging_path = tmp_path / "staging.jsonl"
    observations_path = tmp_path / "observations.jsonl"
    _write_jsonl(staging_path, [_staging_row()])
    _write_jsonl(observations_path, [_observation_row(raw_ocr_text="do not merge")])

    with pytest.raises(ValueError, match="raw_ocr_text"):
        merger.merge_staging_with_observations(
            staging_path=staging_path,
            observation_paths=[observations_path],
        )


def test_merge_rejects_local_path_literals(tmp_path: Path) -> None:
    """Verify local model/media path literals cannot enter merged staging."""
    staging_path = tmp_path / "staging.jsonl"
    observations_path = tmp_path / "observations.jsonl"
    _write_jsonl(staging_path, [_staging_row()])
    _write_jsonl(
        observations_path,
        [
            _observation_row(
                llm_parsed_ingredients=[
                    {
                        "display_name": "/Volumes/Corsair EX400U Media/.ollama/models",
                        "source": "ollama_structured",
                    }
                ]
            )
        ],
    )

    with pytest.raises(ValueError, match="local path literal"):
        merger.merge_staging_with_observations(
            staging_path=staging_path,
            observation_paths=[observations_path],
        )


def test_merge_rejects_unmatched_observations_by_default(tmp_path: Path) -> None:
    """Verify cross-manifest observation rows fail closed."""
    staging_path = tmp_path / "staging.jsonl"
    observations_path = tmp_path / "observations.jsonl"
    _write_jsonl(staging_path, [_staging_row()])
    _write_jsonl(observations_path, [_observation_row(fixture_id="other-fixture")])

    with pytest.raises(ValueError, match="not in staging rows"):
        merger.merge_staging_with_observations(
            staging_path=staging_path,
            observation_paths=[observations_path],
        )


def test_merge_can_count_unmatched_when_explicitly_allowed(tmp_path: Path) -> None:
    """Verify operators can ignore unmatched observations with an explicit flag."""
    staging_path = tmp_path / "staging.jsonl"
    observations_path = tmp_path / "observations.jsonl"
    _write_jsonl(staging_path, [_staging_row()])
    _write_jsonl(observations_path, [_observation_row(fixture_id="other-fixture")])

    rows, summary = merger.merge_staging_with_observations(
        staging_path=staging_path,
        observation_paths=[observations_path],
        allow_unmatched_observations=True,
    )

    assert rows[0]["ocr_observation_count"] == 0
    assert summary["unmatched_observation_count"] == 1
    assert summary["matched_observation_count"] == 0


def test_merge_rejects_pii_pending_review_llm_ingredients(tmp_path: Path) -> None:
    """Verify review rows cannot carry LLM ingredients before PII clearance."""
    staging_path = tmp_path / "staging.jsonl"
    observations_path = tmp_path / "observations.jsonl"
    _write_jsonl(
        staging_path,
        [
            _staging_row(
                section="review",
                contains_personal_data=None,
                pii_screening_status="pending_local_screening",
                external_transfer_allowed=False,
            )
        ],
    )
    _write_jsonl(observations_path, [_observation_row()])

    with pytest.raises(ValueError, match="PII-pending review"):
        merger.merge_staging_with_observations(
            staging_path=staging_path,
            observation_paths=[observations_path],
        )


def test_merge_preserves_review_pii_flags_without_llm_ingredients(tmp_path: Path) -> None:
    """Verify review PII screening flags can be carried as bounded tokens."""
    staging_path = tmp_path / "staging.jsonl"
    observations_path = tmp_path / "observations.jsonl"
    _write_jsonl(
        staging_path,
        [
            _staging_row(
                section="review",
                contains_personal_data=None,
                pii_screening_status="pending_local_screening",
                external_transfer_allowed=False,
            )
        ],
    )
    _write_jsonl(
        observations_path,
        [
            _observation_row(
                llm_parse_status="skipped_pii_screening_required",
                llm_parsed_ingredients=[],
                pii_candidate_flags=["address_candidate"],
            )
        ],
    )

    rows, _summary = merger.merge_staging_with_observations(
        staging_path=staging_path,
        observation_paths=[observations_path],
    )

    observation = rows[0]["ocr_observation_summaries"][0]  # type: ignore[index]
    assert observation["pii_candidate_flags"] == ["address_candidate"]
    assert "llm_parsed_ingredients" not in observation


def test_merge_main_error_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI failures print a redacted JSON summary instead of traceback paths."""
    missing_staging = tmp_path / "missing-staging.jsonl"
    missing_observation = tmp_path / "missing-observations.jsonl"
    output_path = tmp_path / "merged.jsonl"
    monkeypatch.setattr(
        "sys.argv",
        [
            "merge_naver_tampermonkey_ocr_observations_into_db_staging.py",
            "--staging",
            str(missing_staging),
            "--observations",
            str(missing_observation),
            "--output",
            str(output_path),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        merger.main()

    assert exc_info.value.code == 1
    stdout = capsys.readouterr().out
    summary = json.loads(stdout)
    assert summary["status"] == "error"
    assert summary["error_message"] == "Local file operation failed."
    assert str(tmp_path) not in stdout
    assert "/private/" not in stdout
