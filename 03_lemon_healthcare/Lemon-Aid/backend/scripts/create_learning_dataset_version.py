"""Create a privacy-reviewed learning dataset version shell."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.db.session import get_sessionmaker  # noqa: E402
from src.models.db.retraining import LearningDatasetVersion  # noqa: E402

SUMMARY_SCHEMA_VERSION = "learning-dataset-version-create-summary-v1"
DATASET_KEY_CHOICES = (
    "supplement_roi_detection",
    "supplement_ocr_detection",
    "supplement_ocr_recognition",
    "food_detection",
    "food_classification",
    "image_embedding",
)
STATUS_CHOICES = ("draft", "frozen")
PRIVACY_REVIEW_STATUS_CHOICES = ("pending", "approved", "rejected")
HASH_LENGTH = 64


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-key", required=True, choices=DATASET_KEY_CHOICES)
    parser.add_argument("--version", required=True)
    parser.add_argument("--status", default="draft", choices=STATUS_CHOICES)
    parser.add_argument(
        "--privacy-review-status",
        default="pending",
        choices=PRIVACY_REVIEW_STATUS_CHOICES,
    )
    parser.add_argument("--train-count", default=0, type=_nonnegative_int)
    parser.add_argument("--val-count", default=0, type=_nonnegative_int)
    parser.add_argument("--test-count", default=0, type=_nonnegative_int)
    parser.add_argument("--source-window-start", default=None)
    parser.add_argument("--source-window-end", default=None)
    parser.add_argument("--created-by-hash", default=None)
    return parser.parse_args(argv)


async def run_cli(argv: list[str] | None = None) -> int:
    """Parse arguments, create the dataset version, and print a summary.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        summary = await create_learning_dataset_version(
            dataset_key=args.dataset_key,
            version=args.version,
            status=args.status,
            privacy_review_status=args.privacy_review_status,
            train_count=args.train_count,
            val_count=args.val_count,
            test_count=args.test_count,
            source_window_start=_parse_datetime(args.source_window_start),
            source_window_end=_parse_datetime(args.source_window_end),
            created_by_hash=args.created_by_hash,
        )
    except ValueError as exc:
        summary = _error_summary(error=exc)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 1

    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


async def create_learning_dataset_version(
    *,
    dataset_key: str,
    version: str,
    status: str,
    privacy_review_status: str,
    train_count: int,
    val_count: int,
    test_count: int,
    source_window_start: datetime | None,
    source_window_end: datetime | None,
    created_by_hash: str | None,
) -> dict[str, object]:
    """Persist one learning dataset version shell.

    Args:
        dataset_key: Dataset family key.
        version: Dataset version label.
        status: Initial dataset lifecycle status.
        privacy_review_status: Privacy review lifecycle status.
        train_count: Training split count.
        val_count: Validation split count.
        test_count: Test split count.
        source_window_start: Optional source window lower bound.
        source_window_end: Optional source window upper bound.
        created_by_hash: Optional 64-character operator hash.

    Returns:
        Sanitized creation summary.

    Raises:
        ValueError: If enum-like inputs, counts, time window, or operator hash are invalid.
    """
    _validate_inputs(
        dataset_key=dataset_key,
        version=version,
        status=status,
        privacy_review_status=privacy_review_status,
        train_count=train_count,
        val_count=val_count,
        test_count=test_count,
        source_window_start=source_window_start,
        source_window_end=source_window_end,
        created_by_hash=created_by_hash,
    )
    dataset_version = LearningDatasetVersion(
        id=uuid4(),
        dataset_key=dataset_key,
        version=version,
        status=status,
        source_window_start=source_window_start,
        source_window_end=source_window_end,
        train_count=train_count,
        val_count=val_count,
        test_count=test_count,
        privacy_review_status=privacy_review_status,
        created_by_hash=created_by_hash,
        frozen_at=datetime.now(UTC) if status == "frozen" else None,
    )
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        session.add(dataset_version)
        await session.commit()

    return _success_summary(dataset_version=dataset_version)


def _validate_inputs(
    *,
    dataset_key: str,
    version: str,
    status: str,
    privacy_review_status: str,
    train_count: int,
    val_count: int,
    test_count: int,
    source_window_start: datetime | None,
    source_window_end: datetime | None,
    created_by_hash: str | None,
) -> None:
    """Validate dataset version creation inputs.

    Args:
        dataset_key: Dataset family key.
        version: Dataset version label.
        status: Dataset lifecycle status.
        privacy_review_status: Privacy review lifecycle status.
        train_count: Training split count.
        val_count: Validation split count.
        test_count: Test split count.
        source_window_start: Optional source window lower bound.
        source_window_end: Optional source window upper bound.
        created_by_hash: Optional operator hash.

    Raises:
        ValueError: If any input is invalid.
    """
    if dataset_key not in DATASET_KEY_CHOICES:
        raise ValueError("Unsupported dataset key.")
    if not version.strip():
        raise ValueError("Dataset version is required.")
    if status not in STATUS_CHOICES:
        raise ValueError("Unsupported dataset status.")
    if privacy_review_status not in PRIVACY_REVIEW_STATUS_CHOICES:
        raise ValueError("Unsupported privacy review status.")
    if min(train_count, val_count, test_count) < 0:
        raise ValueError("Dataset split counts must be nonnegative.")
    if (
        source_window_start is not None
        and source_window_end is not None
        and source_window_end < source_window_start
    ):
        raise ValueError("Source window end must not be earlier than start.")
    if created_by_hash is not None and len(created_by_hash) != HASH_LENGTH:
        raise ValueError("created_by_hash must be 64 characters when provided.")


def _parse_datetime(raw_value: str | None) -> datetime | None:
    """Parse an optional ISO-8601 datetime.

    Args:
        raw_value: Raw CLI datetime value.

    Returns:
        Parsed timezone-aware datetime or None.

    Raises:
        ValueError: If the datetime is invalid or timezone-naive.
    """
    if raw_value is None:
        return None
    normalized = raw_value.removesuffix("Z") + "+00:00" if raw_value.endswith("Z") else raw_value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("Datetime values must include a timezone.")
    return parsed


def _nonnegative_int(raw_value: str) -> int:
    """Parse a nonnegative integer argparse value.

    Args:
        raw_value: Raw CLI value.

    Returns:
        Parsed nonnegative integer.

    Raises:
        argparse.ArgumentTypeError: If the value is invalid.
    """
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("count must be an integer") from exc
    if value < 0:
        raise argparse.ArgumentTypeError("count must be nonnegative")
    return value


def _success_summary(*, dataset_version: LearningDatasetVersion) -> dict[str, object]:
    """Return a redacted creation summary.

    Args:
        dataset_version: Persisted dataset version.

    Returns:
        Summary without operator hash, source object refs, or raw labels.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "ok",
        "dataset_version_id": str(dataset_version.id),
        "dataset_key": dataset_version.dataset_key,
        "dataset_version": dataset_version.version,
        "dataset_status": dataset_version.status,
        "privacy_review_status": dataset_version.privacy_review_status,
        "train_count": dataset_version.train_count,
        "val_count": dataset_version.val_count,
        "test_count": dataset_version.test_count,
        "source_window_registered": (
            dataset_version.source_window_start is not None
            or dataset_version.source_window_end is not None
        ),
        "operator_hash_printed": False,
        "raw_label_printed": False,
        "source_ref_printed": False,
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
        "operator_hash_printed": False,
        "raw_label_printed": False,
        "source_ref_printed": False,
    }


def main() -> None:
    """Run the CLI entrypoint."""
    raise SystemExit(asyncio.run(run_cli()))


if __name__ == "__main__":
    main()
