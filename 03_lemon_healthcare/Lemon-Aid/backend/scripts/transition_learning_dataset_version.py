"""Transition learning dataset lifecycle status with privacy gates."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.db.session import get_sessionmaker  # noqa: E402
from src.models.db.retraining import LearningDatasetVersion  # noqa: E402

SUMMARY_SCHEMA_VERSION = "learning-dataset-transition-summary-v1"
DATASET_STATUS_CHOICES = ("frozen", "training", "evaluated", "approved", "retired")
PRIVACY_REVIEW_STATUS_CHOICES = ("approved", "rejected")
ALLOWED_TRANSITIONS = {
    "draft": frozenset({"frozen", "retired"}),
    "frozen": frozenset({"training", "retired"}),
    "training": frozenset({"evaluated", "retired"}),
    "evaluated": frozenset({"approved", "retired"}),
    "approved": frozenset({"retired"}),
}
PRIVACY_APPROVED_REQUIRED_STATUSES = frozenset({"frozen", "training", "evaluated", "approved"})
MANIFEST_HASH_REQUIRED_STATUSES = frozenset({"training", "evaluated", "approved"})
SHA256_HEX_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-version-id", required=True, type=UUID)
    parser.add_argument("--target-status", required=True, choices=DATASET_STATUS_CHOICES)
    parser.add_argument(
        "--privacy-review-status",
        choices=PRIVACY_REVIEW_STATUS_CHOICES,
        default=None,
        help="Optional final privacy-review status to store with the transition.",
    )
    parser.add_argument(
        "--manifest-hash",
        default=None,
        help="Optional SHA-256 sanitized manifest hash to store before training.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist transition only after dry-run checks pass.",
    )
    return parser.parse_args(argv)


async def run_cli(argv: list[str] | None = None) -> int:
    """Parse arguments, evaluate transition checks, and print a redacted summary.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        summary = await transition_learning_dataset_version(
            dataset_version_id=args.dataset_version_id,
            target_status=args.target_status,
            privacy_review_status=args.privacy_review_status,
            manifest_hash=args.manifest_hash,
            apply=args.apply,
        )
    except ValueError as exc:
        summary = _error_summary(error=exc)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 1

    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["allowed"] is True else 1


async def transition_learning_dataset_version(
    *,
    dataset_version_id: UUID,
    target_status: str,
    privacy_review_status: str | None,
    manifest_hash: str | None,
    apply: bool,
) -> dict[str, object]:
    """Evaluate and optionally persist one dataset lifecycle transition.

    Args:
        dataset_version_id: Learning dataset version id.
        target_status: Requested lifecycle status.
        privacy_review_status: Optional final privacy-review status.
        manifest_hash: Optional SHA-256 sanitized manifest hash.
        apply: Whether to persist after checks pass.

    Returns:
        Sanitized transition summary.

    Raises:
        ValueError: If the dataset is missing or transition inputs are invalid.
    """
    _validate_static_inputs(
        target_status=target_status,
        privacy_review_status=privacy_review_status,
        manifest_hash=manifest_hash,
    )

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        dataset_version = await session.get(LearningDatasetVersion, dataset_version_id)
        if dataset_version is None:
            raise ValueError("Learning dataset version was not found.")
        final_privacy_review_status = privacy_review_status or dataset_version.privacy_review_status
        final_manifest_hash = manifest_hash or dataset_version.manifest_hash
        summary = _evaluate_transition(
            dataset_version=dataset_version,
            target_status=target_status,
            final_privacy_review_status=final_privacy_review_status,
            final_manifest_hash=final_manifest_hash,
            apply=apply,
        )
        if apply and summary["allowed"] is True:
            dataset_version.status = target_status
            dataset_version.privacy_review_status = final_privacy_review_status
            if manifest_hash is not None:
                dataset_version.manifest_hash = manifest_hash
            if target_status == "frozen" and dataset_version.frozen_at is None:
                dataset_version.frozen_at = datetime.now(UTC)
            await session.commit()
            summary["applied"] = True
            summary["new_status"] = target_status

    return summary


def _validate_static_inputs(
    *,
    target_status: str,
    privacy_review_status: str | None,
    manifest_hash: str | None,
) -> None:
    """Validate enum-like and hash inputs before loading the DB row.

    Args:
        target_status: Requested lifecycle status.
        privacy_review_status: Optional privacy-review status.
        manifest_hash: Optional manifest hash.

    Raises:
        ValueError: If an input is invalid.
    """
    if target_status not in DATASET_STATUS_CHOICES:
        raise ValueError("Unsupported dataset target status.")
    if (
        privacy_review_status is not None
        and privacy_review_status not in PRIVACY_REVIEW_STATUS_CHOICES
    ):
        raise ValueError("Unsupported privacy review status.")
    if manifest_hash is not None and not SHA256_HEX_PATTERN.fullmatch(manifest_hash):
        raise ValueError("Manifest hash must be a SHA-256 lowercase hex string.")


def _evaluate_transition(
    *,
    dataset_version: LearningDatasetVersion,
    target_status: str,
    final_privacy_review_status: str,
    final_manifest_hash: str | None,
    apply: bool,
) -> dict[str, object]:
    """Return a redacted transition readiness summary.

    Args:
        dataset_version: Dataset row being transitioned.
        target_status: Requested lifecycle status.
        final_privacy_review_status: Privacy-review status after transition.
        final_manifest_hash: Manifest hash after transition.
        apply: Whether this invocation will persist changes.

    Returns:
        Sanitized readiness summary.
    """
    allowed = True
    reason = "ready_to_transition"
    allowed_targets = ALLOWED_TRANSITIONS.get(dataset_version.status, frozenset())
    if dataset_version.status == target_status:
        allowed = False
        reason = "already_in_target_status"
    elif target_status not in allowed_targets:
        allowed = False
        reason = "transition_not_allowed"
    elif (
        target_status in PRIVACY_APPROVED_REQUIRED_STATUSES
        and final_privacy_review_status != "approved"
    ):
        allowed = False
        reason = "privacy_review_not_approved"
    elif target_status in MANIFEST_HASH_REQUIRED_STATUSES and final_manifest_hash is None:
        allowed = False
        reason = "manifest_hash_required"

    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "ok",
        "allowed": allowed,
        "applied": False,
        "dry_run": not apply,
        "reason": reason,
        "dataset_version_id": str(dataset_version.id),
        "dataset_key": dataset_version.dataset_key,
        "previous_status": dataset_version.status,
        "new_status": dataset_version.status,
        "target_status": target_status,
        "privacy_review_status": final_privacy_review_status,
        "manifest_hash_present": final_manifest_hash is not None,
        "manifest_hash_printed": False,
        "operator_hash_printed": False,
        "raw_label_printed": False,
    }


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
        "manifest_hash_printed": False,
        "operator_hash_printed": False,
        "raw_label_printed": False,
    }


def main() -> None:
    """Run the CLI entrypoint."""
    raise SystemExit(asyncio.run(run_cli()))


if __name__ == "__main__":
    main()
