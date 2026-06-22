"""Validate the supplement-section YOLO dataset contract.

The validator intentionally uses only standard-library parsing for the small
Ultralytics dataset YAML subset used by this project. It checks the class
contract by default and can optionally validate image/label pairs before an
operator starts YOLO26 training.

Reference:
    https://docs.ultralytics.com/datasets/detect/
    https://docs.ultralytics.com/modes/train/
"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.vision.taxonomy import VISION_DETECTION_LABELS, normalize_vision_label

REQUIRED_SECTION_LABELS = (
    "product_identity",
    "supplement_facts",
    "ingredient_amounts",
    "precautions",
    "allergen_warning",
    "intake_method",
    "other_ingredients",
    "functional_claims",
)
REQUIRED_DATASET_KEYS = ("path", "train", "val", "names")
OPTIONAL_SPLIT_KEY = "test"
IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".webp"}
YOLO_DETECTION_ROW_LENGTH = 5


class DatasetContractError(ValueError):
    """Raised when a supplement-section YOLO dataset contract is invalid."""


@dataclass(frozen=True)
class SupplementSectionYoloDataset:
    """Parsed Ultralytics dataset YAML subset.

    Args:
        dataset_yaml: YAML file path.
        root: Dataset root directory from the YAML ``path`` key.
        train: Training image directory relative to ``root``.
        val: Validation image directory relative to ``root``.
        test: Optional test image directory relative to ``root``.
        names: Ordered class names.
        nc: Optional declared class count.
    """

    dataset_yaml: Path
    root: Path
    train: str
    val: str
    test: str | None
    names: tuple[str, ...]
    nc: int | None


@dataclass(frozen=True)
class DatasetValidationSummary:
    """Safe validation summary for operator output.

    Args:
        dataset_yaml: YAML file path.
        required_sections: Required class labels.
        names: Canonical configured class labels.
        require_files: Whether image/label files were checked.
        image_count: Number of images checked.
        label_count: Number of label files checked.
    """

    dataset_yaml: str
    required_sections: tuple[str, ...]
    names: tuple[str, ...]
    require_files: bool
    image_count: int
    label_count: int

    def model_dump(self) -> dict[str, Any]:
        """Return a JSON-serializable summary.

        Returns:
            Safe validation summary without image paths or raw labels.
        """
        return {
            "dataset_yaml": self.dataset_yaml,
            "required_sections": list(self.required_sections),
            "names": list(self.names),
            "require_files": self.require_files,
            "image_count": self.image_count,
            "label_count": self.label_count,
        }


def load_dataset_yaml(dataset_yaml: Path) -> SupplementSectionYoloDataset:
    """Load the project-supported Ultralytics dataset YAML subset.

    Args:
        dataset_yaml: Dataset YAML path.

    Returns:
        Parsed dataset config.

    Raises:
        DatasetContractError: If the YAML is malformed or misses required keys.
    """
    if not dataset_yaml.is_file():
        raise DatasetContractError("Dataset YAML file does not exist.")
    values = _parse_simple_yaml(dataset_yaml.read_text(encoding="utf-8"))
    missing = [key for key in REQUIRED_DATASET_KEYS if key not in values]
    if missing:
        raise DatasetContractError(f"Dataset YAML missing required keys: {', '.join(missing)}")

    names = _normalize_names(values["names"])
    nc = _int_or_none(values.get("nc"))
    root = _resolve_dataset_root(dataset_yaml, _require_string(values["path"], "path"))
    return SupplementSectionYoloDataset(
        dataset_yaml=dataset_yaml.resolve(),
        root=root,
        train=_require_string(values["train"], "train"),
        val=_require_string(values["val"], "val"),
        test=_optional_string(values.get(OPTIONAL_SPLIT_KEY)),
        names=tuple(names),
        nc=nc,
    )


def validate_dataset(
    dataset_yaml: Path,
    *,
    require_files: bool = False,
) -> DatasetValidationSummary:
    """Validate the supplement-section YOLO dataset contract.

    Args:
        dataset_yaml: Ultralytics dataset YAML path.
        require_files: Whether to validate image/label directories and label lines.

    Returns:
        Safe validation summary.

    Raises:
        DatasetContractError: If the class contract or file layout is invalid.
    """
    dataset = load_dataset_yaml(dataset_yaml)
    canonical_names = _canonical_names(dataset.names)
    _validate_class_contract(dataset, canonical_names)
    image_count = 0
    label_count = 0
    if require_files:
        image_count, label_count = _validate_split_files(dataset)
    return DatasetValidationSummary(
        dataset_yaml=dataset.dataset_yaml.name,
        required_sections=REQUIRED_SECTION_LABELS,
        names=tuple(canonical_names),
        require_files=require_files,
        image_count=image_count,
        label_count=label_count,
    )


def _validate_class_contract(
    dataset: SupplementSectionYoloDataset,
    canonical_names: list[str],
) -> None:
    """Validate class count, supported labels, and required section labels.

    Args:
        dataset: Parsed dataset config.
        canonical_names: Canonical class labels.

    Raises:
        DatasetContractError: If the model class contract is unsafe.
    """
    if not canonical_names:
        raise DatasetContractError("Dataset must define at least one class name.")
    if dataset.nc is not None and dataset.nc != len(canonical_names):
        raise DatasetContractError("Dataset nc must match the number of names.")
    if len(set(canonical_names)) != len(canonical_names):
        raise DatasetContractError("Dataset class names must be unique after normalization.")

    unsupported = sorted(set(canonical_names) - VISION_DETECTION_LABELS)
    if unsupported:
        raise DatasetContractError(
            "Dataset includes unsupported supplement ROI labels: " + ", ".join(unsupported)
        )

    missing_required = sorted(set(REQUIRED_SECTION_LABELS) - set(canonical_names))
    if missing_required:
        raise DatasetContractError(
            "Dataset missing required section labels: " + ", ".join(missing_required)
        )


def _validate_split_files(dataset: SupplementSectionYoloDataset) -> tuple[int, int]:
    """Validate image directories and normalized YOLO label files.

    Args:
        dataset: Parsed dataset config.

    Returns:
        Image and label file counts.

    Raises:
        DatasetContractError: If file structure or label rows are invalid.
    """
    if not dataset.root.is_dir():
        raise DatasetContractError("Dataset root directory does not exist.")

    image_count = 0
    label_count = 0
    for split_name, image_dir in _iter_required_splits(dataset):
        split_images, split_labels = _validate_split(dataset, split_name, image_dir)
        image_count += split_images
        label_count += split_labels
    return image_count, label_count


def _iter_required_splits(dataset: SupplementSectionYoloDataset) -> tuple[tuple[str, str], ...]:
    """Return configured splits that must be file-checked.

    Args:
        dataset: Parsed dataset config.

    Returns:
        Split name and relative image directory pairs.
    """
    splits = [("train", dataset.train), ("val", dataset.val)]
    if dataset.test:
        splits.append(("test", dataset.test))
    return tuple(splits)


def _validate_split(
    dataset: SupplementSectionYoloDataset,
    split_name: str,
    image_dir: str,
) -> tuple[int, int]:
    """Validate one Ultralytics image/label split.

    Args:
        dataset: Parsed dataset config.
        split_name: Split name.
        image_dir: Image directory relative to the dataset root.

    Returns:
        Image and label counts for this split.

    Raises:
        DatasetContractError: If image or label files are missing or malformed.
    """
    image_root = dataset.root / image_dir
    label_root = dataset.root / image_dir.replace("images", "labels", 1)
    if not image_root.is_dir():
        raise DatasetContractError(f"{split_name} image directory does not exist.")
    if not label_root.is_dir():
        raise DatasetContractError(f"{split_name} label directory does not exist.")

    images = sorted(
        path
        for path in image_root.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )
    if not images:
        raise DatasetContractError(f"{split_name} split does not contain images.")

    label_count = 0
    for image_path in images:
        label_path = label_root / f"{image_path.stem}.txt"
        if not label_path.is_file():
            raise DatasetContractError(f"{split_name} image is missing a YOLO label file.")
        _validate_label_file(label_path, class_count=len(dataset.names))
        label_count += 1
    return len(images), label_count


def _validate_label_file(label_path: Path, *, class_count: int) -> None:
    """Validate a YOLO detection label file without printing label contents.

    Args:
        label_path: Label text file.
        class_count: Number of classes configured in the dataset YAML.

    Raises:
        DatasetContractError: If a label row is malformed.
    """
    rows = [line.strip() for line in label_path.read_text(encoding="utf-8").splitlines()]
    rows = [row for row in rows if row]
    if not rows:
        raise DatasetContractError("YOLO label file must contain at least one box.")
    for row in rows:
        parts = row.split()
        if len(parts) != YOLO_DETECTION_ROW_LENGTH:
            raise DatasetContractError("YOLO label row must contain class_id and four coordinates.")
        class_id = _parse_class_id(parts[0], class_count=class_count)
        _ = class_id
        for coordinate in parts[1:]:
            value = _float_or_error(coordinate)
            if not 0.0 <= value <= 1.0:
                raise DatasetContractError("YOLO label coordinates must be normalized.")


def _parse_class_id(raw_value: str, *, class_count: int) -> int:
    """Parse and range-check a YOLO class id.

    Args:
        raw_value: Class id text.
        class_count: Number of configured classes.

    Returns:
        Parsed class id.

    Raises:
        DatasetContractError: If the id is invalid or out of range.
    """
    try:
        class_id = int(raw_value)
    except ValueError as exc:
        raise DatasetContractError("YOLO label class_id must be an integer.") from exc
    if not 0 <= class_id < class_count:
        raise DatasetContractError("YOLO label class_id is outside configured names.")
    return class_id


def _float_or_error(raw_value: str) -> float:
    """Parse a float coordinate.

    Args:
        raw_value: Coordinate text.

    Returns:
        Parsed float.

    Raises:
        DatasetContractError: If the coordinate is not numeric.
    """
    try:
        return float(raw_value)
    except ValueError as exc:
        raise DatasetContractError("YOLO label coordinates must be numeric.") from exc


def _canonical_names(names: tuple[str, ...]) -> list[str]:
    """Normalize dataset names through the supplement ROI taxonomy.

    Args:
        names: Raw dataset class names.

    Returns:
        Canonical class names where possible.
    """
    return [normalize_vision_label(name) or name.strip() for name in names]


def _normalize_names(raw_names: object) -> list[str]:
    """Normalize parsed YAML names into an ordered list.

    Args:
        raw_names: Parsed names object.

    Returns:
        Ordered class labels.

    Raises:
        DatasetContractError: If names are malformed.
    """
    if isinstance(raw_names, list):
        names = raw_names
    elif isinstance(raw_names, dict):
        ordered_keys = sorted(raw_names)
        expected_keys = list(range(len(ordered_keys)))
        if ordered_keys != expected_keys:
            raise DatasetContractError("Dataset names mapping must use contiguous integer keys.")
        names = [raw_names[index] for index in ordered_keys]
    else:
        raise DatasetContractError("Dataset names must be a list or integer-key mapping.")
    if not all(isinstance(name, str) and name.strip() for name in names):
        raise DatasetContractError("Dataset names must be non-empty strings.")
    return [name.strip() for name in names]


def _parse_simple_yaml(text: str) -> dict[str, object]:
    """Parse the limited YAML subset used by Ultralytics dataset configs.

    Args:
        text: YAML text.

    Returns:
        Top-level key/value mapping.
    """
    lines = text.splitlines()
    values: dict[str, object] = {}
    index = 0
    while index < len(lines):
        line = _strip_comment(lines[index]).rstrip()
        index += 1
        if not line.strip() or line.startswith((" ", "\t")):
            continue
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if key == "names" and not raw_value:
            parsed_names, index = _parse_names_block(lines, index)
            values[key] = parsed_names
        else:
            values[key] = _parse_scalar(raw_value)
    return values


def _parse_names_block(
    lines: list[str], start_index: int
) -> tuple[dict[int, str] | list[str], int]:
    """Parse an indented ``names`` block.

    Args:
        lines: Full YAML lines.
        start_index: Index immediately after ``names:``.

    Returns:
        Parsed names and the next unread line index.
    """
    mapping: dict[int, str] = {}
    sequence: list[str] = []
    index = start_index
    while index < len(lines):
        raw_line = lines[index]
        line = _strip_comment(raw_line).rstrip()
        if not line.strip():
            index += 1
            continue
        if not raw_line.startswith((" ", "\t")):
            break
        item = line.strip()
        if item.startswith("- "):
            sequence.append(_parse_string(item[2:].strip()))
        elif ":" in item:
            raw_key, raw_value = item.split(":", 1)
            mapping[_parse_name_index(raw_key.strip())] = _parse_string(raw_value.strip())
        else:
            raise DatasetContractError("Dataset names block is malformed.")
        index += 1
    return (sequence if sequence else mapping), index


def _parse_name_index(raw_key: str) -> int:
    """Parse a YAML names mapping index.

    Args:
        raw_key: Mapping key text.

    Returns:
        Integer class index.

    Raises:
        DatasetContractError: If the index is invalid.
    """
    try:
        return int(raw_key)
    except ValueError as exc:
        raise DatasetContractError("Dataset names mapping keys must be integers.") from exc


def _parse_scalar(raw_value: str) -> object:
    """Parse a YAML scalar or simple inline list/mapping.

    Args:
        raw_value: Scalar text.

    Returns:
        Parsed Python value.
    """
    if raw_value == "":
        return None
    if raw_value.startswith(("[", "{")):
        try:
            return ast.literal_eval(raw_value)
        except (SyntaxError, ValueError) as exc:
            raise DatasetContractError("Dataset YAML inline value is malformed.") from exc
    return _parse_string(raw_value)


def _parse_string(raw_value: str) -> str:
    """Parse a simple YAML string.

    Args:
        raw_value: Raw scalar value.

    Returns:
        Unquoted string value.
    """
    value = raw_value.strip()
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def _strip_comment(line: str) -> str:
    """Strip YAML comments for the project-supported simple syntax.

    Args:
        line: Source line.

    Returns:
        Line without trailing comment text.
    """
    return line.split("#", 1)[0]


def _resolve_dataset_root(dataset_yaml: Path, raw_path: str) -> Path:
    """Resolve dataset root relative to the dataset YAML file.

    Args:
        dataset_yaml: Dataset YAML path.
        raw_path: Path value from the YAML.

    Returns:
        Absolute dataset root path.
    """
    root = Path(raw_path)
    if root.is_absolute():
        return root
    return (dataset_yaml.parent / root).resolve()


def _require_string(value: object, key: str) -> str:
    """Require a non-empty string setting.

    Args:
        value: Candidate value.
        key: Setting key name.

    Returns:
        Non-empty string value.

    Raises:
        DatasetContractError: If the value is missing or not a string.
    """
    if not isinstance(value, str) or not value.strip():
        raise DatasetContractError(f"Dataset YAML key {key} must be a non-empty string.")
    return value.strip()


def _optional_string(value: object) -> str | None:
    """Return an optional string setting.

    Args:
        value: Candidate value.

    Returns:
        String value or None.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise DatasetContractError("Optional dataset split path must be a string.")
    return value.strip() or None


def _int_or_none(value: object) -> int | None:
    """Parse an optional integer.

    Args:
        value: Candidate value.

    Returns:
        Integer value or None.
    """
    if value is None:
        return None
    try:
        return int(str(value))
    except ValueError as exc:
        raise DatasetContractError("Dataset nc must be an integer.") from exc


def main() -> None:
    """Run the dataset validator CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset_yaml", type=Path)
    parser.add_argument(
        "--require-files",
        action="store_true",
        help="also validate image directories, label files, and normalized bbox rows",
    )
    args = parser.parse_args()
    try:
        summary = validate_dataset(args.dataset_yaml, require_files=args.require_files)
    except DatasetContractError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1) from exc
    print(json.dumps({"ok": True, **summary.model_dump()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
