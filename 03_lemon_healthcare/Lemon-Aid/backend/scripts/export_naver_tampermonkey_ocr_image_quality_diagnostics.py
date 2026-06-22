"""Export redacted image-quality diagnostics for Tampermonkey OCR failures.

The exporter joins a redacted Tampermonkey manifest with OCR observations,
opens only the locally referenced image files, and writes coarse image-quality
signals for ``ocr_low_confidence`` triage. It does not persist raw OCR text,
provider payloads, request headers, image bytes, raw model responses, secrets,
or local paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import warnings
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from PIL import Image, ImageOps, ImageStat, UnidentifiedImageError

SCHEMA_VERSION = "naver-tampermonkey-ocr-image-quality-diagnostic-v1"
SUMMARY_SCHEMA_VERSION = "naver-tampermonkey-ocr-image-quality-diagnostic-summary-v1"
DEFAULT_DIAGNOSTICS_NAME = "ocr-image-quality-diagnostics.jsonl"
DEFAULT_SUMMARY_NAME = "ocr-image-quality-diagnostics.summary.json"
SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
IMAGE_ROOT_TOKEN_PATTERN = re.compile(r"^\$(?P<env>[A-Z][A-Z0-9_]*)/(?P<relative>.+)$")
MAX_DECODED_PIXELS = 50_000_000
TINY_MEGAPIXEL_THRESHOLD = 0.4
SMALL_MEGAPIXEL_THRESHOLD = 1.5
MEDIUM_MEGAPIXEL_THRESHOLD = 6.0
MIN_READABLE_SIDE_PX = 500
BRIGHTNESS_DARK_THRESHOLD = 70.0
BRIGHTNESS_BRIGHT_THRESHOLD = 205.0
CONTRAST_LOW_THRESHOLD = 35.0
CONTRAST_HIGH_THRESHOLD = 85.0
VERY_TALL_RATIO_THRESHOLD = 0.35
TALL_RATIO_THRESHOLD = 0.75
SQUAREISH_RATIO_THRESHOLD = 1.35
WIDE_RATIO_THRESHOLD = 2.8
RAW_FORBIDDEN_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "image_bytes",
        "ocr_text",
        "provider_payload",
        "raw_image",
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
FailureMode = Literal["ocr_low_confidence", "all_errors"]


def main() -> None:
    """Export image-quality diagnostics and a redacted summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--diagnostics-name", default=DEFAULT_DIAGNOSTICS_NAME)
    parser.add_argument("--summary-name", default=DEFAULT_SUMMARY_NAME)
    parser.add_argument(
        "--failure-mode",
        choices=("ocr_low_confidence", "all_errors"),
        default="ocr_low_confidence",
    )
    args = parser.parse_args()

    try:
        rows, summary = export_image_quality_diagnostics(
            manifest_path=args.manifest.expanduser().resolve(),
            observations_path=args.observations.expanduser().resolve(),
            output_dir=args.output_dir.expanduser().resolve(),
            diagnostics_name=args.diagnostics_name,
            summary_name=args.summary_name,
            failure_mode=args.failure_mode,
        )
        _write_outputs(
            rows=rows,
            summary=summary,
            output_dir=args.output_dir.expanduser().resolve(),
            diagnostics_name=args.diagnostics_name,
            summary_name=args.summary_name,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure = _failure_summary(
            manifest_path=args.manifest,
            observations_path=args.observations,
            output_dir=args.output_dir,
            error=exc,
        )
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None


def export_image_quality_diagnostics(
    *,
    manifest_path: Path,
    observations_path: Path,
    output_dir: Path,
    diagnostics_name: str = DEFAULT_DIAGNOSTICS_NAME,
    summary_name: str = DEFAULT_SUMMARY_NAME,
    failure_mode: FailureMode = "ocr_low_confidence",
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Build redacted image-quality diagnostic rows for OCR failures.

    Args:
        manifest_path: Redacted collector manifest containing tokenized image paths.
        observations_path: Redacted OCR observations JSONL.
        output_dir: Planned output directory.
        diagnostics_name: Diagnostics JSONL filename.
        summary_name: Summary JSON filename.
        failure_mode: Failure filter to include in diagnostics.

    Returns:
        Diagnostic rows and a redacted summary.

    Raises:
        ValueError: If input rows are malformed or unsafe.
    """
    safe_diagnostics_name = _safe_filename(
        diagnostics_name,
        suffix=".jsonl",
        field_name="diagnostics_name",
    )
    safe_summary_name = _safe_filename(summary_name, suffix=".json", field_name="summary_name")
    manifest_rows = _load_manifest_rows(manifest_path)
    observation_rows = _read_jsonl(observations_path)
    target_observations = [
        row for row in observation_rows if _is_target_failure(row, failure_mode=failure_mode)
    ]
    rows: list[dict[str, object]] = []
    missing_manifest_count = 0
    decode_error_count = 0

    for observation in target_observations:
        fixture_id = _safe_token(_required_str(observation, "fixture_id"))
        manifest_row = manifest_rows.get(fixture_id)
        if manifest_row is None:
            missing_manifest_count += 1
            continue
        try:
            rows.append(_diagnostic_row(manifest_row=manifest_row, observation=observation))
        except (OSError, UnidentifiedImageError, Image.DecompressionBombError, ValueError):
            decode_error_count += 1
            rows.append(_decode_failure_row(manifest_row=manifest_row, observation=observation))

    summary = _build_summary(
        rows=rows,
        manifest_path=manifest_path,
        observations_path=observations_path,
        output_dir=output_dir,
        diagnostics_name=safe_diagnostics_name,
        summary_name=safe_summary_name,
        failure_mode=failure_mode,
        input_observation_count=len(observation_rows),
        target_observation_count=len(target_observations),
        missing_manifest_count=missing_manifest_count,
        decode_error_count=decode_error_count,
    )
    _reject_output_payload({"rows": rows, "summary": summary})
    return rows, summary


def _diagnostic_row(
    *,
    manifest_row: dict[str, object],
    observation: dict[str, object],
) -> dict[str, object]:
    """Build one diagnostic row from a local image without storing raw pixels."""
    image_path = _resolve_tokenized_image_path(_required_str(manifest_row, "image_path"))
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(image_path) as source:
            source.load()
            if source.width * source.height > MAX_DECODED_PIXELS:
                raise ValueError("Decoded image exceeds diagnostic pixel limit.")
            oriented = ImageOps.exif_transpose(source)
            grayscale = ImageOps.grayscale(oriented)
            stat = ImageStat.Stat(grayscale)
            brightness = float(stat.mean[0]) if stat.mean else 0.0
            contrast = float(stat.stddev[0]) if stat.stddev else 0.0
            width, height = oriented.size
            mode_bucket = _mode_bucket(oriented.mode)
            animated_bucket = "multi_frame" if getattr(source, "is_animated", False) else "single"

    row = _base_row(manifest_row=manifest_row, observation=observation)
    megapixels = round((width * height) / 1_000_000, 3)
    row.update(
        {
            "diagnostic_status": "completed",
            "width": width,
            "height": height,
            "megapixels": megapixels,
            "megapixel_bucket": _megapixel_bucket(megapixels),
            "aspect_ratio_bucket": _aspect_ratio_bucket(width=width, height=height),
            "brightness_bucket": _brightness_bucket(brightness),
            "contrast_bucket": _contrast_bucket(contrast),
            "brightness_mean_0_255": round(brightness, 1),
            "contrast_stddev_0_255": round(contrast, 1),
            "mode_bucket": mode_bucket,
            "frame_bucket": animated_bucket,
            "suggested_preprocess_actions": _suggest_actions(
                width=width,
                height=height,
                megapixels=megapixels,
                brightness=brightness,
                contrast=contrast,
            ),
        }
    )
    _reject_output_payload(row)
    return row


def _decode_failure_row(
    *,
    manifest_row: dict[str, object],
    observation: dict[str, object],
) -> dict[str, object]:
    """Return a redacted row when diagnostic image decode fails."""
    row = _base_row(manifest_row=manifest_row, observation=observation)
    row.update(
        {
            "diagnostic_status": "decode_error",
            "suggested_preprocess_actions": ["review_source_image_decode"],
        }
    )
    _reject_output_payload(row)
    return row


def _base_row(
    *,
    manifest_row: dict[str, object],
    observation: dict[str, object],
) -> dict[str, object]:
    """Return safe shared fields for image-quality diagnostics."""
    db_labeling = manifest_row.get("db_labeling")
    db_labeling = db_labeling if isinstance(db_labeling, dict) else {}
    row = {
        "schema_version": SCHEMA_VERSION,
        "fixture_id": _safe_token(_required_str(observation, "fixture_id")),
        "provider": _safe_token(_required_str(observation, "provider")),
        "status": _safe_token(str(observation.get("status") or "unknown")),
        "error_code": _safe_optional_token(observation.get("error_code")),
        "section": _safe_optional_token(manifest_row.get("section")) or "unknown",
        "category_key": _safe_optional_token(db_labeling.get("category_key")) or "unknown",
        "language_targets": _safe_string_list(db_labeling.get("language_targets")),
        "chronic_fixture_tags": _safe_string_list(db_labeling.get("chronic_fixture_tags")),
        "image_sha256": _safe_sha256(_required_str(manifest_row, "image_sha256")),
        "manifest_width": _bounded_int(manifest_row.get("width")),
        "manifest_height": _bounded_int(manifest_row.get("height")),
        "manifest_size_bucket": _safe_optional_token(manifest_row.get("size_bucket")),
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_output_payload(row)
    return row


def _build_summary(
    *,
    rows: list[dict[str, object]],
    manifest_path: Path,
    observations_path: Path,
    output_dir: Path,
    diagnostics_name: str,
    summary_name: str,
    failure_mode: FailureMode,
    input_observation_count: int,
    target_observation_count: int,
    missing_manifest_count: int,
    decode_error_count: int,
) -> dict[str, object]:
    """Build a redacted diagnostics summary."""
    status_counts = Counter(_safe_token(str(row["diagnostic_status"])) for row in rows)
    action_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    brightness_counts: Counter[str] = Counter()
    contrast_counts: Counter[str] = Counter()
    for row in rows:
        category_counts[_safe_token(str(row.get("category_key") or "unknown"))] += 1
        brightness = row.get("brightness_bucket")
        if isinstance(brightness, str):
            brightness_counts[_safe_token(brightness)] += 1
        contrast = row.get("contrast_bucket")
        if isinstance(contrast, str):
            contrast_counts[_safe_token(contrast)] += 1
        actions = row.get("suggested_preprocess_actions")
        if isinstance(actions, list):
            for action in actions:
                action_counts[_safe_token(str(action))] += 1
    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "diagnostics_name": diagnostics_name,
        "summary_name": summary_name,
        "manifest_name": manifest_path.name,
        "manifest_path_hash": _sha256_text(str(manifest_path.expanduser())),
        "observations_name": observations_path.name,
        "observations_path_hash": _sha256_text(str(observations_path.expanduser())),
        "output_dir_name": output_dir.name,
        "output_dir_path_hash": _sha256_text(str(output_dir.expanduser())),
        "failure_mode": failure_mode,
        "input_observation_count": input_observation_count,
        "target_observation_count": target_observation_count,
        "diagnostic_row_count": len(rows),
        "missing_manifest_count": missing_manifest_count,
        "decode_error_count": decode_error_count,
        "diagnostic_status_counts": dict(sorted(status_counts.items())),
        "category_key_counts": dict(sorted(category_counts.items())),
        "brightness_bucket_counts": dict(sorted(brightness_counts.items())),
        "contrast_bucket_counts": dict(sorted(contrast_counts.items())),
        "suggested_preprocess_action_counts": dict(sorted(action_counts.items())),
        "source_doc_urls": [
            "https://pillow.readthedocs.io/en/stable/reference/Image.html",
            "https://pillow.readthedocs.io/en/stable/reference/ImageOps.html",
            "https://pillow.readthedocs.io/en/stable/reference/ImageStat.html",
        ],
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
    diagnostics_name: str,
    summary_name: str,
) -> None:
    """Write diagnostics JSONL and summary JSON."""
    safe_diagnostics_name = _safe_filename(
        diagnostics_name,
        suffix=".jsonl",
        field_name="diagnostics_name",
    )
    safe_summary_name = _safe_filename(summary_name, suffix=".json", field_name="summary_name")
    _reject_output_payload({"rows": rows, "summary": summary})
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / safe_diagnostics_name).write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (output_dir / safe_summary_name).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_manifest_rows(path: Path) -> dict[str, dict[str, object]]:
    """Load redacted manifest rows keyed by fixture id."""
    rows: dict[str, dict[str, object]] = {}
    for row in _read_jsonl(path):
        fixture_id = _safe_token(_required_str(row, "fixture_id"))
        rows[fixture_id] = row
    return rows


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    """Read JSONL object rows and reject unsafe raw content."""
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


def _is_target_failure(row: dict[str, object], *, failure_mode: FailureMode) -> bool:
    """Return whether an observation should receive image-quality diagnostics."""
    if row.get("status") != "error":
        return False
    if failure_mode == "all_errors":
        return True
    return row.get("error_code") == "ocr_low_confidence"


def _resolve_tokenized_image_path(tokenized_path: str) -> Path:
    """Resolve a manifest image token to a local path for process memory only."""
    match = IMAGE_ROOT_TOKEN_PATTERN.fullmatch(tokenized_path.strip())
    if match is None:
        raise ValueError("Manifest image path must use an allowed environment token.")
    env_name = match.group("env")
    relative_text = match.group("relative")
    relative_path = Path(relative_text)
    if relative_path.is_absolute() or any(part in {"", ".", ".."} for part in relative_path.parts):
        raise ValueError("Manifest image path contains an unsafe relative segment.")
    root_text = os.environ.get(env_name)
    if not root_text:
        raise ValueError("Required image root environment variable is missing.")
    root = Path(root_text).expanduser().resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Manifest image path escapes the configured image root.") from exc
    return candidate


def _suggest_actions(
    *,
    width: int,
    height: int,
    megapixels: float,
    brightness: float,
    contrast: float,
) -> list[str]:
    """Return bounded next-action tokens for OCR image-quality triage."""
    actions: list[str] = []
    if megapixels < TINY_MEGAPIXEL_THRESHOLD or min(width, height) < MIN_READABLE_SIDE_PX:
        actions.append("review_crop_or_higher_resolution")
    if _aspect_ratio_bucket(width=width, height=height) in {"very_tall", "very_wide"}:
        actions.append("review_crop_or_detail_region")
    if brightness < BRIGHTNESS_DARK_THRESHOLD:
        actions.append("try_brightness_normalization")
    elif brightness > BRIGHTNESS_BRIGHT_THRESHOLD:
        actions.append("try_glare_or_overexposure_review")
    if contrast < CONTRAST_LOW_THRESHOLD:
        actions.append("try_contrast_autocontrast")
    if not actions:
        actions.append("try_ppocrv5_server_or_layout_model")
    return actions


def _aspect_ratio_bucket(*, width: int, height: int) -> str:
    """Return a coarse aspect-ratio bucket."""
    ratio = width / max(height, 1)
    if ratio < VERY_TALL_RATIO_THRESHOLD:
        return "very_tall"
    if ratio < TALL_RATIO_THRESHOLD:
        return "tall"
    if ratio <= SQUAREISH_RATIO_THRESHOLD:
        return "squareish"
    if ratio <= WIDE_RATIO_THRESHOLD:
        return "wide"
    return "very_wide"


def _megapixel_bucket(megapixels: float) -> str:
    """Return a coarse megapixel bucket."""
    if megapixels < TINY_MEGAPIXEL_THRESHOLD:
        return "tiny"
    if megapixels < SMALL_MEGAPIXEL_THRESHOLD:
        return "small"
    if megapixels < MEDIUM_MEGAPIXEL_THRESHOLD:
        return "medium"
    return "large"


def _brightness_bucket(value: float) -> str:
    """Return a coarse brightness bucket for 0-255 grayscale mean."""
    if value < BRIGHTNESS_DARK_THRESHOLD:
        return "dark"
    if value > BRIGHTNESS_BRIGHT_THRESHOLD:
        return "bright"
    return "normal"


def _contrast_bucket(value: float) -> str:
    """Return a coarse contrast bucket for 0-255 grayscale standard deviation."""
    if value < CONTRAST_LOW_THRESHOLD:
        return "low"
    if value > CONTRAST_HIGH_THRESHOLD:
        return "high"
    return "normal"


def _mode_bucket(mode: str) -> str:
    """Return a bounded public bucket for image mode."""
    if mode in {"1", "L", "LA"}:
        return "grayscale"
    if mode in {"RGB", "CMYK", "YCbCr"}:
        return "color"
    if mode in {"RGBA", "RGBa"}:
        return "alpha"
    if mode == "P":
        return "palette"
    return "other"


def _safe_string_list(value: object) -> list[str]:
    """Return a list of safe tokens."""
    if not isinstance(value, list):
        return []
    return [_safe_token(str(item)) for item in value if isinstance(item, str) and item.strip()]


def _safe_optional_token(value: object) -> str | None:
    """Return a safe token or None."""
    if not isinstance(value, str) or not value:
        return None
    return _safe_token(value)


def _safe_token(value: str) -> str:
    """Return a bounded public-safe token."""
    token = value.strip()
    if not SAFE_TOKEN_PATTERN.fullmatch(token) or any(
        marker in token for marker in LOCAL_PATH_MARKERS
    ):
        raise ValueError("Unsafe token.")
    return token


def _safe_sha256(value: str) -> str:
    """Return a validated SHA-256 hex digest."""
    token = value.strip().lower()
    if not re.fullmatch(r"[a-f0-9]{64}", token):
        raise ValueError("Expected a SHA-256 digest.")
    return token


def _bounded_int(value: object) -> int | None:
    """Return a non-negative bounded integer or None."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0 or value > MAX_DECODED_PIXELS:
        return None
    return value


def _required_str(row: dict[str, object], key: str) -> str:
    """Return a required non-empty string field."""
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing required string field: {key}")
    return value


def _safe_filename(value: str, *, suffix: str, field_name: str) -> str:
    """Return a safe output filename with the required suffix."""
    token = value.strip()
    if not token.endswith(suffix):
        raise ValueError(f"{field_name} has an unexpected suffix.")
    stem = token[: -len(suffix)]
    _safe_token(stem)
    return token


def _reject_input_payload(value: object) -> None:
    """Reject raw fields and local path literals from input artifacts."""
    if isinstance(value, dict):
        forbidden = RAW_FORBIDDEN_KEYS.intersection(str(key).lower() for key in value)
        if forbidden:
            raise ValueError(f"Payload contains forbidden raw field(s): {sorted(forbidden)}")
        for nested in value.values():
            _reject_input_payload(nested)
    elif isinstance(value, list | tuple):
        for item in value:
            _reject_input_payload(item)
    elif isinstance(value, str) and any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")


def _reject_output_payload(value: object) -> None:
    """Reject raw fields, source path keys, and local path literals from output."""
    if isinstance(value, dict):
        forbidden = RAW_FORBIDDEN_KEYS.intersection(str(key).lower() for key in value)
        forbidden = forbidden.union(
            {"image_path", "product_dir", "absolute_path", "local_path"}.intersection(
                str(key).lower() for key in value
            )
        )
        if forbidden:
            raise ValueError(f"Payload contains forbidden field(s): {sorted(forbidden)}")
        for nested in value.values():
            _reject_output_payload(nested)
    elif isinstance(value, list | tuple):
        for item in value:
            _reject_output_payload(item)
    elif isinstance(value, str) and any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")


def _failure_summary(
    *,
    manifest_path: Path,
    observations_path: Path,
    output_dir: Path,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted CLI failure summary."""
    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "manifest_name": manifest_path.name,
        "manifest_path_hash": _sha256_text(str(manifest_path.expanduser())),
        "observations_name": observations_path.name,
        "observations_path_hash": _sha256_text(str(observations_path.expanduser())),
        "output_dir_name": output_dir.name,
        "output_dir_path_hash": _sha256_text(str(output_dir.expanduser())),
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_output_payload(summary)
    return summary


def _safe_error_code(exc: BaseException) -> str:
    """Return a bounded public error code."""
    if isinstance(exc, OSError):
        return "local_file_operation_error"
    if isinstance(exc, json.JSONDecodeError):
        return "json_decode_error"
    return "validation_error"


def _safe_public_error_message(exc: BaseException) -> str:
    """Return a bounded public error message."""
    if isinstance(exc, OSError):
        message = "Local file operation failed."
    elif isinstance(exc, json.JSONDecodeError):
        message = "JSON decode failed."
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
    """Return SHA-256 for text."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
