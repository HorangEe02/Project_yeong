"""Run Naver Tampermonkey OCR evaluation batches with redacted summaries.

This operator wrapper executes ``run_naver_tampermonkey_ocr_eval.py`` once per
batch manifest. It is intended for long EX400U Tampermonkey fixture runs where
each batch must be resumable and failures must be isolated without persisting
raw OCR text, provider payloads, request headers, image bytes, raw model
responses, secrets, or local paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

try:  # pragma: no cover - exercised when run as a repo script.
    from scripts import run_naver_tampermonkey_ocr_eval as provider_runner
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback.
    import run_naver_tampermonkey_ocr_eval as provider_runner

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
PROVIDER_RUNNER = BACKEND_ROOT / "scripts" / "run_naver_tampermonkey_ocr_eval.py"
SCHEMA_VERSION = "naver-tampermonkey-batch-ocr-eval-v1"
DEFAULT_BATCH_SUMMARY_NAME = "manifest-batches.summary.json"
DEFAULT_OUTPUT_SUMMARY_NAME = "batch-ocr-eval.summary.json"
DEFAULT_RUN_PREFIX = "batch-run"
SAFE_FILENAME_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
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


@dataclass(frozen=True)
class BatchRunPlan:
    """One batch provider-runner invocation plan.

    Args:
        index: One-based batch index.
        batch_name: Batch manifest filename.
        manifest_path: Batch manifest path.
        output_root: Per-batch output root.
        command: Provider runner command as an argument sequence.
    """

    index: int
    batch_name: str
    manifest_path: Path
    output_root: Path
    command: tuple[str, ...]

    def redacted(self) -> dict[str, object]:
        """Return a JSON-safe run plan without local filesystem paths."""
        payload = {
            "index": self.index,
            "batch_name": self.batch_name,
            "manifest_path_hash": _sha256_text(str(self.manifest_path.expanduser())),
            "output_root_name": self.output_root.name,
            "output_root_hash": _sha256_text(str(self.output_root.expanduser())),
            "command": _redacted_command(self.command),
        }
        _reject_unsafe_payload(payload)
        return payload


@dataclass(frozen=True)
class BatchRunResult:
    """Sanitized batch execution result.

    Args:
        plan: Batch plan that was executed or dry-run.
        status: Public batch status.
        returncode: Process return code when available.
        completed_run_count: Provider runs available for evaluation.
        executed_run_count: Provider runs executed in this invocation.
        resumed_run_count: Provider runs reused from existing complete output.
        error_code: Stable non-sensitive error code.
    """

    plan: BatchRunPlan
    status: str
    returncode: int | None = None
    completed_run_count: int = 0
    executed_run_count: int = 0
    resumed_run_count: int = 0
    error_code: str | None = None

    def redacted(self) -> dict[str, object]:
        """Return a JSON-safe result without raw subprocess output."""
        payload: dict[str, object] = {
            **self.plan.redacted(),
            "status": self.status,
            "returncode": self.returncode,
            "completed_run_count": self.completed_run_count,
            "executed_run_count": self.executed_run_count,
            "resumed_run_count": self.resumed_run_count,
        }
        if self.error_code:
            payload["error_code"] = self.error_code
        _reject_unsafe_payload(payload)
        return payload


@dataclass(frozen=True)
class BatchExecutionSummary:
    """Batch execution aggregate.

    Args:
        plans: All selected batch plans.
        results: Results for dry-run or executed plans.
        stopped_early: Whether execution stopped after a failed batch.
    """

    plans: list[BatchRunPlan]
    results: list[BatchRunResult]
    stopped_early: bool = False


def main() -> None:
    """Parse CLI arguments, run selected batches, and write a redacted summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--batch-summary",
        type=Path,
        default=None,
        help="Defaults to <batch-dir>/manifest-batches.summary.json.",
    )
    parser.add_argument(
        "--summary-name",
        default=DEFAULT_OUTPUT_SUMMARY_NAME,
        help="Output summary filename under --output-root.",
    )
    parser.add_argument("--run-prefix", default=DEFAULT_RUN_PREFIX)
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument(
        "--python-executable",
        type=Path,
        default=Path(sys.executable),
        help="Python executable passed through to provider collection subprocesses.",
    )
    parser.add_argument(
        "--runner-python-executable",
        type=Path,
        default=Path(sys.executable),
        help="Python executable used to run the provider runner script.",
    )
    parser.add_argument("--providers", default="paddleocr")
    parser.add_argument("--llm-parse", action="store_true")
    parser.add_argument("--allow-external-providers", action="store_true")
    parser.add_argument("--allow-review-external", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-batches", type=int, default=None)
    parser.add_argument("--timeout-seconds", type=float, default=None)
    args = parser.parse_args()

    try:
        batch_dir = args.batch_dir.expanduser().resolve()
        output_root = args.output_root.expanduser().resolve()
        batch_summary = (
            args.batch_summary.expanduser().resolve()
            if args.batch_summary is not None
            else batch_dir / DEFAULT_BATCH_SUMMARY_NAME
        )
        plans = build_batch_run_plans(
            batch_dir=batch_dir,
            batch_summary_path=batch_summary,
            output_root=output_root,
            run_prefix=args.run_prefix,
            runner_python_executable=args.runner_python_executable,
            collector_python_executable=args.python_executable,
            providers=args.providers,
            env_file=args.env_file,
            llm_parse=bool(args.llm_parse),
            allow_external_providers=bool(args.allow_external_providers),
            allow_review_external=bool(args.allow_review_external),
            resume=bool(args.resume),
            max_batches=args.max_batches,
        )
        if args.dry_run:
            execution = BatchExecutionSummary(
                plans=plans,
                results=[
                    BatchRunResult(
                        plan=plan,
                        status="planned",
                    )
                    for plan in plans
                ],
            )
        else:
            execution = run_batch_evaluations(
                plans,
                continue_on_error=bool(args.continue_on_error),
                timeout_seconds=args.timeout_seconds,
            )
        summary = build_batch_execution_summary(
            batch_dir=batch_dir,
            output_root=output_root,
            execution=execution,
            dry_run=bool(args.dry_run),
            continue_on_error=bool(args.continue_on_error),
            timeout_seconds=args.timeout_seconds,
        )
        _write_summary(
            summary=summary,
            output_root=output_root,
            summary_name=args.summary_name,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        if not args.dry_run and any(result.status == "error" for result in execution.results):
            raise SystemExit(1)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure = _failure_summary(
            batch_dir=args.batch_dir,
            output_root=args.output_root,
            error=exc,
        )
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None


def build_batch_run_plans(
    *,
    batch_dir: Path,
    batch_summary_path: Path,
    output_root: Path,
    run_prefix: str = DEFAULT_RUN_PREFIX,
    runner_python_executable: Path = Path(sys.executable),
    collector_python_executable: Path = Path(sys.executable),
    providers: str = "paddleocr",
    env_file: Path | None = None,
    llm_parse: bool = False,
    allow_external_providers: bool = False,
    allow_review_external: bool = False,
    resume: bool = False,
    max_batches: int | None = None,
) -> list[BatchRunPlan]:
    """Build redacted provider-runner plans for batch manifests.

    Args:
        batch_dir: Directory containing JSONL batch manifests.
        batch_summary_path: Batch summary path used for deterministic ordering.
        output_root: Root directory where per-batch outputs will be written.
        run_prefix: Safe prefix for per-batch output directories.
        runner_python_executable: Python executable used for the provider runner.
        collector_python_executable: Python executable passed to the provider runner.
        providers: Provider aliases accepted by ``run_naver_tampermonkey_ocr_eval``.
        env_file: Optional dotenv file passed to the provider runner.
        llm_parse: Whether local Ollama structured parsing is enabled.
        allow_external_providers: Whether external OCR providers may run.
        allow_review_external: Whether review images may be externally transferred.
        resume: Whether existing complete provider outputs may be reused.
        max_batches: Optional cap on selected batches.

    Returns:
        Batch run plans.

    Raises:
        ValueError: If batch manifests or options are unsafe.
    """
    safe_prefix = _safe_filename_token(run_prefix, field_name="run_prefix")
    if max_batches is not None and max_batches < 1:
        raise ValueError("max_batches must be positive.")
    batch_names = _load_batch_names(batch_dir=batch_dir, batch_summary_path=batch_summary_path)
    if max_batches is not None:
        batch_names = batch_names[:max_batches]
    plans: list[BatchRunPlan] = []
    for index, batch_name in enumerate(batch_names, 1):
        manifest_path = batch_dir / batch_name
        _read_safe_manifest_rows(manifest_path)
        batch_output_root = output_root / f"{safe_prefix}-{index:03d}"
        command = _provider_runner_command(
            runner_python_executable=runner_python_executable,
            manifest_path=manifest_path,
            output_root=batch_output_root,
            collector_python_executable=collector_python_executable,
            providers=providers,
            env_file=env_file,
            llm_parse=llm_parse,
            allow_external_providers=allow_external_providers,
            allow_review_external=allow_review_external,
            resume=resume,
        )
        plans.append(
            BatchRunPlan(
                index=index,
                batch_name=batch_name,
                manifest_path=manifest_path,
                output_root=batch_output_root,
                command=tuple(command),
            )
        )
    return plans


def run_batch_evaluations(
    plans: Sequence[BatchRunPlan],
    *,
    continue_on_error: bool = False,
    timeout_seconds: float | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> BatchExecutionSummary:
    """Execute provider-runner plans sequentially with sanitized environments.

    Args:
        plans: Batch run plans.
        continue_on_error: Whether later batches should run after a failure.
        timeout_seconds: Optional subprocess timeout.
        runner: Injectable subprocess runner for tests.

    Returns:
        Execution summary.
    """
    results: list[BatchRunResult] = []
    stopped_early = False
    for plan in plans:
        try:
            completed = runner(
                list(plan.command),
                check=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
                env=_batch_child_env(plan.manifest_path),
                text=True,
                timeout=timeout_seconds,
            )
            result = _result_from_completed_process(plan=plan, completed=completed)
        except subprocess.TimeoutExpired:
            result = BatchRunResult(
                plan=plan,
                status="error",
                error_code="timeout",
            )
        except subprocess.CalledProcessError as exc:
            result = _result_from_called_process_error(plan=plan, error=exc)
        results.append(result)
        if result.status == "error" and not continue_on_error:
            stopped_early = True
            break
    return BatchExecutionSummary(
        plans=list(plans),
        results=results,
        stopped_early=stopped_early,
    )


def build_batch_execution_summary(
    *,
    batch_dir: Path,
    output_root: Path,
    execution: BatchExecutionSummary,
    dry_run: bool,
    continue_on_error: bool,
    timeout_seconds: float | None,
) -> dict[str, object]:
    """Build a public-safe aggregate summary.

    Args:
        batch_dir: Batch manifest directory.
        output_root: Root directory for batch outputs.
        execution: Batch execution results.
        dry_run: Whether no subprocesses were executed.
        continue_on_error: Whether execution continued after errors.
        timeout_seconds: Optional subprocess timeout.

    Returns:
        Redacted JSON summary.
    """
    status = "planned" if dry_run else "completed"
    if any(result.status == "error" for result in execution.results):
        status = "completed_with_errors" if continue_on_error else "error"
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "dry_run": dry_run,
        "continue_on_error": continue_on_error,
        "timeout_seconds": timeout_seconds,
        "batch_dir_name": batch_dir.name,
        "batch_dir_path_hash": _sha256_text(str(batch_dir.expanduser())),
        "output_root_name": output_root.name,
        "output_root_hash": _sha256_text(str(output_root.expanduser())),
        "planned_batch_count": len(execution.plans),
        "result_count": len(execution.results),
        "completed_batch_count": sum(
            1 for result in execution.results if result.status == "completed"
        ),
        "planned_only_batch_count": sum(
            1 for result in execution.results if result.status == "planned"
        ),
        "error_batch_count": sum(1 for result in execution.results if result.status == "error"),
        "stopped_early": execution.stopped_early,
        "provider_completed_run_count": sum(
            result.completed_run_count for result in execution.results
        ),
        "provider_executed_run_count": sum(
            result.executed_run_count for result in execution.results
        ),
        "provider_resumed_run_count": sum(result.resumed_run_count for result in execution.results),
        "batches": [result.redacted() for result in execution.results],
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _load_batch_names(*, batch_dir: Path, batch_summary_path: Path) -> list[str]:
    """Load deterministic batch names from summary or directory listing.

    Args:
        batch_dir: Directory containing JSONL batches.
        batch_summary_path: Optional summary path produced by the splitter.

    Returns:
        Sorted safe batch filenames.

    Raises:
        ValueError: If no JSONL batch files are available or names are unsafe.
    """
    if batch_summary_path.is_file():
        summary = json.loads(batch_summary_path.read_text(encoding="utf-8"))
        _reject_unsafe_payload(summary)
        raw_batches = summary.get("batches")
        if not isinstance(raw_batches, list):
            raise ValueError("Batch summary must contain a batches list.")
        names = []
        for item in raw_batches:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                raise ValueError("Batch summary contains an invalid batch entry.")
            names.append(_safe_batch_filename(item["name"]))
    else:
        names = [_safe_batch_filename(path.name) for path in sorted(batch_dir.glob("*.jsonl"))]
    if not names:
        raise ValueError("No batch manifests found.")
    return names


def _provider_runner_command(
    *,
    runner_python_executable: Path,
    manifest_path: Path,
    output_root: Path,
    collector_python_executable: Path,
    providers: str,
    env_file: Path | None,
    llm_parse: bool,
    allow_external_providers: bool,
    allow_review_external: bool,
    resume: bool,
) -> list[str]:
    """Build a provider-runner command without shell interpolation.

    Args:
        runner_python_executable: Python executable for this command.
        manifest_path: Batch manifest path.
        output_root: Per-batch output root.
        collector_python_executable: Python executable passed to collection.
        providers: Provider aliases.
        env_file: Optional dotenv path.
        llm_parse: Whether to enable local LLM parsing.
        allow_external_providers: Whether external OCR providers may run.
        allow_review_external: Whether review images may be externally transferred.
        resume: Whether complete outputs may be reused.

    Returns:
        Command argument sequence.
    """
    command = [
        str(runner_python_executable),
        str(PROVIDER_RUNNER),
        "--manifest",
        str(manifest_path),
        "--output-root",
        str(output_root),
        "--python-executable",
        str(collector_python_executable),
        "--providers",
        providers,
    ]
    if env_file is not None:
        command.extend(["--env-file", str(env_file)])
    if llm_parse:
        command.append("--llm-parse")
    if allow_external_providers:
        command.append("--allow-external-providers")
    if allow_review_external:
        command.append("--allow-review-external")
    if resume:
        command.append("--resume")
    return command


def _batch_child_env(manifest_path: Path) -> dict[str, str]:
    """Build a minimal environment for the provider runner subprocess.

    Args:
        manifest_path: Batch manifest path used to preserve referenced fixture
            root variables only.

    Returns:
        Sanitized child environment.
    """
    rows = _read_safe_manifest_rows(manifest_path)
    env: dict[str, str] = {}
    _copy_present_env(env, provider_runner.BASE_CHILD_ENV_KEYS)
    _copy_present_env(env, provider_runner.COLLECTOR_OPERATOR_ENV_KEYS)
    _copy_present_env(env, provider_runner._manifest_image_root_env_names(rows))
    env["PYTHONPATH"] = f"{provider_runner.BACKEND_ROOT}:{provider_runner.NUTRITION_BACKEND_ROOT}"
    return env


def _copy_present_env(destination: dict[str, str], keys: set[str] | frozenset[str]) -> None:
    """Copy selected environment variables when present.

    Args:
        destination: Destination environment mapping.
        keys: Allowlisted environment variable names.
    """
    for key in sorted(keys):
        value = os.environ.get(key)
        if value is not None:
            destination[key] = value


def _read_safe_manifest_rows(path: Path) -> list[dict[str, object]]:
    """Read manifest rows through the provider-runner privacy gate.

    Args:
        path: Batch manifest path.

    Returns:
        Manifest rows.
    """
    rows = provider_runner._read_manifest_rows(path)
    _reject_unsafe_payload(rows)
    return rows


def _result_from_completed_process(
    *,
    plan: BatchRunPlan,
    completed: subprocess.CompletedProcess[str],
) -> BatchRunResult:
    """Convert a successful subprocess result into bounded counters.

    Args:
        plan: Batch plan.
        completed: Completed subprocess.

    Returns:
        Redacted batch result.
    """
    payload = _parse_child_stdout(completed.stdout)
    return BatchRunResult(
        plan=plan,
        status="completed",
        returncode=completed.returncode,
        completed_run_count=_list_count(payload.get("completed_runs")),
        executed_run_count=_list_count(payload.get("executed_runs")),
        resumed_run_count=_list_count(payload.get("resumed_runs")),
    )


def _result_from_called_process_error(
    *,
    plan: BatchRunPlan,
    error: subprocess.CalledProcessError,
) -> BatchRunResult:
    """Convert a failed subprocess result into a redacted error result.

    Args:
        plan: Batch plan.
        error: Called process error.

    Returns:
        Redacted batch error result.
    """
    payload = _parse_child_stdout(error.stdout)
    error_code = "provider_runner_failed"
    raw_error_code = payload.get("error_code")
    if isinstance(raw_error_code, str) and raw_error_code:
        error_code = _safe_token(raw_error_code)
    return BatchRunResult(
        plan=plan,
        status="error",
        returncode=error.returncode,
        completed_run_count=_list_count(payload.get("completed_runs")),
        executed_run_count=_list_count(payload.get("executed_runs")),
        resumed_run_count=_list_count(payload.get("resumed_runs")),
        error_code=error_code,
    )


def _parse_child_stdout(value: object) -> dict[str, object]:
    """Parse child stdout when it is a JSON object.

    Args:
        value: Captured stdout.

    Returns:
        Redacted child payload or empty mapping.
    """
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    try:
        _reject_unsafe_payload(parsed)
    except ValueError:
        return {}
    return parsed


def _list_count(value: object) -> int:
    """Return list length for bounded child counters.

    Args:
        value: Candidate list.

    Returns:
        List length or zero.
    """
    return len(value) if isinstance(value, list) else 0


def _write_summary(
    *,
    summary: dict[str, object],
    output_root: Path,
    summary_name: str,
) -> None:
    """Write the redacted batch execution summary.

    Args:
        summary: Summary payload.
        output_root: Destination root.
        summary_name: Summary filename.

    Raises:
        OSError: If writing fails.
    """
    safe_name = _safe_batch_filename(summary_name, suffix=".json")
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / safe_name).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _redacted_command(command: Sequence[str]) -> list[str]:
    """Return a command summary with path-like values reduced to names.

    Args:
        command: Command argument sequence.

    Returns:
        Redacted command argument list.
    """
    redacted: list[str] = []
    path_value_flags = {
        "--batch-dir",
        "--batch-summary",
        "--env-file",
        "--manifest",
        "--output-root",
    }
    path_like_next = True
    for value in command:
        if path_like_next:
            redacted.append(Path(value).name)
            path_like_next = False
            continue
        if value in path_value_flags:
            redacted.append(value)
            path_like_next = True
            continue
        if any(marker in value for marker in LOCAL_PATH_MARKERS):
            redacted.append(Path(value).name)
            continue
        redacted.append(value)
    return redacted


def _safe_batch_filename(value: str, *, suffix: str = ".jsonl") -> str:
    """Validate a filename token with an expected suffix.

    Args:
        value: Candidate filename.
        suffix: Required suffix.

    Returns:
        Safe filename.

    Raises:
        ValueError: If filename is unsafe.
    """
    token = value.strip()
    if not token.endswith(suffix):
        raise ValueError("Batch filename has an unexpected suffix.")
    stem = token[: -len(suffix)]
    _safe_filename_token(stem, field_name="batch_filename")
    return token


def _safe_filename_token(value: str, *, field_name: str) -> str:
    """Return a bounded filename token.

    Args:
        value: Candidate token.
        field_name: Field name used in errors.

    Returns:
        Safe token.

    Raises:
        ValueError: If the token is unsafe.
    """
    token = value.strip()
    if not SAFE_FILENAME_TOKEN_PATTERN.fullmatch(token):
        raise ValueError(f"{field_name} must be a bounded filename token.")
    return token


def _safe_token(value: str) -> str:
    """Return a bounded public identifier.

    Args:
        value: Candidate token.

    Returns:
        Safe token or ``unsafe_token``.
    """
    token = value.strip()
    if re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", token) and not any(
        marker in token for marker in LOCAL_PATH_MARKERS
    ):
        return token
    return "unsafe_token"


def _reject_unsafe_payload(value: object) -> None:
    """Reject raw keys and local path literals recursively.

    Args:
        value: JSON-like payload.

    Raises:
        ValueError: If unsafe keys or local paths are found.
    """
    if isinstance(value, dict):
        forbidden = RAW_FORBIDDEN_KEYS.intersection(str(key).lower() for key in value)
        if forbidden:
            raise ValueError(f"Payload contains forbidden raw field(s): {sorted(forbidden)}")
        for nested in value.values():
            _reject_unsafe_payload(nested)
    elif isinstance(value, list | tuple):
        for item in value:
            _reject_unsafe_payload(item)
    elif isinstance(value, str) and any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")


def _failure_summary(
    *,
    batch_dir: Path,
    output_root: Path,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted CLI failure summary.

    Args:
        batch_dir: Requested batch directory.
        output_root: Requested output root.
        error: Failure exception.

    Returns:
        Public-safe failure summary.
    """
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "batch_dir_name": batch_dir.name,
        "batch_dir_path_hash": _sha256_text(str(batch_dir.expanduser())),
        "output_root_name": output_root.name,
        "output_root_hash": _sha256_text(str(output_root.expanduser())),
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _safe_error_code(exc: BaseException) -> str:
    """Return a bounded public error code.

    Args:
        exc: Failure exception.

    Returns:
        Error code.
    """
    if isinstance(exc, OSError):
        return "local_file_operation_error"
    if isinstance(exc, json.JSONDecodeError):
        return "json_decode_error"
    return "validation_error"


def _safe_public_error_message(exc: BaseException) -> str:
    """Return a public error message without filesystem details.

    Args:
        exc: Failure exception.

    Returns:
        Bounded public message.
    """
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
    """Return SHA-256 for text.

    Args:
        value: Text value.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
