"""Compare PaddleOCR fine-tune metrics against a baseline before promotion.

This pre-promotion gate consumes flat verified PaddleOCR metric JSON from
``run_paddleocr_eval_from_finetune_plan.py`` and a flat baseline metric JSON.
It requires explicit absolute minimum thresholds for every task-required metric
and derives promotion metric rules that can be passed to
``promote_model_candidate.py`` after the fine-tuned metrics are registered.

The script does not mutate DB state and does not print metric names, values,
raw OCR text, provider payloads, local paths, or model artifact refs.

References:
    https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppocr/model_train/detection.html
    https://paddlepaddle.github.io/PaddleOCR/v2.10.0/en/ppocr/model_train/recognition.html
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

SUMMARY_SCHEMA_VERSION = "paddleocr-baseline-comparison-summary-v1"
GATE_SCHEMA_VERSION = "paddleocr-baseline-comparison-gate-v1"
TASK_CHOICES = ("detection", "recognition")
REQUIRED_METRICS_BY_TASK = {
    "detection": ("precision", "recall", "hmean"),
    "recognition": ("acc", "norm_edit_dis"),
}
HIGHER_IS_BETTER_METRICS = frozenset({"precision", "recall", "hmean", "acc", "norm_edit_dis"})
METRIC_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
SECRET_LIKE_MARKERS = (
    "bearer ",
    "ngrok-free.dev",
    "sb_secret_",
    "service_role",
    "aws_secret_access_key",
    "-----begin",
    "raw_ocr_text",
    "provider_payload",
)
SOURCE_DOC_URLS = (
    "https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppocr/model_train/detection.html",
    "https://paddlepaddle.github.io/PaddleOCR/v2.10.0/en/ppocr/model_train/recognition.html",
)


class PaddleOCRBaselineGateError(ValueError):
    """Raised when baseline comparison cannot be trusted."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, choices=TASK_CHOICES)
    parser.add_argument("--finetuned-metrics", required=True, type=Path)
    parser.add_argument("--baseline-metrics", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--promotion-rules-output",
        type=Path,
        help="Optional JSON output containing promote_model_candidate metric rules.",
    )
    parser.add_argument(
        "--min-metric",
        action="append",
        default=[],
        nargs=2,
        metavar=("METRIC", "VALUE"),
        help="Absolute minimum required metric. Must cover every task-required metric.",
    )
    parser.add_argument(
        "--min-improvement",
        action="append",
        default=[],
        nargs=2,
        metavar=("METRIC", "DELTA"),
        help="Minimum improvement over baseline. Defaults to zero for omitted required metrics.",
    )
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None) -> int:
    """Run the baseline gate and print a redacted summary.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        gate, summary, promotion_rules = gate_paddleocr_finetune_against_baseline(
            task=args.task,
            finetuned_metrics_path=args.finetuned_metrics,
            baseline_metrics_path=args.baseline_metrics,
            min_metric_thresholds=_parse_metric_pairs(args.min_metric, "min-metric"),
            min_improvements=_parse_metric_pairs(args.min_improvement, "min-improvement"),
        )
    except (PaddleOCRBaselineGateError, InvalidOperation, ValueError) as exc:
        summary = _error_summary(error=exc)
        _write_json(args.output, summary)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 1

    _write_json(args.output, gate)
    if args.promotion_rules_output is not None:
        _write_json(args.promotion_rules_output, promotion_rules)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if gate["allowed"] is True else 1


def gate_paddleocr_finetune_against_baseline(
    *,
    task: str,
    finetuned_metrics_path: Path,
    baseline_metrics_path: Path,
    min_metric_thresholds: Mapping[str, Decimal],
    min_improvements: Mapping[str, Decimal],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Compare fine-tuned metrics with baseline and absolute thresholds.

    Args:
        task: PaddleOCR task.
        finetuned_metrics_path: Fine-tuned metric JSON path.
        baseline_metrics_path: Baseline metric JSON path.
        min_metric_thresholds: Absolute minimum thresholds for all required metrics.
        min_improvements: Optional minimum baseline deltas for required metrics.

    Returns:
        Gate artifact, redacted summary, and promotion metric rule artifact.

    Raises:
        PaddleOCRBaselineGateError: If metrics or thresholds are incomplete or unsafe.
    """
    if task not in TASK_CHOICES:
        raise PaddleOCRBaselineGateError("Unsupported PaddleOCR baseline gate task.")
    required_metrics = REQUIRED_METRICS_BY_TASK[task]
    finetuned_metrics = _load_metric_json(finetuned_metrics_path)
    baseline_metrics = _load_metric_json(baseline_metrics_path)
    _validate_required_metric_coverage(
        required_metrics=required_metrics,
        metrics=finetuned_metrics,
        label="fine-tuned metrics",
    )
    _validate_required_metric_coverage(
        required_metrics=required_metrics,
        metrics=baseline_metrics,
        label="baseline metrics",
    )
    _validate_threshold_coverage(
        required_metrics=required_metrics,
        thresholds=min_metric_thresholds,
    )

    rules = []
    allowed = True
    reason = "passed"
    for metric_name in required_metrics:
        _validate_supported_direction(metric_name)
        finetuned_value = finetuned_metrics[metric_name]
        baseline_value = baseline_metrics[metric_name]
        absolute_threshold = min_metric_thresholds[metric_name]
        improvement_threshold = min_improvements.get(metric_name, Decimal("0"))
        if improvement_threshold < 0:
            raise PaddleOCRBaselineGateError("Minimum improvements must be nonnegative.")
        derived_threshold = max(absolute_threshold, baseline_value + improvement_threshold)
        absolute_passed = finetuned_value >= absolute_threshold
        improvement_passed = finetuned_value >= baseline_value + improvement_threshold
        passed = absolute_passed and improvement_passed
        if not passed and reason == "passed":
            reason = "metric_gate_failed"
        allowed = allowed and passed
        rules.append(
            {
                "metric_name": metric_name,
                "direction": "higher_is_better",
                "baseline_value": _decimal_to_string(baseline_value),
                "finetuned_value": _decimal_to_string(finetuned_value),
                "absolute_threshold": _decimal_to_string(absolute_threshold),
                "improvement_threshold": _decimal_to_string(improvement_threshold),
                "derived_promotion_threshold": _decimal_to_string(derived_threshold),
                "absolute_passed": absolute_passed,
                "improvement_passed": improvement_passed,
                "passed": passed,
            }
        )

    gate = {
        "schema_version": GATE_SCHEMA_VERSION,
        "task": task,
        "allowed": allowed,
        "reason": reason,
        "required_metric_count": len(required_metrics),
        "rule_count": len(rules),
        "passed_rule_count": sum(1 for rule in rules if rule["passed"] is True),
        "rules": rules,
        "source_doc_urls": list(SOURCE_DOC_URLS),
        "metric_names_printed": False,
        "metric_values_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "source_path_printed": False,
        "artifact_ref_printed": False,
    }
    promotion_rules = {
        "schema_version": "paddleocr-promotion-metric-rules-v1",
        "task": task,
        "allowed_by_baseline_gate": allowed,
        "metric_rules": [
            {
                "metric_name": rule["metric_name"],
                "comparator": ">=",
                "threshold": rule["derived_promotion_threshold"],
            }
            for rule in rules
        ],
        "metric_values_printed_to_stdout": False,
        "artifact_ref_printed": False,
    }
    return gate, _success_summary(gate=gate), promotion_rules


def _load_metric_json(path: Path) -> dict[str, Decimal]:
    """Load and validate a flat metric JSON object.

    Args:
        path: Metric JSON path.

    Returns:
        Decimal metric mapping.

    Raises:
        PaddleOCRBaselineGateError: If the file is missing or malformed.
    """
    if not path.is_file():
        raise PaddleOCRBaselineGateError("Metric JSON does not exist.")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaddleOCRBaselineGateError("Metric JSON is malformed.") from exc
    if not isinstance(parsed, dict):
        raise PaddleOCRBaselineGateError("Metric JSON must be an object.")
    metrics: dict[str, Decimal] = {}
    for metric_name, raw_value in parsed.items():
        _validate_metric_name(metric_name)
        if isinstance(raw_value, bool) or not isinstance(raw_value, int | float | str):
            raise PaddleOCRBaselineGateError("Metric values must be numeric.")
        metric_value = Decimal(str(raw_value))
        _validate_nonnegative_finite_decimal(metric_value, "Metric values")
        metrics[metric_name] = metric_value
    return metrics


def _parse_metric_pairs(raw_pairs: list[list[str]], argument_name: str) -> dict[str, Decimal]:
    """Parse repeated CLI metric/decimal pairs.

    Args:
        raw_pairs: Repeated ``[name, value]`` arguments.
        argument_name: CLI argument name for error context.

    Returns:
        Metric decimal mapping.

    Raises:
        ValueError: If duplicate metrics are supplied.
        InvalidOperation: If a decimal is invalid.
        PaddleOCRBaselineGateError: If metric names or values are unsafe.
    """
    metrics: dict[str, Decimal] = {}
    for metric_name, raw_value in raw_pairs:
        _validate_metric_name(metric_name)
        if metric_name in metrics:
            raise ValueError(f"Duplicate {argument_name} metric names are not allowed.")
        value = Decimal(raw_value)
        _validate_nonnegative_finite_decimal(value, argument_name)
        metrics[metric_name] = value
    return metrics


def _validate_required_metric_coverage(
    *,
    required_metrics: tuple[str, ...],
    metrics: Mapping[str, Decimal],
    label: str,
) -> None:
    """Verify all required metrics are available.

    Args:
        required_metrics: Required task metric names.
        metrics: Metric mapping.
        label: Human-readable metric source label.

    Raises:
        PaddleOCRBaselineGateError: If a required metric is missing.
    """
    missing_count = sum(1 for metric_name in required_metrics if metric_name not in metrics)
    if missing_count:
        raise PaddleOCRBaselineGateError(f"{label} are missing required PaddleOCR metrics.")


def _validate_threshold_coverage(
    *,
    required_metrics: tuple[str, ...],
    thresholds: Mapping[str, Decimal],
) -> None:
    """Require explicit absolute thresholds for all task metrics.

    Args:
        required_metrics: Required task metric names.
        thresholds: Absolute threshold mapping.

    Raises:
        PaddleOCRBaselineGateError: If any threshold is missing.
    """
    missing_count = sum(1 for metric_name in required_metrics if metric_name not in thresholds)
    if missing_count:
        raise PaddleOCRBaselineGateError("Absolute minimum thresholds must cover all task metrics.")


def _validate_metric_name(metric_name: str) -> None:
    """Validate one stable metric name.

    Args:
        metric_name: Candidate metric key.

    Raises:
        PaddleOCRBaselineGateError: If the key is unsafe.
    """
    if not isinstance(metric_name, str) or not METRIC_NAME_PATTERN.fullmatch(metric_name):
        raise PaddleOCRBaselineGateError("Metric names must use stable safe characters.")
    folded = metric_name.casefold()
    if "://" in metric_name or metric_name.startswith("/") or ".." in metric_name:
        raise PaddleOCRBaselineGateError("Metric names must not be paths or URLs.")
    if any(marker in folded for marker in SECRET_LIKE_MARKERS):
        raise PaddleOCRBaselineGateError("Metric names contain unsafe data.")


def _validate_nonnegative_finite_decimal(value: Decimal, label: str) -> None:
    """Validate a nonnegative finite decimal.

    Args:
        value: Candidate value.
        label: Error label.

    Raises:
        PaddleOCRBaselineGateError: If the value is negative or non-finite.
    """
    if not math.isfinite(float(value)) or value < 0:
        raise PaddleOCRBaselineGateError(f"{label} must be finite and nonnegative.")


def _validate_supported_direction(metric_name: str) -> None:
    """Ensure the metric direction is known before comparing values.

    Args:
        metric_name: Metric name.

    Raises:
        PaddleOCRBaselineGateError: If direction is unknown.
    """
    if metric_name not in HIGHER_IS_BETTER_METRICS:
        raise PaddleOCRBaselineGateError("Unsupported PaddleOCR metric direction.")


def _decimal_to_string(value: Decimal) -> str:
    """Return a stable non-scientific decimal string.

    Args:
        value: Decimal value.

    Returns:
        Stable string.
    """
    normalized = value.normalize()
    return format(normalized, "f")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write a JSON object.

    Args:
        path: Destination path.
        payload: JSON payload.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _success_summary(*, gate: Mapping[str, Any]) -> dict[str, Any]:
    """Return a redacted operator summary.

    Args:
        gate: Gate artifact.

    Returns:
        Aggregate-only summary.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "ok",
        "task": gate["task"],
        "allowed": gate["allowed"],
        "reason": gate["reason"],
        "required_metric_count": gate["required_metric_count"],
        "rule_count": gate["rule_count"],
        "passed_rule_count": gate["passed_rule_count"],
        "promotion_rule_count": gate["rule_count"],
        "metric_names_printed": False,
        "metric_values_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "source_path_printed": False,
        "artifact_ref_printed": False,
    }


def _error_summary(*, error: BaseException) -> dict[str, Any]:
    """Return a redacted error summary.

    Args:
        error: Raised exception.

    Returns:
        Error summary without input values.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "error",
        "error_type": type(error).__name__,
        "allowed": False,
        "metric_names_printed": False,
        "metric_values_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "source_path_printed": False,
        "artifact_ref_printed": False,
    }


def main() -> None:
    """Run the CLI entrypoint."""
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
