"""Run privacy-safe ROI crop OCR retries for Tampermonkey fixtures.

This operator tool creates temporary in-process crop images for failed
Tampermonkey OCR fixtures and feeds them to the existing redacted OCR collector.
It persists only observation rows plus safe crop metadata. It never persists
crop images, raw OCR text, provider payloads, request headers, image bytes,
raw model responses, secrets, or local path literals.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter
from collections.abc import Awaitable, Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import collect_supplement_ocr_observations as collector  # noqa: E402

SCHEMA_VERSION = "naver-tampermonkey-roi-crop-ocr-eval-v1"
SUMMARY_SCHEMA_VERSION = "naver-tampermonkey-roi-crop-ocr-eval-summary-v1"
DEFAULT_OBSERVATIONS_NAME = "roi-crop-ocr-observations.jsonl"
DEFAULT_SUMMARY_NAME = "roi-crop-ocr-eval.summary.json"
SOURCE_DOC_URLS = (
    "https://pillow.readthedocs.io/en/stable/reference/Image.html",
    "https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html",
)
SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
IMAGE_ROOT_TOKEN_PATTERN = re.compile(r"^\$(?P<env>[A-Z][A-Z0-9_]*)/(?P<relative>.+)$")
ALLOWED_IMAGE_PATH_ENV_VARS = frozenset(
    {
        "LEMON_OCR_FIXTURE_ROOT",
        "NAVER_TAMPERMONKEY_SOURCE_ROOT",
        "SUPPLEMENT_OCR_FIXTURE_ROOT",
    }
)
TEMP_IMAGE_ROOT_ENV = "LEMON_OCR_FIXTURE_ROOT"
RAW_FORBIDDEN_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "image_bytes",
        "ocr_text",
        "provider_payload",
        "raw_image",
        "raw_markdown",
        "raw_model_response",
        "raw_ocr_text",
        "raw_provider_payload",
        "request_headers",
        "service_key",
    }
)
LOCAL_PATH_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    "file://",
    "\\Users\\",
    "\\Volumes\\",
)
MAX_DECODED_PIXELS = 50_000_000
MAX_CROP_PIXELS = 24_000_000


@dataclass(frozen=True)
class CropProfile:
    """One deterministic crop retry profile.

    Args:
        name: Safe public profile token.
        box: Normalized crop box as left, upper, right, lower fractions.
        scale: Resize multiplier applied to the crop before OCR.
        preprocess_mode: Optional image preprocessing mode.
    """

    name: str
    box: tuple[float, float, float, float]
    scale: float
    preprocess_mode: str


CROP_PROFILES: dict[str, CropProfile] = {
    "full_x2": CropProfile("full_x2", (0.0, 0.0, 1.0, 1.0), 2.0, "none"),
    "full_x2_gray": CropProfile(
        "full_x2_gray",
        (0.0, 0.0, 1.0, 1.0),
        2.0,
        "grayscale_autocontrast",
    ),
    "top_half_x2_gray": CropProfile(
        "top_half_x2_gray",
        (0.0, 0.0, 1.0, 0.55),
        2.0,
        "grayscale_autocontrast",
    ),
    "middle_half_x2_gray": CropProfile(
        "middle_half_x2_gray",
        (0.0, 0.225, 1.0, 0.775),
        2.0,
        "grayscale_autocontrast",
    ),
    "bottom_half_x2_gray": CropProfile(
        "bottom_half_x2_gray",
        (0.0, 0.45, 1.0, 1.0),
        2.0,
        "grayscale_autocontrast",
    ),
    "center_80_x2_gray": CropProfile(
        "center_80_x2_gray",
        (0.1, 0.1, 0.9, 0.9),
        2.0,
        "grayscale_autocontrast",
    ),
}
DEFAULT_PROFILE_NAMES = tuple(CROP_PROFILES)
CollectFunc = Callable[..., Awaitable[Any]]


def main() -> None:
    """Run ROI crop retries and write redacted outputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--observations-name", default=DEFAULT_OBSERVATIONS_NAME)
    parser.add_argument("--summary-name", default=DEFAULT_SUMMARY_NAME)
    parser.add_argument(
        "--profiles",
        default=",".join(DEFAULT_PROFILE_NAMES),
        help=f"Comma-separated crop profiles: {','.join(CROP_PROFILES)}",
    )
    parser.add_argument("--llm-parse", action="store_true")
    args = parser.parse_args()

    try:
        rows, summary = asyncio.run(
            run_roi_crop_eval(
                manifest_path=args.manifest.expanduser().resolve(),
                output_dir=args.output_dir.expanduser().resolve(),
                profiles=parse_profiles(args.profiles),
                env_file=args.env_file.expanduser().resolve() if args.env_file else None,
                observations_name=args.observations_name,
                summary_name=args.summary_name,
                llm_parse_enabled=args.llm_parse,
            )
        )
        _write_outputs(
            rows=rows,
            summary=summary,
            output_dir=args.output_dir.expanduser().resolve(),
            observations_name=args.observations_name,
            summary_name=args.summary_name,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure = _failure_summary(
            manifest_path=args.manifest,
            output_dir=args.output_dir,
            error=exc,
        )
        _write_failure_summary(
            failure=failure,
            output_dir=args.output_dir.expanduser().resolve(),
            summary_name=args.summary_name,
        )
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None


def parse_profiles(value: str) -> tuple[CropProfile, ...]:
    """Parse a comma-separated crop profile list.

    Args:
        value: Profile names separated by commas.

    Returns:
        Crop profiles in requested order.

    Raises:
        ValueError: If a profile name is unknown or unsafe.
    """
    names = [_safe_token(item.strip()) for item in value.split(",") if item.strip()]
    if not names:
        raise ValueError("At least one crop profile is required.")
    profiles: list[CropProfile] = []
    for name in names:
        profile = CROP_PROFILES.get(name)
        if profile is None:
            raise ValueError(f"Unsupported crop profile: {name}")
        profiles.append(profile)
    return tuple(profiles)


async def run_roi_crop_eval(
    *,
    manifest_path: Path,
    output_dir: Path,
    profiles: tuple[CropProfile, ...],
    env_file: Path | None = None,
    observations_name: str = DEFAULT_OBSERVATIONS_NAME,
    summary_name: str = DEFAULT_SUMMARY_NAME,
    llm_parse_enabled: bool = False,
    collect_func: CollectFunc | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Run crop retries and return redacted observation rows and summary.

    Args:
        manifest_path: Redacted manifest containing tokenized image paths.
        output_dir: Planned output directory.
        profiles: Crop profiles to try for every manifest row.
        env_file: Optional collector dotenv file.
        observations_name: Observation JSONL filename.
        summary_name: Summary JSON filename.
        llm_parse_enabled: Whether to run memory-only local LLM parsing.
        collect_func: Optional collector function for tests.

    Returns:
        Redacted crop observation rows and summary.
    """
    safe_observations_name = _safe_filename(
        observations_name,
        suffix=".jsonl",
        field_name="observations_name",
    )
    safe_summary_name = _safe_filename(summary_name, suffix=".json", field_name="summary_name")
    manifest_rows = _read_jsonl(manifest_path)
    collect = collect_func or collector.collect_observations_with_auto_expected
    with tempfile.TemporaryDirectory(prefix="lemon-ocr-roi-") as tmp_text:
        temp_root = Path(tmp_text).resolve()
        temp_manifest, crop_metadata = _build_temp_crop_manifest(
            source_rows=manifest_rows,
            profiles=profiles,
            temp_root=temp_root,
        )
        with _temporary_env({TEMP_IMAGE_ROOT_ENV: str(temp_root)}):
            collection = await collect(
                manifest_path=temp_manifest,
                providers=("paddleocr_local",),
                env_file=env_file,
                llm_parse_enabled=llm_parse_enabled,
            )
        raw_observations = getattr(collection, "observations", collection)
        if not isinstance(raw_observations, list):
            raise ValueError("Collector returned unsupported observation payload.")
        rows = _normalize_observations(
            observations=raw_observations,
            crop_metadata=crop_metadata,
        )

    summary = _build_summary(
        rows=rows,
        manifest_path=manifest_path,
        output_dir=output_dir,
        profiles=profiles,
        observations_name=safe_observations_name,
        summary_name=safe_summary_name,
        source_row_count=len(manifest_rows),
        llm_parse_enabled=llm_parse_enabled,
    )
    _reject_output_payload({"rows": rows, "summary": summary})
    return rows, summary


def _build_temp_crop_manifest(
    *,
    source_rows: list[dict[str, object]],
    profiles: tuple[CropProfile, ...],
    temp_root: Path,
) -> tuple[Path, dict[str, dict[str, object]]]:
    """Create a temporary collector manifest and crop images."""
    temp_rows: list[dict[str, object]] = []
    crop_metadata: dict[str, dict[str, object]] = {}
    for row in source_rows:
        _reject_input_payload(row)
        source_fixture_id = _safe_token(_required_str(row, "fixture_id"))
        source_image_path = _resolve_tokenized_image_path(_required_str(row, "image_path"))
        with Image.open(source_image_path) as source:
            source.load()
            if source.width * source.height > MAX_DECODED_PIXELS:
                raise ValueError("Decoded image exceeds ROI crop pixel limit.")
            oriented = ImageOps.exif_transpose(source)
            for profile in profiles:
                temp_fixture_id = f"{source_fixture_id}:{profile.name}"
                crop_image = _profile_crop(oriented, profile)
                crop_filename = f"{_sha256_text(temp_fixture_id)[:24]}.png"
                crop_path = temp_root / crop_filename
                crop_image.save(crop_path, format="PNG", optimize=True)
                crop_bytes = crop_path.read_bytes()
                temp_row = dict(row)
                temp_row["fixture_id"] = temp_fixture_id
                temp_row["image_path"] = f"${TEMP_IMAGE_ROOT_ENV}/{crop_filename}"
                temp_row["image_sha256"] = hashlib.sha256(crop_bytes).hexdigest()
                temp_row["width"] = crop_image.width
                temp_row["height"] = crop_image.height
                temp_row["file_size_bytes"] = len(crop_bytes)
                temp_row["mime_type"] = "image/png"
                temp_rows.append(temp_row)
                crop_metadata[temp_fixture_id] = {
                    "source_fixture_id": source_fixture_id,
                    "roi_crop_profile": profile.name,
                    "roi_crop_preprocess_mode": profile.preprocess_mode,
                    "roi_crop_scale": profile.scale,
                    "roi_crop_box_normalized": [round(part, 4) for part in profile.box],
                    "roi_crop_width": crop_image.width,
                    "roi_crop_height": crop_image.height,
                    "roi_crop_sha256": hashlib.sha256(crop_bytes).hexdigest(),
                    "roi_temp_artifacts_persisted": False,
                }
    temp_manifest = temp_root / "roi-crop-manifest.jsonl"
    temp_manifest.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in temp_rows),
        encoding="utf-8",
    )
    return temp_manifest, crop_metadata


def _profile_crop(source: Image.Image, profile: CropProfile) -> Image.Image:
    """Return one cropped and optionally preprocessed image."""
    left, upper, right, lower = _pixel_box(source.size, profile.box)
    crop = source.crop((left, upper, right, lower))
    if profile.preprocess_mode == "grayscale_autocontrast":
        crop = ImageOps.autocontrast(ImageOps.grayscale(crop)).convert("RGB")
    elif profile.preprocess_mode == "rgb_autocontrast":
        crop = ImageOps.autocontrast(crop.convert("RGB"))
    else:
        crop = crop.convert("RGB")
    if profile.scale != 1.0:
        width = max(1, round(crop.width * profile.scale))
        height = max(1, round(crop.height * profile.scale))
        if width * height > MAX_CROP_PIXELS:
            raise ValueError("ROI crop output exceeds pixel limit.")
        crop = crop.resize((width, height), Image.Resampling.LANCZOS)
    return crop


def _pixel_box(
    size: tuple[int, int],
    box: tuple[float, float, float, float],
) -> tuple[int, int, int, int]:
    """Convert a normalized crop box to bounded pixel coordinates."""
    width, height = size
    left_f, upper_f, right_f, lower_f = box
    if not (0.0 <= left_f < right_f <= 1.0 and 0.0 <= upper_f < lower_f <= 1.0):
        raise ValueError("Invalid ROI crop box.")
    left = max(0, min(width - 1, round(width * left_f)))
    upper = max(0, min(height - 1, round(height * upper_f)))
    right = max(left + 1, min(width, round(width * right_f)))
    lower = max(upper + 1, min(height, round(height * lower_f)))
    return left, upper, right, lower


def _normalize_observations(
    *,
    observations: list[object],
    crop_metadata: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    """Attach safe crop metadata and restore source fixture ids."""
    rows: list[dict[str, object]] = []
    for observation in observations:
        if not isinstance(observation, dict):
            raise ValueError("Collector observation rows must be objects.")
        _reject_input_payload(observation)
        temp_fixture_id = _required_str(observation, "fixture_id")
        metadata = crop_metadata.get(temp_fixture_id)
        if metadata is None:
            raise ValueError("Collector returned an unknown crop fixture id.")
        row = dict(observation)
        row["fixture_id"] = metadata["source_fixture_id"]
        row["roi_crop"] = dict(metadata)
        row["schema_version"] = SCHEMA_VERSION
        row["source_fixture_variant_hash"] = _sha256_text(temp_fixture_id)
        row["raw_artifacts_stored"] = False
        row["raw_ocr_text_stored"] = False
        row["raw_provider_payload_stored"] = False
        row["raw_model_response_stored"] = False
        row["local_path_literals_stored"] = False
        _reject_output_payload(row)
        rows.append(row)
    return rows


def _build_summary(
    *,
    rows: list[dict[str, object]],
    manifest_path: Path,
    output_dir: Path,
    profiles: tuple[CropProfile, ...],
    observations_name: str,
    summary_name: str,
    source_row_count: int,
    llm_parse_enabled: bool,
) -> dict[str, object]:
    """Build a redacted summary for ROI crop retries."""
    status_counts: Counter[str] = Counter()
    error_counts: Counter[str] = Counter()
    completed_by_fixture: Counter[str] = Counter()
    text_non_empty_by_fixture: Counter[str] = Counter()
    llm_status_counts: Counter[str] = Counter()
    profile_status_counts: Counter[str] = Counter()
    for row in rows:
        status = _safe_token(str(row.get("status") or "unknown"))
        fixture_id = _safe_token(str(row.get("fixture_id") or "unknown"))
        crop = row.get("roi_crop")
        profile = "unknown"
        if isinstance(crop, dict):
            profile = _safe_token(str(crop.get("roi_crop_profile") or "unknown"))
        status_counts[status] += 1
        profile_status_counts[f"{profile}:{status}"] += 1
        if status == "completed":
            completed_by_fixture[fixture_id] += 1
        if row.get("text_non_empty") is True:
            text_non_empty_by_fixture[fixture_id] += 1
        error_code = row.get("error_code")
        if isinstance(error_code, str):
            error_counts[_safe_token(error_code)] += 1
        llm_status = row.get("llm_parse_status")
        if isinstance(llm_status, str):
            llm_status_counts[_safe_token(llm_status)] += 1
    summary: dict[str, object] = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_doc_urls": list(SOURCE_DOC_URLS),
        "manifest_name": _safe_filename(manifest_path.name, suffix=".jsonl", field_name="manifest"),
        "manifest_path_hash": _sha256_text(str(manifest_path.expanduser())),
        "output_dir_name": _safe_filename(output_dir.name, field_name="output_dir"),
        "output_dir_hash": _sha256_text(str(output_dir.expanduser())),
        "observations_filename": observations_name,
        "summary_filename": summary_name,
        "source_row_count": source_row_count,
        "profile_names": [profile.name for profile in profiles],
        "crop_observation_count": len(rows),
        "source_fixture_with_completed_crop_count": len(completed_by_fixture),
        "source_fixture_with_text_non_empty_crop_count": len(text_non_empty_by_fixture),
        "status_counts": dict(sorted(status_counts.items())),
        "error_code_counts": dict(sorted(error_counts.items())),
        "profile_status_counts": dict(sorted(profile_status_counts.items())),
        "llm_parse_enabled": llm_parse_enabled,
        "llm_parse_status_counts": dict(sorted(llm_status_counts.items())),
        "temporary_crop_images_persisted": False,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_output_payload(summary)
    return summary


def _write_outputs(
    *,
    rows: list[dict[str, object]],
    summary: dict[str, object],
    output_dir: Path,
    observations_name: str,
    summary_name: str,
) -> None:
    """Write redacted ROI crop observation rows and summary."""
    safe_observations_name = _safe_filename(
        observations_name,
        suffix=".jsonl",
        field_name="observations_name",
    )
    safe_summary_name = _safe_filename(summary_name, suffix=".json", field_name="summary_name")
    _reject_output_payload({"rows": rows, "summary": summary})
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / safe_observations_name).write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (output_dir / safe_summary_name).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_failure_summary(
    *,
    failure: dict[str, object],
    output_dir: Path,
    summary_name: str,
) -> None:
    """Best-effort write of a redacted failure summary."""
    try:
        safe_summary_name = _safe_filename(summary_name, suffix=".json", field_name="summary_name")
        _reject_output_payload(failure)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / safe_summary_name).write_text(
            json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError):
        return


def _failure_summary(
    *,
    manifest_path: Path,
    output_dir: Path,
    error: BaseException,
) -> dict[str, object]:
    """Build a redacted error summary."""
    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "manifest_name": manifest_path.name,
        "manifest_path_hash": _sha256_text(str(manifest_path.expanduser())),
        "output_dir_name": output_dir.name,
        "output_dir_hash": _sha256_text(str(output_dir.expanduser())),
        "error_type": type(error).__name__,
        "error_message": _safe_public_error_message(error),
        "temporary_crop_images_persisted": False,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_output_payload(summary)
    return summary


@contextmanager
def _temporary_env(values: dict[str, str]) -> object:
    """Temporarily set environment variables."""
    previous: dict[str, str | None] = {}
    for key, value in values.items():
        previous[key] = os.environ.get(key)
        os.environ[key] = value
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    """Read JSONL object rows and reject unsafe payloads."""
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("JSONL rows must be objects.")
        _reject_input_payload(row)
        rows.append(row)
    return rows


def _resolve_tokenized_image_path(value: str) -> Path:
    """Resolve a tokenized image path from an allowlisted environment root."""
    match = IMAGE_ROOT_TOKEN_PATTERN.fullmatch(value)
    if not match:
        raise ValueError("Image path must use an allowlisted environment token.")
    env_name = match.group("env")
    if env_name not in ALLOWED_IMAGE_PATH_ENV_VARS:
        raise ValueError("Image path uses unsupported environment token.")
    root = os.environ.get(env_name)
    if not root:
        raise ValueError("Required image root environment variable is not set.")
    root_path = Path(root).expanduser().resolve()
    relative = PurePosixPath(match.group("relative"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Image path contains unsafe relative segments.")
    resolved = (root_path / Path(*relative.parts)).resolve()
    try:
        resolved.relative_to(root_path)
    except ValueError as exc:
        raise ValueError("Image path escapes the configured fixture root.") from exc
    if not resolved.is_file():
        raise ValueError("Fixture image is missing.")
    return resolved


def _required_str(row: Mapping[str, object], key: str) -> str:
    """Return a required non-empty string field."""
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing required field: {key}")
    return value.strip()


def _safe_token(value: str) -> str:
    """Return a bounded public-safe token."""
    token = value.strip()
    if not SAFE_TOKEN_PATTERN.fullmatch(token) or any(
        marker in token for marker in LOCAL_PATH_MARKERS
    ):
        raise ValueError("Unsafe token.")
    return token


def _safe_filename(value: str, *, suffix: str | None = None, field_name: str = "filename") -> str:
    """Return a bounded safe filename."""
    token = value.strip()
    if "/" in token or "\\" in token or not token:
        raise ValueError(f"Unsafe {field_name}.")
    if suffix is not None and not token.endswith(suffix):
        raise ValueError(f"{field_name} must end with {suffix}.")
    return _safe_token(token)


def _reject_input_payload(value: object) -> None:
    """Reject raw keys and local path literals in input rows."""
    _reject_payload(value=value, allow_tokenized_image_path=True)


def _reject_output_payload(value: object) -> None:
    """Reject raw keys and all local path literals in output rows."""
    _reject_payload(value=value, allow_tokenized_image_path=False)


def _reject_payload(*, value: object, allow_tokenized_image_path: bool) -> None:
    """Reject raw fields and local path literals recursively."""
    if isinstance(value, dict):
        forbidden = RAW_FORBIDDEN_KEYS.intersection(str(key).lower() for key in value)
        if forbidden:
            raise ValueError(f"Payload contains forbidden raw field(s): {sorted(forbidden)}")
        for nested_key, nested in value.items():
            if (
                allow_tokenized_image_path
                and str(nested_key) == "image_path"
                and isinstance(nested, str)
                and IMAGE_ROOT_TOKEN_PATTERN.fullmatch(nested)
            ):
                continue
            _reject_payload(value=nested, allow_tokenized_image_path=allow_tokenized_image_path)
        return
    if isinstance(value, list):
        for item in value:
            _reject_payload(value=item, allow_tokenized_image_path=allow_tokenized_image_path)
        return
    if not isinstance(value, str):
        return
    if any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains a local path literal.")


def _safe_public_error_message(exc: BaseException) -> str:
    """Return a public error message without filesystem details."""
    if isinstance(exc, OSError | UnidentifiedImageError):
        message = "Local file operation failed."
    else:
        message = str(exc).strip()
    if (
        not message
        or any(marker in message for marker in LOCAL_PATH_MARKERS)
        or "/" in message
        or "\\" in message
    ):
        return "Validation failed."
    return message[:200]


def _sha256_text(value: str) -> str:
    """Return SHA-256 for a text value."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
