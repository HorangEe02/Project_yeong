"""Run PaddleOCR evaluation and emit verified metric JSON.

This trusted-worker bridge consumes ``paddleocr-finetune-run-plan-v1`` and a
successful ``paddleocr-finetune-execution-result-v1`` before optionally running
the official-style PaddleOCR ``tools/eval.py`` command. It parses only numeric
metric dictionaries from the captured logs, stores raw stdout/stderr as digests
and line counts, and writes a flat metric JSON object suitable for
``register_paddleocr_finetune_run_from_plan.py --metrics-json``.

References:
    https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppocr/model_train/detection.html
    https://paddlepaddle.github.io/PaddleOCR/v2.10.0/en/ppocr/model_train/recognition.html
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import re
import subprocess
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

PLAN_SCHEMA_VERSION = "paddleocr-finetune-run-plan-v1"
TRAIN_EXECUTION_SCHEMA_VERSION = "paddleocr-finetune-execution-result-v1"
EVAL_RESULT_SCHEMA_VERSION = "paddleocr-finetune-eval-result-v1"
SUMMARY_SCHEMA_VERSION = "paddleocr-finetune-eval-summary-v1"
METRICS_SCHEMA_VERSION = "paddleocr-finetune-verified-metrics-v1"
EVAL_ENTRYPOINT = Path("tools") / "eval.py"
DEFAULT_TIMEOUT_SECONDS = 3600
MAX_TIMEOUT_SECONDS = 86400
TASK_CHOICES = ("detection", "recognition")
REQUIRED_METRICS_BY_TASK = {
    "detection": ("precision", "recall", "hmean"),
    "recognition": ("acc", "norm_edit_dis"),
}
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
SHELL_META_MARKERS = ("|", ";", "&&", "||", "$(", "`", ">", "<")
METRIC_DICT_PATTERN = re.compile(r"\{[^{}]{1,4000}\}")
SOURCE_DOC_URLS = (
    "https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppocr/model_train/detection.html",
    "https://paddlepaddle.github.io/PaddleOCR/v2.10.0/en/ppocr/model_train/recognition.html",
)


class PaddleOCREvalExecutionError(ValueError):
    """Raised when PaddleOCR evaluation cannot be run or trusted safely."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--finetune-execution", type=Path)
    parser.add_argument("--paddleocr-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--metrics-output", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None) -> int:
    """Validate or execute PaddleOCR eval and print a redacted summary.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        result, summary, metrics = run_paddleocr_eval_from_finetune_plan(
            plan_path=args.plan,
            finetune_execution_path=args.finetune_execution,
            paddleocr_root=args.paddleocr_root,
            execute=args.execute,
            timeout_seconds=args.timeout_seconds,
            metrics_output_path=args.metrics_output,
        )
    except (PaddleOCREvalExecutionError, ValueError) as exc:
        summary = _error_summary(error=exc)
        _write_json(args.output, summary)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 1

    _write_json(args.output, result)
    if metrics is not None and args.metrics_output is not None:
        _write_json(args.metrics_output, metrics)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def run_paddleocr_eval_from_finetune_plan(
    *,
    plan_path: Path,
    finetune_execution_path: Path | None,
    paddleocr_root: Path,
    execute: bool,
    timeout_seconds: int,
    metrics_output_path: Path | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, float] | None]:
    """Validate inputs and optionally run PaddleOCR evaluation.

    Args:
        plan_path: Fine-tune run plan artifact.
        finetune_execution_path: Training execution result artifact.
        paddleocr_root: Local PaddleOCR checkout containing ``tools/eval.py``.
        execute: Whether to execute evaluation.
        timeout_seconds: Subprocess timeout.
        metrics_output_path: Optional destination for flat verified metrics.

    Returns:
        Tuple of redacted eval result, redacted summary, and optional metric JSON.

    Raises:
        PaddleOCREvalExecutionError: If plan, execution, root, command, or metrics are invalid.
        ValueError: If timeout configuration is invalid.
    """
    timeout_seconds = _validate_timeout_seconds(timeout_seconds)
    plan = _load_plan(plan_path)
    plan_view = _validated_plan_view(plan)
    command_tokens = _build_eval_command_tokens(plan_view)
    _validate_command_tokens(command_tokens)
    _validate_paddleocr_root(paddleocr_root)

    if finetune_execution_path is not None:
        _validate_finetune_execution_result(finetune_execution_path)
    if execute and finetune_execution_path is None:
        raise PaddleOCREvalExecutionError("Successful fine-tune execution result is required.")
    if execute and metrics_output_path is None:
        raise PaddleOCREvalExecutionError("metrics-output is required for executed eval.")

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
            "metrics_json_ready_for_registration": False,
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
            "metrics_json_ready_for_registration": False,
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
        "metrics_json_ready_for_registration": metrics is not None,
    }
    return result, _success_summary(result=result), metrics


def _load_plan(path: Path) -> dict[str, Any]:
    """Load and validate a plan artifact schema.

    Args:
        path: Plan artifact path.

    Returns:
        Parsed plan object.

    Raises:
        PaddleOCREvalExecutionError: If the plan cannot be trusted.
    """
    if not path.is_file():
        raise PaddleOCREvalExecutionError("Fine-tune plan does not exist.")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaddleOCREvalExecutionError("Fine-tune plan JSON is malformed.") from exc
    if not isinstance(parsed, dict):
        raise PaddleOCREvalExecutionError("Fine-tune plan must be an object.")
    if parsed.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise PaddleOCREvalExecutionError("Unsupported PaddleOCR fine-tune plan schema.")
    if parsed.get("training_execution_performed") is not False:
        raise PaddleOCREvalExecutionError("Fine-tune plan must be pre-execution metadata.")
    return parsed


def _validated_plan_view(plan: Mapping[str, Any]) -> dict[str, str]:
    """Extract the fields needed to build an official-style eval command.

    Args:
        plan: Parsed fine-tune plan.

    Returns:
        Safe string view of task/config/checkpoint/gpu settings.

    Raises:
        PaddleOCREvalExecutionError: If required metadata is invalid.
    """
    task = _string_field(plan, "task")
    if task not in TASK_CHOICES:
        raise PaddleOCREvalExecutionError("Unsupported PaddleOCR eval task.")
    paddleocr = plan.get("paddleocr")
    hyperparams = plan.get("hyperparams")
    if not isinstance(paddleocr, Mapping) or not isinstance(hyperparams, Mapping):
        raise PaddleOCREvalExecutionError("Fine-tune plan metadata blocks are invalid.")
    config_ref = _string_field(paddleocr, "config_ref")
    save_model_ref = _string_field(paddleocr, "save_model_ref")
    gpus = _string_field(hyperparams, "gpus")
    _validate_private_token_value(config_ref)
    _validate_private_token_value(save_model_ref)
    _validate_private_token_value(gpus)
    return {
        "task": task,
        "config_ref": config_ref,
        "checkpoint_ref": f"{save_model_ref}/best_accuracy",
        "gpus": gpus,
    }


def _validate_finetune_execution_result(path: Path) -> None:
    """Validate that training completed before evaluation.

    Args:
        path: Fine-tune execution result artifact path.

    Raises:
        PaddleOCREvalExecutionError: If the execution result is missing or not successful.
    """
    if not path.is_file():
        raise PaddleOCREvalExecutionError("Fine-tune execution result does not exist.")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaddleOCREvalExecutionError("Fine-tune execution result JSON is malformed.") from exc
    if not isinstance(parsed, dict):
        raise PaddleOCREvalExecutionError("Fine-tune execution result must be an object.")
    if parsed.get("schema_version") != TRAIN_EXECUTION_SCHEMA_VERSION:
        raise PaddleOCREvalExecutionError("Unsupported fine-tune execution result schema.")
    if parsed.get("process_status") != "succeeded":
        raise PaddleOCREvalExecutionError("Fine-tune execution must succeed before eval.")
    if parsed.get("metrics_json_required_for_registration") is not True:
        raise PaddleOCREvalExecutionError("Fine-tune execution is not ready for eval metrics.")
    if parsed.get("stdout_raw_stored") is not False or parsed.get("stderr_raw_stored") is not False:
        raise PaddleOCREvalExecutionError("Fine-tune execution result contains raw logs.")


def _build_eval_command_tokens(plan_view: Mapping[str, str]) -> list[str]:
    """Build official-style PaddleOCR eval command tokens.

    Args:
        plan_view: Validated task/config/checkpoint/gpu view.

    Returns:
        Command tokens for ``subprocess.run``.
    """
    common_tail = [
        EVAL_ENTRYPOINT.as_posix(),
        "-c",
        plan_view["config_ref"],
        "-o",
        f"Global.checkpoints={plan_view['checkpoint_ref']}",
    ]
    if plan_view["task"] == "recognition":
        return [
            "python3",
            "-m",
            "paddle.distributed.launch",
            "--gpus",
            plan_view["gpus"],
            *common_tail,
        ]
    return [
        "python3",
        *common_tail,
        "PostProcess.box_thresh=0.6",
        "PostProcess.unclip_ratio=1.5",
    ]


def _validate_command_tokens(tokens: Sequence[str]) -> None:
    """Validate command tokens before subprocess execution.

    Args:
        tokens: Candidate command tokens.

    Raises:
        PaddleOCREvalExecutionError: If any token is unsafe.
    """
    if EVAL_ENTRYPOINT.as_posix() not in tokens:
        raise PaddleOCREvalExecutionError("Eval command must include tools/eval.py.")
    for token in tokens:
        if not isinstance(token, str) or not token.strip():
            raise PaddleOCREvalExecutionError("Eval command token is invalid.")
        if any(control in token for control in ("\x00", "\n", "\r")):
            raise PaddleOCREvalExecutionError("Eval command token has control characters.")
        folded = token.casefold()
        if any(marker in folded for marker in SECRET_LIKE_MARKERS):
            raise PaddleOCREvalExecutionError("Eval command token contains unsafe data.")
        if any(marker in token for marker in SHELL_META_MARKERS):
            raise PaddleOCREvalExecutionError("Eval command token contains shell syntax.")
        _validate_private_token_value(token)
        if "=" in token:
            _validate_private_token_value(token.split("=", maxsplit=1)[1])


def _validate_private_token_value(value: str) -> None:
    """Reject URL, absolute path, traversal, and empty command values.

    Args:
        value: Token text or key-value override value.

    Raises:
        PaddleOCREvalExecutionError: If the value is unsafe.
    """
    if not value:
        raise PaddleOCREvalExecutionError("Eval command token has an empty value.")
    value_path = Path(value)
    if value_path.is_absolute() or ".." in value_path.parts or "://" in value:
        raise PaddleOCREvalExecutionError("Eval command tokens must use private refs.")


def _validate_paddleocr_root(root: Path) -> None:
    """Verify a local PaddleOCR checkout has the eval entrypoint.

    Args:
        root: Local PaddleOCR root.

    Raises:
        PaddleOCREvalExecutionError: If the checkout is not usable.
    """
    if not root.is_dir():
        raise PaddleOCREvalExecutionError("PaddleOCR root does not exist.")
    if not (root / EVAL_ENTRYPOINT).is_file():
        raise PaddleOCREvalExecutionError("PaddleOCR eval entrypoint is missing.")


def _extract_metric_snapshot(
    *,
    stdout: str | None,
    stderr: str | None,
    task: str,
) -> dict[str, float] | None:
    """Extract the last complete numeric PaddleOCR metric dict.

    Args:
        stdout: Captured stdout.
        stderr: Captured stderr.
        task: PaddleOCR task.

    Returns:
        Flat numeric metrics if all required task metrics are present, otherwise ``None``.
    """
    stream = "\n".join(value for value in (stdout, stderr) if value)
    required_keys = REQUIRED_METRICS_BY_TASK[task]
    for candidate in reversed(METRIC_DICT_PATTERN.findall(stream)):
        metrics = _parse_numeric_metric_dict(candidate)
        if metrics is None:
            continue
        if all(key in metrics for key in required_keys):
            return {key: metrics[key] for key in required_keys}
    return None


def _parse_numeric_metric_dict(candidate: str) -> dict[str, float] | None:
    """Parse and sanitize a metric dictionary candidate.

    Args:
        candidate: Text containing a Python/JSON-like metric dict.

    Returns:
        Numeric metric mapping, or ``None`` if parsing fails.
    """
    try:
        parsed = ast.literal_eval(candidate)
    except (SyntaxError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    metrics: dict[str, float] = {}
    for raw_key, raw_value in parsed.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            return None
        _validate_private_metric_key(raw_key)
        if isinstance(raw_value, bool) or not isinstance(raw_value, int | float):
            continue
        value = float(raw_value)
        if not math.isfinite(value) or value < 0:
            return None
        metrics[raw_key] = value
    return metrics


def _validate_private_metric_key(key: str) -> None:
    """Reject metric keys that look like paths, URLs, or secrets.

    Args:
        key: Metric key.

    Raises:
        PaddleOCREvalExecutionError: If the key is unsafe.
    """
    folded = key.casefold()
    if "://" in key or key.startswith("/") or ".." in key:
        raise PaddleOCREvalExecutionError("Metric keys must be private metric names.")
    if any(marker in folded for marker in SECRET_LIKE_MARKERS):
        raise PaddleOCREvalExecutionError("Metric key contains unsafe data.")


def _string_field(mapping: Mapping[str, Any], key: str) -> str:
    """Return a required non-empty string field.

    Args:
        mapping: Source mapping.
        key: Field name.

    Returns:
        Field value.

    Raises:
        PaddleOCREvalExecutionError: If the field is missing.
    """
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PaddleOCREvalExecutionError("Fine-tune plan is missing required metadata.")
    return value


def _validate_timeout_seconds(timeout_seconds: int) -> int:
    """Validate bounded subprocess timeout.

    Args:
        timeout_seconds: Candidate timeout.

    Returns:
        Validated timeout.

    Raises:
        ValueError: If timeout is out of bounds.
    """
    if timeout_seconds <= 0 or timeout_seconds > MAX_TIMEOUT_SECONDS:
        raise ValueError("timeout-seconds must be in 1..86400.")
    return timeout_seconds


def _base_result(
    *,
    execute: bool,
    timeout_seconds: int,
    task: str,
    command_tokens: Sequence[str],
) -> dict[str, Any]:
    """Build common redacted eval result fields.

    Args:
        execute: Whether eval execution was requested.
        timeout_seconds: Validated timeout.
        task: PaddleOCR task.
        command_tokens: Validated command tokens.

    Returns:
        Common eval result payload.
    """
    return {
        "schema_version": EVAL_RESULT_SCHEMA_VERSION,
        "plan_schema_version": PLAN_SCHEMA_VERSION,
        "finetune_execution_schema_version": TRAIN_EXECUTION_SCHEMA_VERSION,
        "metrics_schema_version": METRICS_SCHEMA_VERSION,
        "task": task,
        "execution_requested": execute,
        "eval_execution_performed": execute,
        "timeout_seconds": timeout_seconds,
        "command_token_count": len(command_tokens),
        "tools_eval_checked": True,
        "source_doc_urls": list(SOURCE_DOC_URLS),
        "command_printed": False,
        "paddleocr_root_printed": False,
        "stdout_raw_stored": False,
        "stderr_raw_stored": False,
        "metric_names_printed": False,
        "metric_values_printed": False,
        "source_path_printed": False,
        "label_text_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def _stream_summary(stream: str | bytes | None) -> dict[str, Any]:
    """Summarize a process stream without retaining raw content.

    Args:
        stream: Captured stdout or stderr.

    Returns:
        SHA-256 digest and line count, or empty metadata.
    """
    if stream is None:
        return {"sha256": None, "line_count": 0}
    if isinstance(stream, bytes):
        stream_bytes = stream
        stream_text = stream.decode("utf-8", errors="replace")
    else:
        stream_text = stream
        stream_bytes = stream.encode("utf-8", errors="replace")
    if not stream_bytes:
        return {"sha256": None, "line_count": 0}
    return {
        "sha256": hashlib.sha256(stream_bytes).hexdigest(),
        "line_count": len(stream_text.splitlines()),
    }


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


def _success_summary(*, result: Mapping[str, Any]) -> dict[str, Any]:
    """Return a redacted eval summary.

    Args:
        result: Eval result artifact.

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
        "metrics_json_ready_for_registration": result["metrics_json_ready_for_registration"],
        "command_printed": False,
        "paddleocr_root_printed": False,
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
    """Return a redacted eval error summary.

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
