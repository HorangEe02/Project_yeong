"""Convert mapped AI Hub food images to a 50-class YOLO dataset.

This script reads the local Roboflow-to-AIHub mapping, scans AI Hub JSON labels,
extracts only mapped class chunks from TS/VS zip archives, resizes images, and
writes YOLO labels using the Roboflow class order.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import json
import pickle
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, NotRequired, TypedDict, cast

try:
    from PIL import Image
except ImportError as exc:
    raise SystemExit("Pillow is required. Install it with: pip install pillow") from exc


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_AI_HUB_ROOT = REPO_ROOT / "data" / "food_images" / "raw" / "aihub" / "data"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "data" / "food_images" / "processed" / "aihub_yolo_50"
DEFAULT_TEMP_ROOT = (
    REPO_ROOT / "data" / "food_images" / "interim" / "aihub_yolo_50_extract_temp"
)
DEFAULT_TEMP_ARCHIVE_ROOT = (
    REPO_ROOT / "data" / "food_images" / "quarantine" / "aihub_yolo_50_temp_chunks"
)
DEFAULT_MAP_PATH = (
    REPO_ROOT / "data" / "food_images" / "manifests" / "roboflow_aihub_class_map_50.csv"
)
DEFAULT_SEVEN_ZIP = Path("7z")
RESIZE_TO = 640
JPEG_QUALITY = 90


class LabelRow(TypedDict):
    """Parsed AI Hub label information needed for YOLO conversion."""

    split: str
    class_id: str
    roboflow_class: str
    yolo_index: int
    class_name_ko: str
    width: int
    height: int
    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float
    internal_path: str
    image_name: str
    view_name: str
    set_id: str
    photo_id: str
    label_path: str


class Summary(TypedDict):
    """Processing counters returned by the conversion pipeline."""

    written: int
    missing: int
    bad_bbox: int
    decode_fail: int
    extract_fail: int
    skipped_existing: int
    by_split: dict[str, int]
    by_class: dict[str, int]
    output_root: str
    data_yaml: str
    class_index: str
    dry_run: NotRequired[bool]


def load_class_map(map_path: Path) -> tuple[list[str], dict[str, tuple[int, str]]]:
    """Load Roboflow class order and AI Hub class-id mapping.

    Args:
        map_path: CSV path with ``roboflow_class`` and ``aihub_class_ids`` columns.

    Returns:
        A tuple of Roboflow class names and AI Hub id to YOLO index/class mapping.

    Raises:
        ValueError: If the mapping has empty class ids or duplicate AI Hub ids.

    Examples:
        >>> names, id_map = load_class_map(Path("map.csv"))
        >>> len(names)
        50
    """
    class_names: list[str] = []
    aihub_to_yolo: dict[str, tuple[int, str]] = {}
    duplicate_ids: list[str] = []

    with map_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for index, row in enumerate(reader):
            class_name = row["roboflow_class"].strip()
            class_names.append(class_name)
            ids = [
                value.strip()
                for value in row["aihub_class_ids"].split("|")
                if value.strip()
            ]
            if not ids:
                raise ValueError(f"Empty AI Hub mapping for class: {class_name}")
            for class_id in ids:
                if class_id in aihub_to_yolo:
                    duplicate_ids.append(class_id)
                aihub_to_yolo[class_id] = (index, class_name)

    if len(class_names) != 50:
        raise ValueError(f"Expected 50 Roboflow classes, found {len(class_names)}")
    if duplicate_ids:
        joined = ", ".join(sorted(set(duplicate_ids)))
        raise ValueError(f"Duplicate AI Hub class ids in mapping: {joined}")
    return class_names, aihub_to_yolo


def resolve_label_root(label_parent: Path, prefix: str) -> Path:
    """Find AI Hub label root supporting wrapped and direct folder layouts.

    Args:
        label_parent: ``Training/labeling_data`` or ``Validation/labeling_data``.
        prefix: ``TL`` or ``VL``.

    Returns:
        Directory containing ``TL1``/``VL1`` children.

    Raises:
        FileNotFoundError: If the expected label root cannot be found.

    Examples:
        >>> resolve_label_root(Path("labeling_data"), "TL")
        PosixPath('labeling_data')
    """
    nested = label_parent / prefix
    if (nested / f"{prefix}1").is_dir():
        return nested
    if (label_parent / f"{prefix}1").is_dir():
        return label_parent
    raise FileNotFoundError(f"Cannot find {prefix} labels under {label_parent}")


def split_tokens_from_name(
    file_name: str,
) -> tuple[str, str, str, str, str, str] | None:
    """Parse AI Hub file name tokens.

    Args:
        file_name: AI Hub JSON or JPG file name.

    Returns:
        ``(category, group, class_id, class_name, set_id, photo_id)`` when parsed.

    Examples:
        >>> split_tokens_from_name("A_13_A13001_food_02_09.jpg")
        ('A', '13', 'A13001', 'food', '02', '09')
    """
    stem = Path(file_name).stem
    parts = stem.split("_")
    if len(parts) < 6:
        return None
    return parts[0], parts[1], parts[2], "_".join(parts[3:-2]), parts[-2], parts[-1]


def label_to_internal_path(label_path: Path, label_root: Path) -> str:
    """Convert AI Hub label path to its zip-internal image path.

    Args:
        label_path: JSON label path.
        label_root: Label root returned by ``resolve_label_root``.

    Returns:
        Zip-internal JPG path using forward slashes.

    Examples:
        >>> label_to_internal_path(Path("TL1/A/13/A13001/x/a.json"), Path("."))
        'TS1/A/13/A13001/x/a.jpg'
    """
    parts = list(label_path.relative_to(label_root).parts)
    if parts[0].startswith("TL"):
        parts[0] = f"TS{parts[0][2:]}"
    elif parts[0].startswith("VL"):
        parts[0] = f"VS{parts[0][2:]}"
    parts[-1] = f"{Path(parts[-1]).stem}.jpg"
    return "/".join(parts)


def find_class_id_from_path(label_path: Path) -> str | None:
    """Find AI Hub class id from a label path.

    Args:
        label_path: JSON label path.

    Returns:
        The first path segment that looks like an AI Hub class id.

    Examples:
        >>> find_class_id_from_path(Path("A/13/A13001/01/x.json"))
        'A13001'
    """
    for part in label_path.parts:
        if len(part) == 6 and part[0] in {"A", "B", "C"} and part[1:].isdigit():
            return part
    return None


def parse_label(
    label_path: Path,
    label_root: Path,
    split: str,
    aihub_to_yolo: dict[str, tuple[int, str]],
) -> LabelRow | None:
    """Parse one AI Hub label JSON when it belongs to the mapped 50 classes.

    Args:
        label_path: JSON label path.
        label_root: Label root for relative path conversion.
        split: Dataset split name.
        aihub_to_yolo: AI Hub id to YOLO index/class mapping.

    Returns:
        Parsed label row or ``None`` for out-of-scope labels.

    Raises:
        json.JSONDecodeError: If the label file is invalid JSON.

    Examples:
        >>> parse_label(path, root, "train", {"A13001": (0, "grilled-fish")})
        {'split': 'train', ...}
    """
    class_id = find_class_id_from_path(label_path)
    if class_id is None or class_id not in aihub_to_yolo:
        return None

    yolo_index, roboflow_class = aihub_to_yolo[class_id]
    data_obj = json.loads(label_path.read_text(encoding="utf-8"))
    data = cast(dict[str, object], data_obj["data"])
    image_info = cast(dict[str, object], data["image_info"])
    annotation = cast(dict[str, object], data["2d_annotation"])
    image_name = str(image_info["file_name"])
    parsed_name = split_tokens_from_name(image_name)
    if parsed_name is None:
        return None
    _, _, _, class_name_ko, set_id, photo_id = parsed_name

    return {
        "split": split,
        "class_id": class_id,
        "roboflow_class": roboflow_class,
        "yolo_index": yolo_index,
        "class_name_ko": class_name_ko,
        "width": int(image_info["width"]),
        "height": int(image_info["height"]),
        "bbox_x": float(annotation["x"]),
        "bbox_y": float(annotation["y"]),
        "bbox_w": float(annotation["width"]),
        "bbox_h": float(annotation["height"]),
        "internal_path": label_to_internal_path(label_path, label_root),
        "image_name": image_name,
        "view_name": label_path.parent.name,
        "set_id": set_id,
        "photo_id": photo_id,
        "label_path": str(label_path),
    }


def collect_labels(
    ai_hub_root: Path,
    aihub_to_yolo: dict[str, tuple[int, str]],
    splits: Iterable[str],
) -> dict[tuple[str, Path, str], list[LabelRow]]:
    """Scan labels and group them by archive/class chunk.

    Args:
        ai_hub_root: AI Hub root containing Training and Validation folders.
        aihub_to_yolo: AI Hub id to YOLO index/class mapping.
        splits: Splits to scan.

    Returns:
        Mapping from ``(split, archive, class_folder_pattern)`` to label rows.

    Raises:
        FileNotFoundError: If an archive or label root is missing.

    Examples:
        >>> chunks = collect_labels(root, {"A13001": (0, "grilled-fish")}, ["val"])
        >>> bool(chunks)
        True
    """
    datasets = {
        "train": ("Training", "TS", "TL"),
        "val": ("Validation", "VS", "VL"),
    }
    chunks: dict[tuple[str, Path, str], list[LabelRow]] = defaultdict(list)

    for split in splits:
        folder_name, image_prefix, label_prefix = datasets[split]
        archive = ai_hub_root / folder_name / "raw_data" / f"{image_prefix}.zip"
        if not archive.exists():
            raise FileNotFoundError(f"Archive not found: {archive}")

        label_root = resolve_label_root(
            ai_hub_root / folder_name / "labeling_data", label_prefix
        )
        for label_path in label_root.rglob("*.json"):
            row = parse_label(label_path, label_root, split, aihub_to_yolo)
            if row is None:
                continue
            parts = row["internal_path"].split("/")
            if len(parts) < 4:
                continue
            pattern = "/".join([f"{image_prefix}*", *parts[1:4]])
            chunks[(split, archive, pattern)].append(row)
    return chunks


def extract_chunk(
    seven_zip: Path, archive: Path, pattern: str, temp_root: Path, timeout: int
) -> bool:
    """Extract one archive class-folder chunk into the temporary root.

    Args:
        seven_zip: 7-Zip executable path.
        archive: Zip archive path.
        pattern: Zip-internal class-folder pattern.
        temp_root: Temporary output root.
        timeout: Extraction timeout in seconds.

    Returns:
        ``True`` when 7-Zip reports success.

    Examples:
        >>> extract_chunk(Path("7z"), Path("TS.zip"), "TS1/A/13/A13001", Path("tmp"), 60)
        False
    """
    command = [
        str(seven_zip),
        "x",
        str(archive),
        pattern,
        f"-o{temp_root}",
        "-aoa",
        "-y",
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        print(f"[extract-fail] {pattern}: {message[:500]}", flush=True)
        return False
    return True


def resolve_executable(executable: Path) -> Path:
    """Resolve an executable from an explicit path or PATH lookup.

    Args:
        executable: Executable name or absolute/relative path.

    Returns:
        Resolved executable path suitable for subprocess execution.

    Raises:
        FileNotFoundError: If the executable cannot be found.
    """
    if executable.is_absolute() or executable.parent != Path("."):
        if executable.exists():
            return executable
        raise FileNotFoundError(f"executable not found: {executable}")
    resolved = shutil.which(str(executable))
    if resolved is None:
        raise FileNotFoundError(f"executable not found on PATH: {executable}")
    return Path(resolved)


def normalize_bbox(row: LabelRow) -> tuple[float, float, float, float] | None:
    """Normalize one absolute AI Hub bbox into YOLO cx/cy/w/h values.

    Args:
        row: Parsed label row.

    Returns:
        Normalized bbox tuple or ``None`` for invalid geometry.

    Examples:
        >>> normalize_bbox({"width": 100, "height": 100, "bbox_x": 0, "bbox_y": 0, "bbox_w": 50, "bbox_h": 50})
        (0.25, 0.25, 0.5, 0.5)
    """
    image_w = row["width"]
    image_h = row["height"]
    bbox_x = row["bbox_x"]
    bbox_y = row["bbox_y"]
    bbox_w = row["bbox_w"]
    bbox_h = row["bbox_h"]
    if image_w <= 0 or image_h <= 0 or bbox_w <= 0 or bbox_h <= 0:
        return None
    center_x = max(0.0, min(1.0, (bbox_x + bbox_w / 2.0) / image_w))
    center_y = max(0.0, min(1.0, (bbox_y + bbox_h / 2.0) / image_h))
    width = max(0.0, min(1.0, bbox_w / image_w))
    height = max(0.0, min(1.0, bbox_h / image_h))
    if width == 0.0 or height == 0.0:
        return None
    return center_x, center_y, width, height


def output_stem(row: LabelRow) -> str:
    """Build a stable output stem without relying on Korean file names.

    Args:
        row: Parsed label row.

    Returns:
        ASCII-only file stem.

    Examples:
        >>> output_stem({"split": "train", "class_id": "A13001", ...})
        'train_A13001_s02_p09_abc12345'
    """
    digest = hashlib.sha1(row["internal_path"].encode("utf-8")).hexdigest()[:8]
    return (
        f"{row['split']}_{row['class_id']}_s{row['set_id']}_p{row['photo_id']}_{digest}"
    )


def output_paths(output_root: Path, row: LabelRow) -> tuple[Path, Path]:
    """Build image and label output paths for one parsed label.

    Args:
        output_root: YOLO dataset root.
        row: Parsed label row.

    Returns:
        Tuple of destination image and label paths.

    Examples:
        >>> image_path, label_path = output_paths(Path("out"), row)
        >>> image_path.suffix
        '.jpg'
    """
    stem = output_stem(row)
    split = row["split"]
    return (
        output_root / split / "images" / f"{stem}.jpg",
        output_root / split / "labels" / f"{stem}.txt",
    )


def chunk_outputs_complete(output_root: Path, rows: list[LabelRow]) -> bool:
    """Check whether every output file for a chunk already exists.

    Args:
        output_root: YOLO dataset root.
        rows: Label rows in one extraction chunk.

    Returns:
        Whether all image/label pairs already exist.

    Examples:
        >>> chunk_outputs_complete(Path("out"), [])
        True
    """
    return all(
        image_path.exists() and label_path.exists()
        for image_path, label_path in (output_paths(output_root, row) for row in rows)
    )


def resize_and_write(src: Path, dst: Path) -> bool:
    """Resize a source image to the YOLO training size.

    Args:
        src: Extracted image path.
        dst: Destination JPEG path.

    Returns:
        Whether image decoding and writing succeeded.

    Examples:
        >>> resize_and_write(Path("input.jpg"), Path("output.jpg"))
        True
    """
    try:
        with Image.open(src) as image:
            rgb_image = image.convert("RGB")
            resized = rgb_image.resize((RESIZE_TO, RESIZE_TO), Image.LANCZOS)
            resized.save(dst, "JPEG", quality=JPEG_QUALITY, optimize=True)
        return True
    except Exception as exc:
        print(f"[decode-fail] {src}: {exc}", flush=True)
        return False


def matching_temp_top_dirs(temp_root: Path, pattern: str) -> list[Path]:
    """Find extracted top-level folders for a chunk pattern.

    Args:
        temp_root: Temporary extraction root.
        pattern: Zip-internal class folder pattern.

    Returns:
        Existing top-level directories matching ``TS*`` or ``VS*``.

    Examples:
        >>> matching_temp_top_dirs(Path("tmp"), "TS*/A/13/A13001")
        []
    """
    top_pattern = pattern.split("/")[0]
    if "*" in top_pattern:
        return [path for path in temp_root.glob(top_pattern) if path.is_dir()]
    chunk_dir = temp_root / top_pattern
    return [chunk_dir] if chunk_dir.is_dir() else []


def archive_temp_chunk(
    temp_root: Path, pattern: str, archive_root: Path, chunk_index: int
) -> None:
    """Move an extracted temporary chunk into an archive folder.

    Args:
        temp_root: Temporary extraction root.
        pattern: Zip-internal class folder pattern.
        archive_root: Root that stores moved temporary chunks.
        chunk_index: Current chunk index for stable archive names.

    Returns:
        None.

    Examples:
        >>> archive_temp_chunk(Path("tmp"), "TS1/A/13/A13001", Path("archive"), 1)
    """
    chunk_dirs = matching_temp_top_dirs(temp_root, pattern)
    if not chunk_dirs:
        return
    safe_pattern = pattern.replace("/", "_").replace("\\", "_").replace("*", "star")
    destination_root = archive_root / f"{chunk_index:05d}_{safe_pattern}"
    destination_root.mkdir(parents=True, exist_ok=True)
    for chunk_dir in chunk_dirs:
        shutil.move(str(chunk_dir), str(destination_root / chunk_dir.name))


def delete_temp_chunk(temp_root: Path, pattern: str) -> None:
    """Delete an extracted temporary chunk.

    Args:
        temp_root: Temporary extraction root.
        pattern: Zip-internal class folder pattern.

    Returns:
        None.

    Examples:
        >>> delete_temp_chunk(Path("tmp"), "TS1/A/13/A13001")
    """
    for chunk_dir in matching_temp_top_dirs(temp_root, pattern):
        shutil.rmtree(chunk_dir, ignore_errors=True)


def write_dataset_files(
    output_root: Path,
    class_names: list[str],
    aihub_to_yolo: dict[str, tuple[int, str]],
) -> tuple[Path, Path]:
    """Write data.yaml and class index JSON.

    Args:
        output_root: YOLO dataset root.
        class_names: Roboflow class names in YOLO order.
        aihub_to_yolo: AI Hub id to YOLO index/class mapping.

    Returns:
        Paths to ``data.yaml`` and ``yolo_class_index_50.json``.

    Examples:
        >>> write_dataset_files(Path("out"), ["class-a"], {"A13001": (0, "class-a")})
        (PosixPath('out/data.yaml'), PosixPath('out/yolo_class_index_50.json'))
    """
    data_yaml = output_root / "data.yaml"
    class_index_path = output_root / "yolo_class_index_50.json"
    lines = [
        "# YOLO dataset config for AI Hub food detection mapped to Roboflow 50 classes",
        f"path: {output_root.as_posix()}",
        "train: train/images",
        "val: val/images",
        "",
        f"nc: {len(class_names)}",
        "names:",
    ]
    for class_name in class_names:
        lines.append(f"  - {class_name}")
    data_yaml.write_text("\n".join(lines) + "\n", encoding="utf-8")

    index_payload = {
        "class_names": class_names,
        "aihub_to_yolo": {
            class_id: {"yolo_index": yolo_index, "roboflow_class": roboflow_class}
            for class_id, (yolo_index, roboflow_class) in sorted(aihub_to_yolo.items())
        },
    }
    class_index_path.write_text(
        json.dumps(index_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return data_yaml, class_index_path


def save_chunks_cache(
    chunks: dict[tuple[str, Path, str], list[LabelRow]],
    cache_path: Path,
) -> None:
    """Persist the chunks mapping to disk to avoid rescanning on resume.

    Args:
        chunks: Mapping from (split, archive, pattern) to label rows.
        cache_path: Destination pickle file path.

    Returns:
        None.

    Examples:
        >>> save_chunks_cache({}, Path("cache.pkl"))
    """
    cache_path.write_bytes(pickle.dumps(chunks))


def load_chunks_cache(
    cache_path: Path,
) -> dict[tuple[str, Path, str], list[LabelRow]]:
    """Load a previously saved chunks mapping from disk.

    Args:
        cache_path: Pickle file written by ``save_chunks_cache``.

    Returns:
        Chunks mapping identical to the original ``collect_labels`` result.

    Examples:
        >>> chunks = load_chunks_cache(Path("cache.pkl"))
        >>> isinstance(chunks, dict)
        True
    """
    return pickle.loads(cache_path.read_bytes())  # noqa: S301


def convert(args: argparse.Namespace) -> Summary:
    """Run the conversion pipeline.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Summary counters and output paths.

    Raises:
        FileNotFoundError: If input paths or 7-Zip are missing.

    Examples:
        >>> summary = convert(args)
        >>> summary["written"] >= 0
        True
    """
    ai_hub_root = Path(args.ai_hub_root)
    output_root = Path(args.output_root)
    temp_root = Path(args.temp_root)
    temp_archive_root = Path(args.temp_archive_root)
    map_path = Path(args.map_path)
    seven_zip = resolve_executable(Path(args.seven_zip))
    splits = [value.strip() for value in args.splits.split(",") if value.strip()]

    if not map_path.exists():
        raise FileNotFoundError(f"Class map not found: {map_path}")
    if (
        output_root.exists()
        and any(output_root.iterdir())
        and not args.resume
        and not args.dry_run
    ):
        raise FileExistsError(
            f"Output root already exists and is not empty: {output_root}"
        )

    class_names, aihub_to_yolo = load_class_map(map_path)
    cache_path = output_root / "chunks_cache.pkl"
    if args.resume and cache_path.exists():
        print("[cache] loading chunks from cache (skipping JSON scan)...", flush=True)
        chunks = load_chunks_cache(cache_path)
        print(f"[cache] loaded {len(chunks)} chunks", flush=True)
    else:
        chunks = collect_labels(ai_hub_root, aihub_to_yolo, splits)
        if not args.dry_run:
            save_chunks_cache(chunks, cache_path)
            print(f"[cache] saved {len(chunks)} chunks → {cache_path}", flush=True)
    chunk_keys = sorted(
        chunks.keys(), key=lambda item: (item[0], str(item[1]), item[2])
    )

    total_labels = sum(len(rows) for rows in chunks.values())
    print(f"[scan] mapped labels: {total_labels}")
    print(f"[scan] chunks: {len(chunk_keys)}")
    split_counts = Counter(row["split"] for rows in chunks.values() for row in rows)
    class_counts = Counter(
        row["roboflow_class"] for rows in chunks.values() for row in rows
    )
    print(f"[scan] split counts: {dict(split_counts)}")

    if args.dry_run:
        return {
            "written": 0,
            "missing": 0,
            "bad_bbox": 0,
            "decode_fail": 0,
            "extract_fail": 0,
            "skipped_existing": 0,
            "by_split": dict(split_counts),
            "by_class": dict(class_counts),
            "output_root": str(output_root),
            "data_yaml": str(output_root / "data.yaml"),
            "class_index": str(output_root / "yolo_class_index_50.json"),
            "dry_run": True,
        }

    for split in ("train", "val"):
        (output_root / split / "images").mkdir(parents=True, exist_ok=True)
        (output_root / split / "labels").mkdir(parents=True, exist_ok=True)
    if args.cleanup_mode == "delete" and temp_root.exists():
        shutil.rmtree(temp_root, ignore_errors=True)
    temp_root.mkdir(parents=True, exist_ok=True)

    written = 0
    missing = 0
    bad_bbox = 0
    decode_fail = 0
    extract_fail = 0
    skipped_existing = 0
    written_by_split: Counter[str] = Counter()
    written_by_class: Counter[str] = Counter()
    started_at = time.time()

    if args.limit_chunks:
        chunk_keys = chunk_keys[: args.limit_chunks]

    for chunk_index, key in enumerate(chunk_keys, 1):
        split, archive, pattern = key
        rows = chunks[key]
        if args.resume and chunk_outputs_complete(output_root, rows):
            skipped_existing += len(rows)
            print(
                f"[{chunk_index}/{len(chunk_keys)}] {split} {pattern}: skip complete chunk",
                flush=True,
            )
            continue

        if not extract_chunk(
            seven_zip, archive, pattern, temp_root, args.extract_timeout
        ):
            extract_fail += 1
            continue

        chunk_written = 0
        for row in rows:
            if args.limit_images and written >= args.limit_images:
                break
            source_image = temp_root / Path(row["internal_path"])
            if not source_image.exists():
                missing += 1
                continue
            bbox = normalize_bbox(row)
            if bbox is None:
                bad_bbox += 1
                continue

            image_output, label_output = output_paths(output_root, row)
            if image_output.exists() and label_output.exists() and args.resume:
                skipped_existing += 1
                continue

            if not resize_and_write(source_image, image_output):
                decode_fail += 1
                continue
            center_x, center_y, width, height = bbox
            label_output.write_text(
                (
                    f"{row['yolo_index']} {center_x:.6f} {center_y:.6f} "
                    f"{width:.6f} {height:.6f}\n"
                ),
                encoding="utf-8",
            )
            written += 1
            chunk_written += 1
            written_by_split[split] += 1
            written_by_class[row["roboflow_class"]] += 1

        if args.cleanup_mode == "archive":
            archive_temp_chunk(temp_root, pattern, temp_archive_root, chunk_index)
        elif args.cleanup_mode == "delete":
            delete_temp_chunk(temp_root, pattern)
        elif args.cleanup_mode == "keep":
            pass
        else:
            raise ValueError(f"Unsupported cleanup mode: {args.cleanup_mode}")

        elapsed = time.time() - started_at
        rate = chunk_index / elapsed if elapsed else 0.0
        remaining = len(chunk_keys) - chunk_index
        eta_min = (remaining / rate / 60.0) if rate else 0.0
        print(
            (
                f"[{chunk_index}/{len(chunk_keys)}] {split} {pattern}: "
                f"+{chunk_written}, total={written}, eta={eta_min:.1f}m"
            ),
            flush=True,
        )

        if (
            args.max_runtime_minutes
            and (time.time() - started_at) / 60.0 >= args.max_runtime_minutes
        ):
            print(
                f"[pause] max runtime reached: {args.max_runtime_minutes} minutes",
                flush=True,
            )
            break

        if args.limit_images and written >= args.limit_images:
            break

    data_yaml, class_index = write_dataset_files(
        output_root, class_names, aihub_to_yolo
    )
    summary: Summary = {
        "written": written,
        "missing": missing,
        "bad_bbox": bad_bbox,
        "decode_fail": decode_fail,
        "extract_fail": extract_fail,
        "skipped_existing": skipped_existing,
        "by_split": dict(written_by_split),
        "by_class": dict(written_by_class),
        "output_root": str(output_root),
        "data_yaml": str(data_yaml),
        "class_index": str(class_index),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser.

    Args:
        None.

    Returns:
        Configured argument parser.

    Examples:
        >>> parser = build_parser()
        >>> parser.prog
        'convert_aihub_50_to_yolo.py'
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--ai-hub-root", default=str(DEFAULT_AI_HUB_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--temp-root", default=str(DEFAULT_TEMP_ROOT))
    parser.add_argument("--temp-archive-root", default=str(DEFAULT_TEMP_ARCHIVE_ROOT))
    parser.add_argument("--map-path", default=str(DEFAULT_MAP_PATH))
    parser.add_argument("--seven-zip", default=str(DEFAULT_SEVEN_ZIP))
    parser.add_argument("--splits", default="train,val")
    parser.add_argument(
        "--cleanup-mode", choices=("archive", "delete", "keep"), default="archive"
    )
    parser.add_argument("--extract-timeout", type=int, default=3600)
    parser.add_argument("--limit-chunks", type=int, default=0)
    parser.add_argument("--limit-images", type=int, default=0)
    parser.add_argument("--max-runtime-minutes", type=float, default=0.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--log-file", default="")
    return parser


def main() -> None:
    """Run the command-line entrypoint.

    Args:
        None.

    Returns:
        None.

    Raises:
        SystemExit: If conversion fails.

    Examples:
        >>> main()
    """
    parser = build_parser()
    args = parser.parse_args()
    log_file = Path(args.log_file) if args.log_file else None
    if log_file is None:
        try:
            convert(args)
        except Exception as exc:
            print(f"[error] {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        return

    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8", buffering=1) as stream:
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            try:
                print(f"[log] writing progress to {log_file}", flush=True)
                convert(args)
            except Exception as exc:
                print(f"[error] {exc}", file=sys.stderr, flush=True)
                raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
