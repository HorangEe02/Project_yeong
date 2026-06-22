"""Tests for supplement-section YOLO dataset materialization."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

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


def _write_dataset_yaml(root: Path) -> Path:
    """Write a section YOLO dataset YAML.

    Args:
        root: Temporary root.

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
                "test: images/test",
                f"nc: {len(SECTION_CLASS_NAMES)}",
                "names:",
                *[f"  {index}: {name}" for index, name in enumerate(SECTION_CLASS_NAMES)],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return yaml_path


def _write_export(root: Path) -> Path:
    """Write a supplement-section YOLO export fixture.

    Args:
        root: Temporary root.

    Returns:
        Export JSON path.
    """
    export_path = root / "export.json"
    items = [
        _export_item("media:11111111-1111-4111-8111-111111111111", "train", 1),
        _export_item("media:22222222-2222-4222-8222-222222222222", "val", 3),
        _export_item("media:33333333-3333-4333-8333-333333333333", "test", 4),
    ]
    export_path.write_text(
        json.dumps(
            {
                "schema_version": "supplement-section-yolo-detect-export-v1",
                "class_names": SECTION_CLASS_NAMES,
                "item_count": len(items),
                "split_counts": {"train": 1, "val": 1, "test": 1, "holdout": 0},
                "items": items,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return export_path


def _export_item(source_ref: str, split: str, class_id: int) -> dict[str, object]:
    """Build one export item.

    Args:
        source_ref: Private source token.
        split: Dataset split.
        class_id: Supplement section class id.

    Returns:
        Export item fixture.
    """
    return {
        "source_ref": source_ref,
        "split": split,
        "labels": [
            {
                "class_id": class_id,
                "label": "supplement_facts",
                "x_center": 0.5,
                "y_center": 0.4,
                "width": 0.6,
                "height": 0.3,
            }
        ],
    }


def _write_source_map(root: Path) -> Path:
    """Write source images and a row-form source map.

    Args:
        root: Temporary root.

    Returns:
        Source map path.
    """
    images_dir = root / "sources"
    images_dir.mkdir(parents=True)
    rows = []
    for index, source_ref in enumerate(
        [
            "media:11111111-1111-4111-8111-111111111111",
            "media:22222222-2222-4222-8222-222222222222",
            "media:33333333-3333-4333-8333-333333333333",
        ],
        start=1,
    ):
        image_path = images_dir / f"source-{index}.jpg"
        image_path.write_bytes(b"placeholder")
        rows.append({"source_ref": source_ref, "image_path": str(image_path)})
    source_map_path = root / "source-map.json"
    source_map_path.write_text(json.dumps({"sources": rows}), encoding="utf-8")
    return source_map_path


def test_materialize_dataset_writes_yolo_files_and_validates(tmp_path: Path) -> None:
    """Verify materialization writes image copies and normalized YOLO labels."""
    dataset_yaml = _write_dataset_yaml(tmp_path)
    export_path = _write_export(tmp_path)
    source_map_path = _write_source_map(tmp_path)

    summary = materializer.materialize_dataset(
        export_path=export_path,
        source_map_path=source_map_path,
        dataset_yaml=dataset_yaml,
    )

    assert summary.item_count == 3
    assert summary.image_count == 3
    assert summary.label_count == 3
    assert summary.split_counts == {"train": 1, "val": 1, "test": 1}
    dataset_root = tmp_path / "dataset"
    label_files = sorted((dataset_root / "labels").glob("*/*.txt"))
    assert len(label_files) == 3
    train_label = next(path for path in label_files if path.parent.name == "train")
    assert train_label.read_text(encoding="utf-8").splitlines()[0].split() == [
        "1",
        "0.500000",
        "0.400000",
        "0.600000",
        "0.300000",
    ]


def test_main_prints_safe_summary_without_source_refs_or_paths(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI stdout omits source refs and local source paths."""
    dataset_yaml = _write_dataset_yaml(tmp_path)
    export_path = _write_export(tmp_path)
    source_map_path = _write_source_map(tmp_path)

    materializer.main(
        [
            "--export",
            str(export_path),
            "--source-map",
            str(source_map_path),
            "--dataset-yaml",
            str(dataset_yaml),
        ]
    )

    stdout = capsys.readouterr().out
    assert '"ok": true' in stdout
    assert "media:" not in stdout
    assert str(tmp_path) not in stdout
    assert "source-" not in stdout


def test_materialize_dataset_rejects_missing_source_map_item(tmp_path: Path) -> None:
    """Verify every export item must resolve through the trusted source map."""
    dataset_yaml = _write_dataset_yaml(tmp_path)
    export_path = _write_export(tmp_path)
    source_map_path = tmp_path / "source-map.json"
    source_map_path.write_text("{}", encoding="utf-8")

    with pytest.raises(materializer.MaterializationError, match="missing an export item"):
        materializer.materialize_dataset(
            export_path=export_path,
            source_map_path=source_map_path,
            dataset_yaml=dataset_yaml,
        )


def test_materialize_dataset_rejects_holdout_split(tmp_path: Path) -> None:
    """Verify holdout rows are not silently materialized into train/val/test."""
    dataset_yaml = _write_dataset_yaml(tmp_path)
    export_path = tmp_path / "export.json"
    item = _export_item("media:11111111-1111-4111-8111-111111111111", "holdout", 0)
    export_path.write_text(
        json.dumps(
            {
                "schema_version": "supplement-section-yolo-detect-export-v1",
                "class_names": SECTION_CLASS_NAMES,
                "item_count": 1,
                "split_counts": {"train": 0, "val": 0, "test": 0, "holdout": 1},
                "items": [item],
            }
        ),
        encoding="utf-8",
    )
    source_map_path = _write_source_map(tmp_path)

    with pytest.raises(materializer.MaterializationError, match="split is not supported"):
        materializer.materialize_dataset(
            export_path=export_path,
            source_map_path=source_map_path,
            dataset_yaml=dataset_yaml,
        )
