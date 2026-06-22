"""Run PaddleOCR baseline evaluation and emit verified metric JSON.

This trusted-worker bridge evaluates an existing PaddleOCR baseline checkpoint
against the same dataset/config encoded in a ``paddleocr-finetune-run-plan-v1``
artifact. It does not require a fine-tune execution result because no training
is being evaluated. Raw stdout/stderr are never stored; only stream digests,
line counts, and task-required numeric metrics are retained.

References:
    https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppocr/model_train/detection.html
    https://paddlepaddle.github.io/PaddleOCR/v2.10.0/en/ppocr/model_train/recognition.html
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.run_paddleocr_eval_from_finetune_plan import (  # noqa: E402
    PLAN_SCHEMA_VERSION,
    SOURCE_DOC_URLS,
    TASK_CHOICES,
    _build_eval_command_tokens,
    _extract_metric_snapshot,
    _stream_summary,
    _validate_command_tokens,
    _validate_paddleocr_root,
    _validate_private_token_value,
    _validate_timeout_seconds,
    _write_json,
)

BASELINE_EVAL_RESULT_SCHEMA_VERSION = "paddleocr-baseline-eval-result-v1"
SUMMARY_SCHEMA_VERSION = "paddleocr-baseline-eval-summary-v1"
METRICS_SCHEMA_VERSION = "paddleocr-baseline-verified-metrics-v1"


class PaddleOCRBaselineEvalError(ValueError):
    """Raised when baseline evaluation cannot be run or trusted safely."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--baseline-checkpoint-ref", required=True)
    parser.add_argument("--paddleocr-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--metrics-output", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None) -> int:
    """Validate or execute baseline PaddleOCR eval and print a redacted summary.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        result, summary, metrics = run_paddleocr_baseline_eval(
            plan_path=args.plan,
            baseline_checkpoint_ref=args.baseline_checkpoint_ref,
            paddleocr_root=args.paddleocr_root,
            execute=args.execute,
            timeout_seconds=args.timeout_seconds,
            metrics_output_path=args.metrics_output,
        )
    except (PaddleOCRBaselineEvalError, ValueError) as exc:
        summary = _error_summary(error=exc)
        _write_json(args.output, summary)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 1

    _write_json(args.output, result)
    if metrics is not None and args.metrics_output is not None:
        _write_json(args.metrics_output, metrics)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def run_paddleocr_baseline_eval(
    *,
    plan_path: Path,
    baseline_checkpoint_ref: str,
    paddleocr_root: Path,
    execute: bool,
    timeout_seconds: int,
    metrics_output_path: Path | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, float] | None]:
    """Validate inputs and optionally run PaddleOCR baseline evaluation.

    Args:
        plan_path: Fine-tune run plan artifact that defines task/config/dataset.
        baseline_checkpoint_ref: Private relative checkpoint ref for baseline eval.
        paddleocr_root: Local PaddleOCR checkout containing ``tools/eval.py``.
        execute: Whether to execute evaluation.
        timeout_seconds: Subprocess timeout.
        metrics_output_path: Optional destination for flat verified metrics.

    Returns:
        Tuple of redacted baseline eval result, redacted summary, and optional metrics.

    Raises:
        PaddleOCRBaselineEvalError: If inputs or metrics are not trustworthy.
        ValueError: If timeout configuration is invalid.
    """
    timeout_seconds = _validate_timeout_seconds(timeout_seconds)
    plan = _load_plan(plan_path)
    plan_view = _validated_baseline_plan_view(
        plan=plan,
        baseline_checkpoint_ref=baseline_checkpoint_ref,
    )
    command_tokens = _build_eval_command_tokens(plan_view)
    _validate_command_tokens(command_tokens)
    _validate_paddleocr_root(paddleocr_root)

    if execute and metrics_output_path is None:
        raise PaddleOCRBaselineEvalError("metrics-output is required for executed baseline eval.")

    base_result = _base_result(
        execute=execute,
        timeout_seconds=timeout_seconds,
        task=plan_view["task"],
        command_tokens=command_tokens,
    )
    if not execute:
        result = {
            **base_result,
            "process_status": "validated_not_executed",
            "return_code": None,
            "elapsed_seconds": 0.0,
            "stdout_sha256": None,
            "stderr_sha256": None,
            "stdout_line_count": 0,
            "stderr_line_count": 0,
            "metric_key_count": 0,
            "metrics_output_written": False,
            "metrics_json_ready_for_comparison": False,
        }
        return result, _success_summary(result=result), None

    started = time.monotonic()
    try:
        completed = subprocess.run(
            command_tokens,
            cwd=paddleocr_root,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - started
        stdout_summary = _stream_summary(exc.stdout)
        stderr_summary = _stream_summary(exc.stderr)
        result = {
            **base_result,
            "process_status": "timeout",
            "return_code": None,
            "elapsed_seconds": round(elapsed, 3),
            "stdout_sha256": stdout_summary["sha256"],
            "stderr_sha256": stderr_summary["sha256"],
            "stdout_line_count": stdout_summary["line_count"],
            "stderr_line_count": stderr_summary["line_count"],
            "metric_key_count": 0,
            "metrics_output_written": False,
            "metrics_json_ready_for_comparison": False,
        }
        return result, _success_summary(result=result), None

    elapsed = time.monotonic() - started
    stdout_summary = _stream_summary(completed.stdout)
    stderr_summary = _stream_summary(completed.stderr)
    metrics = _extract_metric_snapshot(
        stdout=completed.stdout,
        stderr=completed.stderr,
        task=plan_view["task"],
    )
    if completed.returncode != 0:
        process_status = "failed"
        metrics = None
    elif metrics is None:
        process_status = "metrics_missing"
    else:
        process_status = "metrics_verified"

    result = {
        **base_result,
        "process_status": process_status,
        "return_code": completed.returncode,
        "elapsed_seconds": round(elapsed, 3),
        "stdout_sha256": stdout_summary["sha256"],
        "stderr_sha256": stderr_summary["sha256"],
        "stdout_line_count": stdout_summary["line_count"],
        "stderr_line_count": stderr_summary["line_count"],
        "metric_key_count": len(metrics or {}),
        "metrics_output_written": metrics is not None,
        "metrics_json_ready_for_comparison": metrics is not None,
    }
    return result, _success_summary(result=result), metrics


def _load_plan(path: Path) -> dict[str, Any]:
    """Load a fine-tune plan as baseline eval dataset/config metadata.

    Args:
        path: Plan artifact path.

    Returns:
        Parsed plan object.

    Raises:
        PaddleOCRBaselineEvalError: If the plan cannot be trusted.
    """
    if not path.is_file():
        raise PaddleOCRBaselineEvalError("Fine-tune plan does not exist.")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaddleOCRBaselineEvalError("Fine-tune plan JSON is malformed.") from exc
    if not isinstance(parsed, dict):
        raise PaddleOCRBaselineEvalError("Fine-tune plan must be an object.")
    if parsed.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise PaddleOCRBaselineEvalError("Unsupported PaddleOCR fine-tune plan schema.")
    if parsed.get("training_execution_performed") is not False:
        raise PaddleOCRBaselineEvalError("Fine-tune plan must be pre-execution metadata.")
    return parsed


def _validated_baseline_plan_view(
    *,
    plan: Mapping[str, Any],
    baseline_checkpoint_ref: str,
) -> dict[str, str]:
    """Extract safe task/config/checkpoint/gpu fields for baseline eval.

    Args:
        plan: Parsed fine-tune run plan.
        baseline_checkpoint_ref: Private relative checkpoint ref.

    Returns:
        Safe string view used to build command tokens.

    Raises:
        PaddleOCRBaselineEvalError: If metadata is missing or unsupported.
    """
    task = _string_field(plan, "task")
    if task not in TASK_CHOICES:
        raise PaddleOCRBaselineEvalError("Unsupported PaddleOCR baseline eval task.")
    paddleocr = plan.get("paddleocr")
    hyperparams = plan.get("hyperparams")
    if not isinstance(paddleocr, Mapping) or not isinstance(hyperparams, Mapping):
        raise PaddleOCRBaselineEvalError("Fine-tune plan metadata blocks are invalid.")
    config_ref = _string_field(paddleocr, "config_ref")
    gpus = _string_field(hyperparams, "gpus")
    if not isinstance(baseline_checkpoint_ref, str) or not baseline_checkpoint_ref.strip():
        raise PaddleOCRBaselineEvalError("Baseline checkpoint ref is required.")
    _validate_private_token_value(config_ref)
    _validate_private_token_value(gpus)
    _validate_private_token_value(baseline_checkpoint_ref)
    return {
        "task": task,
        "config_ref": config_ref,
        "checkpoint_ref": baseline_checkpoint_ref,
        "gpus": gpus,
    }


def _string_field(mapping: Mapping[str, Any], key: str) -> str:
    """Return a required non-empty string field.

    Args:
        mapping: Source mapping.
        key: Field name.

    Returns:
        Field value.

    Raises:
        PaddleOCRBaselineEvalError: If the field is missing.
    """
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PaddleOCRBaselineEvalError("Fine-tune plan is missing required metadata.")
    return value


def _base_result(
    *,
    execute: bool,
    timeout_seconds: int,
    task: str,
    command_tokens: Sequence[str],
) -> dict[str, Any]:
    """Build common redacted baseline eval result fields.

    Args:
        execute: Whether eval execution was requested.
        timeout_seconds: Validated timeout.
        task: PaddleOCR task.
        command_tokens: Validated command tokens.

    Returns:
        Common result payload.
    """
    return {
        "schema_version": BASELINE_EVAL_RESULT_SCHEMA_VERSION,
        "plan_schema_version": PLAN_SCHEMA_VERSION,
        "metrics_schema_version": METRICS_SCHEMA_VERSION,
        "task": task,
        "execution_requested": execute,
        "eval_execution_performed": execute,
        "timeout_seconds": timeout_seconds,
        "command_token_count": len(command_tokens),
        "tools_eval_checked": True,
        "baseline_checkpoint_checked": True,
        "source_doc_urls": list(SOURCE_DOC_URLS),
        "command_printed": False,
        "paddleocr_root_printed": False,
        "checkpoint_ref_printed": False,
        "stdout_raw_stored": False,
        "stderr_raw_stored": False,
        "metric_names_printed": False,
        "metric_values_printed": False,
        "source_path_printed": False,
        "label_text_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def _success_summary(*, result: Mapping[str, Any]) -> dict[str, Any]:
    """Return a redacted baseline eval summary.

    Args:
        result: Baseline eval result artifact.

    Returns:
        Aggregate-only operator summary.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "ok",
        "task": result["task"],
        "execution_requested": result["execution_requested"],
        "eval_execution_performed": result["eval_execution_performed"],
        "process_status": result["process_status"],
        "return_code": result["return_code"],
        "command_token_count": result["command_token_count"],
        "stdout_line_count": result["stdout_line_count"],
        "stderr_line_count": result["stderr_line_count"],
        "stdout_digest_stored": result["stdout_sha256"] is not None,
        "stderr_digest_stored": result["stderr_sha256"] is not None,
        "metric_key_count": result["metric_key_count"],
        "metrics_output_written": result["metrics_output_written"],
        "metrics_json_ready_for_comparison": result["metrics_json_ready_for_comparison"],
        "command_printed": False,
        "paddleocr_root_printed": False,
        "checkpoint_ref_printed": False,
        "stdout_raw_stored": False,
        "stderr_raw_stored": False,
        "metric_names_printed": False,
        "metric_values_printed": False,
        "source_path_printed": False,
        "label_text_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def _error_summary(*, error: BaseException) -> dict[str, Any]:
    """Return a redacted baseline eval error summary.

    Args:
        error: Raised exception.

    Returns:
        Error summary without input values.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "error",
        "error_type": type(error).__name__,
        "execution_requested": False,
        "eval_execution_performed": False,
        "command_printed": False,
        "paddleocr_root_printed": False,
        "checkpoint_ref_printed": False,
        "stdout_raw_stored": False,
        "stderr_raw_stored": False,
        "metric_names_printed": False,
        "metric_values_printed": False,
        "source_path_printed": False,
        "label_text_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def main() -> None:
    """Run the CLI entrypoint."""
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
