"""Tests for PaddleOCR dataset materialization."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

materializer = importlib.import_module("scripts.materialize_paddleocr_dataset")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    """Write a JSON object.

    Args:
        path: Destination path.
        payload: JSON payload.
    """
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _write_source_image(path: Path) -> None:
    """Write a deterministic image-like fixture file.

    Args:
        path: Image path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"image-bytes")


def _detection_export(path: Path) -> Path:
    """Write a PaddleOCR detection export fixture.

    Args:
        path: Export path.

    Returns:
        Export path.
    """
    _write_json(
        path,
        {
            "schema_version": "learning-paddleocr-det-export-v1",
            "item_count": 1,
            "items": [
                {
                    "source_ref": "media:11111111-1111-4111-8111-111111111111",
                    "split": "train",
                    "textline_boxes": [
                        {
                            "class_id": 0,
                            "x_center": 0.5,
                            "y_center": 0.5,
                            "width": 0.4,
                            "height": 0.2,
                        }
                    ],
                }
            ],
        },
    )
    return path


def _recognition_export(
    path: Path,
    *,
    text_label: str = "Vitamin C 100 mg",
    crop_box: dict[str, float] | None = None,
) -> Path:
    """Write a PaddleOCR recognition export fixture.

    Args:
        path: Export path.
        text_label: Recognition label.
        crop_box: Optional normalized crop box.

    Returns:
        Export path.
    """
    item: dict[str, object] = {
        "source_ref": "media:22222222-2222-4222-8222-222222222222",
        "split": "val",
        "text_label": text_label,
        "recognition_source": "source_image_crop" if crop_box else "pre_cropped_image",
    }
    if crop_box is not None:
        item["crop_box"] = crop_box
    _write_json(
        path,
        {
            "schema_version": "learning-paddleocr-rec-export-v1",
            "item_count": 1,
            "items": [item],
        },
    )
    return path


def _source_map(path: Path, *, source_ref: str, image_path: Path) -> Path:
    """Write a source map fixture.

    Args:
        path: Source map path.
        source_ref: Private source ref.
        image_path: Source image path.

    Returns:
        Source map path.
    """
    _write_json(
        path,
        {
            "sources": [
                {
                    "source_ref": source_ref,
                    "image_path": str(image_path),
                    "width_px": 100,
                    "height_px": 50,
                }
            ]
        },
    )
    return path


def test_materialize_detection_writes_paddleocr_det_label(tmp_path: Path) -> None:
    """Verify detection export becomes PaddleOCR tab-separated JSON labels."""
    source_image = tmp_path / "source" / "label.jpg"
    _write_source_image(source_image)
    export_path = _detection_export(tmp_path / "det-export.json")
    source_map_path = _source_map(
        tmp_path / "source-map.json",
        source_ref="media:11111111-1111-4111-8111-111111111111",
        image_path=source_image,
    )

    summary = materializer.materialize_paddleocr_dataset(
        export_path=export_path,
        source_map_path=source_map_path,
        output_dir=tmp_path / "paddleocr",
    )

    assert summary.item_count == 1
    assert summary.image_count == 1
    assert summary.label_files == ["det_gt_train.txt"]
    label_path = tmp_path / "paddleocr" / "det" / "det_gt_train.txt"
    image_rel, annotation_json = label_path.read_text(encoding="utf-8").strip().split("\t")
    assert image_rel.startswith("det/images/train/")
    annotation = json.loads(annotation_json)
    assert annotation == [
        {
            "transcription": "text",
            "points": [[30, 20], [70, 20], [70, 30], [30, 30]],
        }
    ]
    assert (tmp_path / "paddleocr" / image_rel).read_bytes() == b"image-bytes"


def test_materialize_recognition_writes_paddleocr_rec_label(tmp_path: Path) -> None:
    """Verify recognition export becomes PaddleOCR tab-separated text labels."""
    source_image = tmp_path / "source" / "crop.png"
    _write_source_image(source_image)
    export_path = _recognition_export(tmp_path / "rec-export.json")
    source_map_path = _source_map(
        tmp_path / "source-map.json",
        source_ref="media:22222222-2222-4222-8222-222222222222",
        image_path=source_image,
    )

    summary = materializer.materialize_paddleocr_dataset(
        export_path=export_path,
        source_map_path=source_map_path,
        output_dir=tmp_path / "paddleocr",
    )

    assert summary.label_files == ["rec_gt_val.txt"]
    label_path = tmp_path / "paddleocr" / "rec" / "rec_gt_val.txt"
    image_rel, text_label = label_path.read_text(encoding="utf-8").strip().split("\t")
    assert image_rel.startswith("rec/val/")
    assert text_label == "Vitamin C 100 mg"
    assert (tmp_path / "paddleocr" / image_rel).read_bytes() == b"image-bytes"


def test_materialize_recognition_crop_box_writes_crop_image(tmp_path: Path) -> None:
    """Verify recognition crop_box creates a cropped training image."""
    if materializer.Image is None:
        pytest.skip("Pillow is not installed")
    source_image = tmp_path / "source" / "full.jpg"
    source_image.parent.mkdir(parents=True, exist_ok=True)
    image = materializer.Image.new("RGB", (100, 50), color="white")
    image.save(source_image)
    export_path = _recognition_export(
        tmp_path / "rec-export.json",
        crop_box={
            "x_center": 0.5,
            "y_center": 0.5,
            "width": 0.4,
            "height": 0.2,
        },
    )
    source_map_path = _source_map(
        tmp_path / "source-map.json",
        source_ref="media:22222222-2222-4222-8222-222222222222",
        image_path=source_image,
    )

    materializer.materialize_paddleocr_dataset(
        export_path=export_path,
        source_map_path=source_map_path,
        output_dir=tmp_path / "paddleocr",
    )

    label_path = tmp_path / "paddleocr" / "rec" / "rec_gt_val.txt"
    image_rel = label_path.read_text(encoding="utf-8").strip().split("\t")[0]
    with materializer.Image.open(tmp_path / "paddleocr" / image_rel) as cropped:
        assert cropped.size == (40, 10)


def test_main_prints_safe_summary_without_source_or_label(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI stdout omits source refs, source paths, and label text."""
    source_image = tmp_path / "source" / "crop.jpg"
    _write_source_image(source_image)
    export_path = _recognition_export(tmp_path / "rec-export.json")
    source_map_path = _source_map(
        tmp_path / "source-map.json",
        source_ref="media:22222222-2222-4222-8222-222222222222",
        image_path=source_image,
    )

    materializer.main(
        [
            "--export",
            str(export_path),
            "--source-map",
            str(source_map_path),
            "--output-dir",
            str(tmp_path / "paddleocr"),
        ]
    )

    stdout = capsys.readouterr().out
    assert '"ok": true' in stdout
    assert "media:" not in stdout
    assert str(tmp_path) not in stdout
    assert "Vitamin C" not in stdout
    assert "crop.jpg" not in stdout


def test_materialize_rejects_missing_source_map_item(tmp_path: Path) -> None:
    """Verify every export item must resolve through source map."""
    export_path = _detection_export(tmp_path / "det-export.json")
    _write_json(tmp_path / "source-map.json", {"sources": []})

    with pytest.raises(materializer.PaddleOCRMaterializationError, match="missing an export item"):
        materializer.materialize_paddleocr_dataset(
            export_path=export_path,
            source_map_path=tmp_path / "source-map.json",
            output_dir=tmp_path / "paddleocr",
        )


def test_recognition_label_with_tab_is_rejected(tmp_path: Path) -> None:
    """Verify recognition labels cannot corrupt PaddleOCR tab format."""
    source_image = tmp_path / "source" / "crop.jpg"
    _write_source_image(source_image)
    export_path = _recognition_export(tmp_path / "rec-export.json", text_label="Vitamin\tC")
    source_map_path = _source_map(
        tmp_path / "source-map.json",
        source_ref="media:22222222-2222-4222-8222-222222222222",
        image_path=source_image,
    )

    with pytest.raises(materializer.PaddleOCRMaterializationError, match="tab-safe line"):
        materializer.materialize_paddleocr_dataset(
            export_path=export_path,
            source_map_path=source_map_path,
            output_dir=tmp_path / "paddleocr",
        )
