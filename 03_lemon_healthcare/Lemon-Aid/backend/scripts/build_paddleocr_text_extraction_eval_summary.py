"""Build PaddleOCR text extraction eval summaries for the 95 percent target gate.

This script consumes a redacted OCR benchmark manifest whose provider
observations already contain numeric text-extraction metrics. It does not read
OCR text, image bytes, provider payloads, source rows, database records, or
local source-image paths.

The output schema is accepted by ``gate_paddleocr_text_extraction_target.py``.
Missing per-observation text metrics are counted as zero contributions so the
target gate fails closed instead of treating absent evidence as success.

References:
    https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
    https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppocr/model_train/detection.html
    https://paddlepaddle.github.io/PaddleOCR/v2.10.0/en/ppocr/model_train/recognition.html
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "supplement-paddleocr-text-extraction-eval-summary-v1"
TARGET_PROVIDER = "paddleocr_local"
ALLOWED_EVAL_SPLITS = frozenset({"holdout", "test"})
HUMAN_REVIEWED_STATUSES = frozenset({"human_reviewed", "verified", "approved"})
REQUIRED_METRICS = (
    "normalized_text_precision",
    "normalized_text_recall",
    "normalized_text_f1",
)
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
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
SOURCE_DOC_URLS = (
    "https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html",
    "https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppocr/model_train/detection.html",
    "https://paddlepaddle.github.io/PaddleOCR/v2.10.0/en/ppocr/model_train/recognition.html",
)


class PaddleOCRTextEvalSummaryError(ValueError):
    """Raised when the text extraction eval summary cannot be trusted."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--provider", default=TARGET_PROVIDER)
    parser.add_argument("--eval-split", required=True, choices=sorted(ALLOWED_EVAL_SPLITS))
    parser.add_argument(
        "--leakage-check-passed",
        action="store_true",
        help="Required assertion that the benchmark split passed leakage validation.",
    )
    parser.add_argument(
        "--privacy-review-cleared",
        action="store_true",
        help="Required assertion that human GT rows were cleared for privacy-safe evaluation.",
    )
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None) -> int:
    """Run the summary builder and print redacted status.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        summary = build_paddleocr_text_extraction_eval_summary(
            benchmark_manifest=args.benchmark_manifest,
            provider=args.provider,
            eval_split=args.eval_split,
            leakage_check_passed=args.leakage_check_passed,
            privacy_review_cleared=args.privacy_review_cleared,
        )
    except (OSError, json.JSONDecodeError, InvalidOperation, PaddleOCRTextEvalSummaryError) as exc:
        summary = _error_summary(error=exc)
        _write_json(args.output, summary)
        print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
        return 1

    _write_json(args.output, summary)
    print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    return 0


def build_paddleocr_text_extraction_eval_summary(
    *,
    benchmark_manifest: Path,
    provider: str = TARGET_PROVIDER,
    eval_split: str,
    leakage_check_passed: bool,
    privacy_review_cleared: bool,
) -> dict[str, Any]:
    """Build a redacted text-extraction eval summary.

    Args:
        benchmark_manifest: OCR benchmark manifest with redacted observations.
        provider: Provider id to aggregate.
        eval_split: Evaluation split, usually ``holdout`` or ``test``.
        leakage_check_passed: Explicit split-level leakage validation result.
        privacy_review_cleared: Explicit operator assertion that the benchmark
            rows were privacy-reviewed before target-gate use.

    Returns:
        Summary accepted by ``gate_paddleocr_text_extraction_target.py``.

    Raises:
        PaddleOCRTextEvalSummaryError: If provider, split, or input rows are
            unsupported or unsafe.
    """
    provider = _safe_token(provider, field_name="provider")
    if eval_split not in ALLOWED_EVAL_SPLITS:
        raise PaddleOCRTextEvalSummaryError("eval_split must be holdout or test.")
    rows = _read_jsonl(benchmark_manifest)
    aggregate = _aggregate_rows(rows=rows, provider=provider, eval_split=eval_split)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "benchmark_manifest_name": benchmark_manifest.name,
        "provider": provider,
        "eval_split": eval_split,
        "fixture_count": aggregate["fixture_count"],
        "human_reviewed_fixture_count": aggregate["human_reviewed_fixture_count"],
        "observation_count": aggregate["observation_count"],
        "metric_complete_observation_count": aggregate["metric_complete_observation_count"],
        "metric_missing_observation_count": aggregate["metric_missing_observation_count"],
        "skip_reason_counts": aggregate["skip_reason_counts"],
        "metrics": aggregate["metrics"],
        "leakage_check_passed": leakage_check_passed and aggregate["row_leakage_checks_passed"],
        "privacy_review_cleared": privacy_review_cleared,
        "row_leakage_checks_passed": aggregate["row_leakage_checks_passed"],
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


def _aggregate_rows(
    *,
    rows: list[dict[str, Any]],
    provider: str,
    eval_split: str,
) -> dict[str, Any]:
    """Aggregate fixture rows into target-gate metrics.

    Args:
        rows: Benchmark manifest rows.
        provider: Target provider id.
        eval_split: Requested split.

    Returns:
        Aggregate summary fields.
    """
    skip_reasons: Counter[str] = Counter()
    metric_sums = {name: Decimal("0") for name in REQUIRED_METRICS}
    fixture_count = 0
    human_reviewed_fixture_count = 0
    observation_count = 0
    complete_count = 0
    missing_count = 0
    row_leakage_checks_passed = True

    for row in rows:
        _reject_unsafe_payload(row)
        row_split = row.get("eval_split") or row.get("split")
        if row_split is not None and row_split != eval_split:
            skip_reasons["split_mismatch"] += 1
            continue
        if row.get("leakage_check_passed") is False:
            row_leakage_checks_passed = False

        expected = row.get("expected")
        if not _expected_is_human_reviewed(expected):
            skip_reasons["expected_not_human_reviewed"] += 1
            continue
        observation = _provider_observation(row, provider)
        if observation is None:
            skip_reasons["missing_provider_observation"] += 1
            continue

        fixture_count += 1
        human_reviewed_fixture_count += 1
        observation_count += 1
        metrics = _observation_metrics(observation)
        if metrics is None:
            missing_count += 1
            continue
        complete_count += 1
        for metric_name, metric_value in metrics.items():
            metric_sums[metric_name] += metric_value

    denominator = Decimal(str(fixture_count)) if fixture_count else Decimal("1")
    return {
        "fixture_count": fixture_count,
        "human_reviewed_fixture_count": human_reviewed_fixture_count,
        "observation_count": observation_count,
        "metric_complete_observation_count": complete_count,
        "metric_missing_observation_count": missing_count,
        "row_leakage_checks_passed": row_leakage_checks_passed,
        "skip_reason_counts": dict(sorted(skip_reasons.items())),
        "metrics": {
            metric_name: _decimal_to_float(metric_sums[metric_name] / denominator)
            for metric_name in REQUIRED_METRICS
        },
    }


def _expected_is_human_reviewed(expected: Any) -> bool:
    """Return whether expected fields are human reviewed.

    Args:
        expected: Expected fixture payload.

    Returns:
        True when the expected data can be used as ground truth.
    """
    if not isinstance(expected, Mapping):
        return False
    status = expected.get("verification_status") or expected.get("ground_truth_status")
    return status in HUMAN_REVIEWED_STATUSES


def _provider_observation(row: Mapping[str, Any], provider: str) -> dict[str, Any] | None:
    """Return the first observation for a provider.

    Args:
        row: Benchmark fixture row.
        provider: Provider id.

    Returns:
        Observation row or ``None``.
    """
    observations = row.get("observations")
    if not isinstance(observations, list):
        return None
    for observation in observations:
        if not isinstance(observation, dict):
            continue
        _reject_unsafe_payload(observation)
        if observation.get("provider") == provider:
            return observation
    return None


def _observation_metrics(observation: Mapping[str, Any]) -> dict[str, Decimal] | None:
    """Return required metric values from one observation.

    Args:
        observation: Provider observation.

    Returns:
        Metric mapping, or ``None`` when any metric is missing.
    """
    metrics: dict[str, Decimal] = {}
    for metric_name in REQUIRED_METRICS:
        raw_value = observation.get(metric_name)
        if isinstance(raw_value, bool) or not isinstance(raw_value, int | float | str):
            return None
        value = Decimal(str(raw_value))
        _validate_metric_value(value)
        metrics[metric_name] = value
    return metrics


def _validate_metric_value(value: Decimal) -> None:
    """Validate a metric value in ``0..1``.

    Args:
        value: Metric value.

    Raises:
        PaddleOCRTextEvalSummaryError: If value is invalid.
    """
    if not value.is_finite() or value < 0 or value > 1:
        raise PaddleOCRTextEvalSummaryError("metric values must be decimals from 0 to 1.")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL object rows.

    Args:
        path: JSONL path.

    Returns:
        Parsed object rows.

    Raises:
        PaddleOCRTextEvalSummaryError: If a line is not an object.
    """
    if not path.is_file():
        raise PaddleOCRTextEvalSummaryError("benchmark manifest does not exist.")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parsed = json.loads(stripped)
        if not isinstance(parsed, dict):
            raise PaddleOCRTextEvalSummaryError(f"JSONL line {line_number} must be an object.")
        rows.append(parsed)
    return rows


def _safe_token(value: Any, *, field_name: str) -> str:
    """Return a safe token.

    Args:
        value: Candidate value.
        field_name: Field name for diagnostics.

    Returns:
        Safe token.

    Raises:
        PaddleOCRTextEvalSummaryError: If value is unsafe.
    """
    if not isinstance(value, str) or not value.strip():
        raise PaddleOCRTextEvalSummaryError(f"{field_name} must be a non-empty string.")
    token = value.strip()
    if not TOKEN_PATTERN.fullmatch(token):
        raise PaddleOCRTextEvalSummaryError(f"{field_name} must be a stable token.")
    return token


def _decimal_to_float(value: Decimal) -> float:
    """Return a rounded float from a Decimal metric.

    Args:
        value: Decimal value.

    Returns:
        Rounded float.
    """
    return float(value.quantize(Decimal("0.0001")))


def _cli_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Return a redacted CLI summary.

    Args:
        summary: Summary artifact.

    Returns:
        Safe stdout summary.
    """
    return {
        "schema_version": "paddleocr-text-extraction-eval-summary-cli-v1",
        "status": summary.get("status", "ok"),
        "provider": summary.get("provider", TARGET_PROVIDER),
        "eval_split": summary.get("eval_split"),
        "fixture_count": summary.get("fixture_count", 0),
        "metric_complete_observation_count": summary.get(
            "metric_complete_observation_count",
            0,
        ),
        "metric_values_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
    }


def _error_summary(*, error: Exception) -> dict[str, Any]:
    """Return a redacted error summary.

    Args:
        error: Exception that stopped summary generation.

    Returns:
        Redacted error artifact.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "error_type": type(error).__name__,
        "fixture_count": 0,
        "human_reviewed_fixture_count": 0,
        "observation_count": 0,
        "metric_complete_observation_count": 0,
        "metric_missing_observation_count": 0,
        "metrics": dict.fromkeys(REQUIRED_METRICS, 0.0),
        "leakage_check_passed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write a JSON object.

    Args:
        path: Destination path.
        payload: JSON payload.
    """
    _reject_unsafe_payload(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _reject_unsafe_payload(value: Any) -> None:
    """Reject raw OCR, provider payloads, local paths, and secrets.

    Args:
        value: JSON-like payload.

    Raises:
        ValueError: If unsafe content is found.
    """
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).lower()
            if key_text in RAW_FORBIDDEN_KEYS:
                raise ValueError(key_text)
            _reject_unsafe_payload(child)
        return
    if isinstance(value, list | tuple):
        for child in value:
            _reject_unsafe_payload(child)
        return
    if isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in SECRET_LIKE_MARKERS):
            raise ValueError("secret-like marker")
        if any(marker in value for marker in LOCAL_PATH_MARKERS):
            raise ValueError("local path literal")


if __name__ == "__main__":
    raise SystemExit(run_cli())
