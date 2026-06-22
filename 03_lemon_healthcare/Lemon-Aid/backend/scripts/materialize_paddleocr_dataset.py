"""Materialize PaddleOCR training exports into local dataset files.

This trusted-worker script consumes sanitized
``learning-paddleocr-det-export-v1`` or ``learning-paddleocr-rec-export-v1``
artifacts and an operator-only source map that resolves private ``source_ref``
tokens to local image files. It writes PaddleOCR-compatible label files and
image copies, while stdout only includes aggregate counts.

PaddleOCR text detection labels are emitted as::

    image/path<TAB>[{"transcription": "text", "points": [[x1, y1], ...]}]

PaddleOCR recognition labels are emitted as::

    image/path<TAB>confirmed text label

References:
    https://www.paddleocr.ai/main/en/datasets/ocr_datasets.html
    https://www.paddleocr.ai/v3.3.2/en/version2.x/ppocr/model_train/finetune.html
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

try:
    from PIL import Image
except ImportError:  # pragma: no cover - environment dependent
    Image = None  # type: ignore[assignment]

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.learning.retraining import (  # noqa: E402
    PADDLEOCR_DETECTION_EXPORT_SCHEMA_VERSION,
    PADDLEOCR_RECOGNITION_EXPORT_SCHEMA_VERSION,
)

SUMMARY_SCHEMA_VERSION = "paddleocr-dataset-materialize-summary-v1"
SUPPORTED_SPLITS = frozenset({"train", "val", "test"})
IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp"})
SOURCE_REF_HASH_LENGTH = 20
DETECTION_TRANSCRIPTION_PLACEHOLDER = "text"
SOURCE_DOC_URLS = (
    "https://www.paddleocr.ai/main/en/datasets/ocr_datasets.html",
    "https://www.paddleocr.ai/v3.3.2/en/version2.x/ppocr/model_train/finetune.html",
)


class PaddleOCRMaterializationError(ValueError):
    """Raised when PaddleOCR dataset materialization input is invalid."""


@dataclass(frozen=True)
class SourceImage:
    """Resolved private source image.

    Attributes:
        path: Local source image path.
        width_px: Optional image width in pixels.
        height_px: Optional image height in pixels.
    """

    path: Path
    width_px: int | None = None
    height_px: int | None = None


@dataclass(frozen=True)
class MaterializationSummary:
    """Safe aggregate materialization summary.

    Attributes:
        export_schema_version: Source export schema version.
        item_count: Number of materialized export items.
        image_count: Number of images copied.
        label_file_count: Number of split label files written.
        split_counts: Number of materialized items by split.
        label_files: Label file names only.
    """

    export_schema_version: str
    item_count: int
    image_count: int
    label_file_count: int
    split_counts: dict[str, int]
    label_files: list[str]

    def model_dump(self) -> dict[str, Any]:
        """Return a JSON-serializable safe summary.

        Returns:
            Summary without source refs, source paths, labels, or raw payloads.
        """
        return {
            "schema_version": SUMMARY_SCHEMA_VERSION,
            "status": "ok",
            "export_schema_version": self.export_schema_version,
            "item_count": self.item_count,
            "image_count": self.image_count,
            "label_file_count": self.label_file_count,
            "split_counts": self.split_counts,
            "label_files": self.label_files,
            "source_ref_printed": False,
            "source_path_printed": False,
            "label_text_printed": False,
            "raw_ocr_text_stored": False,
            "raw_provider_payload_stored": False,
            "paddleocr_training_performed": False,
            "source_doc_urls": list(SOURCE_DOC_URLS),
        }


def materialize_paddleocr_dataset(
    *,
    export_path: Path,
    source_map_path: Path,
    output_dir: Path,
) -> MaterializationSummary:
    """Materialize a PaddleOCR detection or recognition export.

    Args:
        export_path: Sanitized PaddleOCR export artifact.
        source_map_path: Operator-only private source-ref to image path map.
        output_dir: Destination dataset directory.

    Returns:
        Safe aggregate summary.

    Raises:
        PaddleOCRMaterializationError: If export/source map/input files are invalid.
    """
    export = _load_json_object(export_path, "export artifact")
    source_map = _load_source_map(source_map_path)
    schema_version = _export_schema_version(export)
    items = _export_items(export)
    if schema_version == PADDLEOCR_DETECTION_EXPORT_SCHEMA_VERSION:
        return _materialize_detection_export(
            items=items,
            source_map=source_map,
            output_dir=output_dir,
            schema_version=schema_version,
        )
    if schema_version == PADDLEOCR_RECOGNITION_EXPORT_SCHEMA_VERSION:
        return _materialize_recognition_export(
            items=items,
            source_map=source_map,
            output_dir=output_dir,
            schema_version=schema_version,
        )
    raise PaddleOCRMaterializationError("Unsupported PaddleOCR export schema.")


def _materialize_detection_export(
    *,
    items: list[dict[str, Any]],
    source_map: dict[str, SourceImage],
    output_dir: Path,
    schema_version: str,
) -> MaterializationSummary:
    """Materialize PaddleOCR text detection data.

    Args:
        items: Export item rows.
        source_map: Private source map.
        output_dir: Dataset output directory.
        schema_version: Export schema version.

    Returns:
        Safe aggregate summary.
    """
    split_lines: dict[str, list[str]] = {split: [] for split in SUPPORTED_SPLITS}
    split_counts = {"train": 0, "val": 0, "test": 0}
    seen_outputs: set[tuple[str, str]] = set()
    for item in items:
        split = _item_split(item)
        source_ref = _source_ref(item)
        source_image = _source_image_for_ref(source_ref, source_map)
        width_px, height_px = _image_dimensions(source_image)
        digest = _source_ref_digest(source_ref)
        output_key = (split, digest)
        if output_key in seen_outputs:
            raise PaddleOCRMaterializationError("Duplicate source item for one split.")
        seen_outputs.add(output_key)

        relative_image_path = _relative_detection_image_path(
            split=split,
            digest=digest,
            suffix=source_image.path.suffix.lower(),
        )
        image_destination = output_dir / relative_image_path
        _copy_image(image_source=source_image.path, image_destination=image_destination)
        annotation = _detection_annotation(
            item=item,
            width_px=width_px,
            height_px=height_px,
        )
        split_lines[split].append(
            f"{relative_image_path.as_posix()}\t"
            f"{json.dumps(annotation, ensure_ascii=False, separators=(',', ':'))}"
        )
        split_counts[split] += 1

    label_files = _write_split_label_files(
        output_dir=output_dir / "det",
        prefix="det_gt",
        split_lines=split_lines,
    )
    return MaterializationSummary(
        export_schema_version=schema_version,
        item_count=len(items),
        image_count=len(items),
        label_file_count=len(label_files),
        split_counts=split_counts,
        label_files=label_files,
    )


def _materialize_recognition_export(
    *,
    items: list[dict[str, Any]],
    source_map: dict[str, SourceImage],
    output_dir: Path,
    schema_version: str,
) -> MaterializationSummary:
    """Materialize PaddleOCR text recognition data.

    Recognition source images are usually text-line or word crops. When an
    reviewed export row carries a normalized ``crop_box``, this script crops
    the private source image locally so whole-label fixtures can still become
    PaddleOCR recognition samples without exposing source paths or label text.

    Args:
        items: Export item rows.
        source_map: Private source map.
        output_dir: Dataset output directory.
        schema_version: Export schema version.

    Returns:
        Safe aggregate summary.
    """
    split_lines: dict[str, list[str]] = {split: [] for split in SUPPORTED_SPLITS}
    split_counts = {"train": 0, "val": 0, "test": 0}
    seen_outputs: set[tuple[str, str]] = set()
    for item in items:
        split = _item_split(item)
        source_ref = _source_ref(item)
        source_image = _source_image_for_ref(source_ref, source_map)
        digest = _source_ref_digest(source_ref)
        output_key = (split, digest)
        if output_key in seen_outputs:
            raise PaddleOCRMaterializationError("Duplicate source item for one split.")
        seen_outputs.add(output_key)

        text_label = _text_label(item)
        relative_image_path = _relative_recognition_image_path(
            split=split,
            digest=digest,
            suffix=source_image.path.suffix.lower(),
        )
        image_destination = output_dir / relative_image_path
        crop_box = _recognition_crop_box(item)
        if crop_box is None:
            _copy_image(image_source=source_image.path, image_destination=image_destination)
        else:
            _crop_image(
                source_image=source_image,
                image_destination=image_destination,
                crop_box=crop_box,
            )
        split_lines[split].append(f"{relative_image_path.as_posix()}\t{text_label}")
        split_counts[split] += 1

    label_files = _write_split_label_files(
        output_dir=output_dir / "rec",
        prefix="rec_gt",
        split_lines=split_lines,
    )
    return MaterializationSummary(
        export_schema_version=schema_version,
        item_count=len(items),
        image_count=len(items),
        label_file_count=len(label_files),
        split_counts=split_counts,
        label_files=label_files,
    )


def _load_json_object(path: Path, description: str) -> dict[str, Any]:
    """Load a JSON object from disk without exposing paths in errors.

    Args:
        path: JSON file path.
        description: Human-readable input description.

    Returns:
        Parsed JSON object.

    Raises:
        PaddleOCRMaterializationError: If the file is missing or malformed.
    """
    if not path.is_file():
        raise PaddleOCRMaterializationError(f"{description} file does not exist.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaddleOCRMaterializationError(f"{description} JSON is malformed.") from exc
    if not isinstance(value, dict):
        raise PaddleOCRMaterializationError(f"{description} must be a JSON object.")
    return value


def _load_source_map(path: Path) -> dict[str, SourceImage]:
    """Load an operator-only private source map.

    Args:
        path: JSON source map path.

    Returns:
        Source ref mapping.

    Raises:
        PaddleOCRMaterializationError: If the source map is malformed.
    """
    payload = _load_json_object(path, "source map")
    if "sources" in payload:
        raw_sources = payload["sources"]
        if not isinstance(raw_sources, list):
            raise PaddleOCRMaterializationError("source map sources must be a list.")
        return _source_map_from_rows(raw_sources, base_dir=path.parent)
    return _source_map_from_mapping(payload, base_dir=path.parent)


def _source_map_from_rows(
    raw_sources: list[object],
    *,
    base_dir: Path,
) -> dict[str, SourceImage]:
    """Parse row-form source map.

    Args:
        raw_sources: Source rows.
        base_dir: Directory for relative image paths.

    Returns:
        Private source-ref to source image mapping.
    """
    sources: dict[str, SourceImage] = {}
    for row in raw_sources:
        if not isinstance(row, dict):
            raise PaddleOCRMaterializationError("source map rows must be objects.")
        _add_source_mapping(
            sources,
            source_ref=row.get("source_ref"),
            image_path=row.get("image_path"),
            width_px=row.get("width_px"),
            height_px=row.get("height_px"),
            base_dir=base_dir,
        )
    return sources


def _source_map_from_mapping(
    payload: dict[str, Any],
    *,
    base_dir: Path,
) -> dict[str, SourceImage]:
    """Parse direct source-ref to image-path mapping.

    Args:
        payload: Source map object.
        base_dir: Directory for relative image paths.

    Returns:
        Private source-ref to source image mapping.
    """
    sources: dict[str, SourceImage] = {}
    for source_ref, image_path in payload.items():
        _add_source_mapping(
            sources,
            source_ref=source_ref,
            image_path=image_path,
            width_px=None,
            height_px=None,
            base_dir=base_dir,
        )
    return sources


def _add_source_mapping(
    sources: dict[str, SourceImage],
    *,
    source_ref: object,
    image_path: object,
    width_px: object,
    height_px: object,
    base_dir: Path,
) -> None:
    """Add one validated source mapping.

    Args:
        sources: Mutable source map.
        source_ref: Candidate private source ref.
        image_path: Candidate source image path.
        width_px: Optional source width.
        height_px: Optional source height.
        base_dir: Directory for relative image paths.

    Raises:
        PaddleOCRMaterializationError: If the mapping is invalid.
    """
    if not isinstance(source_ref, str) or not source_ref.strip():
        raise PaddleOCRMaterializationError("source map entries require source_ref.")
    if source_ref in sources:
        raise PaddleOCRMaterializationError("source map contains duplicate source_ref entries.")
    _validate_private_source_ref(source_ref)
    if not isinstance(image_path, str) or not image_path.strip():
        raise PaddleOCRMaterializationError("source map entries require image_path.")
    candidate = Path(image_path)
    resolved = candidate if candidate.is_absolute() else base_dir / candidate
    sources[source_ref] = SourceImage(
        path=resolved.resolve(),
        width_px=_optional_positive_int(width_px),
        height_px=_optional_positive_int(height_px),
    )


def _export_schema_version(export: dict[str, Any]) -> str:
    """Return the supported PaddleOCR export schema version.

    Args:
        export: Export artifact.

    Returns:
        Export schema version.

    Raises:
        PaddleOCRMaterializationError: If the schema is not supported.
    """
    schema_version = export.get("schema_version")
    if schema_version not in {
        PADDLEOCR_DETECTION_EXPORT_SCHEMA_VERSION,
        PADDLEOCR_RECOGNITION_EXPORT_SCHEMA_VERSION,
    }:
        raise PaddleOCRMaterializationError("Unsupported PaddleOCR export schema.")
    return str(schema_version)


def _export_items(export: dict[str, Any]) -> list[dict[str, Any]]:
    """Return export items after shape validation.

    Args:
        export: Export artifact.

    Returns:
        Export item rows.
    """
    items = export.get("items")
    if not isinstance(items, list) or not items:
        raise PaddleOCRMaterializationError("Export artifact requires at least one item.")
    if export.get("item_count") != len(items):
        raise PaddleOCRMaterializationError("Export item_count does not match items.")
    if not all(isinstance(item, dict) for item in items):
        raise PaddleOCRMaterializationError("Export items must be objects.")
    return items


def _item_split(item: dict[str, Any]) -> str:
    """Return a supported dataset split for one item."""
    split = item.get("split")
    if split not in SUPPORTED_SPLITS:
        raise PaddleOCRMaterializationError(
            "Export item split is not supported for PaddleOCR materialization."
        )
    return str(split)


def _source_ref(item: dict[str, Any]) -> str:
    """Return a private source ref for one item."""
    source_ref = item.get("source_ref")
    if not isinstance(source_ref, str) or not source_ref.strip():
        raise PaddleOCRMaterializationError("Export item requires source_ref.")
    _validate_private_source_ref(source_ref)
    return source_ref


def _validate_private_source_ref(source_ref: str) -> None:
    """Validate a backend-private source ref.

    Args:
        source_ref: Candidate source ref.

    Raises:
        PaddleOCRMaterializationError: If the ref is URL/path-like.
    """
    if (
        "://" in source_ref
        or source_ref.startswith("/")
        or "\\" in source_ref
        or ".." in source_ref
    ):
        raise PaddleOCRMaterializationError("source_ref must be a private token.")


def _source_image_for_ref(source_ref: str, source_map: dict[str, SourceImage]) -> SourceImage:
    """Resolve a private source ref to a local image path."""
    source_image = source_map.get(source_ref)
    if source_image is None:
        raise PaddleOCRMaterializationError("Source map is missing an export item.")
    if not source_image.path.is_file():
        raise PaddleOCRMaterializationError("Source image for one export item does not exist.")
    if source_image.path.suffix.lower() not in IMAGE_SUFFIXES:
        raise PaddleOCRMaterializationError(
            "Source image format is not supported for PaddleOCR materialization."
        )
    return source_image


def _image_dimensions(source_image: SourceImage) -> tuple[int, int]:
    """Return image dimensions for detection label conversion.

    Args:
        source_image: Resolved source image.

    Returns:
        Width and height in pixels.

    Raises:
        PaddleOCRMaterializationError: If dimensions cannot be determined.
    """
    if source_image.width_px is not None and source_image.height_px is not None:
        return source_image.width_px, source_image.height_px
    if Image is None:
        raise PaddleOCRMaterializationError(
            "Detection materialization requires source dimensions or Pillow."
        )
    try:
        with Image.open(source_image.path) as image:
            width, height = image.size
    except OSError as exc:
        raise PaddleOCRMaterializationError("Source image dimensions could not be read.") from exc
    if width <= 0 or height <= 0:
        raise PaddleOCRMaterializationError("Source image dimensions must be positive.")
    return int(width), int(height)


def _optional_positive_int(value: object) -> int | None:
    """Return an optional positive integer.

    Args:
        value: Candidate value.

    Returns:
        Positive integer or None.

    Raises:
        PaddleOCRMaterializationError: If provided value is not positive.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PaddleOCRMaterializationError("source map dimensions must be positive integers.")
    return value


def _source_ref_digest(source_ref: str) -> str:
    """Return a stable opaque filename stem for one source ref."""
    return hashlib.sha256(source_ref.encode("utf-8")).hexdigest()[:SOURCE_REF_HASH_LENGTH]


def _relative_detection_image_path(*, split: str, digest: str, suffix: str) -> Path:
    """Return a relative detection image path for PaddleOCR labels."""
    return Path("det") / "images" / split / f"{digest}{suffix}"


def _relative_recognition_image_path(*, split: str, digest: str, suffix: str) -> Path:
    """Return a relative recognition image path for PaddleOCR labels."""
    return Path("rec") / split / f"{digest}{suffix}"


def _copy_image(*, image_source: Path, image_destination: Path) -> None:
    """Copy one source image to a dataset path.

    Args:
        image_source: Source image path.
        image_destination: Destination image path.

    Raises:
        PaddleOCRMaterializationError: If a destination already exists.
    """
    image_destination.parent.mkdir(parents=True, exist_ok=True)
    if image_destination.exists():
        raise PaddleOCRMaterializationError("Destination image already exists.")
    shutil.copyfile(image_source, image_destination)


def _detection_annotation(
    *,
    item: dict[str, Any],
    width_px: int,
    height_px: int,
) -> list[dict[str, object]]:
    """Return PaddleOCR detection annotation objects for one item.

    Args:
        item: Detection export item.
        width_px: Source image width.
        height_px: Source image height.

    Returns:
        PaddleOCR-compatible annotation list.
    """
    boxes = item.get("textline_boxes")
    if not isinstance(boxes, list) or not boxes:
        raise PaddleOCRMaterializationError("Detection item requires textline_boxes.")
    annotations = []
    for box in boxes:
        if not isinstance(box, dict):
            raise PaddleOCRMaterializationError("Detection textline box must be an object.")
        annotations.append(
            {
                "transcription": DETECTION_TRANSCRIPTION_PLACEHOLDER,
                "points": _box_points(box=box, width_px=width_px, height_px=height_px),
            }
        )
    return annotations


def _box_points(*, box: dict[str, Any], width_px: int, height_px: int) -> list[list[int]]:
    """Convert normalized center box coordinates to clockwise pixel points."""
    x_center = _normalized_float(box.get("x_center"))
    y_center = _normalized_float(box.get("y_center"))
    box_width = _normalized_float(box.get("width"))
    box_height = _normalized_float(box.get("height"))
    if box_width <= 0 or box_height <= 0:
        raise PaddleOCRMaterializationError("Detection box dimensions must be positive.")
    x_min = max(0, round((x_center - box_width / 2) * width_px))
    y_min = max(0, round((y_center - box_height / 2) * height_px))
    x_max = min(width_px - 1, round((x_center + box_width / 2) * width_px))
    y_max = min(height_px - 1, round((y_center + box_height / 2) * height_px))
    if x_max <= x_min or y_max <= y_min:
        raise PaddleOCRMaterializationError("Detection box collapsed after pixel conversion.")
    return [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]]


def _normalized_float(value: object) -> float:
    """Return a normalized float coordinate."""
    if isinstance(value, bool) or not isinstance(value, int | float) or not 0 <= float(value) <= 1:
        raise PaddleOCRMaterializationError("Detection box coordinates must be normalized.")
    return float(value)


def _text_label(item: dict[str, Any]) -> str:
    """Return a confirmed recognition label.

    Args:
        item: Recognition export item.

    Returns:
        Text label.

    Raises:
        PaddleOCRMaterializationError: If the label contains line breaks or tabs.
    """
    text_label = item.get("text_label")
    if not isinstance(text_label, str) or not text_label.strip():
        raise PaddleOCRMaterializationError("Recognition item requires text_label.")
    if "\t" in text_label or "\n" in text_label or "\r" in text_label:
        raise PaddleOCRMaterializationError("Recognition text label must be one tab-safe line.")
    return text_label.strip()


def _recognition_crop_box(item: dict[str, Any]) -> dict[str, float] | None:
    """Return an optional normalized crop box for recognition training.

    Args:
        item: Recognition export item.

    Returns:
        Normalized crop box or None.

    Raises:
        PaddleOCRMaterializationError: If crop coordinates are malformed.
    """
    raw_box = item.get("crop_box")
    if raw_box is None:
        return None
    if not isinstance(raw_box, dict):
        raise PaddleOCRMaterializationError("Recognition crop_box must be an object.")
    crop_box = {}
    for key in ("x_center", "y_center", "width", "height"):
        crop_box[key] = _normalized_float(raw_box.get(key))
    if crop_box["width"] <= 0 or crop_box["height"] <= 0:
        raise PaddleOCRMaterializationError("Recognition crop_box dimensions must be positive.")
    return crop_box


def _crop_image(
    *,
    source_image: SourceImage,
    image_destination: Path,
    crop_box: dict[str, float],
) -> None:
    """Crop one source image into a recognition training image.

    Args:
        source_image: Source image with optional dimensions.
        image_destination: Destination crop path.
        crop_box: Normalized crop box.

    Raises:
        PaddleOCRMaterializationError: If crop generation fails.
    """
    if Image is None:
        raise PaddleOCRMaterializationError("Recognition crop materialization requires Pillow.")
    image_destination.parent.mkdir(parents=True, exist_ok=True)
    if image_destination.exists():
        raise PaddleOCRMaterializationError("Destination image already exists.")
    try:
        with Image.open(source_image.path) as image:
            width_px, height_px = image.size
            crop_rectangle = _crop_rectangle(
                crop_box=crop_box,
                width_px=width_px,
                height_px=height_px,
            )
            image.crop(crop_rectangle).save(image_destination)
    except OSError as exc:
        raise PaddleOCRMaterializationError("Recognition crop image could not be written.") from exc


def _crop_rectangle(
    *,
    crop_box: dict[str, float],
    width_px: int,
    height_px: int,
) -> tuple[int, int, int, int]:
    """Convert normalized crop box to a Pillow crop rectangle."""
    x_center = crop_box["x_center"]
    y_center = crop_box["y_center"]
    box_width = crop_box["width"]
    box_height = crop_box["height"]
    x_min = max(0, round((x_center - box_width / 2) * width_px))
    y_min = max(0, round((y_center - box_height / 2) * height_px))
    x_max = min(width_px, round((x_center + box_width / 2) * width_px))
    y_max = min(height_px, round((y_center + box_height / 2) * height_px))
    if x_max <= x_min or y_max <= y_min:
        raise PaddleOCRMaterializationError("Recognition crop_box collapsed after conversion.")
    return x_min, y_min, x_max, y_max


def _write_split_label_files(
    *,
    output_dir: Path,
    prefix: str,
    split_lines: dict[str, list[str]],
) -> list[str]:
    """Write one PaddleOCR label file per non-empty split.

    Args:
        output_dir: Label file output directory.
        prefix: Label file prefix.
        split_lines: Split to label line mapping.

    Returns:
        Written label file names only.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    label_files = []
    for split in ("train", "val", "test"):
        lines = split_lines[split]
        if not lines:
            continue
        label_path = output_dir / f"{prefix}_{split}.txt"
        if label_path.exists():
            raise PaddleOCRMaterializationError("Destination label file already exists.")
        label_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        label_files.append(label_path.name)
    return label_files


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
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Run the materializer CLI.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    try:
        summary = materialize_paddleocr_dataset(
            export_path=args.export,
            source_map_path=args.source_map,
            output_dir=args.output_dir,
        )
    except (OSError, PaddleOCRMaterializationError) as exc:
        print(json.dumps({"ok": False, "error": _safe_error_message(exc)}, ensure_ascii=False))
        raise SystemExit(1) from exc
    print(json.dumps({"ok": True, **summary.model_dump()}, ensure_ascii=False, indent=2))


def _safe_error_message(error: BaseException) -> str:
    """Return a bounded public error message without filesystem details."""
    message = str(error)[:160]
    for marker in ("/Volumes/", "/private/", "/Users/"):
        if marker in message:
            return "PaddleOCR dataset materialization failed."
    return message or type(error).__name__


if __name__ == "__main__":
    main()
