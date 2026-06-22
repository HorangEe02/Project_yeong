"""Tests for privacy-safe Tampermonkey ROI crop OCR retries."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from scripts import run_naver_tampermonkey_roi_crop_ocr_eval as roi_runner


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL rows for tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _source_row(image_sha256: str = "a" * 64) -> dict[str, object]:
    """Return a redacted source manifest row."""
    return {
        "fixture_id": "naver-tm-detail-000001",
        "section": "detail",
        "image_path": "$NAVER_TAMPERMONKEY_SOURCE_ROOT/[아연]/sample/detail.jpg",
        "image_sha256": image_sha256,
        "license_status": "team_approved",
        "consent_status": "team_approved",
        "contains_personal_data": False,
        "external_transfer_allowed": True,
        "local_processing_allowed": True,
        "expected": {},
        "db_labeling": {"category_key": "zinc"},
    }


@dataclass(frozen=True)
class _FakeCollection:
    """Fake collector result with observation rows."""

    observations: list[dict[str, object]]


async def _fake_collect(**kwargs: Any) -> _FakeCollection:
    """Verify the temp manifest and return redacted observation rows."""
    manifest_path = Path(kwargs["manifest_path"])
    temp_rows = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    observations: list[dict[str, object]] = []
    for row in temp_rows:
        assert str(row["image_path"]).startswith("$LEMON_OCR_FIXTURE_ROOT/")
        assert Path(str(row["image_path"]).split("/", 1)[1]).suffix == ".png"
        observations.append(
            {
                "fixture_id": row["fixture_id"],
                "provider": "paddleocr_local",
                "status": "completed",
                "text_non_empty": True,
                "char_count": 12,
                "layout_available": False,
                "parser_success": True,
                "parsed_ingredients": [],
                "evidence_grounded": False,
                "warning_codes": ["layout_unavailable"],
            }
        )
    return _FakeCollection(observations=observations)


def test_roi_crop_eval_writes_observations_without_temp_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify crop retries restore source ids and store only safe metadata."""
    image_root = tmp_path / "source"
    image_path = image_root / "[아연]" / "sample" / "detail.jpg"
    image_path.parent.mkdir(parents=True)
    Image.new("RGB", (20, 20), color=(240, 240, 240)).save(image_path)
    image_sha256 = "a" * 64
    monkeypatch.setenv("NAVER_TAMPERMONKEY_SOURCE_ROOT", str(image_root))
    manifest = tmp_path / "manifest.jsonl"
    _write_jsonl(manifest, [_source_row(image_sha256=image_sha256)])

    rows, summary = asyncio.run(
        roi_runner.run_roi_crop_eval(
            manifest_path=manifest,
            output_dir=tmp_path / "out",
            profiles=(roi_runner.CROP_PROFILES["full_x2"],),
            collect_func=_fake_collect,
        )
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["fixture_id"] == "naver-tm-detail-000001"
    assert row["roi_crop"]["roi_crop_profile"] == "full_x2"
    assert row["roi_crop"]["roi_temp_artifacts_persisted"] is False
    assert summary["temporary_crop_images_persisted"] is False
    serialized = json.dumps({"rows": rows, "summary": summary}, ensure_ascii=False)
    assert str(image_root) not in serialized
    assert "$LEMON_OCR_FIXTURE_ROOT" not in serialized
    assert "image_path" not in serialized


def test_write_outputs_are_privacy_safe(tmp_path: Path) -> None:
    """Verify output writer rejects path-like values and writes safe files."""
    rows = [
        {
            "schema_version": roi_runner.SCHEMA_VERSION,
            "fixture_id": "naver-tm-detail-000001",
            "provider": "paddleocr_local",
            "status": "completed",
            "text_non_empty": True,
            "char_count": 10,
            "layout_available": False,
            "parser_success": True,
            "parsed_ingredients": [],
            "evidence_grounded": False,
            "warning_codes": [],
            "roi_crop": {
                "source_fixture_id": "naver-tm-detail-000001",
                "roi_crop_profile": "full_x2",
                "roi_crop_preprocess_mode": "none",
                "roi_crop_scale": 2.0,
                "roi_crop_box_normalized": [0.0, 0.0, 1.0, 1.0],
                "roi_crop_width": 20,
                "roi_crop_height": 20,
                "roi_crop_sha256": "b" * 64,
                "roi_temp_artifacts_persisted": False,
            },
            "raw_artifacts_stored": False,
            "raw_ocr_text_stored": False,
            "raw_provider_payload_stored": False,
            "raw_model_response_stored": False,
            "local_path_literals_stored": False,
        }
    ]
    summary = {
        "schema_version": roi_runner.SUMMARY_SCHEMA_VERSION,
        "status_counts": {"completed": 1},
        "temporary_crop_images_persisted": False,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }

    roi_runner._write_outputs(
        rows=rows,
        summary=summary,
        output_dir=tmp_path / "out",
        observations_name=roi_runner.DEFAULT_OBSERVATIONS_NAME,
        summary_name=roi_runner.DEFAULT_SUMMARY_NAME,
    )

    output_text = (tmp_path / "out" / roi_runner.DEFAULT_OBSERVATIONS_NAME).read_text(
        encoding="utf-8"
    )
    assert "naver-tm-detail-000001" in output_text
    assert "/private/" not in output_text
    assert "image_path" not in output_text


def test_roi_crop_eval_rejects_raw_manifest_field(tmp_path: Path) -> None:
    """Verify raw OCR fields cannot enter crop retry inputs."""
    manifest = tmp_path / "manifest.jsonl"
    row = _source_row()
    row["raw_ocr_text"] = "forbidden"
    _write_jsonl(manifest, [row])

    with pytest.raises(ValueError, match="raw_ocr_text"):
        asyncio.run(
            roi_runner.run_roi_crop_eval(
                manifest_path=manifest,
                output_dir=tmp_path / "out",
                profiles=(roi_runner.CROP_PROFILES["full_x2"],),
                collect_func=_fake_collect,
            )
        )


def test_roi_crop_eval_rejects_local_path_literal(tmp_path: Path) -> None:
    """Verify local absolute paths cannot enter crop retry inputs."""
    manifest = tmp_path / "manifest.jsonl"
    row = _source_row()
    row["image_path"] = "/Volumes/private/detail.jpg"
    _write_jsonl(manifest, [row])

    with pytest.raises(ValueError, match="local path"):
        asyncio.run(
            roi_runner.run_roi_crop_eval(
                manifest_path=manifest,
                output_dir=tmp_path / "out",
                profiles=(roi_runner.CROP_PROFILES["full_x2"],),
                collect_func=_fake_collect,
            )
        )
