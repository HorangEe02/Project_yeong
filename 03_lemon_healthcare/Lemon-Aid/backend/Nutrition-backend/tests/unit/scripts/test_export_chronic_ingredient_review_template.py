"""Tests for chronic ingredient review template export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import export_chronic_ingredient_review_template as exporter


def _write_json(path: Path, payload: dict[str, object]) -> None:
    """Write one JSON object."""
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL rows."""
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_export_review_template_rows_requires_human_review(tmp_path: Path) -> None:
    """Verify V3 chronic snapshots become non-importable review templates."""
    expected_dir = tmp_path / "expected"
    expected_dir.mkdir()
    _write_json(
        expected_dir / "naver-chronic-0001.snapshot_v3.json",
        {
            "schema_version": "supplement-parsed-snapshot-v3",
            "verification_status": "provisional",
            "warnings": ["ground_truth_pending_human_review", "category:비타민D"],
            "chronic_disease_indications": ["osteoporosis"],
            "ingredients": [
                {
                    "display_name": "비타민 D",
                    "normalized_name": "비타민 d",
                    "amount": 1000,
                    "unit": "IU",
                    "confidence": 0.9,
                    "source": "ocr_llm_preview",
                }
            ],
        },
    )
    manifest_path = tmp_path / "manifest.jsonl"
    _write_jsonl(
        manifest_path,
        [
            {
                "fixture_id": "naver-live-0001",
                "image_path": "/tmp/not-exported.jpg",
                "observations": [
                    {
                        "provider": "paddleocr_local",
                        "status": "completed",
                        "parser_success": True,
                        "parsed_ingredients": [{"name": "비타민 D", "amount": 1000, "unit": "IU"}],
                    }
                ],
            }
        ],
    )

    rows, summary = exporter.export_review_template_rows(
        expected_dir=expected_dir,
        manifest_path=manifest_path,
    )

    assert summary["row_count"] == 1
    assert summary["pending_human_review_count"] == 1
    assert summary["decision_batch_importable"] is False
    assert summary["raw_ocr_text_stored"] is False
    row = rows[0]
    assert row["fixture_id"] == "naver-chronic-0001"
    assert row["expected_status"]["pending_human_review"] is True  # type: ignore[index]
    assert row["chronic_disease_indications"] == ["osteoporosis"]
    assert row["current_expected_ingredients"] == [
        {
            "amount": 1000,
            "confidence": 0.9,
            "display_name": "비타민 D",
            "normalized_name": "비타민 d",
            "source": "ocr_llm_preview",
            "unit": "IU",
        }
    ]
    observation_context = row["observation_context"]
    assert observation_context["providers"] == ["paddleocr_local"]  # type: ignore[index]
    assert observation_context["status_counts"] == {"completed": 1}  # type: ignore[index]
    assert observation_context["parser_success_count"] == 1  # type: ignore[index]
    assert observation_context["ingredient_hints"] == [  # type: ignore[index]
        {
            "amount": 1000,
            "display_name": "비타민 D",
            "provider": "paddleocr_local",
            "source": "ocr_regex",
            "unit": "IU",
        }
    ]
    serialized = json.dumps({"rows": rows, "summary": summary}, ensure_ascii=False)
    assert str(tmp_path) not in serialized
    assert "not-exported" not in serialized


def test_export_review_template_rejects_raw_ocr_text(tmp_path: Path) -> None:
    """Verify raw OCR text cannot enter the review template workflow."""
    expected_dir = tmp_path / "expected"
    expected_dir.mkdir()
    _write_json(
        expected_dir / "naver-chronic-0001.snapshot_v3.json",
        {"schema_version": "supplement-parsed-snapshot-v3", "ingredients": []},
    )
    manifest_path = tmp_path / "manifest.jsonl"
    _write_jsonl(
        manifest_path,
        [
            {
                "fixture_id": "naver-chronic-0001",
                "observations": [{"provider": "paddleocr_local", "raw_ocr_text": "secret"}],
            }
        ],
    )

    with pytest.raises(ValueError, match="raw_ocr_text"):
        exporter.export_review_template_rows(
            expected_dir=expected_dir,
            manifest_path=manifest_path,
        )


def test_export_review_template_rejects_local_path_ingredient(tmp_path: Path) -> None:
    """Verify path-like ingredient strings fail closed."""
    expected_dir = tmp_path / "expected"
    expected_dir.mkdir()
    _write_json(
        expected_dir / "naver-chronic-0001.snapshot_v3.json",
        {
            "schema_version": "supplement-parsed-snapshot-v3",
            "ingredients": [{"display_name": "/Volumes/private/path"}],
        },
    )

    with pytest.raises(ValueError, match="local path"):
        exporter.export_review_template_rows(expected_dir=expected_dir)


def test_export_review_template_bounds_candidate_limit(tmp_path: Path) -> None:
    """Verify candidate limit is enforced."""
    expected_dir = tmp_path / "expected"
    expected_dir.mkdir()
    _write_json(
        expected_dir / "naver-chronic-0001.snapshot_v3.json",
        {
            "schema_version": "supplement-parsed-snapshot-v3",
            "ingredients": [
                {"display_name": "A"},
                {"display_name": "B"},
            ],
        },
    )

    rows, summary = exporter.export_review_template_rows(
        expected_dir=expected_dir,
        max_candidates=1,
    )

    assert summary["max_candidates_per_row"] == 1
    assert rows[0]["current_expected_ingredients"] == [{"display_name": "A"}]
