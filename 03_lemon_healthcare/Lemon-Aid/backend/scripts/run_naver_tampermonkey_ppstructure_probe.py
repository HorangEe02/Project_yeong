"""Run a redacted PP-StructureV3 layout probe for Tampermonkey fixtures.

This probe is for OCR failure triage only. It calls PaddleOCR PP-StructureV3 on
tokenized local fixture images and writes bounded layout/table/OCR count
signals. It never writes raw OCR text, Markdown, table HTML, provider payloads,
request headers, image bytes, secrets, or local path literals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "naver-tampermonkey-ppstructure-probe-v1"
SUMMARY_SCHEMA_VERSION = "naver-tampermonkey-ppstructure-probe-summary-v1"
DEFAULT_PROBE_NAME = "ppstructure-probe.jsonl"
DEFAULT_SUMMARY_NAME = "ppstructure-probe.summary.json"
SOURCE_DOC_URLS = (
    "https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PP-StructureV3.html",
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
LAYOUT_TEXT_LABELS = frozenset({"text", "paragraph_title", "doc_title", "figure_title"})
LAYOUT_TABLE_LABELS = frozenset({"table", "table_title"})
LAYOUT_FIGURE_LABELS = frozenset({"image", "figure", "chart", "figure_title"})
TEXT_KEY_FRAGMENTS = (
    "text",
    "html",
    "markdown",
    "content",
    "formula",
)


def main() -> None:
    """Run PP-StructureV3 and write a redacted probe report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--probe-name", default=DEFAULT_PROBE_NAME)
    parser.add_argument("--summary-name", default=DEFAULT_SUMMARY_NAME)
    parser.add_argument("--lang", default="korean")
    parser.add_argument("--device", default=None)
    parser.add_argument("--use-doc-orientation-classify", action="store_true")
    parser.add_argument("--use-doc-unwarping", action="store_true")
    parser.add_argument("--use-textline-orientation", action="store_true")
    args = parser.parse_args()

    try:
        rows, summary = run_probe(
            manifest_path=args.manifest.expanduser().resolve(),
            output_dir=args.output_dir.expanduser().resolve(),
            probe_name=args.probe_name,
            summary_name=args.summary_name,
            lang=args.lang,
            device=args.device,
            use_doc_orientation_classify=args.use_doc_orientation_classify,
            use_doc_unwarping=args.use_doc_unwarping,
            use_textline_orientation=args.use_textline_orientation,
        )
        _write_outputs(
            rows=rows,
            summary=summary,
            output_dir=args.output_dir.expanduser().resolve(),
            probe_name=args.probe_name,
            summary_name=args.summary_name,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    except (ImportError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
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


def run_probe(
    *,
    manifest_path: Path,
    output_dir: Path,
    probe_name: str = DEFAULT_PROBE_NAME,
    summary_name: str = DEFAULT_SUMMARY_NAME,
    lang: str = "korean",
    device: str | None = None,
    use_doc_orientation_classify: bool = False,
    use_doc_unwarping: bool = False,
    use_textline_orientation: bool = False,
    pipeline_factory: Callable[..., Any] | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Run a PP-StructureV3 probe and return redacted rows and summary.

    Args:
        manifest_path: Redacted manifest containing tokenized image paths.
        output_dir: Planned output directory.
        probe_name: Probe JSONL filename.
        summary_name: Summary JSON filename.
        lang: PP-StructureV3 language option.
        device: Optional PaddleOCR device selector.
        use_doc_orientation_classify: Whether to enable document orientation.
        use_doc_unwarping: Whether to enable document unwarping.
        use_textline_orientation: Whether to enable textline orientation.
        pipeline_factory: Optional factory for tests.

    Returns:
        Redacted probe rows and summary.
    """
    safe_probe_name = _safe_filename(probe_name, suffix=".jsonl", field_name="probe_name")
    safe_summary_name = _safe_filename(summary_name, suffix=".json", field_name="summary_name")
    rows: list[dict[str, object]] = []
    manifest_rows = _read_jsonl(manifest_path)
    pipeline_kwargs = _pipeline_kwargs(
        lang=lang,
        device=device,
        use_doc_orientation_classify=use_doc_orientation_classify,
        use_doc_unwarping=use_doc_unwarping,
        use_textline_orientation=use_textline_orientation,
    )
    pipeline = _build_pipeline(pipeline_factory=pipeline_factory, kwargs=pipeline_kwargs)
    for manifest_row in manifest_rows:
        rows.append(_probe_row(manifest_row=manifest_row, pipeline=pipeline))

    summary = _build_summary(
        rows=rows,
        manifest_path=manifest_path,
        output_dir=output_dir,
        probe_name=safe_probe_name,
        summary_name=safe_summary_name,
        pipeline_kwargs=pipeline_kwargs,
    )
    _reject_output_payload({"rows": rows, "summary": summary})
    return rows, summary


def _pipeline_kwargs(
    *,
    lang: str,
    device: str | None,
    use_doc_orientation_classify: bool,
    use_doc_unwarping: bool,
    use_textline_orientation: bool,
) -> dict[str, object]:
    """Return bounded PP-StructureV3 constructor kwargs."""
    kwargs: dict[str, object] = {
        "lang": _safe_token(lang),
        "use_doc_orientation_classify": use_doc_orientation_classify,
        "use_doc_unwarping": use_doc_unwarping,
        "use_textline_orientation": use_textline_orientation,
    }
    if device:
        kwargs["device"] = _safe_token(device)
    return kwargs


def _build_pipeline(
    *,
    pipeline_factory: Callable[..., Any] | None,
    kwargs: dict[str, object],
) -> Any:
    """Build a PP-StructureV3 pipeline."""
    if pipeline_factory is not None:
        return pipeline_factory(**kwargs)
    paddleocr_module = import_module("paddleocr")
    pipeline_class = paddleocr_module.PPStructureV3
    return pipeline_class(**kwargs)


def _probe_row(*, manifest_row: dict[str, object], pipeline: Any) -> dict[str, object]:
    """Run one image through PP-StructureV3 and return a redacted row."""
    _reject_input_payload(manifest_row)
    fixture_id = _safe_token(_required_str(manifest_row, "fixture_id"))
    row = _base_row(manifest_row)
    try:
        image_path = _resolve_tokenized_image_path(_required_str(manifest_row, "image_path"))
        output = pipeline.predict(str(image_path))
        summaries = [_summarize_result(item) for item in output]
        row.update(_merge_result_summaries(summaries))
        row["probe_status"] = "completed"
    except Exception as exc:  # pragma: no cover - defensive around native runtime
        row.update(
            {
                "probe_status": "error",
                "error_code": _probe_error_code(exc),
            }
        )
    row["fixture_id"] = fixture_id
    _reject_output_payload(row)
    return row


def _base_row(manifest_row: dict[str, object]) -> dict[str, object]:
    """Return safe manifest metadata for one probe row."""
    db_labeling = manifest_row.get("db_labeling")
    db_labeling = db_labeling if isinstance(db_labeling, dict) else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "fixture_id": _safe_token(_required_str(manifest_row, "fixture_id")),
        "section": _safe_optional_token(manifest_row.get("section")) or "unknown",
        "category_key": _safe_optional_token(db_labeling.get("category_key")) or "unknown",
        "image_sha256": _safe_optional_token(manifest_row.get("image_sha256")),
        "source_doc_urls": list(SOURCE_DOC_URLS),
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }


def _summarize_result(result: object) -> dict[str, object]:
    """Return text-free counts from one PP-StructureV3 result object."""
    payload = _result_payload(result)
    root = payload.get("res") if isinstance(payload.get("res"), Mapping) else payload
    layout_boxes = _list_from_path(root, ("layout_det_res", "boxes"))
    labels = Counter(
        _safe_optional_token(box.get("label")) or "unknown"
        for box in layout_boxes
        if isinstance(box, Mapping)
    )
    scores = [
        float(box["score"])
        for box in layout_boxes
        if isinstance(box, Mapping) and isinstance(box.get("score"), int | float)
    ]
    overall_ocr = root.get("overall_ocr_res") if isinstance(root, Mapping) else None
    overall_ocr = overall_ocr if isinstance(overall_ocr, Mapping) else {}
    rec_texts_count = _safe_len(overall_ocr.get("rec_texts"))
    dt_polys_count = _safe_len(overall_ocr.get("dt_polys"))
    return {
        "result_count": 1,
        "layout_box_count": len(layout_boxes),
        "layout_label_counts": dict(sorted(labels.items())),
        "layout_score_min": round(min(scores), 4) if scores else None,
        "layout_score_avg": round(sum(scores) / len(scores), 4) if scores else None,
        "layout_score_max": round(max(scores), 4) if scores else None,
        "layout_text_region_count": _count_labels(labels, LAYOUT_TEXT_LABELS),
        "layout_table_region_count": _count_labels(labels, LAYOUT_TABLE_LABELS),
        "layout_figure_region_count": _count_labels(labels, LAYOUT_FIGURE_LABELS),
        "overall_ocr_rec_text_count": rec_texts_count,
        "overall_ocr_detection_count": dt_polys_count,
        "table_result_count": _recursive_keyed_list_count(root, "table"),
        "region_result_count": _recursive_keyed_list_count(root, "region"),
    }


def _result_payload(result: object) -> Mapping[str, Any]:
    """Return a mapping from a PP-StructureV3 result without storing it."""
    if isinstance(result, Mapping):
        return result
    json_value = getattr(result, "json", None)
    if isinstance(json_value, Mapping):
        return json_value
    if callable(json_value):
        parsed = json_value()
        if isinstance(parsed, Mapping):
            return parsed
    to_dict = getattr(result, "to_dict", None)
    if callable(to_dict):
        parsed = to_dict()
        if isinstance(parsed, Mapping):
            return parsed
    return {}


def _merge_result_summaries(summaries: list[dict[str, object]]) -> dict[str, object]:
    """Merge per-result count summaries into one probe row."""
    labels: Counter[str] = Counter()
    merged: dict[str, object] = {
        "result_count": len(summaries),
        "layout_box_count": 0,
        "layout_text_region_count": 0,
        "layout_table_region_count": 0,
        "layout_figure_region_count": 0,
        "overall_ocr_rec_text_count": 0,
        "overall_ocr_detection_count": 0,
        "table_result_count": 0,
        "region_result_count": 0,
    }
    score_values: list[float] = []
    for summary in summaries:
        for key in (
            "layout_box_count",
            "layout_text_region_count",
            "layout_table_region_count",
            "layout_figure_region_count",
            "overall_ocr_rec_text_count",
            "overall_ocr_detection_count",
            "table_result_count",
            "region_result_count",
        ):
            merged[key] = int(merged[key]) + int(summary.get(key) or 0)
        label_counts = summary.get("layout_label_counts")
        if isinstance(label_counts, dict):
            labels.update({str(key): int(value) for key, value in label_counts.items()})
        for key in ("layout_score_min", "layout_score_avg", "layout_score_max"):
            value = summary.get(key)
            if isinstance(value, int | float):
                score_values.append(float(value))
    merged["layout_label_counts"] = dict(sorted(labels.items()))
    merged["layout_score_min"] = round(min(score_values), 4) if score_values else None
    merged["layout_score_avg"] = (
        round(sum(score_values) / len(score_values), 4) if score_values else None
    )
    merged["layout_score_max"] = round(max(score_values), 4) if score_values else None
    return merged


def _build_summary(
    *,
    rows: list[dict[str, object]],
    manifest_path: Path,
    output_dir: Path,
    probe_name: str,
    summary_name: str,
    pipeline_kwargs: dict[str, object],
) -> dict[str, object]:
    """Build a redacted probe summary."""
    status_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    error_counts: Counter[str] = Counter()
    layout_label_counts: Counter[str] = Counter()
    for row in rows:
        status_counts[_safe_token(str(row.get("probe_status") or "unknown"))] += 1
        category_counts[_safe_token(str(row.get("category_key") or "unknown"))] += 1
        error_code = row.get("error_code")
        if isinstance(error_code, str):
            error_counts[_safe_token(error_code)] += 1
        label_counts = row.get("layout_label_counts")
        if isinstance(label_counts, dict):
            layout_label_counts.update(
                {_safe_token(str(key)): int(value) for key, value in label_counts.items()}
            )
    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_doc_urls": list(SOURCE_DOC_URLS),
        "manifest_name": _safe_filename(manifest_path.name, suffix=".jsonl", field_name="manifest"),
        "output_dir_name": _safe_filename(output_dir.name, field_name="output_dir"),
        "manifest_path_hash": _sha256_text(str(manifest_path.expanduser())),
        "output_dir_hash": _sha256_text(str(output_dir.expanduser())),
        "probe_filename": probe_name,
        "summary_filename": summary_name,
        "probe_row_count": len(rows),
        "pipeline_kwargs": pipeline_kwargs,
        "status_counts": dict(sorted(status_counts.items())),
        "category_key_counts": dict(sorted(category_counts.items())),
        "error_code_counts": dict(sorted(error_counts.items())),
        "layout_label_counts": dict(sorted(layout_label_counts.items())),
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
    probe_name: str,
    summary_name: str,
) -> None:
    """Write redacted probe JSONL and summary JSON."""
    safe_probe_name = _safe_filename(probe_name, suffix=".jsonl", field_name="probe_name")
    safe_summary_name = _safe_filename(summary_name, suffix=".json", field_name="summary_name")
    _reject_output_payload({"rows": rows, "summary": summary})
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / safe_probe_name).write_text(
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


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    """Read JSONL object rows and reject unsafe content."""
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
    relative = Path(match.group("relative"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Image path contains unsafe relative segments.")
    resolved = (root_path / relative).resolve()
    try:
        resolved.relative_to(root_path)
    except ValueError as exc:
        raise ValueError("Image path escapes the configured fixture root.") from exc
    if not resolved.is_file():
        raise ValueError("Fixture image is missing.")
    return resolved


def _list_from_path(value: Mapping[str, Any], path: tuple[str, ...]) -> list[object]:
    """Return a nested list from a mapping path."""
    current: object = value
    for key in path:
        if not isinstance(current, Mapping):
            return []
        current = current.get(key)
    if isinstance(current, list):
        return list(current)
    return []


def _safe_len(value: object) -> int:
    """Return bounded len for list-like values without materializing text."""
    if isinstance(value, list | tuple):
        return len(value)
    shape = getattr(value, "shape", None)
    if isinstance(shape, tuple) and shape:
        first = shape[0]
        if isinstance(first, int):
            return max(0, first)
    return 0


def _recursive_keyed_list_count(value: object, key_fragment: str) -> int:
    """Count list items under keys containing a public-safe fragment."""
    count = 0
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key).lower()
            if key_fragment in key_text and isinstance(nested, list):
                count += len(nested)
            count += _recursive_keyed_list_count(nested, key_fragment)
    elif isinstance(value, list | tuple):
        for item in value:
            count += _recursive_keyed_list_count(item, key_fragment)
    return count


def _count_labels(labels: Counter[str], targets: frozenset[str]) -> int:
    """Count layout boxes matching a target label set."""
    return sum(count for label, count in labels.items() if label in targets)


def _probe_error_code(exc: Exception) -> str:
    """Return a bounded probe error code."""
    name = type(exc).__name__
    if "Import" in name:
        return "ppstructure_import_failed"
    if "Memory" in name:
        return "ppstructure_memory_error"
    if "File" in name or "OSError" in name:
        return "ppstructure_file_error"
    return "ppstructure_predict_failed"


def _failure_summary(
    *,
    manifest_path: Path,
    output_dir: Path,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted CLI failure summary."""
    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "manifest_name": manifest_path.name,
        "output_dir_name": output_dir.name,
        "manifest_path_hash": _sha256_text(str(manifest_path.expanduser())),
        "output_dir_hash": _sha256_text(str(output_dir.expanduser())),
        "error_type": type(error).__name__,
        "error_message": _safe_public_error_message(error),
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_output_payload(summary)
    return summary


def _required_str(row: dict[str, object], key: str) -> str:
    """Return a required non-empty string field."""
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing required field: {key}")
    return value.strip()


def _safe_optional_token(value: object) -> str | None:
    """Return a safe token or None for empty values."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Optional token must be a string when present.")
    if not value.strip():
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
    if any(fragment in value.lower() for fragment in TEXT_KEY_FRAGMENTS) and "\n" in value:
        raise ValueError("Payload contains multiline text content.")


def _safe_public_error_message(exc: BaseException) -> str:
    """Return a public error message without filesystem details."""
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
    """Return SHA-256 for a text value."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
