"""Tests for review PII screening model suggestion export."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts import export_naver_tampermonkey_review_pii_screening_suggestions as exporter


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL rows."""
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _manifest_row() -> dict[str, object]:
    """Return one local-only review PII screening row."""
    return {
        "schema_version": "naver-tampermonkey-review-pii-screening-manifest-v1",
        "fixture_id": "naver-tm-review-pii-000001",
        "source": "naver_tampermonkey",
        "section": "review",
        "image_path": "$NAVER_TAMPERMONKEY_SOURCE_ROOT/review.jpg",
        "image_ref_hash": "a" * 64,
        "category_key": "omega_3",
        "contains_personal_data": None,
        "pii_screening_status": "pending_local_screening",
        "external_transfer_allowed": False,
        "local_processing_allowed": True,
        "operator_decision_required": True,
    }


def _suggestion(**overrides: object) -> dict[str, object]:
    """Return one model-generated PII screening suggestion row."""
    suggestion: dict[str, object] = {
        "model_id": "gemma4:e4b",
        "generated_at": "2026-05-24T16:00:00+09:00",
        "status_suggestion": "needs_operator_review",
        "confidence_bucket": "low",
        "evidence_codes": ["local_model_uncertain"],
        "reason_codes": ["operator_required"],
    }
    suggestion.update(overrides)
    return {
        "fixture_id": "naver-tm-review-pii-000001",
        "pii_screening_suggestion": suggestion,
    }


def test_export_review_pii_screening_suggestions_is_non_importable(tmp_path: Path) -> None:
    """Verify model suggestions stay separate from operator decisions."""
    manifest_path = tmp_path / "manifest.jsonl"
    suggestions_path = tmp_path / "suggestions.jsonl"
    _write_jsonl(manifest_path, [_manifest_row()])
    _write_jsonl(suggestions_path, [_suggestion()])

    rows, summary = exporter.export_review_pii_screening_suggestions(
        manifest_path=manifest_path,
        suggestions_path=suggestions_path,
    )

    assert summary["exported_suggestion_count"] == 1
    assert summary["decision_importable_rows"] == 0
    assert summary["external_transfer_allowed_rows"] == 0
    row = rows[0]
    assert row["schema_version"] == exporter.SCHEMA_VERSION
    assert row["decision_importable"] is False
    assert row["operator_decision_required"] is True
    assert row["contains_personal_data"] is None
    assert row["external_transfer_allowed"] is False
    assert row["model"] == {
        "model_id": "gemma4:e4b",
        "generated_at": "2026-05-24T16:00:00+09:00",
    }
    serialized = json.dumps(row, ensure_ascii=False).lower()
    assert "image_path" not in serialized
    assert "reviewer_id" not in serialized
    assert "pii_screening_decision" not in serialized
    assert '"raw_model_response":' not in serialized
    assert "/volumes/" not in serialized


def test_export_review_pii_screening_suggestions_handles_empty_batch(tmp_path: Path) -> None:
    """Verify empty model suggestion batches leave every row pending."""
    manifest_path = tmp_path / "manifest.jsonl"
    suggestions_path = tmp_path / "suggestions.jsonl"
    _write_jsonl(manifest_path, [_manifest_row()])
    _write_jsonl(suggestions_path, [])

    rows, summary = exporter.export_review_pii_screening_suggestions(
        manifest_path=manifest_path,
        suggestions_path=suggestions_path,
    )

    assert rows == []
    assert summary["manifest_row_count"] == 1
    assert summary["suggestion_row_count"] == 0
    assert summary["pending_without_suggestion_count"] == 1
    assert summary["decision_importable_rows"] == 0


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        (
            {
                "fixture_id": "naver-tm-review-pii-000001",
                "pii_screening_decision": {"status": "cleared"},
            },
            "decision field",
        ),
        (_suggestion(reviewer_id="operator_1"), "decision field"),
        (_suggestion(status="cleared"), "decision field"),
        (_suggestion(attest_no_personal_data_visible=True), "attestation field"),
        (_suggestion(review_note="contains text"), "free-text"),
        (_suggestion(raw_model_response="secret"), "raw_model_response"),
        (_suggestion(model_id="/Volumes/Corsair/model"), "local path"),
        (_suggestion(model_id="/private/tmp/model"), "local path"),
    ],
)
def test_export_review_pii_screening_suggestions_rejects_unsafe_payloads(
    tmp_path: Path,
    payload: dict[str, object],
    match: str,
) -> None:
    """Verify suggestions cannot contain decisions, raw fields, or local paths."""
    manifest_path = tmp_path / "manifest.jsonl"
    suggestions_path = tmp_path / "suggestions.jsonl"
    _write_jsonl(manifest_path, [_manifest_row()])
    _write_jsonl(suggestions_path, [payload])

    with pytest.raises(ValueError, match=match):
        exporter.export_review_pii_screening_suggestions(
            manifest_path=manifest_path,
            suggestions_path=suggestions_path,
        )


def test_export_review_pii_screening_suggestions_rejects_unmatched_ids(tmp_path: Path) -> None:
    """Verify suggestion ids must exist in the source manifest."""
    manifest_path = tmp_path / "manifest.jsonl"
    suggestions_path = tmp_path / "suggestions.jsonl"
    unmatched = _suggestion()
    unmatched["fixture_id"] = "naver-tm-review-pii-999999"
    _write_jsonl(manifest_path, [_manifest_row()])
    _write_jsonl(suggestions_path, [unmatched])

    with pytest.raises(ValueError, match="not in manifest"):
        exporter.export_review_pii_screening_suggestions(
            manifest_path=manifest_path,
            suggestions_path=suggestions_path,
        )


def test_export_review_pii_screening_suggestions_rejects_duplicate_ids(tmp_path: Path) -> None:
    """Verify duplicate model suggestions fail closed."""
    manifest_path = tmp_path / "manifest.jsonl"
    suggestions_path = tmp_path / "suggestions.jsonl"
    _write_jsonl(manifest_path, [_manifest_row()])
    _write_jsonl(suggestions_path, [_suggestion(), _suggestion()])

    with pytest.raises(ValueError, match="Duplicate PII suggestion"):
        exporter.export_review_pii_screening_suggestions(
            manifest_path=manifest_path,
            suggestions_path=suggestions_path,
        )


def test_export_review_pii_screening_suggestions_rejects_non_object_rows_without_path_leak(
    tmp_path: Path,
) -> None:
    """Verify direct export errors do not include the input path."""
    manifest_path = tmp_path / "manifest.jsonl"
    suggestions_path = tmp_path / "suggestions.jsonl"
    manifest_path.write_text("[]\n", encoding="utf-8")
    _write_jsonl(suggestions_path, [])

    with pytest.raises(ValueError) as exc_info:
        exporter.export_review_pii_screening_suggestions(
            manifest_path=manifest_path,
            suggestions_path=suggestions_path,
        )

    assert str(tmp_path) not in str(exc_info.value)
    assert str(manifest_path) not in str(exc_info.value)
    assert str(exc_info.value) == "JSONL rows must be objects."


def test_main_error_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI failures do not print tracebacks or local paths."""
    manifest_path = tmp_path / "missing-manifest.jsonl"
    suggestions_path = tmp_path / "missing-suggestions.jsonl"
    output_path = tmp_path / "suggestions-export.jsonl"
    summary_path = tmp_path / "summary.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "export_naver_tampermonkey_review_pii_screening_suggestions.py",
            "--manifest",
            str(manifest_path),
            "--suggestions",
            str(suggestions_path),
            "--output",
            str(output_path),
            "--summary",
            str(summary_path),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        exporter.main()

    printed = capsys.readouterr().out
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert exc_info.value.code == 1
    assert "Traceback" not in printed
    assert str(tmp_path) not in printed
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)
    assert summary["status"] == "error"
    assert summary["error_code"] == "local_file_read_error"
    assert summary["error_message"] == "Local file read failed."
    assert summary["decision_importable_rows"] == 0
    assert summary["external_transfer_performed"] is False
    assert summary["local_path_literals_stored"] is False
    assert not output_path.exists()
