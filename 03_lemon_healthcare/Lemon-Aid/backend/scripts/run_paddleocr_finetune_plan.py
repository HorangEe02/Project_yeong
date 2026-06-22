"""Run a sanitized PaddleOCR fine-tune plan at the trusted-worker boundary.

This script consumes ``paddleocr-finetune-run-plan-v1`` and optionally executes
its pre-validated PaddleOCR command from a local PaddleOCR checkout. It stores
only aggregate execution metadata and stdout/stderr digests. Raw logs, local
paths, labels, OCR text, provider payloads, config refs, and model artifact refs
are never printed.

References:
    https://www.paddleocr.ai/v3.3.2/en/version2.x/ppocr/model_train/finetune.html
    https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppocr/blog/config.html
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

PLAN_SCHEMA_VERSION = "paddleocr-finetune-run-plan-v1"
RESULT_SCHEMA_VERSION = "paddleocr-finetune-execution-result-v1"
SUMMARY_SCHEMA_VERSION = "paddleocr-finetune-execution-summary-v1"
TRAIN_ENTRYPOINT = Path("tools") / "train.py"
DEFAULT_TIMEOUT_SECONDS = 3600
MAX_TIMEOUT_SECONDS = 86400
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


class PaddleOCRFinetuneExecutionError(ValueError):
    """Raised when a PaddleOCR fine-tune plan cannot be executed safely."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--paddleocr-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None) -> int:
    """Validate or execute a PaddleOCR plan and print a redacted summary.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        result, summary = run_paddleocr_finetune_plan(
            plan_path=args.plan,
            paddleocr_root=args.paddleocr_root,
            output_path=args.output,
            execute=args.execute,
            timeout_seconds=args.timeout_seconds,
        )
    except (PaddleOCRFinetuneExecutionError, ValueError) as exc:
        summary = _error_summary(error=exc)
        _write_json(args.output, summary)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 1

    _write_json(args.output, result)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def run_paddleocr_finetune_plan(
    *,
    plan_path: Path,
    paddleocr_root: Path,
    output_path: Path,
    execute: bool,
    timeout_seconds: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate a run plan and optionally execute PaddleOCR training.

    Args:
        plan_path: Path to a fine-tune run plan artifact.
        paddleocr_root: Local PaddleOCR checkout containing ``tools/train.py``.
        output_path: Destination result path, used only for summary metadata.
        execute: Whether to execute the command after validation.
        timeout_seconds: Subprocess timeout.

    Returns:
        Tuple of private result artifact and sanitized operator summary.

    Raises:
        PaddleOCRFinetuneExecutionError: If the plan, command, or root is unsafe.
        ValueError: If timeout configuration is invalid.
    """
    _ = output_path
    timeout_seconds = _validate_timeout_seconds(timeout_seconds)
    plan = _load_plan(plan_path)
    command_tokens = _validated_command_tokens(plan)
    _validate_paddleocr_root(paddleocr_root)

    base_result = _base_result(
        execute=execute,
        timeout_seconds=timeout_seconds,
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
            "metrics_json_required_for_registration": False,
        }
        return result, _success_summary(result=result)

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
            "metrics_json_required_for_registration": False,
        }
        return result, _success_summary(result=result)

    elapsed = time.monotonic() - started
    stdout_summary = _stream_summary(completed.stdout)
    stderr_summary = _stream_summary(completed.stderr)
    process_status = "succeeded" if completed.returncode == 0 else "failed"
    result = {
        **base_result,
        "process_status": process_status,
        "return_code": completed.returncode,
        "elapsed_seconds": round(elapsed, 3),
        "stdout_sha256": stdout_summary["sha256"],
        "stderr_sha256": stderr_summary["sha256"],
        "stdout_line_count": stdout_summary["line_count"],
        "stderr_line_count": stderr_summary["line_count"],
        "metrics_json_required_for_registration": process_status == "succeeded",
    }
    return result, _success_summary(result=result)


def _load_plan(path: Path) -> dict[str, Any]:
    """Load a fine-tune plan without leaking the path in errors.

    Args:
        path: Plan artifact path.

    Returns:
        Parsed plan object.

    Raises:
        PaddleOCRFinetuneExecutionError: If the plan is missing or malformed.
    """
    if not path.is_file():
        raise PaddleOCRFinetuneExecutionError("Fine-tune plan does not exist.")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaddleOCRFinetuneExecutionError("Fine-tune plan JSON is malformed.") from exc
    if not isinstance(parsed, dict):
        raise PaddleOCRFinetuneExecutionError("Fine-tune plan must be an object.")
    if parsed.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise PaddleOCRFinetuneExecutionError("Unsupported PaddleOCR fine-tune plan schema.")
    if parsed.get("training_execution_performed") is not False:
        raise PaddleOCRFinetuneExecutionError("Fine-tune plan must be pre-execution metadata.")
    return parsed


def _validated_command_tokens(plan: Mapping[str, Any]) -> list[str]:
    """Extract and validate the official-style PaddleOCR command tokens.

    Args:
        plan: Parsed fine-tune plan.

    Returns:
        Safe command tokens for ``subprocess.run`` with ``shell=False``.

    Raises:
        PaddleOCRFinetuneExecutionError: If command tokens are unsafe.
    """
    raw_tokens = plan.get("suggested_command_tokens")
    if not isinstance(raw_tokens, list) or not raw_tokens:
        raise PaddleOCRFinetuneExecutionError("Fine-tune plan command tokens are missing.")
    tokens: list[str] = []
    for raw_token in raw_tokens:
        if not isinstance(raw_token, str) or not raw_token.strip():
            raise PaddleOCRFinetuneExecutionError("Fine-tune plan command token is invalid.")
        _validate_command_token(raw_token)
        tokens.append(raw_token)
    if TRAIN_ENTRYPOINT.as_posix() not in tokens:
        raise PaddleOCRFinetuneExecutionError("Fine-tune command must include tools/train.py.")
    return tokens


def _validate_command_token(token: str) -> None:
    """Reject command tokens that could leak or escape the trusted boundary.

    Args:
        token: Candidate command token.

    Raises:
        PaddleOCRFinetuneExecutionError: If the token is unsafe.
    """
    if any(control in token for control in ("\x00", "\n", "\r")):
        raise PaddleOCRFinetuneExecutionError("Fine-tune command token has control characters.")
    folded = token.casefold()
    if any(marker in folded for marker in SECRET_LIKE_MARKERS):
        raise PaddleOCRFinetuneExecutionError("Fine-tune command token contains unsafe data.")
    if any(marker in token for marker in SHELL_META_MARKERS):
        raise PaddleOCRFinetuneExecutionError("Fine-tune command token contains shell syntax.")
    _validate_private_token_value(token)
    if "=" in token:
        _validate_private_token_value(token.split("=", maxsplit=1)[1])


def _validate_private_token_value(value: str) -> None:
    """Validate a token or override value as a private relative reference.

    Args:
        value: Token text or key-value override value.

    Raises:
        PaddleOCRFinetuneExecutionError: If the value is path-like and unsafe.
    """
    if not value:
        raise PaddleOCRFinetuneExecutionError("Fine-tune command token has an empty value.")
    value_path = Path(value)
    if value_path.is_absolute() or ".." in value_path.parts or "://" in value:
        raise PaddleOCRFinetuneExecutionError("Fine-tune command tokens must use private refs.")


def _validate_paddleocr_root(root: Path) -> None:
    """Verify a local PaddleOCR checkout has the expected train entrypoint.

    Args:
        root: Local PaddleOCR root.

    Raises:
        PaddleOCRFinetuneExecutionError: If the checkout is not usable.
    """
    if not root.is_dir():
        raise PaddleOCRFinetuneExecutionError("PaddleOCR root does not exist.")
    if not (root / TRAIN_ENTRYPOINT).is_file():
        raise PaddleOCRFinetuneExecutionError("PaddleOCR train entrypoint is missing.")


def _validate_timeout_seconds(timeout_seconds: int) -> int:
    """Validate bounded subprocess timeout.

    Args:
        timeout_seconds: Candidate timeout.

    Returns:
        Validated timeout.

    Raises:
        ValueError: If the timeout is out of bounds.
    """
    if timeout_seconds <= 0 or timeout_seconds > MAX_TIMEOUT_SECONDS:
        raise ValueError("timeout-seconds must be in 1..86400.")
    return timeout_seconds


def _base_result(
    *,
    execute: bool,
    timeout_seconds: int,
    command_tokens: Sequence[str],
) -> dict[str, Any]:
    """Build the common redacted result payload.

    Args:
        execute: Whether execution was requested.
        timeout_seconds: Validated timeout.
        command_tokens: Validated command tokens.

    Returns:
        Common result fields.
    """
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "plan_schema_version": PLAN_SCHEMA_VERSION,
        "execution_requested": execute,
        "training_execution_performed": execute,
        "timeout_seconds": timeout_seconds,
        "command_token_count": len(command_tokens),
        "tools_train_checked": True,
        "command_printed": False,
        "paddleocr_root_printed": False,
        "stdout_raw_stored": False,
        "stderr_raw_stored": False,
        "source_path_printed": False,
        "label_text_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def _stream_summary(stream: str | bytes | None) -> dict[str, Any]:
    """Summarize a process stream without retaining its raw content.

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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
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
    """Return an operator-facing summary without command or log content.

    Args:
        result: Execution result payload.

    Returns:
        Redacted aggregate-only summary.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "ok",
        "execution_requested": result["execution_requested"],
        "training_execution_performed": result["training_execution_performed"],
        "process_status": result["process_status"],
        "return_code": result["return_code"],
        "command_token_count": result["command_token_count"],
        "stdout_line_count": result["stdout_line_count"],
        "stderr_line_count": result["stderr_line_count"],
        "stdout_digest_stored": result["stdout_sha256"] is not None,
        "stderr_digest_stored": result["stderr_sha256"] is not None,
        "metrics_json_required_for_registration": result["metrics_json_required_for_registration"],
        "command_printed": False,
        "paddleocr_root_printed": False,
        "stdout_raw_stored": False,
        "stderr_raw_stored": False,
        "source_path_printed": False,
        "label_text_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def _error_summary(*, error: BaseException) -> dict[str, Any]:
    """Return a redacted error summary.

    Args:
        error: Raised exception.

    Returns:
        Aggregate error summary with no input values.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "error",
        "error_type": type(error).__name__,
        "execution_requested": False,
        "training_execution_performed": False,
        "command_printed": False,
        "paddleocr_root_printed": False,
        "stdout_raw_stored": False,
        "stderr_raw_stored": False,
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
