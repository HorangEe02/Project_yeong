"""Tests for applying review PII screening decisions."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from scripts import apply_naver_tampermonkey_review_pii_screening_decisions as applier


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL rows."""
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _manifest_row(
    image_path: str = "$NAVER_TAMPERMONKEY_SOURCE_ROOT/review.jpg",
) -> dict[str, object]:
    """Return a local-only review PII screening manifest row."""
    return {
        "schema_version": "naver-tampermonkey-review-pii-screening-manifest-v1",
        "fixture_id": "naver-tm-review-pii-000001",
        "source": "naver_tampermonkey",
        "section": "review",
        "image_path": image_path,
        "image_ref_hash": "a" * 64,
        "category_key": "omega_3",
        "category_display": {"ko": "오메가3", "en": "Omega-3"},
        "product": {"product_id": "12345", "product_dir_hash": "b" * 64},
        "contains_personal_data": None,
        "pii_screening_status": "pending_local_screening",
        "external_transfer_allowed": False,
        "local_processing_allowed": True,
        "operator_decision_required": True,
    }


def _decision(status: str = "cleared", **overrides: object) -> dict[str, object]:
    """Return one PII screening decision row."""
    decision: dict[str, object] = {
        "status": status,
        "reviewer_id": "operator_1",
        "reviewed_at": "2026-05-24T15:00:00+09:00",
    }
    if status == "cleared":
        decision.update(
            {
                "attest_local_screening_completed": True,
                "attest_no_personal_data_visible": True,
                "attest_no_raw_text_copied": True,
            }
        )
    else:
        decision["reason_codes"] = ["personal_data_visible"]
    decision.update(overrides)
    return {
        "fixture_id": "naver-tm-review-pii-000001",
        "pii_screening_decision": decision,
    }


def test_apply_pii_screening_decisions_exports_only_cleared_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify cleared review rows become local-only OCR manifest rows."""
    image = tmp_path / "source" / "review.jpg"
    image.parent.mkdir()
    image.write_bytes(b"review-image")
    monkeypatch.setenv("NAVER_TAMPERMONKEY_SOURCE_ROOT", str(image.parent))
    manifest_path = tmp_path / "manifest.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(manifest_path, [_manifest_row()])
    _write_jsonl(decisions_path, [_decision()])

    rows, summary = applier.apply_pii_screening_decisions(
        manifest_path=manifest_path,
        decisions_path=decisions_path,
    )

    assert summary["cleared_row_count"] == 1
    assert summary["external_transfer_allowed_rows"] == 0
    assert rows[0]["schema_version"] == applier.OUTPUT_SCHEMA_VERSION
    assert rows[0]["contains_personal_data"] is False
    assert rows[0]["pii_screening_status"] == "operator_cleared_review_local_only"
    assert rows[0]["external_transfer_allowed"] is False
    assert rows[0]["image_sha256"] == hashlib.sha256(b"review-image").hexdigest()
    serialized = json.dumps(rows, ensure_ascii=False).lower()
    assert '"raw_ocr_text"' not in serialized
    assert '"/volumes/' not in serialized
    assert '"product_dir":' not in serialized


def test_apply_pii_screening_decisions_skips_non_cleared_rows(tmp_path: Path) -> None:
    """Verify visible personal data decisions are not exported."""
    manifest_path = tmp_path / "manifest.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(manifest_path, [_manifest_row()])
    _write_jsonl(decisions_path, [_decision(status="contains_personal_data")])

    rows, summary = applier.apply_pii_screening_decisions(
        manifest_path=manifest_path,
        decisions_path=decisions_path,
    )

    assert rows == []
    assert summary["status_counts"] == {"contains_personal_data": 1}
    assert summary["cleared_row_count"] == 0


def test_apply_pii_screening_decisions_rejects_unsafe_decisions(tmp_path: Path) -> None:
    """Verify raw fields, local paths, notes, and unknown keys fail closed."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_jsonl(manifest_path, [_manifest_row()])
    for payload, match in [
        (_decision(raw_ocr_text="secret"), "raw_ocr_text"),
        (_decision(review_note="free text"), "free-text"),
        (_decision(reviewer_id="/Volumes/Corsair/user"), "local path"),
        (_decision(reviewer_id="/private/tmp/user"), "local path"),
        (_decision(reviewer_id="ollama_gemma4"), "operator_ prefix"),
        (_decision(extracted_name="홍길동"), "unsupported field"),
    ]:
        decisions_path = tmp_path / f"{match}.jsonl"
        _write_jsonl(decisions_path, [payload])
        with pytest.raises(ValueError, match=match):
            applier.apply_pii_screening_decisions(
                manifest_path=manifest_path,
                decisions_path=decisions_path,
            )


def test_apply_pii_screening_decisions_requires_cleared_attestations(
    tmp_path: Path,
) -> None:
    """Verify cleared rows need every no-PII attestation."""
    manifest_path = tmp_path / "manifest.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(manifest_path, [_manifest_row()])
    _write_jsonl(decisions_path, [_decision(attest_no_personal_data_visible=False)])

    with pytest.raises(ValueError, match="attest_no_personal_data_visible"):
        applier.apply_pii_screening_decisions(
            manifest_path=manifest_path,
            decisions_path=decisions_path,
        )


def test_apply_pii_screening_decisions_requires_token_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify cleared rows cannot resolve local images without an env root."""
    monkeypatch.delenv("NAVER_TAMPERMONKEY_SOURCE_ROOT", raising=False)
    manifest_path = tmp_path / "manifest.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(manifest_path, [_manifest_row()])
    _write_jsonl(decisions_path, [_decision()])

    with pytest.raises(ValueError, match="env is not set"):
        applier.apply_pii_screening_decisions(
            manifest_path=manifest_path,
            decisions_path=decisions_path,
        )


def test_apply_pii_screening_decisions_requires_reviewed_when_strict(tmp_path: Path) -> None:
    """Verify strict mode fails when rows remain pending."""
    manifest_path = tmp_path / "manifest.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(manifest_path, [_manifest_row()])
    _write_jsonl(decisions_path, [])

    with pytest.raises(ValueError, match="every row"):
        applier.apply_pii_screening_decisions(
            manifest_path=manifest_path,
            decisions_path=decisions_path,
            require_all_reviewed=True,
        )


def test_apply_pii_screening_decisions_rejects_unmatched_decisions(tmp_path: Path) -> None:
    """Verify decision rows must match the PII manifest."""
    manifest_path = tmp_path / "manifest.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    unmatched = _decision()
    unmatched["fixture_id"] = "naver-tm-review-pii-999999"
    _write_jsonl(manifest_path, [_manifest_row()])
    _write_jsonl(decisions_path, [unmatched])

    with pytest.raises(ValueError, match="not in manifest"):
        applier.apply_pii_screening_decisions(
            manifest_path=manifest_path,
            decisions_path=decisions_path,
        )


def test_apply_pii_screening_decisions_rejects_duplicate_decisions(tmp_path: Path) -> None:
    """Verify duplicate decision rows fail closed."""
    manifest_path = tmp_path / "manifest.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(manifest_path, [_manifest_row()])
    _write_jsonl(decisions_path, [_decision(), _decision()])

    with pytest.raises(ValueError, match="Duplicate PII decision"):
        applier.apply_pii_screening_decisions(
            manifest_path=manifest_path,
            decisions_path=decisions_path,
        )


def test_apply_pii_screening_decisions_rejects_non_object_rows_without_path_leak(
    tmp_path: Path,
) -> None:
    """Verify direct decision-apply errors do not include the input path."""
    manifest_path = tmp_path / "manifest.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    manifest_path.write_text("[]\n", encoding="utf-8")
    _write_jsonl(decisions_path, [])

    with pytest.raises(ValueError) as exc_info:
        applier.apply_pii_screening_decisions(
            manifest_path=manifest_path,
            decisions_path=decisions_path,
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
    decisions_path = tmp_path / "missing-decisions.jsonl"
    output_path = tmp_path / "cleared.jsonl"
    summary_path = tmp_path / "summary.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "apply_naver_tampermonkey_review_pii_screening_decisions.py",
            "--manifest",
            str(manifest_path),
            "--decisions",
            str(decisions_path),
            "--output",
            str(output_path),
            "--summary",
            str(summary_path),
            "--require-all-reviewed",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        applier.main()

    printed = capsys.readouterr().out
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert exc_info.value.code == 1
    assert "Traceback" not in printed
    assert str(tmp_path) not in printed
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)
    assert summary["status"] == "error"
    assert summary["error_code"] == "local_file_read_error"
    assert summary["error_message"] == "Local file read failed."
    assert summary["require_all_reviewed"] is True
    assert summary["db_write_performed"] is False
    assert summary["external_transfer_performed"] is False
    assert summary["local_path_literals_stored"] is False
    assert not output_path.exists()
