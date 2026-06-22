"""Tests for accepted PaddleOCR annotation task promotion."""

from __future__ import annotations

import importlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from src.models.db.learning import LearningImageObject
from src.models.db.media import MediaObject
from src.models.db.retraining import AnnotationTask, LearningDatasetItem, LearningDatasetVersion

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

promoter = importlib.import_module("scripts.promote_paddleocr_annotation_tasks_to_dataset")


class _FakeScalarResult:
    """Fake SQLAlchemy scalar result."""

    def __init__(self, rows: list[AnnotationTask]) -> None:
        """Initialize result rows.

        Args:
            rows: Rows returned by ``all``.
        """
        self._rows = rows

    def all(self) -> list[AnnotationTask]:
        """Return all fake rows."""
        return self._rows


class _FakeSession:
    """Fake async session for PaddleOCR annotation promotion tests."""

    def __init__(
        self,
        *,
        dataset_version: LearningDatasetVersion | None,
        tasks: list[AnnotationTask],
        learning_images: list[LearningImageObject] | None = None,
        media_objects: list[MediaObject] | None = None,
        existing_items: list[LearningDatasetItem] | None = None,
    ) -> None:
        """Initialize fake database state.

        Args:
            dataset_version: Dataset version returned by ``get``.
            tasks: Accepted annotation tasks returned by ``scalars``.
            learning_images: Learning image source rows addressable by id.
            media_objects: Media source rows addressable by id.
            existing_items: Existing dataset items returned by duplicate checks.
        """
        self.dataset_version = dataset_version
        self.tasks = tasks
        self.learning_images = {row.id: row for row in learning_images or []}
        self.media_objects = {row.id: row for row in media_objects or []}
        self.existing_items = existing_items or []
        self.added: list[LearningDatasetItem] = []
        self.commit_count = 0

    async def get(self, model_type: object, row_id: UUID) -> object | None:
        """Return fake rows by model type and id.

        Args:
            model_type: ORM model class.
            row_id: Requested row id.

        Returns:
            Fake row or None.
        """
        if model_type is LearningDatasetVersion:
            if self.dataset_version is not None and self.dataset_version.id == row_id:
                return self.dataset_version
            return None
        if model_type is LearningImageObject:
            return self.learning_images.get(row_id)
        if model_type is MediaObject:
            return self.media_objects.get(row_id)
        return None

    async def scalars(self, _statement: object) -> _FakeScalarResult:
        """Return fake accepted annotation tasks."""
        return _FakeScalarResult(self.tasks)

    async def scalar(self, _statement: object) -> LearningDatasetItem | None:
        """Return one existing item when duplicate rows are configured."""
        if self.existing_items:
            return self.existing_items[0]
        return None

    def add(self, item: LearningDatasetItem) -> None:
        """Record a dataset item insert.

        Args:
            item: Dataset item to add.
        """
        self.added.append(item)

    async def commit(self) -> None:
        """Record a fake commit call."""
        self.commit_count += 1


class _FakeSessionContext:
    """Fake async session context manager."""

    def __init__(self, session: _FakeSession) -> None:
        """Initialize context session.

        Args:
            session: Fake session.
        """
        self.session = session

    async def __aenter__(self) -> _FakeSession:
        """Return the fake session."""
        return self.session

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        """Close the fake context."""
        _ = (exc_type, exc, traceback)


def _dataset_version(*, dataset_key: str) -> LearningDatasetVersion:
    """Build a dataset version fixture.

    Args:
        dataset_key: Dataset key.

    Returns:
        Dataset version fixture.
    """
    return LearningDatasetVersion(
        id=uuid4(),
        dataset_key=dataset_key,
        version="2026-06-03.paddleocr",
        status="draft",
        train_count=0,
        val_count=0,
        test_count=0,
        privacy_review_status="pending",
    )


def _annotation_task(
    *,
    label_snapshot: dict[str, object],
    media_object_id: UUID | None = None,
    learning_image_object_id: UUID | None = None,
) -> AnnotationTask:
    """Build an accepted OCR annotation task.

    Args:
        label_snapshot: OCR label payload.
        media_object_id: Optional media source id.
        learning_image_object_id: Optional learning image source id.

    Returns:
        Annotation task fixture.
    """
    return AnnotationTask(
        id=uuid4(),
        owner_subject_hash="a" * 64,
        media_object_id=media_object_id,
        learning_image_object_id=learning_image_object_id,
        task_type="ocr_textline_label",
        status="accepted",
        assignee_role="data_reviewer",
        label_snapshot=label_snapshot,
        review_notes_code="reviewed_ocr_label",
        reviewer_hash="b" * 64,
        completed_at=datetime(2026, 6, 3, tzinfo=UTC),
    )


def _learning_image_object(*, row_id: UUID) -> LearningImageObject:
    """Build a learning image source fixture.

    Args:
        row_id: Source id.

    Returns:
        Learning image object fixture.
    """
    return LearningImageObject(
        id=row_id,
        owner_subject_hash="a" * 64,
        analysis_id=uuid4(),
        image_sha256="c" * 64,
        object_uri="private-learning-object",
        object_storage_provider="local",
        object_version_id=None,
        image_mime_type="image/jpeg",
        image_size_bytes=2048,
        retained_until=datetime(2026, 7, 3, tzinfo=UTC),
        status="ready",
        consent_snapshot={"consent_type": "image_learning_dataset"},
        review_metadata_snapshot={},
        deleted_at=None,
    )


def _media_object(*, row_id: UUID) -> MediaObject:
    """Build a media source fixture.

    Args:
        row_id: Source id.

    Returns:
        Media object fixture.
    """
    return MediaObject(
        id=row_id,
        owner_subject_hash="a" * 64,
        domain="supplement_label",
        source_run_id=uuid4(),
        object_storage_provider="local",
        object_ref="private-media-object",
        object_version_id=None,
        image_sha256="d" * 64,
        image_mime_type="image/jpeg",
        image_size_bytes=4096,
        width_px=1200,
        height_px=1600,
        exif_stripped=True,
        retained_until=datetime(2026, 7, 3, tzinfo=UTC) + timedelta(days=1),
        status="retained",
        consent_snapshot={"consent_type": "image_learning_dataset"},
        deleted_at=None,
    )


def _existing_item(
    *,
    dataset_version_id: UUID,
    source_id: UUID,
    task_type: str = "paddleocr_recognition",
) -> LearningDatasetItem:
    """Build an existing dataset item fixture.

    Args:
        dataset_version_id: Dataset version id.
        source_id: Existing learning image source id.
        task_type: Existing task type.

    Returns:
        Existing dataset item.
    """
    return LearningDatasetItem(
        id=uuid4(),
        dataset_version_id=dataset_version_id,
        owner_subject_hash="a" * 64,
        learning_image_object_id=source_id,
        source_domain="supplement",
        task_type=task_type,
        label_status="human_reviewed",
        split="train",
        label_snapshot={"text_label": "Vitamin C 100 mg"},
        label_hash="e" * 64,
        quality_score=None,
        consent_snapshot={"source": "paddleocr_annotation_review"},
        retained_until=datetime(2026, 7, 3, tzinfo=UTC),
    )


def _patch_sessionmaker(monkeypatch: pytest.MonkeyPatch, session: _FakeSession) -> None:
    """Patch the script DB session factory.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        session: Fake session.
    """
    monkeypatch.setattr(
        promoter,
        "get_sessionmaker",
        lambda: lambda: _FakeSessionContext(session),
    )


@pytest.mark.asyncio
async def test_promote_recognition_annotation_task_to_dataset_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify accepted OCR text labels become recognition dataset items."""
    dataset = _dataset_version(dataset_key="supplement_ocr_recognition")
    source_id = uuid4()
    label_snapshot = {
        "text_label": "Vitamin C 100 mg",
        "crop_box": {
            "x_center": 0.5,
            "y_center": 0.5,
            "width": 0.4,
            "height": 0.2,
        },
    }
    task = _annotation_task(
        learning_image_object_id=source_id,
        label_snapshot=label_snapshot,
    )
    session = _FakeSession(
        dataset_version=dataset,
        tasks=[task],
        learning_images=[_learning_image_object(row_id=source_id)],
    )
    _patch_sessionmaker(monkeypatch, session)

    summary = await promoter.promote_accepted_paddleocr_annotation_tasks_to_dataset(
        dataset_version_id=dataset.id,
        dataset_task_type="paddleocr_recognition",
        split="train",
    )

    assert session.commit_count == 1
    assert summary["promoted_count"] == 1
    assert summary["scanned_count"] == 1
    assert len(session.added) == 1
    item = session.added[0]
    assert item.dataset_version_id == dataset.id
    assert item.learning_image_object_id == source_id
    assert item.media_object_id is None
    assert item.source_domain == "supplement"
    assert item.task_type == "paddleocr_recognition"
    assert item.label_status == "human_reviewed"
    assert item.label_snapshot == label_snapshot
    assert item.consent_snapshot == {
        "source": "paddleocr_annotation_review",
        "source_type": "learning_image_object",
        "dataset_task_type": "paddleocr_recognition",
    }
    serialized = json.dumps(summary, ensure_ascii=False)
    assert "Vitamin C" not in serialized
    assert source_id.hex not in serialized
    assert "a" * 64 not in serialized


@pytest.mark.asyncio
async def test_promote_detection_annotation_task_to_dataset_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify accepted OCR textline boxes become detection dataset items."""
    dataset = _dataset_version(dataset_key="supplement_ocr_detection")
    source_id = uuid4()
    task = _annotation_task(
        media_object_id=source_id,
        label_snapshot={
            "textline_boxes": [
                {
                    "class_id": 0,
                    "x_center": 0.5,
                    "y_center": 0.5,
                    "width": 0.4,
                    "height": 0.1,
                }
            ]
        },
    )
    session = _FakeSession(
        dataset_version=dataset,
        tasks=[task],
        media_objects=[_media_object(row_id=source_id)],
    )
    _patch_sessionmaker(monkeypatch, session)

    summary = await promoter.promote_accepted_paddleocr_annotation_tasks_to_dataset(
        dataset_version_id=dataset.id,
        dataset_task_type="paddleocr_detection",
        split="val",
    )

    assert summary["promoted_count"] == 1
    item = session.added[0]
    assert item.media_object_id == source_id
    assert item.learning_image_object_id is None
    assert item.task_type == "paddleocr_detection"
    assert item.split == "val"
    assert item.consent_snapshot["source_type"] == "media_object"


@pytest.mark.asyncio
async def test_promote_rejects_incompatible_dataset_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify recognition rows cannot target a detection dataset version."""
    dataset = _dataset_version(dataset_key="supplement_ocr_detection")
    session = _FakeSession(dataset_version=dataset, tasks=[])
    _patch_sessionmaker(monkeypatch, session)

    with pytest.raises(ValueError, match="not compatible"):
        await promoter.promote_accepted_paddleocr_annotation_tasks_to_dataset(
            dataset_version_id=dataset.id,
            dataset_task_type="paddleocr_recognition",
        )


@pytest.mark.asyncio
async def test_promote_skips_label_not_matching_task_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify malformed labels are skipped before dataset insertion."""
    dataset = _dataset_version(dataset_key="supplement_ocr_recognition")
    source_id = uuid4()
    task = _annotation_task(
        learning_image_object_id=source_id,
        label_snapshot={"textline_boxes": []},
    )
    session = _FakeSession(
        dataset_version=dataset,
        tasks=[task],
        learning_images=[_learning_image_object(row_id=source_id)],
    )
    _patch_sessionmaker(monkeypatch, session)

    summary = await promoter.promote_accepted_paddleocr_annotation_tasks_to_dataset(
        dataset_version_id=dataset.id,
        dataset_task_type="paddleocr_recognition",
    )

    assert summary["promoted_count"] == 0
    assert summary["rejected_label_count"] == 1
    assert session.added == []


@pytest.mark.asyncio
async def test_promote_skips_existing_dataset_item(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify duplicate source/label rows are not inserted twice."""
    dataset = _dataset_version(dataset_key="supplement_ocr_recognition")
    source_id = uuid4()
    task = _annotation_task(
        learning_image_object_id=source_id,
        label_snapshot={"text_label": "Vitamin C 100 mg"},
    )
    session = _FakeSession(
        dataset_version=dataset,
        tasks=[task],
        learning_images=[_learning_image_object(row_id=source_id)],
        existing_items=[_existing_item(dataset_version_id=dataset.id, source_id=source_id)],
    )
    _patch_sessionmaker(monkeypatch, session)

    summary = await promoter.promote_accepted_paddleocr_annotation_tasks_to_dataset(
        dataset_version_id=dataset.id,
        dataset_task_type="paddleocr_recognition",
    )

    assert summary["promoted_count"] == 0
    assert summary["skipped_existing_count"] == 1
    assert session.added == []


def test_cli_failure_summary_is_redacted(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI failure output does not print private labels or refs."""
    dataset_id = uuid4()
    session = _FakeSession(dataset_version=None, tasks=[])
    _patch_sessionmaker(monkeypatch, session)

    with pytest.raises(SystemExit) as exc_info:
        promoter.main(
            [
                "--dataset-version-id",
                str(dataset_id),
                "--dataset-task-type",
                "paddleocr_recognition",
            ]
        )

    stdout = capsys.readouterr().out
    assert exc_info.value.code == 1
    assert "ValueError" in stdout
    assert "Vitamin C" not in stdout
    assert "media:" not in stdout
    assert "label_snapshot_printed" in stdout
