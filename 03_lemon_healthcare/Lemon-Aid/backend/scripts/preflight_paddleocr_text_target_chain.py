"""Preflight the PaddleOCR 95 percent text target artifact chain.

This script verifies whether a redacted benchmark or metric manifest is ready
for the final PaddleOCR text extraction target gate. It intentionally reports
only counts, check names, and safe file basenames. It does not read image bytes,
does not call OCR providers, does not train PaddleOCR, and does not emit OCR
text, provider payloads, local paths, or source row payloads.

References:
    https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
    https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppocr/model_train/detection.html
    https://paddlepaddle.github.io/PaddleOCR/v2.10.0/en/ppocr/model_train/recognition.html
    https://docs.python.org/3/library/argparse.html
    https://docs.python.org/3/library/json.html
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "paddleocr-text-target-chain-preflight-v1"
TARGET_PROVIDER = "paddleocr_local"
ALLOWED_EVAL_SPLITS = frozenset({"holdout", "test"})
HUMAN_REVIEWED_STATUSES = frozenset({"approved", "human_reviewed", "verified"})
SUPPORTED_ROW_SCHEMA_VERSIONS = frozenset(
    {
        "supplement-ocr-provider-benchmark-fixture-v1",
        "supplement-paddleocr-text-metric-fixture-v1",
    }
)
CANDIDATE_ROW_SCHEMA_VERSIONS = frozenset(
    {
        "supplement-review-ocr-ground-truth-candidate-v1",
        "supplement-learning-ocr-ground-truth-candidate-v1",
    }
)
REQUIRED_METRICS = (
    "normalized_text_precision",
    "normalized_text_recall",
    "normalized_text_f1",
)
DEFAULT_MIN_FIXTURE_COUNT = 30
STATUS_READY = "ready_for_target_gate"
STATUS_NO_ROWS = "blocked_by_no_rows"
STATUS_CANDIDATE_MANIFEST = "blocked_by_candidate_manifest"
STATUS_UNSUPPORTED_SCHEMA = "blocked_by_unsupported_manifest_schema"
STATUS_NOT_SCOREABLE = "blocked_by_not_scoreable"
STATUS_MISSING_METRICS = "blocked_by_missing_provider_metrics"
STATUS_ERROR = "error"
RAW_FORBIDDEN_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "image_bytes",
        "local_path",
        "ocr_text",
        "provider_payload",
        "raw_image",
        "raw_model_response",
        "raw_ocr_text",
        "raw_provider_payload",
        "request_headers",
        "secret",
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
SECRET_LIKE_MARKERS = (
    "bearer ",
    "ngrok-free.dev",
    "sb_secret_",
    "service_role",
    "aws_secret_access_key",
    "-----begin",
)
SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
SOURCE_DOC_URLS = (
    "https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html",
    "https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppocr/model_train/detection.html",
    "https://paddlepaddle.github.io/PaddleOCR/v2.10.0/en/ppocr/model_train/recognition.html",
    "https://docs.python.org/3/library/argparse.html",
    "https://docs.python.org/3/library/json.html",
)
NEXT_STEPS_BY_STATUS = {
    STATUS_READY: (
        "build_eval_summary_for_requested_split",
        "run_paddleocr_text_extraction_target_gate",
        "stop_training_only_if_target_gate_reaches_95_percent",
    ),
    STATUS_NO_ROWS: (
        "build_human_reviewed_ocr_benchmark_manifest",
        "collect_provider_observations_or_private_text_metrics",
        "rerun_paddleocr_text_target_chain_preflight",
    ),
    STATUS_CANDIDATE_MANIFEST: (
        "complete_review_image_pii_screening",
        "complete_human_reviewed_ocr_ground_truth",
        "build_human_reviewed_ocr_benchmark_manifest_from_candidates",
        "assign_product_group_safe_benchmark_splits",
        "rerun_paddleocr_text_target_chain_preflight",
    ),
    STATUS_UNSUPPORTED_SCHEMA: (
        "build_human_reviewed_ocr_benchmark_manifest_from_candidates",
        "merge_provider_observations_or_build_metric_manifest",
        "rerun_paddleocr_text_target_chain_preflight",
    ),
    STATUS_NOT_SCOREABLE: (
        "complete_holdout_or_test_split_assignment",
        "complete_human_reviewed_ground_truth",
        "ensure_leakage_check_passed_for_eval_split",
        "rerun_paddleocr_text_target_chain_preflight",
    ),
    STATUS_MISSING_METRICS: (
        "collect_paddleocr_local_observations",
        "build_redacted_text_metric_manifest",
        "build_eval_summary_for_requested_split",
        "rerun_paddleocr_text_target_chain_preflight",
    ),
}


class PaddleOCRTextTargetChainPreflightError(ValueError):
    """Raised when the target-chain preflight input is unsafe or malformed."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--markdown-output", type=Path, default=None)
    parser.add_argument("--provider", default=TARGET_PROVIDER)
    parser.add_argument("--eval-split", required=True, choices=sorted(ALLOWED_EVAL_SPLITS))
    parser.add_argument("--min-fixtures", type=int, default=DEFAULT_MIN_FIXTURE_COUNT)
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None) -> int:
    """Run the preflight and write redacted artifacts.

    Args:
        argv: Optional argument list for tests.

    Returns:
        ``0`` when ready for the target gate, otherwise ``1``.
    """
    args = parse_args(argv)
    try:
        summary = build_paddleocr_text_target_chain_preflight(
            benchmark_manifest=args.benchmark_manifest,
            provider=args.provider,
            eval_split=args.eval_split,
            min_fixture_count=args.min_fixtures,
        )
    except (
        OSError,
        json.JSONDecodeError,
        PaddleOCRTextTargetChainPreflightError,
        ValueError,
    ) as exc:
        summary = _error_summary(error=exc, manifest_name=args.benchmark_manifest.name)

    _write_json(args.output, summary)
    if args.markdown_output is not None:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(build_markdown(summary), encoding="utf-8")
    print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    return 0 if summary.get("ready_for_target_gate") is True else 1


def build_paddleocr_text_target_chain_preflight(
    *,
    benchmark_manifest: Path,
    provider: str = TARGET_PROVIDER,
    eval_split: str,
    min_fixture_count: int = DEFAULT_MIN_FIXTURE_COUNT,
) -> dict[str, Any]:
    """Build a redacted preflight summary for the final target gate chain.

    Args:
        benchmark_manifest: Redacted benchmark or metric manifest JSONL.
        provider: Provider id expected in observations.
        eval_split: Evaluation split to use for the 95 percent target gate.
        min_fixture_count: Minimum scoreable fixture count required.

    Returns:
        Redacted preflight summary.

    Raises:
        PaddleOCRTextTargetChainPreflightError: If input data is unsafe or
            structurally unsupported.
        ValueError: If arguments are invalid.
    """
    provider = _safe_token(provider, field_name="provider")
    if eval_split not in ALLOWED_EVAL_SPLITS:
        raise ValueError("eval_split must be holdout or test.")
    if min_fixture_count <= 0:
        raise ValueError("min_fixture_count must be positive.")

    rows = _read_jsonl(benchmark_manifest)
    row_count = len(rows)
    stats = _summarize_rows(rows=rows, provider=provider, eval_split=eval_split)
    checks = {
        "has_rows": row_count > 0,
        "all_rows_use_supported_schema": stats["unsupported_schema_count"] == 0,
        "candidate_manifest_requires_benchmark_build": (
            stats["candidate_schema_count"] == row_count and row_count > 0
        ),
        "minimum_fixture_count_met": stats["eval_split_row_count"] >= min_fixture_count,
        "all_eval_rows_have_human_reviewed_expected": (
            stats["human_reviewed_expected_count"] == stats["eval_split_row_count"]
            and stats["eval_split_row_count"] > 0
        ),
        "all_eval_rows_have_reference_text": (
            stats["expected_reference_text_count"] == stats["eval_split_row_count"]
            and stats["eval_split_row_count"] > 0
        ),
        "all_eval_rows_have_provider_observation": (
            stats["provider_observation_count"] == stats["eval_split_row_count"]
            and stats["eval_split_row_count"] > 0
        ),
        "all_eval_rows_have_complete_metrics": (
            stats["metric_complete_observation_count"] == stats["eval_split_row_count"]
            and stats["eval_split_row_count"] > 0
        ),
        "all_eval_rows_passed_leakage_check": (
            stats["leakage_check_passed_count"] == stats["eval_split_row_count"]
            and stats["eval_split_row_count"] > 0
        ),
        "no_raw_or_path_payload_flags": stats["unsafe_flag_count"] == 0,
    }
    status = _status_from_checks(checks=checks, row_count=row_count, stats=stats)
    ready = status == STATUS_READY
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "benchmark_manifest_name": benchmark_manifest.name,
        "provider": provider,
        "eval_split": eval_split,
        "min_fixture_count": min_fixture_count,
        "row_count": row_count,
        **stats,
        "checks": checks,
        "status": status,
        "ready_for_target_gate": ready,
        "continue_training_loop": True,
        "next_steps": list(NEXT_STEPS_BY_STATUS[status]),
        "db_write_performed": False,
        "source_rows_read": False,
        "source_image_read_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    _reject_unsafe_payload(summary)
    return summary


def build_markdown(summary: Mapping[str, Any]) -> str:
    """Build a redacted Markdown preflight report.

    Args:
        summary: Preflight summary.

    Returns:
        Markdown report text.
    """
    _reject_unsafe_payload(summary)
    checks = summary.get("checks")
    if not isinstance(checks, Mapping):
        checks = {}
    check_lines = "\n".join(
        f"- `{_display_check_name(str(name))}`: `{_bool_text(value)}`"
        for name, value in sorted(checks.items())
    )
    next_steps = "\n".join(
        f"- `{_safe_output_token(str(step))}`" for step in summary.get("next_steps", [])
    )
    markdown = "\n".join(
        [
            "# PaddleOCR Text Target Chain Preflight",
            "",
            "이 문서는 PaddleOCR 95% target gate 실행 준비 상태만 요약합니다. OCR 원문, provider payload, 이미지 경로, 로컬 절대경로는 포함하지 않습니다.",
            "",
            f"- Status: `{_safe_output_token(str(summary.get('status') or 'unknown'))}`",
            f"- Ready for target gate: `{_bool_text(summary.get('ready_for_target_gate'))}`",
            f"- Eval split: `{_safe_output_token(str(summary.get('eval_split') or 'unknown'))}`",
            f"- Row count: `{_nonnegative_int(summary.get('row_count'), 'row_count')}`",
            f"- Scoreable fixtures: `{_nonnegative_int(summary.get('scoreable_fixture_count'), 'scoreable_fixture_count')}`",
            "",
            "## Checks",
            "",
            check_lines,
            "",
            "## Next Steps",
            "",
            next_steps,
            "",
            "## Privacy",
            "",
            "- `db_write_performed`: `false`",
            "- `source_image_read_performed`: `false`",
            "- `ocr_provider_call_performed`: `false`",
            "- `raw_ocr_text_stored`: `false`",
            "- `raw_provider_payload_stored`: `false`",
            "- `absolute_paths_stored`: `false`",
            "",
        ]
    )
    _reject_unsafe_payload({"markdown": markdown})
    return markdown


def _summarize_rows(
    *,
    rows: list[dict[str, Any]],
    provider: str,
    eval_split: str,
) -> dict[str, Any]:
    """Summarize redacted benchmark rows without exposing row payloads.

    Args:
        rows: JSONL rows.
        provider: Provider id expected in observations.
        eval_split: Requested held-out split.

    Returns:
        Redacted counts and skip reasons.
    """
    counters: dict[str, int] = {
        "eval_split_row_count": 0,
        "unsupported_schema_count": 0,
        "candidate_schema_count": 0,
        "human_reviewed_expected_count": 0,
        "expected_reference_text_count": 0,
        "provider_observation_count": 0,
        "metric_complete_observation_count": 0,
        "leakage_check_passed_count": 0,
        "scoreable_fixture_count": 0,
        "unsafe_flag_count": 0,
    }
    split_counts: Counter[str] = Counter()
    schema_counts: Counter[str] = Counter()
    skip_reasons: Counter[str] = Counter()

    for row in rows:
        inspected = _inspect_row(row=row, provider=provider, eval_split=eval_split)
        schema_counts[inspected["schema_version"]] += 1
        split_counts[inspected["split"]] += 1
        for reason in inspected["skip_reasons"]:
            skip_reasons[reason] += 1
        for key in counters:
            counters[key] += int(inspected[key])

    return {
        "split_counts": dict(sorted(split_counts.items())),
        "schema_version_counts": dict(sorted(schema_counts.items())),
        **counters,
        "skip_reason_counts": dict(sorted(skip_reasons.items())),
    }


def _inspect_row(
    *,
    row: Mapping[str, Any],
    provider: str,
    eval_split: str,
) -> dict[str, Any]:
    """Inspect one row and return redacted booleans only.

    Args:
        row: Benchmark fixture row.
        provider: Provider id expected in observations.
        eval_split: Requested evaluation split.

    Returns:
        Safe row inspection fields.
    """
    _reject_unsafe_payload(row)
    schema_version = _safe_optional_token(row.get("schema_version"), field_name="schema_version")
    row_split = _safe_optional_token(row.get("eval_split") or row.get("split"), field_name="split")
    unsupported_schema = schema_version not in SUPPORTED_ROW_SCHEMA_VERSIONS
    candidate_schema = schema_version in CANDIDATE_ROW_SCHEMA_VERSIONS
    in_eval_split = row_split == eval_split
    expected = row.get("expected") if in_eval_split else None
    expected_human_reviewed = _expected_is_human_reviewed(expected)
    expected_has_text = _expected_has_reference_text(expected)
    observation = _provider_observation(row, provider) if in_eval_split else None
    observation_has_metrics = observation is not None and _observation_has_complete_metrics(
        observation
    )
    leakage_check_passed = in_eval_split and row.get("leakage_check_passed") is True
    unsafe_flags = _row_has_unsafe_payload_flags(row)
    scoreable = (
        in_eval_split
        and not unsupported_schema
        and expected_human_reviewed
        and expected_has_text
        and observation is not None
        and observation_has_metrics
        and leakage_check_passed
        and not unsafe_flags
    )
    return {
        "schema_version": schema_version or "<missing>",
        "split": row_split or "<missing>",
        "eval_split_row_count": in_eval_split,
        "unsupported_schema_count": unsupported_schema,
        "candidate_schema_count": candidate_schema,
        "human_reviewed_expected_count": in_eval_split and expected_human_reviewed,
        "expected_reference_text_count": in_eval_split and expected_has_text,
        "provider_observation_count": in_eval_split and observation is not None,
        "metric_complete_observation_count": in_eval_split and observation_has_metrics,
        "leakage_check_passed_count": leakage_check_passed,
        "scoreable_fixture_count": scoreable,
        "unsafe_flag_count": unsafe_flags,
        "skip_reasons": _skip_reasons(
            in_eval_split=in_eval_split,
            unsupported_schema=unsupported_schema,
            candidate_schema=candidate_schema,
            expected_human_reviewed=expected_human_reviewed,
            expected_has_text=expected_has_text,
            observation_present=observation is not None,
            observation_has_metrics=observation_has_metrics,
            leakage_check_passed=leakage_check_passed,
            unsafe_flags=unsafe_flags,
        ),
    }


def _skip_reasons(
    *,
    in_eval_split: bool,
    unsupported_schema: bool,
    candidate_schema: bool,
    expected_human_reviewed: bool,
    expected_has_text: bool,
    observation_present: bool,
    observation_has_metrics: bool,
    leakage_check_passed: bool,
    unsafe_flags: bool,
) -> list[str]:
    """Return redacted skip reasons for one inspected row.

    Args:
        in_eval_split: Whether the row belongs to the requested split.
        unsupported_schema: Whether the row schema is unsupported.
        candidate_schema: Whether the row is a pre-benchmark candidate.
        expected_human_reviewed: Whether expected output is human-reviewed.
        expected_has_text: Whether expected output has text evidence.
        observation_present: Whether the target provider observation exists.
        observation_has_metrics: Whether the observation has all metrics.
        leakage_check_passed: Whether leakage validation passed.
        unsafe_flags: Whether raw/path flags are unsafe.

    Returns:
        Skip reason tokens.
    """
    reasons: list[str] = []
    if unsupported_schema:
        reasons.append("unsupported_row_schema")
    if candidate_schema:
        reasons.append("candidate_manifest_requires_benchmark_build")
    if not in_eval_split:
        reasons.append("split_mismatch_or_missing")
        return reasons
    if not leakage_check_passed:
        reasons.append("leakage_check_missing_or_failed")
    if not expected_human_reviewed:
        reasons.append("expected_not_human_reviewed")
    if not expected_has_text:
        reasons.append("expected_reference_text_missing")
    if not observation_present:
        reasons.append("missing_provider_observation")
    elif not observation_has_metrics:
        reasons.append("provider_metrics_incomplete")
    if unsafe_flags:
        reasons.append("unsafe_payload_flag")
    return reasons


def _status_from_checks(
    *,
    checks: Mapping[str, bool],
    row_count: int,
    stats: Mapping[str, Any],
) -> str:
    """Choose a preflight status from checks and counts.

    Args:
        checks: Boolean readiness checks.
        row_count: Total input row count.
        stats: Row summary counts.

    Returns:
        Status token.
    """
    if row_count <= 0:
        return STATUS_NO_ROWS
    if stats.get("candidate_schema_count") == row_count:
        return STATUS_CANDIDATE_MANIFEST
    if stats.get("unsupported_schema_count") == row_count:
        return STATUS_UNSUPPORTED_SCHEMA
    if not (
        checks.get("minimum_fixture_count_met")
        and checks.get("all_eval_rows_have_human_reviewed_expected")
        and checks.get("all_eval_rows_have_reference_text")
        and checks.get("all_eval_rows_passed_leakage_check")
        and checks.get("no_raw_or_path_payload_flags")
    ):
        return STATUS_NOT_SCOREABLE
    if not (
        checks.get("all_eval_rows_have_provider_observation")
        and checks.get("all_eval_rows_have_complete_metrics")
    ):
        return STATUS_MISSING_METRICS
    readiness_checks = {
        key: value
        for key, value in checks.items()
        if key != "candidate_manifest_requires_benchmark_build"
    }
    return STATUS_READY if all(readiness_checks.values()) else STATUS_NOT_SCOREABLE


def _expected_is_human_reviewed(expected: Any) -> bool:
    """Return whether expected output has human-reviewed status.

    Args:
        expected: Expected field payload.

    Returns:
        True when expected is a mapping with a reviewed status.
    """
    if not isinstance(expected, Mapping):
        return False
    status = expected.get("verification_status") or expected.get("ground_truth_status")
    return str(status or "").strip().lower() in HUMAN_REVIEWED_STATUSES


def _expected_has_reference_text(expected: Any) -> bool:
    """Return whether expected output can be scored for text extraction.

    Args:
        expected: Expected field payload.

    Returns:
        True when the row declares text GT or has enough reviewed structured
        fields for the private metric builder's structured fallback.
    """
    return isinstance(expected, Mapping) and (
        expected.get("text_ground_truth_present") is True
        or _expected_has_text_field(expected)
        or _expected_has_structured_text_fallback(expected)
    )


def _expected_has_text_field(expected: Mapping[str, Any]) -> bool:
    """Return whether expected contains a private text field.

    Args:
        expected: Expected mapping.

    Returns:
        True if a text field is non-empty.
    """
    for key in ("reference_text", "normalized_text", "full_text", "text_ground_truth"):
        value = expected.get(key)
        if isinstance(value, str) and value.strip():
            return True
    return False


def _expected_has_structured_text_fallback(expected: Mapping[str, Any]) -> bool:
    """Return whether expected has structured fields for text fallback.

    Args:
        expected: Expected mapping.

    Returns:
        True if structured GT is present.
    """
    ingredients = expected.get("ingredients")
    if isinstance(ingredients, list) and ingredients:
        return True
    if any(
        isinstance(expected.get(key), str) and expected[key].strip()
        for key in ("product_name", "manufacturer")
    ):
        return True
    for key in ("intake_method", "precautions", "functional_claims"):
        value = expected.get(key)
        if isinstance(value, Mapping) and str(value.get("text") or "").strip():
            return True
        if isinstance(value, list) and value:
            return True
    return False


def _provider_observation(row: Mapping[str, Any], provider: str) -> Mapping[str, Any] | None:
    """Return the provider observation for a row.

    Args:
        row: Benchmark fixture row.
        provider: Provider id to find.

    Returns:
        Observation mapping, if present.
    """
    observations = row.get("observations")
    if not isinstance(observations, list):
        return None
    for observation in observations:
        if not isinstance(observation, Mapping):
            continue
        observation_provider = _safe_optional_token(
            observation.get("provider"),
            field_name="observation.provider",
        )
        if observation_provider == provider:
            _reject_unsafe_payload(observation)
            return observation
    return None


def _observation_has_complete_metrics(observation: Mapping[str, Any]) -> bool:
    """Return whether an observation has all required text metrics.

    Args:
        observation: Provider observation.

    Returns:
        True when precision, recall, and F1 are numeric.
    """
    for metric_name in REQUIRED_METRICS:
        value = observation.get(metric_name)
        if not isinstance(value, int | float):
            return False
    return True


def _row_has_unsafe_payload_flags(row: Mapping[str, Any]) -> bool:
    """Return whether redaction boolean flags show unsafe persisted payload.

    Args:
        row: Benchmark fixture row.

    Returns:
        True when a raw payload or local path flag is explicitly true.
    """
    for key in (
        "raw_ocr_text_stored",
        "raw_provider_payload_stored",
        "absolute_paths_stored",
        "local_path_literals_stored",
    ):
        if row.get(key) is True:
            return True
    return False


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSON object rows from a JSONL file.

    Args:
        path: JSONL path.

    Returns:
        JSON object rows.

    Raises:
        PaddleOCRTextTargetChainPreflightError: If rows are not JSON objects.
    """
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            if not isinstance(row, dict):
                raise PaddleOCRTextTargetChainPreflightError(
                    f"JSONL row {line_number} must be an object."
                )
            rows.append(row)
    return rows


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write a JSON payload.

    Args:
        path: Destination path.
        payload: Payload to write.
    """
    _reject_unsafe_payload(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _error_summary(*, error: Exception, manifest_name: str) -> dict[str, Any]:
    """Build a redacted error summary.

    Args:
        error: Raised exception.
        manifest_name: Input basename.

    Returns:
        Error summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": STATUS_ERROR,
        "benchmark_manifest_name": manifest_name,
        "ready_for_target_gate": False,
        "continue_training_loop": True,
        "error_type": error.__class__.__name__,
        "next_steps": ["fix_preflight_input_and_rerun"],
        "db_write_performed": False,
        "source_rows_read": False,
        "source_image_read_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


def _cli_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Build a compact CLI summary.

    Args:
        summary: Full preflight summary.

    Returns:
        Redacted CLI-safe fields.
    """
    return {
        "schema_version": summary.get("schema_version"),
        "status": summary.get("status"),
        "ready_for_target_gate": summary.get("ready_for_target_gate"),
        "row_count": summary.get("row_count"),
        "scoreable_fixture_count": summary.get("scoreable_fixture_count"),
        "next_steps": summary.get("next_steps"),
    }


def _reject_unsafe_payload(payload: Any) -> None:
    """Reject payloads containing raw keys, local paths, or secret-like values.

    Args:
        payload: Arbitrary JSON-like payload.

    Raises:
        PaddleOCRTextTargetChainPreflightError: If unsafe content appears.
    """
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            lowered_key = str(key).lower()
            if lowered_key in RAW_FORBIDDEN_KEYS:
                raise PaddleOCRTextTargetChainPreflightError(
                    f"Unsafe raw payload key detected: {key}"
                )
            _reject_unsafe_payload(value)
        return
    if isinstance(payload, list | tuple):
        for item in payload:
            _reject_unsafe_payload(item)
        return
    if isinstance(payload, str):
        lowered = payload.lower()
        if any(marker.lower() in payload for marker in LOCAL_PATH_MARKERS):
            raise PaddleOCRTextTargetChainPreflightError(
                "Local path marker detected in preflight payload."
            )
        if any(marker in lowered for marker in SECRET_LIKE_MARKERS):
            raise PaddleOCRTextTargetChainPreflightError(
                "Secret-like marker detected in preflight payload."
            )


def _safe_token(value: Any, *, field_name: str) -> str:
    """Return a required safe token.

    Args:
        value: Raw token value.
        field_name: Field name for error messages.

    Returns:
        Safe token.

    Raises:
        PaddleOCRTextTargetChainPreflightError: If token is invalid.
    """
    token = _safe_optional_token(value, field_name=field_name)
    if token is None:
        raise PaddleOCRTextTargetChainPreflightError(f"{field_name} is required.")
    return token


def _safe_optional_token(value: Any, *, field_name: str) -> str | None:
    """Return an optional safe token.

    Args:
        value: Raw token value.
        field_name: Field name for error messages.

    Returns:
        Safe token or None.

    Raises:
        PaddleOCRTextTargetChainPreflightError: If token is invalid.
    """
    if value is None:
        return None
    token = str(value).strip()
    if not SAFE_TOKEN_PATTERN.fullmatch(token):
        raise PaddleOCRTextTargetChainPreflightError(f"{field_name} is not a safe token.")
    return token


def _safe_output_token(value: str) -> str:
    """Return a bounded token for Markdown output.

    Args:
        value: Raw value.

    Returns:
        Safe token.
    """
    if SAFE_TOKEN_PATTERN.fullmatch(value):
        return value
    return "unsafe"


def _display_check_name(value: str) -> str:
    """Convert an internal check id to a readable safe token.

    Args:
        value: Check id.

    Returns:
        Display token.
    """
    return _safe_output_token(value.replace("_", "-"))


def _bool_text(value: Any) -> str:
    """Return a safe bool token.

    Args:
        value: Raw bool-like value.

    Returns:
        ``true`` or ``false``.
    """
    return "true" if value is True else "false"


def _nonnegative_int(value: Any, field_name: str) -> int:
    """Parse a nonnegative integer.

    Args:
        value: Raw value.
        field_name: Field name for errors.

    Returns:
        Parsed integer.

    Raises:
        PaddleOCRTextTargetChainPreflightError: If invalid.
    """
    if not isinstance(value, int) or value < 0:
        raise PaddleOCRTextTargetChainPreflightError(f"{field_name} must be nonnegative.")
    return value


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_cli())
