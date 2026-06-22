"""Evaluate Naver Tampermonkey OCR/Ollama observation coverage.

The crawl set does not have human ground truth, so this evaluator reports
coverage/readiness metrics instead of accuracy. It rejects raw OCR text,
provider payloads, request headers, image bytes, and raw model responses.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from statistics import median

SOURCE_DOC_URLS = (
    "https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html",
    "https://api.ncloud-docs.com/docs/en/ai-application-service-ocr",
    "https://api.ncloud-docs.com/docs/en/ai-application-service-ocr-ocr",
    "https://cloud.google.com/vision/docs/ocr",
    "https://docs.ollama.com/capabilities/structured-outputs",
)
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
DEFAULT_JSON_NAME = "naver-ocr-provider-comparison.json"
DEFAULT_MARKDOWN_NAME = "naver-ocr-provider-comparison.md"
MEDIAN_PERCENTILE = 50
PERCENTILE_SCALE = 100
NEAREST_RANK_OFFSET = 0.5
LLM_PARSE_NON_ATTEMPT_STATUSES = frozenset({"skipped_empty_text", "skipped_pii_screening_required"})


@dataclass(frozen=True)
class ManifestMeta:
    """Report grouping metadata for one manifest row."""

    fixture_id: str
    section: str
    category: str
    product_id: str | None
    mime_type: str | None
    size_bucket: str | None


@dataclass
class MetricBucket:
    """Mutable aggregate for OCR/Ollama coverage metrics."""

    call_count: int = 0
    completed_count: int = 0
    error_count: int = 0
    not_run_count: int = 0
    text_non_empty_count: int = 0
    parser_success_count: int = 0
    llm_parse_attempt_count: int = 0
    llm_parse_success_count: int = 0
    ingredient_counts: list[int] = field(default_factory=list)
    char_counts: list[int] = field(default_factory=list)
    latencies: list[float] = field(default_factory=list)
    error_codes: Counter[str] = field(default_factory=Counter)
    pii_candidate_flags: Counter[str] = field(default_factory=Counter)

    def add(self, row: dict[str, object]) -> None:
        """Add one redacted observation row to this bucket.

        Args:
            row: Observation row produced by the collector.
        """
        self.call_count += 1
        status = str(row.get("status") or "unknown")
        if status == "completed":
            self.completed_count += 1
        elif status == "not_run":
            self.not_run_count += 1
        else:
            self.error_count += 1
        if row.get("text_non_empty") is True:
            self.text_non_empty_count += 1
        if row.get("parser_success") is True:
            self.parser_success_count += 1
        latency_ms = row.get("latency_ms")
        if isinstance(latency_ms, int | float):
            self.latencies.append(float(latency_ms))
        char_count = row.get("char_count")
        if status == "completed" and isinstance(char_count, int):
            self.char_counts.append(char_count)
        llm_status = row.get("llm_parse_status")
        if isinstance(llm_status, str) and llm_status not in LLM_PARSE_NON_ATTEMPT_STATUSES:
            self.llm_parse_attempt_count += 1
            if llm_status == "completed":
                self.llm_parse_success_count += 1
        ingredient_count = row.get("llm_parsed_ingredient_count")
        if isinstance(ingredient_count, int):
            self.ingredient_counts.append(ingredient_count)
        elif isinstance(row.get("llm_parsed_ingredients"), list):
            self.ingredient_counts.append(len(row["llm_parsed_ingredients"]))  # type: ignore[arg-type]
        error_code = row.get("error_code")
        if isinstance(error_code, str) and error_code:
            self.error_codes[error_code] += 1
        _add_pii_candidate_flags(self.pii_candidate_flags, row.get("pii_candidate_flags"))

    def to_dict(self) -> dict[str, object]:
        """Return JSON-serializable metrics."""
        return {
            "call_count": self.call_count,
            "completed_count": self.completed_count,
            "error_count": self.error_count,
            "not_run_count": self.not_run_count,
            "completed_rate": _ratio(self.completed_count, self.call_count),
            "text_non_empty_rate": _ratio(self.text_non_empty_count, self.call_count),
            "parser_success_rate": _ratio(self.parser_success_count, self.call_count),
            "llm_parse_attempt_count": self.llm_parse_attempt_count,
            "llm_parse_success_rate": _ratio(
                self.llm_parse_success_count,
                self.llm_parse_attempt_count,
            ),
            "median_char_count": median(self.char_counts) if self.char_counts else None,
            "ingredient_count_avg": (
                round(sum(self.ingredient_counts) / len(self.ingredient_counts), 4)
                if self.ingredient_counts
                else None
            ),
            "latency_ms_p50": _percentile(self.latencies, 50),
            "latency_ms_p95": _percentile(self.latencies, 95),
            "error_code_counts": dict(sorted(self.error_codes.items())),
            "pii_candidate_flag_counts": dict(sorted(self.pii_candidate_flags.items())),
        }


def main() -> None:
    """Evaluate observation JSONL files from CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--observation-dir",
        action="append",
        type=Path,
        default=[],
        help="Directory containing supplement-ocr-observations.jsonl.",
    )
    parser.add_argument(
        "--observations",
        action="append",
        type=Path,
        default=[],
        help="Direct observation JSONL path.",
    )
    args = parser.parse_args()
    json_path = args.output_dir / DEFAULT_JSON_NAME
    md_path = args.output_dir / DEFAULT_MARKDOWN_NAME
    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        summary = evaluate_manifest(
            manifest_path=args.manifest,
            observation_dirs=tuple(args.observation_dir),
            observation_paths=tuple(args.observations),
        )
        json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", "utf-8")
        md_path.write_text(render_markdown(summary), "utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure = _failure_summary(manifest_path=args.manifest, error=exc)
        try:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            json_path.write_text(
                json.dumps(failure, ensure_ascii=False, indent=2) + "\n",
                "utf-8",
            )
            md_path.write_text(render_markdown(failure), "utf-8")
        except OSError:
            pass
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None
    print(
        json.dumps(
            {
                "json_name": DEFAULT_JSON_NAME,
                "markdown_name": DEFAULT_MARKDOWN_NAME,
            },
            ensure_ascii=False,
        )
    )


def evaluate_manifest(
    *,
    manifest_path: Path,
    observation_dirs: tuple[Path, ...] = (),
    observation_paths: tuple[Path, ...] = (),
) -> dict[str, object]:
    """Evaluate redacted OCR/Ollama observations against a crawl manifest.

    Args:
        manifest_path: JSONL or JSON manifest path.
        observation_dirs: Directories with ``supplement-ocr-observations.jsonl`` files.
        observation_paths: Direct observation JSONL paths.

    Returns:
        JSON-serializable coverage summary.
    """
    manifest_rows = _read_manifest_rows(manifest_path)
    manifest_meta = _manifest_meta(manifest_rows)
    observations = _collect_observation_rows(
        manifest_rows=manifest_rows,
        observation_dirs=observation_dirs,
        observation_paths=observation_paths,
    )
    provider_buckets: dict[str, MetricBucket] = {}
    section_buckets: dict[str, dict[str, MetricBucket]] = {}
    category_buckets: dict[str, dict[str, MetricBucket]] = {}
    product_buckets: dict[str, dict[str, MetricBucket]] = {}
    mime_type_buckets: dict[str, dict[str, MetricBucket]] = {}
    size_bucket_buckets: dict[str, dict[str, MetricBucket]] = {}
    missing_manifest_rows = 0

    for row in observations:
        _reject_raw_fields(row)
        fixture_id = row.get("fixture_id")
        provider = str(row.get("provider") or "unknown")
        meta = manifest_meta.get(str(fixture_id))
        if meta is None:
            missing_manifest_rows += 1
            meta = ManifestMeta(
                fixture_id=str(fixture_id),
                section="unknown",
                category="unknown",
                product_id=None,
                mime_type=None,
                size_bucket=None,
            )
        provider_buckets.setdefault(provider, MetricBucket()).add(row)
        section_buckets.setdefault(meta.section, {}).setdefault(provider, MetricBucket()).add(row)
        category_buckets.setdefault(meta.category, {}).setdefault(provider, MetricBucket()).add(row)
        product_buckets.setdefault(meta.product_id or "unknown", {}).setdefault(
            provider,
            MetricBucket(),
        ).add(row)
        mime_type_buckets.setdefault(meta.mime_type or "unknown", {}).setdefault(
            provider,
            MetricBucket(),
        ).add(row)
        size_bucket_buckets.setdefault(meta.size_bucket or "unknown", {}).setdefault(
            provider,
            MetricBucket(),
        ).add(row)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "manifest_name": manifest_path.name,
        "manifest_path_hash": _sha256_text(str(manifest_path.expanduser())),
        "fixture_count": len(manifest_rows),
        "observation_count": len(observations),
        "missing_manifest_observation_count": missing_manifest_rows,
        "source_doc_urls": list(SOURCE_DOC_URLS),
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "providers": _bucket_map(provider_buckets),
        "by_section": {key: _bucket_map(value) for key, value in sorted(section_buckets.items())},
        "by_category": {key: _bucket_map(value) for key, value in sorted(category_buckets.items())},
        "by_product": {key: _bucket_map(value) for key, value in sorted(product_buckets.items())},
        "by_mime_type": {
            key: _bucket_map(value) for key, value in sorted(mime_type_buckets.items())
        },
        "by_size_bucket": {
            key: _bucket_map(value) for key, value in sorted(size_bucket_buckets.items())
        },
    }


def render_markdown(summary: dict[str, object]) -> str:
    """Render a compact Markdown report.

    Args:
        summary: Evaluation summary from ``evaluate_manifest``.

    Returns:
        Markdown report without raw OCR text.
    """
    providers = summary.get("providers", {})
    lines = [
        "# Naver Tampermonkey OCR Provider Comparison",
        "",
        f"- Generated at: `{summary.get('generated_at')}`",
        f"- Status: `{summary.get('status', 'completed')}`",
        f"- Manifest: `{summary.get('manifest_name')}`",
        f"- Fixtures: `{summary.get('fixture_count')}`",
        f"- Observations: `{summary.get('observation_count')}`",
        f"- Raw OCR text stored: `{summary.get('raw_ocr_text_stored')}`",
        f"- Raw provider payload stored: `{summary.get('raw_provider_payload_stored')}`",
        f"- Raw model response stored: `{summary.get('raw_model_response_stored')}`",
        "",
        "## Provider Metrics",
        "",
        "| Provider | Calls | Completed | Text non-empty | LLM success | p50 latency ms | p95 latency ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    if isinstance(providers, dict):
        for provider, value in sorted(providers.items()):
            if not isinstance(value, dict):
                continue
            lines.append(
                "| {provider} | {calls} | {completed} | {text_rate} | {llm_rate} | {p50} | {p95} |".format(
                    provider=_markdown_cell(provider),
                    calls=_markdown_cell(value.get("call_count")),
                    completed=_markdown_cell(value.get("completed_rate")),
                    text_rate=_markdown_cell(value.get("text_non_empty_rate")),
                    llm_rate=_markdown_cell(value.get("llm_parse_success_rate")),
                    p50=_markdown_cell(value.get("latency_ms_p50")),
                    p95=_markdown_cell(value.get("latency_ms_p95")),
                )
            )
    _append_group_metrics(
        lines=lines,
        title="Section Metrics",
        group_label="Section",
        grouped=summary.get("by_section", {}),
    )
    _append_group_metrics(
        lines=lines,
        title="Category Metrics",
        group_label="Category",
        grouped=summary.get("by_category", {}),
    )
    _append_group_metrics(
        lines=lines,
        title="Product Metrics",
        group_label="Product",
        grouped=summary.get("by_product", {}),
    )
    _append_group_metrics(
        lines=lines,
        title="MIME Type Metrics",
        group_label="MIME type",
        grouped=summary.get("by_mime_type", {}),
    )
    _append_group_metrics(
        lines=lines,
        title="Size Bucket Metrics",
        group_label="Size bucket",
        grouped=summary.get("by_size_bucket", {}),
    )
    return "\n".join(lines) + "\n"


def _append_group_metrics(
    *,
    lines: list[str],
    title: str,
    group_label: str,
    grouped: object,
) -> None:
    """Append grouped provider coverage rows to a Markdown report."""
    lines.extend(
        [
            "",
            f"## {title}",
            "",
            f"| {group_label} | Provider | Calls | Completed | Text non-empty | LLM success |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    if not isinstance(grouped, dict):
        return
    for group, providers_for_group in sorted(grouped.items()):
        if not isinstance(providers_for_group, dict):
            continue
        for provider, value in sorted(providers_for_group.items()):
            if not isinstance(value, dict):
                continue
            lines.append(
                "| {group} | {provider} | {calls} | {completed} | {text_rate} | {llm_rate} |".format(
                    group=_markdown_cell(group),
                    provider=_markdown_cell(provider),
                    calls=_markdown_cell(value.get("call_count")),
                    completed=_markdown_cell(value.get("completed_rate")),
                    text_rate=_markdown_cell(value.get("text_non_empty_rate")),
                    llm_rate=_markdown_cell(value.get("llm_parse_success_rate")),
                )
            )


def _markdown_cell(value: object) -> str:
    """Return one safe GitHub Markdown table cell value."""
    if value is None:
        return ""
    text = " ".join(str(value).splitlines())
    return html.escape(text, quote=False).replace("|", r"\|")


def _collect_observation_rows(
    *,
    manifest_rows: list[dict[str, object]],
    observation_dirs: tuple[Path, ...],
    observation_paths: tuple[Path, ...],
) -> list[dict[str, object]]:
    """Collect observations from manifest-attached rows and JSONL files."""
    rows: list[dict[str, object]] = []
    for manifest_row in manifest_rows:
        observations = manifest_row.get("observations")
        if isinstance(observations, list):
            for observation in observations:
                if isinstance(observation, dict):
                    rows.append(observation)
    for directory in observation_dirs:
        rows.extend(_read_jsonl_rows(directory / "supplement-ocr-observations.jsonl"))
    for path in observation_paths:
        rows.extend(_read_jsonl_rows(path))
    return rows


def _read_manifest_rows(path: Path) -> list[dict[str, object]]:
    """Read JSONL, JSON list, or JSON object-with-cases manifests."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        rows = [
            json.loads(line)
            for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    else:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and isinstance(parsed.get("cases"), list):
            rows = [item for item in parsed["cases"] if isinstance(item, dict)]
        elif isinstance(parsed, list):
            rows = [item for item in parsed if isinstance(item, dict)]
        else:
            raise ValueError("Manifest must be JSONL, a JSON list, or an object with cases.")
    for row in rows:
        _reject_raw_fields(row)
    return rows


def _read_jsonl_rows(path: Path) -> list[dict[str, object]]:
    """Read JSONL observation rows."""
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        parsed = json.loads(line)
        if not isinstance(parsed, dict):
            raise ValueError("Observation row must be an object.")
        _reject_unsafe_payload(parsed)
        rows.append(parsed)
    return rows


def _manifest_meta(rows: list[dict[str, object]]) -> dict[str, ManifestMeta]:
    """Build fixture metadata lookup."""
    meta: dict[str, ManifestMeta] = {}
    for row in rows:
        fixture_id = row.get("fixture_id")
        if not isinstance(fixture_id, str) or not fixture_id:
            continue
        source_metadata = row.get("source_metadata")
        if not isinstance(source_metadata, dict):
            source_metadata = {}
        section = row.get("section") or source_metadata.get("section") or "unknown"
        category = row.get("category") or source_metadata.get("category") or "unknown"
        product_id = row.get("product_id")
        mime_type = row.get("mime_type")
        size_bucket = row.get("size_bucket")
        meta[fixture_id] = ManifestMeta(
            fixture_id=fixture_id,
            section=str(section),
            category=str(category),
            product_id=product_id if isinstance(product_id, str) else None,
            mime_type=mime_type if isinstance(mime_type, str) else None,
            size_bucket=size_bucket if isinstance(size_bucket, str) else None,
        )
    return meta


def _bucket_map(buckets: dict[str, MetricBucket]) -> dict[str, dict[str, object]]:
    """Serialize sorted metric buckets."""
    return {key: bucket.to_dict() for key, bucket in sorted(buckets.items())}


def _add_pii_candidate_flags(counter: Counter[str], flags: object) -> None:
    """Add bounded PII flag tokens to a counter."""
    if not isinstance(flags, list):
        return
    for flag in flags:
        if isinstance(flag, str) and flag:
            counter[flag] += 1


def _ratio(numerator: int, denominator: int) -> float | None:
    """Return a rounded ratio or None for empty denominators."""
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def _percentile(values: list[float], percentile: int) -> float | None:
    """Return a nearest-rank percentile."""
    if not values:
        return None
    ordered = sorted(values)
    if percentile <= MEDIAN_PERCENTILE:
        return round(float(median(ordered)), 4)
    rank = round((percentile / PERCENTILE_SCALE) * len(ordered) + NEAREST_RANK_OFFSET)
    index = max(0, min(len(ordered) - 1, rank - 1))
    return round(float(ordered[index]), 4)


def _failure_summary(*, manifest_path: Path, error: BaseException) -> dict[str, object]:
    """Return a redacted evaluator failure summary."""
    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "manifest_name": manifest_path.name,
        "manifest_path_hash": _sha256_text(str(manifest_path.expanduser())),
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "fixture_count": 0,
        "observation_count": 0,
        "missing_manifest_observation_count": 0,
        "source_doc_urls": list(SOURCE_DOC_URLS),
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "providers": {},
        "by_section": {},
        "by_category": {},
        "by_product": {},
        "by_mime_type": {},
        "by_size_bucket": {},
    }
    _reject_unsafe_payload(summary)
    return summary


def _safe_error_code(exc: BaseException) -> str:
    """Return a non-sensitive CLI error code."""
    if isinstance(exc, OSError):
        return "local_file_error"
    if isinstance(exc, json.JSONDecodeError):
        return "json_decode_error"
    return "validation_error"


def _safe_public_error_message(exc: BaseException) -> str:
    """Return a bounded public error message without filesystem details."""
    if isinstance(exc, OSError):
        return "Local file operation failed."
    if isinstance(exc, json.JSONDecodeError):
        return "JSON decode failed."
    message = str(exc).strip()
    if not message:
        return "Validation failed."
    if any(marker in message for marker in LOCAL_PATH_MARKERS):
        return "Validation failed."
    if "/" in message or "\\" in message:
        return "Validation failed."
    return message[:200]


def _sha256_text(value: str) -> str:
    """Return SHA-256 for redacted path identifiers."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _reject_raw_fields(value: object) -> None:
    """Reject raw OCR/image/provider/model fields recursively."""
    _reject_unsafe_payload(value)


def _reject_unsafe_payload(value: object) -> None:
    """Reject raw OCR fields and local path literals recursively."""
    if isinstance(value, dict):
        forbidden = RAW_FORBIDDEN_KEYS.intersection(str(key).lower() for key in value)
        if forbidden:
            raise ValueError(f"Payload contains forbidden raw field(s): {sorted(forbidden)}")
        for nested in value.values():
            _reject_unsafe_payload(nested)
    elif isinstance(value, list):
        for item in value:
            _reject_unsafe_payload(item)
    elif isinstance(value, str) and any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")


if __name__ == "__main__":
    main()
