"""Preflight manual supplement OCR ground-truth rows before benchmark build.

This tool checks whether an operator-edited ground-truth JSONL can be promoted
to an OCR benchmark manifest. It reports only counts, stable blocker names, and
safe file basenames. It does not call OCR providers, does not write to the
database, does not train PaddleOCR, and does not emit OCR text, provider
payloads, image bytes, local paths, or source row payloads.

References:
    https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
    https://cloud.google.com/vision/docs/ocr
    https://api.ncloud-docs.com/docs/en/ai-application-service-ocr
    https://docs.python.org/3/library/argparse.html
    https://docs.python.org/3/library/json.html
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import build_supplement_ocr_benchmark_manifest as benchmark  # noqa: E402

SCHEMA_VERSION = "supplement-ocr-ground-truth-preflight-v1"
STATUS_READY = "ready_for_benchmark_build"
STATUS_NO_ROWS = "blocked_by_no_rows"
STATUS_NOT_REVIEWED = "blocked_by_manual_review"
STATUS_MISSING_SECTIONS = "blocked_by_missing_required_sections"
STATUS_NO_READY_ROWS = "blocked_by_no_ready_rows"
STATUS_ERROR = "error"
SOURCE_DOC_URLS = (
    "https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html",
    "https://cloud.google.com/vision/docs/ocr",
    "https://api.ncloud-docs.com/docs/en/ai-application-service-ocr",
    "https://docs.python.org/3/library/argparse.html",
    "https://docs.python.org/3/library/json.html",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, default=None)
    parser.add_argument(
        "--required-expected-section",
        action="append",
        choices=sorted(benchmark.ALLOWED_REQUIRED_EXPECTED_SECTIONS),
        default=None,
    )
    parser.add_argument("--min-ready-rows", type=int, default=1)
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None) -> int:
    """Run the ground-truth preflight and write redacted artifacts.

    Args:
        argv: Optional argument list for tests.

    Returns:
        ``0`` when the manifest is ready for benchmark build, otherwise ``1``.
    """
    args = parse_args(argv)
    try:
        summary = build_ground_truth_preflight(
            ground_truth_manifest=args.ground_truth,
            required_expected_sections=args.required_expected_section,
            min_ready_rows=args.min_ready_rows,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = _error_summary(error=exc, manifest_name=args.ground_truth.name)

    _write_json(args.output, summary)
    if args.markdown_output is not None:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(build_markdown(summary), encoding="utf-8")
    print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    return 0 if summary.get("ready_for_benchmark_build") is True else 1


def build_ground_truth_preflight(
    *,
    ground_truth_manifest: Path,
    required_expected_sections: list[str] | tuple[str, ...] | None = None,
    min_ready_rows: int = 1,
) -> dict[str, Any]:
    """Build a redacted readiness summary for manual OCR ground truth.

    Args:
        ground_truth_manifest: Operator-edited ground-truth JSONL path.
        required_expected_sections: Required expected sections for the benchmark.
        min_ready_rows: Minimum eligible row count.

    Returns:
        Redacted preflight summary.

    Raises:
        ValueError: If the manifest is unsafe or arguments are invalid.
    """
    if min_ready_rows <= 0:
        raise ValueError("min_ready_rows must be positive.")
    rows = benchmark._read_jsonl(ground_truth_manifest)
    required_sections = benchmark._required_expected_sections(required_expected_sections)
    row_count = len(rows)
    issue_counts: Counter[str] = Counter()
    missing_required_section_counts: Counter[str] = Counter()
    human_reviewed_row_count = 0
    benchmark_ready_row_count = 0
    explicit_ready_flag_count = 0

    for row in rows:
        benchmark._reject_unsafe_payload(row)
        _validate_safe_row_key(row)
        if row.get("ready_for_benchmark_after_review") is True:
            explicit_ready_flag_count += 1
        block_reason = benchmark._manual_ground_truth_block_reason(row)
        if block_reason is not None:
            issue_counts[block_reason] += 1

        expected = benchmark._expected_from_decision(row)
        if not expected["ingredients"]:
            issue_counts["manual_ground_truth_missing_ingredients"] += 1
        missing_sections = benchmark._missing_required_expected_sections(
            expected, required_sections
        )
        if missing_sections:
            issue_counts["manual_ground_truth_missing_required_sections"] += 1
            missing_required_section_counts.update(missing_sections)

        if block_reason is None:
            human_reviewed_row_count += 1
            if expected["ingredients"] and not missing_sections:
                benchmark_ready_row_count += 1

    status = _status(
        row_count=row_count,
        benchmark_ready_row_count=benchmark_ready_row_count,
        min_ready_rows=min_ready_rows,
        issue_counts=issue_counts,
        missing_required_section_counts=missing_required_section_counts,
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "ground_truth_manifest_name": ground_truth_manifest.name,
        "ground_truth_manifest_hash": benchmark._sha256_text(
            str(ground_truth_manifest.expanduser())
        ),
        "row_count": row_count,
        "human_reviewed_row_count": human_reviewed_row_count,
        "explicit_ready_flag_count": explicit_ready_flag_count,
        "benchmark_ready_row_count": benchmark_ready_row_count,
        "min_ready_rows": min_ready_rows,
        "required_expected_sections": list(required_sections),
        "issue_counts": dict(sorted(issue_counts.items())),
        "missing_required_section_counts": dict(sorted(missing_required_section_counts.items())),
        "status": status,
        "ready_for_benchmark_build": status == STATUS_READY,
        "next_steps": _next_steps(status),
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    benchmark._reject_unsafe_payload(summary)
    return summary


def build_markdown(summary: dict[str, Any]) -> str:
    """Build a redacted Markdown report.

    Args:
        summary: Ground-truth preflight summary.

    Returns:
        Markdown report text.
    """
    benchmark._reject_unsafe_payload(summary)
    issues = summary.get("issue_counts")
    if not isinstance(issues, dict):
        issues = {}
    issue_lines = "\n".join(
        f"- `{_safe_output_token(str(name))}`: `{_safe_count(value)}`"
        for name, value in sorted(issues.items())
    )
    if not issue_lines:
        issue_lines = "- `none`: `0`"
    missing = summary.get("missing_required_section_counts")
    if not isinstance(missing, dict):
        missing = {}
    missing_lines = "\n".join(
        f"- `{_safe_output_token(str(name))}`: `{_safe_count(value)}`"
        for name, value in sorted(missing.items())
    )
    if not missing_lines:
        missing_lines = "- `none`: `0`"
    next_steps = "\n".join(
        f"- `{_safe_output_token(str(step))}`" for step in summary.get("next_steps", [])
    )
    return "\n".join(
        [
            "# Supplement OCR Ground Truth Preflight",
            "",
            "이 문서는 수동 OCR 정답지의 benchmark 승격 가능 여부만 요약합니다. OCR 원문, provider payload, 이미지 경로, 로컬 절대경로는 포함하지 않습니다.",
            "",
            f"- Status: `{_safe_output_token(str(summary.get('status') or 'unknown'))}`",
            f"- Ready for benchmark build: `{_bool_text(summary.get('ready_for_benchmark_build'))}`",
            f"- Row count: `{_safe_count(summary.get('row_count'))}`",
            f"- Benchmark-ready rows: `{_safe_count(summary.get('benchmark_ready_row_count'))}`",
            "",
            "## Issues",
            "",
            issue_lines,
            "",
            "## Missing Required Sections",
            "",
            missing_lines,
            "",
            "## Next Steps",
            "",
            next_steps,
            "",
            "## Privacy",
            "",
            "- `db_write_performed`: `false`",
            "- `ocr_provider_call_performed`: `false`",
            "- `paddleocr_training_performed`: `false`",
            "- `raw_ocr_text_stored`: `false`",
            "- `raw_provider_payload_stored`: `false`",
            "- `absolute_paths_stored`: `false`",
            "",
        ]
    )


def _validate_safe_row_key(row: dict[str, Any]) -> None:
    """Validate that a row has a safe synthetic key.

    Args:
        row: Ground-truth row.

    Raises:
        ValueError: If no safe fixture id or image hash exists.
    """
    fixture_id = row.get("fixture_id")
    image_ref_hash = row.get("image_ref_hash")
    if isinstance(fixture_id, str) and fixture_id:
        benchmark._safe_required_token(fixture_id, field_name="fixture_id")
        return
    if isinstance(image_ref_hash, str) and image_ref_hash:
        benchmark._safe_required_sha256(image_ref_hash)
        return
    raise ValueError("Ground-truth row must include a safe fixture_id or image_ref_hash.")


def _status(
    *,
    row_count: int,
    benchmark_ready_row_count: int,
    min_ready_rows: int,
    issue_counts: Counter[str],
    missing_required_section_counts: Counter[str],
) -> str:
    """Return the stable preflight status.

    Args:
        row_count: Total row count.
        benchmark_ready_row_count: Rows that can enter benchmark build.
        min_ready_rows: Minimum required ready rows.
        issue_counts: Issue counters.
        missing_required_section_counts: Missing section counters.

    Returns:
        Stable status string.
    """
    if row_count == 0:
        return STATUS_NO_ROWS
    if benchmark_ready_row_count >= min_ready_rows:
        return STATUS_READY
    if missing_required_section_counts:
        return STATUS_MISSING_SECTIONS
    if any("not_human_reviewed" in key or "not_marked_ready" in key for key in issue_counts):
        return STATUS_NOT_REVIEWED
    return STATUS_NO_READY_ROWS


def _next_steps(status: str) -> list[str]:
    """Return stable next steps for a preflight status.

    Args:
        status: Preflight status.

    Returns:
        Ordered next-step identifiers.
    """
    steps = {
        STATUS_READY: [
            "run_build_supplement_ocr_benchmark_manifest",
            "assign_product_group_safe_benchmark_splits",
            "run_clova_google_vision_paddleocr_comparison",
        ],
        STATUS_NO_ROWS: [
            "export_ground_truth_template_from_pii_cleared_candidates",
            "complete_local_ground_truth_review_bundle",
            "rerun_ground_truth_preflight",
        ],
        STATUS_NOT_REVIEWED: [
            "complete_human_double_check",
            "set_ground_truth_status_to_human_reviewed",
            "set_ready_for_benchmark_after_review_true",
            "rerun_ground_truth_preflight",
        ],
        STATUS_MISSING_SECTIONS: [
            "fill_required_expected_sections_visible_in_review_image",
            "keep_missing_unvisible_sections_out_of_strict_benchmark",
            "rerun_ground_truth_preflight",
        ],
        STATUS_NO_READY_ROWS: [
            "inspect_issue_counts",
            "complete_required_ground_truth_fields",
            "rerun_ground_truth_preflight",
        ],
    }
    return steps.get(status, ["inspect_preflight_error"])


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON payload.

    Args:
        path: Destination path.
        payload: JSON-safe payload.
    """
    benchmark._reject_unsafe_payload(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _cli_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Return a short redacted CLI summary.

    Args:
        summary: Full summary.

    Returns:
        CLI-safe subset.
    """
    return {
        "schema_version": summary.get("schema_version"),
        "status": summary.get("status"),
        "ready_for_benchmark_build": summary.get("ready_for_benchmark_build"),
        "row_count": summary.get("row_count", 0),
        "benchmark_ready_row_count": summary.get("benchmark_ready_row_count", 0),
        "issue_counts": summary.get("issue_counts", {}),
    }


def _error_summary(*, error: Exception, manifest_name: str) -> dict[str, Any]:
    """Return a redacted error summary.

    Args:
        error: Raised exception.
        manifest_name: Safe input basename.

    Returns:
        Error summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "ground_truth_manifest_name": manifest_name,
        "status": STATUS_ERROR,
        "ready_for_benchmark_build": False,
        "error_code": type(error).__name__,
        "error_message": "Supplement OCR ground-truth preflight failed.",
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
    }


def _safe_output_token(value: str) -> str:
    """Return a bounded display token.

    Args:
        value: Raw display value.

    Returns:
        Safe token for Markdown.
    """
    return "".join(ch if ch.isalnum() or ch in "_.:-" else "_" for ch in value)[:160]


def _safe_count(value: Any) -> int:
    """Return a non-negative integer count.

    Args:
        value: Raw count.

    Returns:
        Non-negative integer count.
    """
    return value if isinstance(value, int) and value >= 0 else 0


def _bool_text(value: Any) -> str:
    """Return a stable boolean display value.

    Args:
        value: Raw value.

    Returns:
        ``true`` or ``false``.
    """
    return "true" if value is True else "false"


def main(argv: list[str] | None = None) -> None:
    """Run the CLI and exit with its readiness status.

    Args:
        argv: Optional argument list for tests.
    """
    raise SystemExit(run_cli(argv))


if __name__ == "__main__":
    main()
