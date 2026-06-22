"""Tests for reviewed supplement YOLO annotation template promotion."""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

promoter = importlib.import_module("scripts.promote_supplement_yolo_annotation_template")
materializer = importlib.import_module("scripts.materialize_supplement_section_yolo_dataset")
SECTION_CLASS_NAMES = [
    "product_identity",
    "supplement_facts",
    "ingredient_amounts",
    "precautions",
    "allergen_warning",
    "intake_method",
    "other_ingredients",
    "functional_claims",
]


def _sha256(value: bytes) -> str:
    """Return a SHA-256 digest for fixture bytes.

    Args:
        value: Fixture bytes.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value).hexdigest()


def _write_template(
    tmp_path: Path,
    *,
    row: dict[str, object] | None = None,
) -> tuple[Path, Path]:
    """Write one reviewed template row and fixture image.

    Args:
        tmp_path: Temporary test root.
        row: Optional row override.

    Returns:
        Template path and image path.
    """
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    image_path = image_dir / "detail.jpg"
    image_bytes = b"detail-page-image"
    image_path.write_bytes(image_bytes)
    template_path = tmp_path / "template.jsonl"
    payload = row or _reviewed_row(image_sha256=_sha256(image_bytes))
    template_path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    return template_path, image_path


def _write_dataset_yaml(root: Path) -> Path:
    """Write one Ultralytics supplement-section dataset YAML.

    Args:
        root: Temporary test root.

    Returns:
        Dataset YAML path.
    """
    yaml_path = root / "dataset.yaml"
    yaml_path.write_text(
        "\n".join(
            [
                "path: dataset",
                "train: images/train",
                "val: images/val",
                f"nc: {len(SECTION_CLASS_NAMES)}",
                "names:",
                *[f"  {index}: {name}" for index, name in enumerate(SECTION_CLASS_NAMES)],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return yaml_path


def _reviewed_row(*, image_sha256: str) -> dict[str, object]:
    """Build one accepted supplement section annotation template row.

    Args:
        image_sha256: Expected fixture image digest.

    Returns:
        Reviewed template row.
    """
    return {
        "schema_version": "supplement-yolo-annotation-template-row-v1",
        "fixture_id": "detail-yolo-abc123",
        "source_ref": "crawling-image:abc123",
        "image_ref_hash": "a" * 64,
        "image_sha256": image_sha256,
        "image_mime_type": "image/jpeg",
        "category_key": "오메가3",
        "source_kind": "detail_page",
        "annotation_task_type": "supplement_roi_box",
        "annotation_status": "accepted_for_training",
        "coordinate_space": "source_image",
        "allowed_labels": [
            "product_identity",
            "supplement_facts",
            "ingredient_amounts",
            "precautions",
            "allergen_warning",
            "intake_method",
            "other_ingredients",
            "functional_claims",
        ],
        "image_path": "images/detail.jpg",
        "label_snapshot": {
            "schema_version": "supplement-section-yolo-label-candidates-v1",
            "candidate_source": "human_annotation_template",
            "coordinate_space": "source_image",
            "human_review_required": False,
            "text_stored": False,
            "training_export_allowed": True,
            "boxes": [
                {
                    "label": "supplement_facts",
                    "x_center": 0.5,
                    "y_center": 0.4,
                    "width": 0.6,
                    "height": 0.3,
                },
                {
                    "label": "warning",
                    "x_center": 0.5,
                    "y_center": 0.8,
                    "width": 0.6,
                    "height": 0.2,
                },
            ],
        },
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


def test_promote_reviewed_templates_writes_export_and_source_map(tmp_path: Path) -> None:
    """Verify accepted template rows become YOLO export rows and source-map rows."""
    template_path, _image_path = _write_template(tmp_path)
    output_path = tmp_path / "export.json"
    source_map_path = tmp_path / "source-map.json"

    export, source_map, summary = promoter.promote_reviewed_templates(
        template_path=template_path,
        source_map_path=source_map_path,
        default_split="train",
        limit=10,
        source_run_id="run-1",
    )

    assert export["schema_version"] == "supplement-section-yolo-detect-export-v1"
    assert export["item_count"] == 1
    assert export["split_counts"]["train"] == 1
    assert export["items"][0]["source_ref"] == "template:detail-yolo-abc123"
    assert export["items"][0]["labels"][0]["class_id"] == 1
    assert export["items"][0]["labels"][1]["label"] == "precautions"
    assert source_map["sources"] == [
        {"source_ref": "template:detail-yolo-abc123", "image_path": "images/detail.jpg"}
    ]
    assert summary["promoted_item_count"] == 1
    assert summary["source_ref_printed"] is False
    assert summary["image_path_printed"] is False
    assert summary["labels_printed"] is False
    _ = output_path


def test_pending_template_rows_are_not_promoted(tmp_path: Path) -> None:
    """Verify pending rows stay out of training export artifacts."""
    image_bytes = b"detail-page-image"
    row = _reviewed_row(image_sha256=_sha256(image_bytes))
    row["annotation_status"] = "pending_human_bbox_review"
    row["label_snapshot"] = {
        **row["label_snapshot"],  # type: ignore[arg-type]
        "human_review_required": True,
        "training_export_allowed": False,
    }
    template_path, _image_path = _write_template(tmp_path, row=row)

    export, source_map, summary = promoter.promote_reviewed_templates(
        template_path=template_path,
        source_map_path=tmp_path / "source-map.json",
    )

    assert export["item_count"] == 0
    assert source_map["sources"] == []
    assert summary["skip_reason_counts"] == {"not_accepted_for_training": 1}


def test_template_with_raw_ocr_text_is_rejected(tmp_path: Path) -> None:
    """Verify raw OCR text cannot enter reviewed annotation promotion."""
    image_bytes = b"detail-page-image"
    row = _reviewed_row(image_sha256=_sha256(image_bytes))
    row["label_snapshot"] = {
        **row["label_snapshot"],  # type: ignore[arg-type]
        "raw_ocr_text": "secret OCR text",
    }
    template_path, _image_path = _write_template(tmp_path, row=row)

    with pytest.raises(promoter.TemplatePromotionError, match="Unsafe key"):
        promoter.promote_reviewed_templates(
            template_path=template_path,
            source_map_path=tmp_path / "source-map.json",
        )


def test_template_with_absolute_image_path_is_rejected(tmp_path: Path) -> None:
    """Verify template image paths must remain relative fixture paths."""
    image_bytes = b"detail-page-image"
    row = _reviewed_row(image_sha256=_sha256(image_bytes))
    row["image_path"] = "/private/tmp/detail.jpg"
    template_path, _image_path = _write_template(tmp_path, row=row)

    with pytest.raises(promoter.TemplatePromotionError, match="image_path"):
        promoter.promote_reviewed_templates(
            template_path=template_path,
            source_map_path=tmp_path / "source-map.json",
        )


def test_main_writes_files_and_prints_only_redacted_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI writes artifacts while stdout hides labels, refs, and paths."""
    template_path, _image_path = _write_template(tmp_path)
    output_path = tmp_path / "export.json"
    source_map_path = tmp_path / "source-map.json"

    promoter.main(
        [
            "--template",
            str(template_path),
            "--output",
            str(output_path),
            "--source-map",
            str(source_map_path),
            "--source-run-id",
            "run-2",
        ]
    )

    stdout = capsys.readouterr().out
    assert output_path.exists()
    assert source_map_path.exists()
    assert output_path.with_suffix(".json.summary.json").exists()
    assert "template:detail-yolo" not in stdout
    assert "supplement_facts" not in stdout
    assert "images/detail.jpg" not in stdout
    assert str(tmp_path) not in stdout
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["item_count"] == 1


def test_promoted_template_artifacts_can_materialize_yolo_dataset(tmp_path: Path) -> None:
    """Verify promoted template artifacts work with the YOLO materializer."""
    template_path, _image_path = _write_template(tmp_path)
    val_image_bytes = b"detail-page-image-val"
    val_image_path = tmp_path / "images" / "detail-val.jpg"
    val_image_path.write_bytes(val_image_bytes)
    val_row = _reviewed_row(image_sha256=_sha256(val_image_bytes))
    val_row["fixture_id"] = "detail-yolo-def456"
    val_row["image_ref_hash"] = "b" * 64
    val_row["image_path"] = "images/detail-val.jpg"
    val_row["split"] = "val"
    with template_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(val_row, ensure_ascii=False) + "\n")
    output_path = tmp_path / "export.json"
    source_map_path = tmp_path / "source-map.json"
    dataset_yaml = _write_dataset_yaml(tmp_path)

    promoter.main(
        [
            "--template",
            str(template_path),
            "--output",
            str(output_path),
            "--source-map",
            str(source_map_path),
        ]
    )
    summary = materializer.materialize_dataset(
        export_path=output_path,
        source_map_path=source_map_path,
        dataset_yaml=dataset_yaml,
    )

    assert summary.item_count == 2
    assert summary.image_count == 2
    assert summary.label_count == 2
    assert summary.split_counts == {"train": 1, "val": 1, "test": 0}
    label_files = sorted((tmp_path / "dataset" / "labels" / "train").glob("*.txt"))
    assert len(label_files) == 1
    label_lines = label_files[0].read_text(encoding="utf-8").splitlines()
    assert label_lines[0].split()[0] == "1"
    assert label_lines[1].split()[0] == "3"
    assert len(list((tmp_path / "dataset" / "labels" / "val").glob("*.txt"))) == 1
