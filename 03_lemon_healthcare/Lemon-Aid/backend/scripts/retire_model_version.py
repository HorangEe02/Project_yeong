"""Retire a deployable model version with fail-closed rollback checks."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.db.session import get_sessionmaker  # noqa: E402
from src.learning.retraining import RetrainingSecurityError  # noqa: E402
from src.models.db.retraining import ModelRegistryEntry  # noqa: E402

SUMMARY_SCHEMA_VERSION = "model-retirement-summary-v1"
RETIREMENT_SNAPSHOT_SCHEMA_VERSION = "model-retirement-snapshot-v1"
RETIRABLE_STATUSES = frozenset({"candidate", "staging", "production", "rolled_back"})
ROLLBACK_TARGET_STATUSES = frozenset({"staging", "production"})
REASON_CODE_PATTERN = re.compile(r"^[a-z0-9_:-]{1,80}$")
SECRET_LIKE_MARKERS = (
    "bearer ",
    "ngrok-free.dev",
    "sb_secret_",
    "service_role",
    "aws_secret_access_key",
    "-----begin",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", required=True, type=UUID)
    parser.add_argument("--reason-code", required=True)
    parser.add_argument("--rollback-model-id", default=None, type=UUID)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist retirement only after dry-run checks pass.",
    )
    return parser.parse_args(argv)


async def run_cli(argv: list[str] | None = None) -> int:
    """Parse arguments, evaluate retirement checks, and print a redacted summary.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        summary = await retire_model_version(
            model_id=args.model_id,
            reason_code=args.reason_code,
            rollback_model_id=args.rollback_model_id,
            apply=args.apply,
        )
    except (RetrainingSecurityError, ValueError) as exc:
        summary = _error_summary(error=exc)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 1

    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["allowed"] is True else 1


async def retire_model_version(
    *,
    model_id: UUID,
    reason_code: str,
    rollback_model_id: UUID | None,
    apply: bool,
) -> dict[str, object]:
    """Evaluate and optionally retire one model registry entry.

    Args:
        model_id: Model registry row to retire.
        reason_code: Stable operator reason code.
        rollback_model_id: Optional rollback model in the same task family.
        apply: Whether to persist retirement after checks pass.

    Returns:
        Sanitized retirement summary.

    Raises:
        RetrainingSecurityError: If reason code is unsafe.
        ValueError: If model rows are missing or rollback lineage is invalid.
    """
    _validate_reason_code(reason_code)

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        model = await session.get(ModelRegistryEntry, model_id)
        if model is None:
            raise ValueError("Model registry entry was not found.")
        rollback_model = await _load_rollback_model(
            session=session,
            model=model,
            rollback_model_id=rollback_model_id,
        )
        summary = _evaluate_retirement(
            model=model,
            rollback_model=rollback_model,
            apply=apply,
        )
        if apply and summary["allowed"] is True:
            previous_status = model.deployment_status
            model.deployment_status = "retired"
            model.rollback_model_id = rollback_model_id
            model.metric_gate_snapshot = _with_retirement_snapshot(
                existing=model.metric_gate_snapshot,
                reason_code=reason_code,
                previous_status=previous_status,
                rollback_model_id=rollback_model_id,
            )
            await session.commit()
            summary["applied"] = True
            summary["new_deployment_status"] = "retired"

    return summary


async def _load_rollback_model(
    *,
    session: Any,
    model: ModelRegistryEntry,
    rollback_model_id: UUID | None,
) -> ModelRegistryEntry | None:
    """Load and validate an optional rollback model.

    Args:
        session: Async DB session.
        model: Model being retired.
        rollback_model_id: Optional rollback model id.

    Returns:
        Rollback model row, or None.

    Raises:
        ValueError: If rollback row is missing or incompatible.
    """
    if rollback_model_id is None:
        return None
    if rollback_model_id == model.id:
        raise ValueError("Rollback model cannot be the retiring model.")
    rollback_model = await session.get(ModelRegistryEntry, rollback_model_id)
    if rollback_model is None:
        raise ValueError("Rollback model registry entry was not found.")
    if rollback_model.task_type != model.task_type:
        raise ValueError("Rollback model task type does not match.")
    if rollback_model.deployment_status not in ROLLBACK_TARGET_STATUSES:
        raise ValueError("Rollback model must be staging or production.")
    return rollback_model


def _evaluate_retirement(
    *,
    model: ModelRegistryEntry,
    rollback_model: ModelRegistryEntry | None,
    apply: bool,
) -> dict[str, object]:
    """Return a redacted retirement readiness summary.

    Args:
        model: Model being retired.
        rollback_model: Optional rollback target.
        apply: Whether this invocation will persist changes.

    Returns:
        Sanitized readiness summary.
    """
    allowed = True
    reason = "ready_to_retire"
    if model.deployment_status == "retired":
        allowed = False
        reason = "already_retired"
    elif model.deployment_status not in RETIRABLE_STATUSES:
        allowed = False
        reason = "status_not_retirable"
    elif model.deployment_status == "production" and rollback_model is None:
        allowed = False
        reason = "production_requires_rollback"
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "ok",
        "allowed": allowed,
        "applied": False,
        "dry_run": not apply,
        "reason": reason,
        "model_id": str(model.id),
        "task_type": model.task_type,
        "previous_deployment_status": model.deployment_status,
        "new_deployment_status": model.deployment_status,
        "rollback_model_present": rollback_model is not None,
        "artifact_ref_printed": False,
        "reason_code_printed": False,
    }


def _with_retirement_snapshot(
    *,
    existing: dict[str, Any],
    reason_code: str,
    previous_status: str,
    rollback_model_id: UUID | None,
) -> dict[str, Any]:
    """Return a metric-gate snapshot carrying sanitized retirement metadata.

    Args:
        existing: Existing model registry snapshot.
        reason_code: Stable operator reason code.
        previous_status: Deployment status before retirement.
        rollback_model_id: Optional rollback target id.

    Returns:
        Updated JSON snapshot.
    """
    snapshot = dict(existing or {})
    snapshot["retirement"] = {
        "schema_version": RETIREMENT_SNAPSHOT_SCHEMA_VERSION,
        "reason_code": reason_code,
        "previous_deployment_status": previous_status,
        "rollback_model_id": str(rollback_model_id) if rollback_model_id is not None else None,
    }
    return snapshot


def _validate_reason_code(reason_code: str) -> None:
    """Validate a stable retirement reason code.

    Args:
        reason_code: Operator reason code.

    Raises:
        RetrainingSecurityError: If the reason code is unsafe.
    """
    if not REASON_CODE_PATTERN.fullmatch(reason_code):
        raise RetrainingSecurityError("Reason code must use stable safe characters.")
    _reject_path_url_or_secret(reason_code, "Reason code")


def _reject_path_url_or_secret(value: str, label: str) -> None:
    """Reject URL, absolute path, traversal, and secret-like values.

    Args:
        value: Candidate string.
        label: Error label.

    Raises:
        RetrainingSecurityError: If the value is unsafe.
    """
    folded = value.casefold()
    if "://" in value or value.startswith("/") or ".." in value:
        raise RetrainingSecurityError(f"{label} must not be a path or URL.")
    if any(marker in folded for marker in SECRET_LIKE_MARKERS):
        raise RetrainingSecurityError(f"{label} contains a secret-like value.")


def _error_summary(*, error: BaseException) -> dict[str, object]:
    """Return a redacted error summary.

    Args:
        error: Raised exception.

    Returns:
        Summary with only the exception class.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "error",
        "error_type": type(error).__name__,
        "allowed": False,
        "applied": False,
        "artifact_ref_printed": False,
        "reason_code_printed": False,
    }


def main() -> None:
    """Run the CLI entrypoint."""
    raise SystemExit(asyncio.run(run_cli()))


if __name__ == "__main__":
    main()
