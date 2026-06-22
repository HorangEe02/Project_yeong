"""Promote accepted PaddleOCR annotation tasks into learning dataset items.

This bridge is intentionally separate from provider benchmarking. It only
promotes already accepted ``ocr_textline_label`` annotation tasks into
``paddleocr_detection`` or ``paddleocr_recognition`` dataset items. The script
does not call OCR providers, does not export raw images, and does not train a
model.

References:
    https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
    https://www.paddleocr.ai/v3.3.2/en/version2.x/ppocr/model_train/finetune.html
    https://docs.sqlalchemy.org/en/21/orm/queryguide/select.html
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.db.session import get_sessionmaker  # noqa: E402
from src.learning.retraining import (  # noqa: E402
    DATASET_EXPORT_SCHEMA_VERSION,
    RetrainingSecurityError,
    build_paddleocr_detection_export,
    build_paddleocr_recognition_export,
)
from src.models.db.learning import LearningImageObject  # noqa: E402
from src.models.db.media import MediaObject  # noqa: E402
from src.models.db.retraining import (  # noqa: E402
    AnnotationTask,
    LearningDatasetItem,
    LearningDatasetVersion,
)

SUMMARY_SCHEMA_VERSION = "paddleocr-annotation-task-dataset-promotion-summary-v1"
PROMOTABLE_TASK_TYPE = "ocr_textline_label"
SOURCE_DOMAIN = "supplement"
LABEL_STATUS = "human_reviewed"
MAX_PROMOTION_LIMIT = 500
ALLOWED_SPLITS = frozenset({"train", "val", "test", "holdout"})
DATASET_TASK_CHOICES = ("paddleocr_detection", "paddleocr_recognition")
DATASET_KEY_BY_TASK_TYPE = {
    "paddleocr_detection": "supplement_ocr_detection",
    "paddleocr_recognition": "supplement_ocr_recognition",
}


@dataclass(frozen=True)
class _SourceRetention:
    """Retained source metadata needed for dataset item creation.

    Attributes:
        source_type: Sanitized source type label.
        retained_until: Source retention deadline copied to the dataset item.
    """

    source_type: str
    retained_until: datetime


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-version-id", required=True, type=UUID)
    parser.add_argument("--dataset-task-type", required=True, choices=DATASET_TASK_CHOICES)
    parser.add_argument("--split", choices=sorted(ALLOWED_SPLITS), default="train")
    parser.add_argument("--limit", type=int, default=MAX_PROMOTION_LIMIT)
    return parser.parse_args(argv)


async def run_cli(argv: list[str] | None = None) -> int:
    """Parse arguments, promote tasks, and print a redacted summary.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        summary = await promote_accepted_paddleocr_annotation_tasks_to_dataset(
            dataset_version_id=args.dataset_version_id,
            dataset_task_type=args.dataset_task_type,
            split=args.split,
            limit=args.limit,
        )
    except (RetrainingSecurityError, ValueError) as exc:
        summary = _failure_summary(dataset_version_id=args.dataset_version_id, error=exc)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 1

    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> None:
    """Run the CLI entrypoint.

    Args:
        argv: Optional argument list for tests.
    """
    raise SystemExit(asyncio.run(run_cli(argv)))


async def promote_accepted_paddleocr_annotation_tasks_to_dataset(
    *,
    dataset_version_id: UUID,
    dataset_task_type: str,
    split: str = "train",
    limit: int = MAX_PROMOTION_LIMIT,
) -> dict[str, object]:
    """Promote accepted OCR annotation tasks into PaddleOCR dataset items.

    Args:
        dataset_version_id: Target learning dataset version id.
        dataset_task_type: Either ``paddleocr_detection`` or
            ``paddleocr_recognition``.
        split: Dataset split assigned to promoted rows.
        limit: Maximum accepted tasks to scan.

    Returns:
        Redacted promotion summary.

    Raises:
        ValueError: If args or dataset version are invalid.
    """
    _validate_promotion_args(dataset_task_type=dataset_task_type, split=split, limit=limit)
    sessionmaker = get_sessionmaker()
    promoted_count = 0
    skipped_existing_count = 0
    skipped_missing_source_count = 0
    invalid_source_count = 0
    rejected_label_count = 0

    async with sessionmaker() as session:
        dataset_version = await session.get(LearningDatasetVersion, dataset_version_id)
        _validate_dataset_version(dataset_version, dataset_task_type=dataset_task_type)
        tasks = await _load_promotable_tasks(session=session, limit=limit)

        for task in tasks:
            if not _has_exactly_one_source(task):
                invalid_source_count += 1
                continue
            source_ref = _private_source_ref(task)
            try:
                label_snapshot = _normalize_label_snapshot(task.label_snapshot)
                _validate_label_snapshot_for_task(
                    label_snapshot=label_snapshot,
                    dataset_task_type=dataset_task_type,
                    source_ref=source_ref,
                )
            except RetrainingSecurityError:
                rejected_label_count += 1
                continue

            source_retention = await _load_source_retention(session=session, task=task)
            if source_retention is None:
                skipped_missing_source_count += 1
                continue

            label_hash = _sha256_json(label_snapshot)
            if await _existing_dataset_item_exists(
                session=session,
                dataset_version_id=dataset_version_id,
                dataset_task_type=dataset_task_type,
                task=task,
                label_hash=label_hash,
            ):
                skipped_existing_count += 1
                continue

            session.add(
                LearningDatasetItem(
                    dataset_version_id=dataset_version_id,
                    owner_subject_hash=task.owner_subject_hash,
                    media_object_id=task.media_object_id,
                    learning_image_object_id=task.learning_image_object_id,
                    source_domain=SOURCE_DOMAIN,
                    task_type=dataset_task_type,
                    label_status=LABEL_STATUS,
                    split=split,
                    label_snapshot=label_snapshot,
                    label_hash=label_hash,
                    quality_score=None,
                    consent_snapshot={
                        "source": "paddleocr_annotation_review",
                        "source_type": source_retention.source_type,
                        "dataset_task_type": dataset_task_type,
                    },
                    retained_until=source_retention.retained_until,
                )
            )
            promoted_count += 1

        await session.commit()

    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "ok",
        "dataset_version_id": str(dataset_version_id),
        "task_type": PROMOTABLE_TASK_TYPE,
        "dataset_task_type": dataset_task_type,
        "split": split,
        "scanned_count": len(tasks),
        "promoted_count": promoted_count,
        "skipped_existing_count": skipped_existing_count,
        "skipped_missing_source_count": skipped_missing_source_count,
        "invalid_source_count": invalid_source_count,
        "rejected_label_count": rejected_label_count,
        "label_snapshot_printed": False,
        "source_ref_printed": False,
        "owner_subject_hash_printed": False,
        "raw_payload_printed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
    }


def _validate_promotion_args(*, dataset_task_type: str, split: str, limit: int) -> None:
    """Validate promotion arguments.

    Args:
        dataset_task_type: Target dataset task type.
        split: Dataset split.
        limit: Maximum rows to scan.

    Raises:
        ValueError: If any argument is invalid.
    """
    if dataset_task_type not in DATASET_TASK_CHOICES:
        raise ValueError("Dataset task type is not allowed.")
    if split not in ALLOWED_SPLITS:
        raise ValueError("Dataset split is not allowed.")
    if limit < 1 or limit > MAX_PROMOTION_LIMIT:
        raise ValueError("Promotion limit must be between 1 and 500.")


def _validate_dataset_version(
    dataset_version: LearningDatasetVersion | None,
    *,
    dataset_task_type: str,
) -> None:
    """Validate the target dataset version.

    Args:
        dataset_version: Loaded dataset version row.
        dataset_task_type: Target dataset task type.

    Raises:
        ValueError: If the dataset version is missing or incompatible.
    """
    if dataset_version is None:
        raise ValueError("Learning dataset version was not found.")
    expected_key = DATASET_KEY_BY_TASK_TYPE[dataset_task_type]
    if dataset_version.dataset_key != expected_key:
        raise ValueError("Dataset version key is not compatible with the PaddleOCR task type.")


async def _load_promotable_tasks(*, session: Any, limit: int) -> list[AnnotationTask]:
    """Load accepted OCR annotation tasks.

    Args:
        session: Async DB session.
        limit: Maximum rows to scan.

    Returns:
        Accepted OCR annotation task rows.
    """
    statement = (
        select(AnnotationTask)
        .where(
            AnnotationTask.task_type == PROMOTABLE_TASK_TYPE,
            AnnotationTask.status == "accepted",
        )
        .order_by(AnnotationTask.completed_at.asc(), AnnotationTask.id.asc())
        .limit(limit)
    )
    return list((await session.scalars(statement)).all())


def _has_exactly_one_source(task: AnnotationTask) -> bool:
    """Return whether a task has exactly one supported private source id.

    Args:
        task: Annotation task row.

    Returns:
        True when exactly one source column is populated.
    """
    return (task.media_object_id is None) != (task.learning_image_object_id is None)


def _private_source_ref(task: AnnotationTask) -> str:
    """Return a backend-only source ref for export validation.

    Args:
        task: Annotation task row.

    Returns:
        ``media:<uuid>`` or ``learning_image:<uuid>`` token.

    Raises:
        ValueError: If the task does not have exactly one source.
    """
    if task.media_object_id is not None and task.learning_image_object_id is None:
        return f"media:{task.media_object_id}"
    if task.learning_image_object_id is not None and task.media_object_id is None:
        return f"learning_image:{task.learning_image_object_id}"
    raise ValueError("Annotation task must have exactly one private source.")


def _normalize_label_snapshot(label_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Return deterministic JSON object form for label snapshots.

    Args:
        label_snapshot: Source label snapshot.

    Returns:
        JSON-normalized label snapshot.
    """
    return json.loads(json.dumps(label_snapshot, ensure_ascii=False, sort_keys=True))


def _validate_label_snapshot_for_task(
    *,
    label_snapshot: Mapping[str, Any],
    dataset_task_type: str,
    source_ref: str,
) -> None:
    """Validate a label snapshot against PaddleOCR export contracts.

    The existing export builders are used here so the DB promotion gate and
    later training manifest export share the same accepted shape.

    Args:
        label_snapshot: Candidate label payload.
        dataset_task_type: Target PaddleOCR task type.
        source_ref: Backend-only source token.

    Raises:
        RetrainingSecurityError: If the label snapshot cannot be exported.
    """
    manifest = {
        "schema_version": DATASET_EXPORT_SCHEMA_VERSION,
        "items": [
            {
                "source_ref": source_ref,
                "split": "train",
                "task_type": dataset_task_type,
                "label_snapshot": label_snapshot,
            }
        ],
    }
    if dataset_task_type == "paddleocr_detection":
        build_paddleocr_detection_export(manifest)
    elif dataset_task_type == "paddleocr_recognition":
        build_paddleocr_recognition_export(manifest)
    else:
        raise RetrainingSecurityError("Unsupported PaddleOCR task type.")


async def _load_source_retention(
    *,
    session: Any,
    task: AnnotationTask,
) -> _SourceRetention | None:
    """Load source retention metadata without exposing source refs.

    Args:
        session: Async DB session.
        task: Annotation task row.

    Returns:
        Source retention metadata or ``None`` when source is unavailable.
    """
    if task.media_object_id is not None:
        media_object = await session.get(MediaObject, task.media_object_id)
        return _media_source_retention(media_object)
    if task.learning_image_object_id is not None:
        image_object = await session.get(LearningImageObject, task.learning_image_object_id)
        return _learning_image_source_retention(image_object)
    return None


def _media_source_retention(media_object: MediaObject | None) -> _SourceRetention | None:
    """Return source retention metadata for a live media object.

    Args:
        media_object: Media source row.

    Returns:
        Source retention metadata or ``None`` when unavailable.
    """
    if media_object is None or media_object.deleted_at is not None:
        return None
    if media_object.status in {"deleted", "failed"}:
        return None
    return _SourceRetention(source_type="media_object", retained_until=media_object.retained_until)


def _learning_image_source_retention(
    image_object: LearningImageObject | None,
) -> _SourceRetention | None:
    """Return source retention metadata for a live learning image object.

    Args:
        image_object: Learning image source row.

    Returns:
        Source retention metadata or ``None`` when unavailable.
    """
    if image_object is None or image_object.deleted_at is not None:
        return None
    if image_object.status in {
        "deleted",
        "cancelled",
        "failed",
        "rejected_by_auto_filter",
        "rejected_by_review",
    }:
        return None
    return _SourceRetention(
        source_type="learning_image_object",
        retained_until=image_object.retained_until,
    )


async def _existing_dataset_item_exists(
    *,
    session: Any,
    dataset_version_id: UUID,
    dataset_task_type: str,
    task: AnnotationTask,
    label_hash: str,
) -> bool:
    """Return whether the target dataset item already exists.

    Args:
        session: Async DB session.
        dataset_version_id: Target dataset version id.
        dataset_task_type: Target PaddleOCR task type.
        task: Source annotation task.
        label_hash: Deterministic label hash.

    Returns:
        True when an equivalent dataset item is already present.
    """
    statement = select(LearningDatasetItem).where(
        LearningDatasetItem.dataset_version_id == dataset_version_id,
        LearningDatasetItem.source_domain == SOURCE_DOMAIN,
        LearningDatasetItem.task_type == dataset_task_type,
        LearningDatasetItem.label_hash == label_hash,
    )
    if task.media_object_id is not None:
        statement = statement.where(LearningDatasetItem.media_object_id == task.media_object_id)
    else:
        statement = statement.where(
            LearningDatasetItem.learning_image_object_id == task.learning_image_object_id
        )
    return await session.scalar(statement.limit(1)) is not None


def _sha256_json(value: object) -> str:
    """Return a SHA-256 digest for deterministic JSON payloads.

    Args:
        value: JSON-serializable value.

    Returns:
        SHA-256 hexadecimal digest.
    """
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _failure_summary(*, dataset_version_id: UUID, error: BaseException) -> dict[str, object]:
    """Return a redacted failure summary.

    Args:
        dataset_version_id: Requested dataset version id.
        error: Raised error.

    Returns:
        Failure summary without source refs, task ids, owner hashes, or labels.
    """
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "error",
        "dataset_version_id": str(dataset_version_id),
        "error_type": type(error).__name__,
        "label_snapshot_printed": False,
        "source_ref_printed": False,
        "owner_subject_hash_printed": False,
        "raw_payload_printed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
    }


if __name__ == "__main__":
    main()
