"""Tests for supplement-section YOLO dataset validation."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

validator = importlib.import_module("scripts.validate_supplement_section_yolo_dataset")
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


def _write_dataset_yaml(root: Path, *, names: list[str] | None = None) -> Path:
    """Write a minimal dataset YAML for tests.

    Args:
        root: Temporary test root.
        names: Optional class names override.

    Returns:
        Dataset YAML path.
    """
    class_names = names or SECTION_CLASS_NAMES
    yaml_path = root / "dataset.yaml"
    name_lines = "\n".join(f"  {index}: {name}" for index, name in enumerate(class_names))
    yaml_path.write_text(
        "\n".join(
            [
                "path: dataset",
                "train: images/train",
                "val: images/val",
                "test: images/test",
                f"nc: {len(class_names)}",
                "names:",
                name_lines,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return yaml_path


def _write_image_and_label(dataset_root: Path, split: str, stem: str, class_id: int = 0) -> None:
    """Write placeholder image and YOLO label files.

    Args:
        dataset_root: Dataset root directory.
        split: Split name.
        stem: File stem.
        class_id: YOLO class id.
    """
    image_dir = dataset_root / "images" / split
    label_dir = dataset_root / "labels" / split
    image_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)
    (image_dir / f"{stem}.jpg").write_bytes(b"placeholder")
    (label_dir / f"{stem}.txt").write_text(
        f"{class_id} 0.500000 0.500000 0.400000 0.300000\n",
        encoding="utf-8",
    )


def test_validate_dataset_accepts_section_contract_without_files(tmp_path: Path) -> None:
    """Verify class-contract validation passes before annotations are present."""
    yaml_path = _write_dataset_yaml(tmp_path)

    summary = validator.validate_dataset(yaml_path)

    assert summary.required_sections == (
        "product_identity",
        "supplement_facts",
        "ingredient_amounts",
        "precautions",
        "allergen_warning",
        "intake_method",
        "other_ingredients",
        "functional_claims",
    )
    assert summary.names == tuple(SECTION_CLASS_NAMES)
    assert summary.require_files is False
    assert summary.image_count == 0
    assert summary.label_count == 0


def test_validate_dataset_rejects_coco_names(tmp_path: Path) -> None:
    """Verify COCO class names cannot pass supplement section contract checks."""
    yaml_path = _write_dataset_yaml(tmp_path, names=["person", "bicycle", "car", "bus"])

    with pytest.raises(validator.DatasetContractError, match="unsupported supplement ROI"):
        validator.validate_dataset(yaml_path)


def test_validate_dataset_rejects_missing_precautions_class(tmp_path: Path) -> None:
    """Verify warning/allergy section class is mandatory."""
    yaml_path = _write_dataset_yaml(
        tmp_path,
        names=[
            "product_identity",
            "supplement_facts",
            "ingredient_amounts",
            "intake_method",
            "other_ingredients",
            "functional_claims",
            "supplement_label",
        ],
    )

    with pytest.raises(validator.DatasetContractError, match="precautions"):
        validator.validate_dataset(yaml_path)


def test_validate_dataset_rejects_missing_allergen_warning_class(tmp_path: Path) -> None:
    """Verify dedicated allergen warning section class is mandatory."""
    names = [name for name in SECTION_CLASS_NAMES if name != "allergen_warning"]
    yaml_path = _write_dataset_yaml(tmp_path, names=names)

    with pytest.raises(validator.DatasetContractError, match="allergen_warning"):
        validator.validate_dataset(yaml_path)


def test_validate_dataset_rejects_non_contiguous_name_mapping(tmp_path: Path) -> None:
    """Verify dataset class ids must map to contiguous YOLO class indexes."""
    yaml_path = tmp_path / "dataset.yaml"
    yaml_path.write_text(
        "\n".join(
            [
                "path: dataset",
                "train: images/train",
                "val: images/val",
                "nc: 4",
                "names:",
                "  0: product_identity",
                "  1: supplement_facts",
                "  3: precautions",
                "  4: intake_method",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(validator.DatasetContractError, match="contiguous integer keys"):
        validator.validate_dataset(yaml_path)


def test_validate_dataset_checks_image_label_pairs(tmp_path: Path) -> None:
    """Verify file checks validate split image-label pairs and bbox rows."""
    yaml_path = _write_dataset_yaml(tmp_path)
    dataset_root = tmp_path / "dataset"
    _write_image_and_label(dataset_root, "train", "train-001", class_id=1)
    _write_image_and_label(dataset_root, "val", "val-001", class_id=3)
    _write_image_and_label(dataset_root, "test", "test-001", class_id=4)

    summary = validator.validate_dataset(yaml_path, require_files=True)

    assert summary.require_files is True
    assert summary.image_count == 3
    assert summary.label_count == 3


def test_validate_dataset_rejects_out_of_range_label_class(tmp_path: Path) -> None:
    """Verify label files cannot reference a class outside configured names."""
    yaml_path = _write_dataset_yaml(tmp_path)
    dataset_root = tmp_path / "dataset"
    _write_image_and_label(dataset_root, "train", "train-001", class_id=9)
    _write_image_and_label(dataset_root, "val", "val-001", class_id=3)
    _write_image_and_label(dataset_root, "test", "test-001", class_id=4)

    with pytest.raises(validator.DatasetContractError, match="outside configured names"):
        validator.validate_dataset(yaml_path, require_files=True)
