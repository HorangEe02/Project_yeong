"""Materialize supplement-section YOLO exports into a local dataset.

This trusted-worker script consumes a sanitized
``supplement-section-yolo-detect-export-v1`` artifact and an operator-only
source map that resolves private ``source_ref`` tokens to local image files.
It writes Ultralytics YOLO image/label files and prints only aggregate counts.

Reference:
    https://docs.ultralytics.com/datasets/detect/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.learning.retraining import (  # noqa: E402
    SUPPLEMENT_SECTION_CLASS_NAMES,
    SUPPLEMENT_SECTION_YOLO_EXPORT_SCHEMA_VERSION,
)

from scripts.validate_supplement_section_yolo_dataset import (  # noqa: E402
    IMAGE_SUFFIXES,
    DatasetContractError,
    load_dataset_yaml,
    validate_dataset,
)

SUMMARY_SCHEMA_VERSION = "supplement-section-yolo-materialize-summary-v1"
SUPPORTED_SPLITS = frozenset({"train", "val", "test"})
YOLO_FLOAT_PRECISION = 6
SOURCE_REF_HASH_LENGTH = 20


class MaterializationError(ValueError):
    """Raised when YOLO dataset materialization input is invalid."""


@dataclass(frozen=True)
class MaterializationSummary:
    """Safe aggregate materialization summary.

    Args:
        dataset_yaml: Dataset YAML file name.
        item_count: Number of export items materialized.
        image_count: Number of images written.
        label_count: Number of label files written.
        split_counts: Number of materialized items by split.
    """

    dataset_yaml: str
    item_count: int
    image_count: int
    label_count: int
    split_counts: dict[str, int]

    def model_dump(self) -> dict[str, Any]:
        """Return a JSON-serializable safe summary.

        Returns:
            Summary without source refs, source paths, or label rows.
        """
        return {
            "schema_version": SUMMARY_SCHEMA_VERSION,
            "status": "ok",
            "dataset_yaml": self.dataset_yaml,
            "item_count": self.item_count,
            "image_count": self.image_count,
            "label_count": self.label_count,
            "split_counts": self.split_counts,
            "raw_ocr_text_stored": False,
            "raw_provider_payload_stored": False,
            "source_ref_printed": False,
            "source_path_printed": False,
        }


def materialize_dataset(
    *,
    export_path: Path,
    source_map_path: Path,
    dataset_yaml: Path,
) -> MaterializationSummary:
    """Materialize supplement section YOLO export rows into image/label files.

    Args:
        export_path: Sanitized supplement-section YOLO export artifact.
        source_map_path: Operator-only private source-ref to image path map.
        dataset_yaml: Ultralytics dataset YAML path.

    Returns:
        Safe aggregate summary.

    Raises:
        DatasetContractError: If dataset YAML or output files are invalid.
        MaterializationError: If export/source map input is invalid.
    """
    dataset = load_dataset_yaml(dataset_yaml)
    export = _load_json_object(export_path, "export artifact")
    source_map = _load_source_map(source_map_path)
    _validate_export_header(export)

    split_counts = {"train": 0, "val": 0, "test": 0}
    seen_outputs: set[tuple[str, str]] = set()
    items = _export_items(export)
    for item in items:
        split = _item_split(item)
        source_ref = _source_ref(item)
        source_image = _source_image_for_ref(source_ref, source_map)
        digest = _source_ref_digest(source_ref)
        output_key = (split, digest)
        if output_key in seen_outputs:
            raise MaterializationError("Duplicate source item for one YOLO split.")
        seen_outputs.add(output_key)

        image_destination = _image_destination(
            dataset.root, _split_image_dir(dataset, split), digest, source_image
        )
        label_destination = _label_destination(
            dataset.root, _split_image_dir(dataset, split), digest
        )
        _write_image(image_source=source_image, image_destination=image_destination)
        _write_label_file(label_destination=label_destination, labels=_item_labels(item))
        split_counts[split] += 1

    validation = validate_dataset(dataset_yaml, require_files=True)
    return MaterializationSummary(
        dataset_yaml=validation.dataset_yaml,
        item_count=len(items),
        image_count=validation.image_count,
        label_count=validation.label_count,
        split_counts=split_counts,
    )


def _load_json_object(path: Path, description: str) -> dict[str, Any]:
    """Load a JSON object from disk without leaking paths in errors.

    Args:
        path: JSON file path.
        description: Human-readable input description.

    Returns:
        Parsed JSON object.

    Raises:
        MaterializationError: If the file is missing or malformed.
    """
    if not path.is_file():
        raise MaterializationError(f"{description} file does not exist.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MaterializationError(f"{description} JSON is malformed.") from exc
    if not isinstance(value, dict):
        raise MaterializationError(f"{description} must be a JSON object.")
    return value


def _load_source_map(path: Path) -> dict[str, Path]:
    """Load an operator-only private source map.

    Args:
        path: JSON map path.

    Returns:
        Mapping from private source refs to local image paths.

    Raises:
        MaterializationError: If the source map is malformed.
    """
    payload = _load_json_object(path, "source map")
    if "sources" in payload:
        raw_sources = payload["sources"]
        if not isinstance(raw_sources, list):
            raise MaterializationError("source map sources must be a list.")
        return _source_map_from_rows(raw_sources, base_dir=path.parent)
    return _source_map_from_mapping(payload, base_dir=path.parent)


def _source_map_from_rows(raw_sources: list[object], *, base_dir: Path) -> dict[str, Path]:
    """Parse source map rows.

    Args:
        raw_sources: Source rows.
        base_dir: Directory used to resolve relative paths.

    Returns:
        Private source-ref to image-path mapping.
    """
    sources: dict[str, Path] = {}
    for row in raw_sources:
        if not isinstance(row, dict):
            raise MaterializationError("source map rows must be objects.")
        source_ref = row.get("source_ref")
        image_path = row.get("image_path")
        _add_source_mapping(
            sources, source_ref=source_ref, image_path=image_path, base_dir=base_dir
        )
    return sources


def _source_map_from_mapping(payload: dict[str, Any], *, base_dir: Path) -> dict[str, Path]:
    """Parse a direct source-ref to image-path JSON object.

    Args:
        payload: Raw source map payload.
        base_dir: Directory used to resolve relative paths.

    Returns:
        Private source-ref to image-path mapping.
    """
    sources: dict[str, Path] = {}
    for source_ref, image_path in payload.items():
        _add_source_mapping(
            sources, source_ref=source_ref, image_path=image_path, base_dir=base_dir
        )
    return sources


def _add_source_mapping(
    sources: dict[str, Path],
    *,
    source_ref: object,
    image_path: object,
    base_dir: Path,
) -> None:
    """Add one validated source mapping.

    Args:
        sources: Mutable source mapping.
        source_ref: Candidate private source ref.
        image_path: Candidate image path.
        base_dir: Directory used to resolve relative paths.

    Raises:
        MaterializationError: If the mapping is invalid.
    """
    if not isinstance(source_ref, str) or not source_ref.strip():
        raise MaterializationError("source map entries require source_ref.")
    if source_ref in sources:
        raise MaterializationError("source map contains duplicate source_ref entries.")
    if not isinstance(image_path, str) or not image_path.strip():
        raise MaterializationError("source map entries require image_path.")
    candidate = Path(image_path)
    resolved = candidate if candidate.is_absolute() else base_dir / candidate
    sources[source_ref] = resolved.resolve()


def _validate_export_header(export: dict[str, Any]) -> None:
    """Validate supplement section export schema and class names.

    Args:
        export: Export artifact.

    Raises:
        MaterializationError: If the export is not a supplement section artifact.
    """
    if export.get("schema_version") != SUPPLEMENT_SECTION_YOLO_EXPORT_SCHEMA_VERSION:
        raise MaterializationError("Unsupported supplement section YOLO export schema.")
    if export.get("class_names") != list(SUPPLEMENT_SECTION_CLASS_NAMES):
        raise MaterializationError("Export class names do not match supplement section contract.")


def _export_items(export: dict[str, Any]) -> list[dict[str, Any]]:
    """Return export items after shape validation.

    Args:
        export: Export artifact.

    Returns:
        Export item rows.
    """
    items = export.get("items")
    if not isinstance(items, list) or not items:
        raise MaterializationError("Export artifact requires at least one item.")
    if export.get("item_count") != len(items):
        raise MaterializationError("Export item_count does not match items.")
    if not all(isinstance(item, dict) for item in items):
        raise MaterializationError("Export items must be objects.")
    return items


def _item_split(item: dict[str, Any]) -> str:
    """Return and validate the dataset split for one export item."""
    split = item.get("split")
    if split not in SUPPORTED_SPLITS:
        raise MaterializationError("Export item split is not supported for YOLO materialization.")
    return split


def _source_ref(item: dict[str, Any]) -> str:
    """Return a private source ref for one export item."""
    source_ref = item.get("source_ref")
    if not isinstance(source_ref, str) or not source_ref.strip():
        raise MaterializationError("Export item requires source_ref.")
    if "://" in source_ref or source_ref.startswith("/") or ".." in source_ref:
        raise MaterializationError("Export source_ref must be a private token.")
    return source_ref


def _source_image_for_ref(source_ref: str, source_map: dict[str, Path]) -> Path:
    """Resolve one private source ref to a local image path."""
    source_image = source_map.get(source_ref)
    if source_image is None:
        raise MaterializationError("Source map is missing an export item.")
    if not source_image.is_file():
        raise MaterializationError("Source image for one export item does not exist.")
    if source_image.suffix.lower() not in IMAGE_SUFFIXES:
        raise MaterializationError("Source image format is not supported for YOLO materialization.")
    return source_image


def _source_ref_digest(source_ref: str) -> str:
    """Return a stable opaque filename stem for one source ref."""
    return hashlib.sha256(source_ref.encode("utf-8")).hexdigest()[:SOURCE_REF_HASH_LENGTH]


def _split_image_dir(dataset: Any, split: str) -> str:
    """Return the configured image directory for a split."""
    if split == "train":
        return dataset.train
    if split == "val":
        return dataset.val
    if split == "test" and dataset.test:
        return dataset.test
    raise MaterializationError("Dataset YAML does not configure the requested split.")


def _image_destination(root: Path, image_dir: str, digest: str, source_image: Path) -> Path:
    """Return destination image path for a source image."""
    return root / image_dir / f"{digest}{source_image.suffix.lower()}"


def _label_destination(root: Path, image_dir: str, digest: str) -> Path:
    """Return destination YOLO label path for a source image."""
    return root / image_dir.replace("images", "labels", 1) / f"{digest}.txt"


def _write_image(*, image_source: Path, image_destination: Path) -> None:
    """Copy one image into the YOLO dataset directory."""
    image_destination.parent.mkdir(parents=True, exist_ok=True)
    if image_destination.exists():
        raise MaterializationError("Destination image already exists.")
    shutil.copy2(image_source, image_destination)


def _write_label_file(*, label_destination: Path, labels: list[dict[str, Any]]) -> None:
    """Write one YOLO label file."""
    label_destination.parent.mkdir(parents=True, exist_ok=True)
    if label_destination.exists():
        raise MaterializationError("Destination label file already exists.")
    rows = [_label_row(label) for label in labels]
    label_destination.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _item_labels(item: dict[str, Any]) -> list[dict[str, Any]]:
    """Return labels for one export item."""
    labels = item.get("labels")
    if not isinstance(labels, list) or not labels:
        raise MaterializationError("Export item requires at least one label.")
    if not all(isinstance(label, dict) for label in labels):
        raise MaterializationError("Export item labels must be objects.")
    return labels


def _label_row(label: dict[str, Any]) -> str:
    """Return one YOLO label row.

    Args:
        label: Normalized label mapping from the section export.

    Returns:
        YOLO ``class x_center y_center width height`` row.
    """
    class_id = label.get("class_id")
    if (
        isinstance(class_id, bool)
        or not isinstance(class_id, int)
        or not 0 <= class_id < len(SUPPLEMENT_SECTION_CLASS_NAMES)
    ):
        raise MaterializationError("YOLO label class_id is outside supplement section names.")
    coordinates = [_coordinate(label, key) for key in ("x_center", "y_center", "width", "height")]
    return " ".join([str(class_id), *coordinates])


def _coordinate(label: dict[str, Any], key: str) -> str:
    """Return one normalized YOLO coordinate string."""
    value = label.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float) or not 0 <= float(value) <= 1:
        raise MaterializationError("YOLO label coordinates must be normalized.")
    return f"{float(value):.{YOLO_FLOAT_PRECISION}f}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", required=True, type=Path)
    parser.add_argument("--source-map", required=True, type=Path)
    parser.add_argument("--dataset-yaml", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Run the materializer CLI.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    try:
        summary = materialize_dataset(
            export_path=args.export,
            source_map_path=args.source_map,
            dataset_yaml=args.dataset_yaml,
        )
    except (DatasetContractError, MaterializationError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1) from exc
    except OSError as exc:
        print(
            json.dumps(
                {"ok": False, "error": "File materialization failed."},
                ensure_ascii=False,
            )
        )
        raise SystemExit(1) from exc
    print(json.dumps({"ok": True, **summary.model_dump()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
