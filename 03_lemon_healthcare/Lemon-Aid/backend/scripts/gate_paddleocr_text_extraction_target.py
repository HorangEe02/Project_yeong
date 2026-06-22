"""Gate PaddleOCR text extraction against the held-out 95 percent target.

This script consumes a redacted benchmark evaluation summary for
``paddleocr_local``. It does not read images, OCR text, provider payloads,
database records, or source manifests. The gate is intended to answer one
operator question: can the PaddleOCR learning loop stop because held-out human
ground-truth extraction quality reached the project target?

References:
    https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
    https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppocr/model_train/detection.html
    https://paddlepaddle.github.io/PaddleOCR/v2.10.0/en/ppocr/model_train/recognition.html
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "paddleocr-text-extraction-target-gate-v1"
SUPPORTED_EVAL_SCHEMA_VERSIONS = frozenset(
    {
        "paddleocr-text-extraction-eval-summary-v1",
        "supplement-paddleocr-text-extraction-eval-summary-v1",
    }
)
TARGET_PROVIDER = "paddleocr_local"
ALLOWED_STOP_SPLITS = frozenset({"holdout", "test"})
REQUIRED_METRICS = (
    "normalized_text_precision",
    "normalized_text_recall",
    "normalized_text_f1",
)
DEFAULT_TARGET_THRESHOLD = Decimal("0.95")
DEFAULT_MIN_FIXTURE_COUNT = 30
STATUS_TARGET_REACHED = "target_reached"
STATUS_CONTINUE = "continue_training_loop"
STATUS_UNTRUSTED = "blocked_by_untrusted_eval"
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
LOCAL_PATH_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    "file://",
    "\\Users\\",
    "\\Volumes\\",
)
SOURCE_DOC_URLS = (
    "https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html",
    "https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppocr/model_train/detection.html",
    "https://paddlepaddle.github.io/PaddleOCR/v2.10.0/en/ppocr/model_train/recognition.html",
)


class PaddleOCRTextTargetGateError(ValueError):
    """Raised when the target gate input cannot be trusted."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--markdown-output", type=Path, default=None)
    parser.add_argument("--target-threshold", default=str(DEFAULT_TARGET_THRESHOLD))
    parser.add_argument("--min-fixtures", type=int, default=DEFAULT_MIN_FIXTURE_COUNT)
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None) -> int:
    """Run the PaddleOCR target gate and print redacted status.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code. ``0`` means target reached; ``1`` means blocked or
        training should continue.
    """
    args = parse_args(argv)
    try:
        gate = build_paddleocr_text_extraction_target_gate(
            eval_summary_path=args.eval_summary,
            target_threshold=Decimal(str(args.target_threshold)),
            min_fixture_count=args.min_fixtures,
        )
    except (InvalidOperation, PaddleOCRTextTargetGateError, ValueError) as exc:
        gate = _error_summary(error=exc)
        _write_json(args.output, gate)
        print(json.dumps(_cli_summary(gate), ensure_ascii=False, sort_keys=True))
        return 1

    _write_json(args.output, gate)
    if args.markdown_output is not None:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(build_markdown(gate), encoding="utf-8")
    print(json.dumps(_cli_summary(gate), ensure_ascii=False, sort_keys=True))
    return 0 if gate["paddleocr_target_reached"] is True else 1


def build_paddleocr_text_extraction_target_gate(
    *,
    eval_summary_path: Path,
    target_threshold: Decimal = DEFAULT_TARGET_THRESHOLD,
    min_fixture_count: int = DEFAULT_MIN_FIXTURE_COUNT,
) -> dict[str, Any]:
    """Build the final PaddleOCR 95 percent stop gate.

    Args:
        eval_summary_path: Redacted PaddleOCR benchmark evaluation summary.
        target_threshold: Required threshold for precision, recall, and F1.
        min_fixture_count: Minimum held-out human-reviewed fixture count.

    Returns:
        Redacted target gate artifact.

    Raises:
        PaddleOCRTextTargetGateError: If the evaluation summary is unsafe or
            structurally unsupported.
        ValueError: If threshold arguments are invalid.
    """
    _validate_threshold(target_threshold)
    if min_fixture_count <= 0:
        raise ValueError("min_fixture_count must be positive.")
    summary = _load_eval_summary(eval_summary_path)
    metrics = _extract_metrics(summary)
    fixture_count = _nonnegative_int(summary.get("fixture_count"), "fixture_count")
    human_reviewed_fixture_count = _nonnegative_int(
        summary.get("human_reviewed_fixture_count"),
        "human_reviewed_fixture_count",
    )
    eval_split = _safe_optional_token(
        summary.get("eval_split") or summary.get("split"),
        field_name="eval_split",
    )
    provider = _safe_optional_token(
        summary.get("provider") or summary.get("target_provider"),
        field_name="provider",
    )

    trust_checks = {
        "schema_supported": summary.get("schema_version") in SUPPORTED_EVAL_SCHEMA_VERSIONS,
        "provider_is_paddleocr": provider == TARGET_PROVIDER,
        "eval_split_is_heldout": eval_split in ALLOWED_STOP_SPLITS,
        "minimum_fixture_count_met": fixture_count >= min_fixture_count,
        "all_fixtures_human_reviewed": human_reviewed_fixture_count == fixture_count,
        "leakage_check_passed": summary.get("leakage_check_passed") is True,
        "privacy_review_cleared": summary.get("privacy_review_cleared") is True,
        "raw_ocr_text_absent": summary.get("raw_ocr_text_stored") is False,
        "raw_provider_payload_absent": summary.get("raw_provider_payload_stored") is False,
        "absolute_paths_absent": summary.get("absolute_paths_stored") is False,
    }
    metric_checks = {
        metric_name: metrics[metric_name] >= target_threshold for metric_name in REQUIRED_METRICS
    }
    trusted = all(trust_checks.values())
    metric_target_reached = all(metric_checks.values())
    target_reached = trusted and metric_target_reached
    if not trusted:
        status = STATUS_UNTRUSTED
    elif target_reached:
        status = STATUS_TARGET_REACHED
    else:
        status = STATUS_CONTINUE

    gate = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "eval_summary_name": eval_summary_path.name,
        "provider": provider,
        "eval_split": eval_split,
        "target_threshold": _decimal_to_string(target_threshold),
        "min_fixture_count": min_fixture_count,
        "fixture_count": fixture_count,
        "human_reviewed_fixture_count": human_reviewed_fixture_count,
        "trust_checks": trust_checks,
        "metric_checks": metric_checks,
        "metrics": {
            metric_name: _decimal_to_string(metrics[metric_name])
            for metric_name in REQUIRED_METRICS
        },
        "human_ground_truth_compared": trust_checks["all_fixtures_human_reviewed"],
        "privacy_review_cleared": trust_checks["privacy_review_cleared"],
        "text_extraction_accuracy_meets_95_percent": metric_target_reached,
        "minimum_required_accuracy": _decimal_to_string(target_threshold),
        "training_loop_stop_allowed": target_reached,
        "paddleocr_target_reached": target_reached,
        "continue_training_loop": not target_reached,
        "next_steps": _next_steps(status),
        "db_write_performed": False,
        "source_rows_read": False,
        "source_image_read_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "metric_names_printed": False,
        "metric_values_printed": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    _reject_unsafe_payload(gate)
    return gate


def build_markdown(gate: Mapping[str, Any]) -> str:
    """Build a redacted Markdown report.

    Args:
        gate: Target gate artifact.

    Returns:
        Markdown report text.
    """
    _reject_unsafe_payload(gate)
    next_steps = "\n".join(f"- `{_safe_output_token(str(step))}`" for step in gate["next_steps"])
    checks = gate.get("trust_checks")
    metric_checks = gate.get("metric_checks")
    if not isinstance(checks, Mapping) or not isinstance(metric_checks, Mapping):
        raise PaddleOCRTextTargetGateError("Gate checks are malformed.")
    trust_lines = "\n".join(
        f"- `{_safe_output_token(_display_check_name(str(name)))}`: `{_bool_text(value)}`"
        for name, value in sorted(checks.items())
    )
    metric_lines = "\n".join(
        f"- `{_safe_output_token(str(name))}`: `{_bool_text(value)}`"
        for name, value in sorted(metric_checks.items())
    )
    markdown = "\n".join(
        [
            "# PaddleOCR Text Extraction Target Gate",
            "",
            f"Schema: `{SCHEMA_VERSION}`",
            "",
            "이 문서는 PaddleOCR이 held-out human GT 기준 95% 텍스트 추출 목표에 도달했는지 판단합니다. OCR 원문, provider payload, 이미지 경로, source row는 포함하지 않습니다.",
            "",
            f"- Status: `{_safe_output_token(str(gate.get('status') or 'unknown'))}`",
            f"- Target reached: `{_bool_text(gate.get('paddleocr_target_reached'))}`",
            f"- Continue training loop: `{_bool_text(gate.get('continue_training_loop'))}`",
            f"- Fixture count: `{_nonnegative_int(gate.get('fixture_count'), 'fixture_count')}`",
            "",
            "## Trust Checks",
            "",
            trust_lines,
            "",
            "## Metric Checks",
            "",
            metric_lines,
            "",
            "## Next Steps",
            "",
            next_steps,
            "",
            "## Rule",
            "",
            "학습 루프 종료는 held-out/test human-reviewed fixture에서 leakage check가 통과하고 normalized text precision, recall, F1이 모두 target threshold 이상일 때만 허용합니다.",
            "",
        ]
    )
    _reject_unsafe_payload(markdown)
    return markdown


def _load_eval_summary(path: Path) -> dict[str, Any]:
    """Load and validate a redacted eval summary.

    Args:
        path: Evaluation summary path.

    Returns:
        Parsed summary object.

    Raises:
        PaddleOCRTextTargetGateError: If the summary is missing or unsafe.
    """
    if not path.is_file():
        raise PaddleOCRTextTargetGateError("Evaluation summary does not exist.")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaddleOCRTextTargetGateError("Evaluation summary JSON is malformed.") from exc
    if not isinstance(parsed, dict):
        raise PaddleOCRTextTargetGateError("Evaluation summary must be an object.")
    _reject_unsafe_payload(parsed)
    if parsed.get("schema_version") not in SUPPORTED_EVAL_SCHEMA_VERSIONS:
        raise PaddleOCRTextTargetGateError("Unsupported evaluation summary schema.")
    return parsed


def _extract_metrics(summary: Mapping[str, Any]) -> dict[str, Decimal]:
    """Extract required text extraction metrics.

    Args:
        summary: Evaluation summary.

    Returns:
        Decimal metric mapping.

    Raises:
        PaddleOCRTextTargetGateError: If metrics are missing or invalid.
    """
    raw_metrics = summary.get("metrics")
    if not isinstance(raw_metrics, Mapping):
        raise PaddleOCRTextTargetGateError("Evaluation summary requires metrics object.")
    metrics: dict[str, Decimal] = {}
    for metric_name in REQUIRED_METRICS:
        _validate_metric_name(metric_name)
        raw_value = raw_metrics.get(metric_name)
        if isinstance(raw_value, bool) or not isinstance(raw_value, int | float | str):
            raise PaddleOCRTextTargetGateError("Required text extraction metric is missing.")
        metric_value = Decimal(str(raw_value))
        _validate_metric_value(metric_value)
        metrics[metric_name] = metric_value
    return metrics


def _validate_threshold(value: Decimal) -> None:
    """Validate target threshold.

    Args:
        value: Decimal threshold.

    Raises:
        ValueError: If the threshold is outside ``0..1``.
    """
    _validate_metric_value(value)


def _validate_metric_value(value: Decimal) -> None:
    """Validate a finite metric value in ``0..1``.

    Args:
        value: Candidate metric.

    Raises:
        ValueError: If value is invalid.
    """
    if not value.is_finite() or value < 0 or value > 1:
        raise ValueError("metric values must be finite decimals from 0 to 1.")


def _validate_metric_name(metric_name: str) -> None:
    """Validate a metric key.

    Args:
        metric_name: Candidate metric name.

    Raises:
        PaddleOCRTextTargetGateError: If the name is unsafe.
    """
    if not METRIC_NAME_PATTERN.fullmatch(metric_name):
        raise PaddleOCRTextTargetGateError("Metric names must be stable safe tokens.")


def _nonnegative_int(value: Any, field_name: str) -> int:
    """Return a nonnegative integer.

    Args:
        value: Candidate value.
        field_name: Field name used only for error context.

    Returns:
        Nonnegative integer.

    Raises:
        PaddleOCRTextTargetGateError: If the value is invalid.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PaddleOCRTextTargetGateError(f"{field_name} must be a nonnegative integer.")
    return value


def _safe_optional_token(value: Any, *, field_name: str) -> str | None:
    """Return a safe optional token.

    Args:
        value: Candidate value.
        field_name: Field name used only for error context.

    Returns:
        Safe token or ``None``.

    Raises:
        PaddleOCRTextTargetGateError: If the value is unsafe.
    """
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise PaddleOCRTextTargetGateError(f"{field_name} must be a non-empty string.")
    token = value.strip()
    if not METRIC_NAME_PATTERN.fullmatch(token):
        raise PaddleOCRTextTargetGateError(f"{field_name} must be a stable safe token.")
    return token


def _safe_output_token(value: str) -> str:
    """Return a safe token for Markdown output.

    Args:
        value: Candidate token.

    Returns:
        Safe output token.
    """
    if METRIC_NAME_PATTERN.fullmatch(value):
        return value
    return "redacted"


def _display_check_name(value: str) -> str:
    """Return a safe display name for a gate check.

    Args:
        value: Internal check name.

    Returns:
        Display-safe check name.
    """
    replacements = {
        "raw_ocr_text_absent": "ocr_text_absent",
        "raw_provider_payload_absent": "provider_response_absent",
    }
    return replacements.get(value, value)


def _decimal_to_string(value: Decimal) -> str:
    """Return a compact decimal string.

    Args:
        value: Decimal value.

    Returns:
        String without trailing zeros.
    """
    return format(value.normalize(), "f").rstrip("0").rstrip(".") or "0"


def _bool_text(value: Any) -> str:
    """Return a stable boolean string.

    Args:
        value: Candidate value.

    Returns:
        ``true`` or ``false``.
    """
    return "true" if value is True else "false"


def _next_steps(status: str) -> list[str]:
    """Return next-step tokens for a gate status.

    Args:
        status: Gate status.

    Returns:
        Ordered next-step tokens.
    """
    if status == STATUS_TARGET_REACHED:
        return [
            "freeze_paddleocr_candidate_as_target_met",
            "write_operator_summary_without_raw_ocr",
            "prepare_reviewed_model_promotion_package",
        ]
    if status == STATUS_UNTRUSTED:
        return [
            "rerun_eval_on_human_reviewed_holdout_or_test_split",
            "verify_leakage_check_and_fixture_counts",
            "rerun_paddleocr_text_extraction_target_gate",
        ]
    return [
        "continue_paddleocr_error_mining",
        "create_or_extend_detection_recognition_annotation_tasks",
        "rerun_finetune_and_heldout_eval_before_target_gate",
    ]


def _cli_summary(gate: Mapping[str, Any]) -> dict[str, Any]:
    """Return a redacted CLI summary.

    Args:
        gate: Gate artifact.

    Returns:
        Summary safe for stdout.
    """
    return {
        "schema_version": "paddleocr-text-extraction-target-gate-cli-summary-v1",
        "status": gate.get("status", "error"),
        "paddleocr_target_reached": gate.get("paddleocr_target_reached") is True,
        "continue_training_loop": gate.get("continue_training_loop") is not False,
        "fixture_count": gate.get("fixture_count", 0),
        "metric_names_printed": False,
        "metric_values_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
    }


def _error_summary(*, error: Exception) -> dict[str, Any]:
    """Return a redacted error artifact.

    Args:
        error: Exception that stopped the gate.

    Returns:
        Redacted error summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "error_type": type(error).__name__,
        "paddleocr_target_reached": False,
        "continue_training_loop": True,
        "db_write_performed": False,
        "source_rows_read": False,
        "source_image_read_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "metric_names_printed": False,
        "metric_values_printed": False,
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
            if key_text in {"raw_ocr_text", "provider_payload", "raw_provider_payload"}:
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
