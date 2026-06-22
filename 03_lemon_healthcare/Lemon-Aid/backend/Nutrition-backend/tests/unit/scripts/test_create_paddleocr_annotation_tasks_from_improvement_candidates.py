"""Tests for creating PaddleOCR annotation tasks from improvement candidates."""

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
from src.models.db.retraining import AnnotationTask

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

creator = importlib.import_module(
    "scripts.create_paddleocr_annotation_tasks_from_improvement_candidates"
)


class _FakeSession:
    """Fake async session for annotation task creation tests."""

    def __init__(
        self,
        *,
        learning_images: list[LearningImageObject] | None = None,
        media_objects: list[MediaObject] | None = None,
        existing_task: AnnotationTask | None = None,
    ) -> None:
        """Initialize fake database state.

        Args:
            learning_images: Learning image source rows addressable by id.
            media_objects: Media source rows addressable by id.
            existing_task: Existing active task returned by duplicate checks.
        """
        self.learning_images = {row.id: row for row in learning_images or []}
        self.media_objects = {row.id: row for row in media_objects or []}
        self.existing_task = existing_task
        self.added: list[AnnotationTask] = []
        self.commit_count = 0

    async def get(self, model_type: object, row_id: UUID) -> object | None:
        """Return fake rows by model type and id."""
        if model_type is LearningImageObject:
            return self.learning_images.get(row_id)
        if model_type is MediaObject:
            return self.media_objects.get(row_id)
        return None

    async def scalar(self, _statement: object) -> AnnotationTask | None:
        """Return an existing task when configured."""
        return self.existing_task

    def add(self, task: AnnotationTask) -> None:
        """Record an annotation task insert.

        Args:
            task: Task to add.
        """
        self.added.append(task)

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
        """Return fake session."""
        return self.session

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        """Close fake context."""
        _ = (exc_type, exc, traceback)


def _patch_sessionmaker(monkeypatch: pytest.MonkeyPatch, session: _FakeSession) -> None:
    """Patch the script DB session factory.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        session: Fake session.
    """
    monkeypatch.setattr(
        creator,
        "get_sessionmaker",
        lambda: lambda: _FakeSessionContext(session),
    )


def _write_manifest(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL candidate rows.

    Args:
        path: Output path.
        rows: JSON object rows.
    """
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _candidate_row(*, source_ref: str) -> dict[str, object]:
    """Build a safe improvement candidate row.

    Args:
        source_ref: Candidate source ref.

    Returns:
        Improvement candidate fixture.
    """
    return {
        "schema_version": "supplement-paddleocr-improvement-candidate-v1",
        "source_run_id": "run-20260603",
        "fixture_id": "fixture-001",
        "source_ref": source_ref,
        "image_ref_hash": "b" * 64,
        "image_sha256": "c" * 64,
        "category_key": "vitamin",
        "source_kind": "review",
        "target_provider": "paddleocr_local",
        "teacher_providers": ["clova_ocr", "google_vision_document"],
        "expected": {
            "verification_status": "human_reviewed",
            "product_name": "Lemon Aid Test",
            "manufacturer": "Lemon Healthcare",
            "ingredients": [{"display_name": "Vitamin C", "amount": 100, "unit": "mg"}],
            "intake_method": {"text": "daily"},
            "precautions": [],
            "functional_claims": [],
            "label_sections": [{"section_type": "supplement_facts"}],
        },
        "failure_codes": ["ingredient_amount_unit_miss"],
        "score_snapshot": {
            "expected_ingredient_count": 1,
            "observed_ingredient_count": 0,
            "teacher_expected_match_count": 1,
        },
        "training_task_suggestions": ["paddleocr_recognition"],
        "recommended_next_step": "paddleocr_recognition_manual_review",
        "requires_manual_review": True,
        "ready_for_training_export": False,
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
    }


def _learning_image_object(*, row_id: UUID, owner_hash: str = "a" * 64) -> LearningImageObject:
    """Build a learning image source fixture.

    Args:
        row_id: Source id.
        owner_hash: Source owner hash.

    Returns:
        Learning image object fixture.
    """
    return LearningImageObject(
        id=row_id,
        owner_subject_hash=owner_hash,
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


def _media_object(*, row_id: UUID, owner_hash: str = "a" * 64) -> MediaObject:
    """Build a media source fixture.

    Args:
        row_id: Source id.
        owner_hash: Source owner hash.

    Returns:
        Media object fixture.
    """
    return MediaObject(
        id=row_id,
        owner_subject_hash=owner_hash,
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


def _existing_task(*, source_id: UUID) -> AnnotationTask:
    """Build an existing active OCR annotation task.

    Args:
        source_id: Learning image source id.

    Returns:
        Existing annotation task fixture.
    """
    return AnnotationTask(
        id=uuid4(),
        owner_subject_hash="a" * 64,
        media_object_id=None,
        learning_image_object_id=source_id,
        task_type="ocr_textline_label",
        status="pending",
        assignee_role="data_reviewer",
        label_snapshot={"schema_version": "existing"},
        review_notes_code="paddleocr_improvement_candidate",
        reviewer_hash=None,
        completed_at=None,
    )


@pytest.mark.asyncio
async def test_create_learning_image_backed_annotation_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a DB-backed learning image candidate creates a pending task."""
    source_id = uuid4()
    manifest = tmp_path / "candidates.jsonl"
    _write_manifest(manifest, [_candidate_row(source_ref=f"learning_image:{source_id}")])
    session = _FakeSession(learning_images=[_learning_image_object(row_id=source_id)])
    _patch_sessionmaker(monkeypatch, session)

    summary = await creator.create_paddleocr_annotation_tasks_from_improvement_candidates(
        improvement_manifest=manifest,
        owner_subject_hash="a" * 64,
    )

    assert session.commit_count == 1
    assert summary["created_count"] == 1
    assert summary["annotation_task_write_performed"] is True
    assert len(session.added) == 1
    task = session.added[0]
    assert task.learning_image_object_id == source_id
    assert task.media_object_id is None
    assert task.task_type == "ocr_textline_label"
    assert task.status == "pending"
    assert task.review_notes_code == "paddleocr_improvement_candidate"
    assert task.label_snapshot["target_dataset_task_types"] == ["paddleocr_recognition"]
    assert task.label_snapshot["expected_snapshot"]["ingredients"][0]["display_name"] == "Vitamin C"
    serialized_summary = json.dumps(summary, ensure_ascii=False)
    assert "Vitamin C" not in serialized_summary
    assert source_id.hex not in serialized_summary
    assert "a" * 64 not in serialized_summary


@pytest.mark.asyncio
async def test_create_media_backed_annotation_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a retained media object candidate creates a pending task."""
    source_id = uuid4()
    manifest = tmp_path / "candidates.jsonl"
    _write_manifest(manifest, [_candidate_row(source_ref=f"media:{source_id}")])
    session = _FakeSession(media_objects=[_media_object(row_id=source_id)])
    _patch_sessionmaker(monkeypatch, session)

    summary = await creator.create_paddleocr_annotation_tasks_from_improvement_candidates(
        improvement_manifest=manifest,
        owner_subject_hash="a" * 64,
    )

    assert summary["created_count"] == 1
    task = session.added[0]
    assert task.media_object_id == source_id
    assert task.learning_image_object_id is None


@pytest.mark.asyncio
async def test_skip_file_only_crawling_image_source_ref(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify file-only candidates are skipped until materialized into DB rows."""
    manifest = tmp_path / "candidates.jsonl"
    _write_manifest(manifest, [_candidate_row(source_ref="crawling-image:abc123")])
    session = _FakeSession()
    _patch_sessionmaker(monkeypatch, session)

    summary = await creator.create_paddleocr_annotation_tasks_from_improvement_candidates(
        improvement_manifest=manifest,
        owner_subject_hash="a" * 64,
    )

    assert summary["created_count"] == 0
    assert summary["skip_reason_counts"] == {"unsupported_source_ref": 1}
    assert session.added == []


@pytest.mark.asyncio
async def test_skip_existing_active_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify duplicate active OCR tasks are not inserted twice."""
    source_id = uuid4()
    manifest = tmp_path / "candidates.jsonl"
    _write_manifest(manifest, [_candidate_row(source_ref=f"learning_image:{source_id}")])
    session = _FakeSession(
        learning_images=[_learning_image_object(row_id=source_id)],
        existing_task=_existing_task(source_id=source_id),
    )
    _patch_sessionmaker(monkeypatch, session)

    summary = await creator.create_paddleocr_annotation_tasks_from_improvement_candidates(
        improvement_manifest=manifest,
        owner_subject_hash="a" * 64,
    )

    assert summary["created_count"] == 0
    assert summary["skip_reason_counts"] == {"existing_active_task": 1}
    assert session.added == []


@pytest.mark.asyncio
async def test_reject_unsafe_candidate_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify raw OCR/provider keys are skipped before task creation."""
    source_id = uuid4()
    manifest = tmp_path / "candidates.jsonl"
    row = _candidate_row(source_ref=f"learning_image:{source_id}")
    row["raw_ocr_text"] = "Vitamin C 100 mg"
    _write_manifest(manifest, [row])
    session = _FakeSession(learning_images=[_learning_image_object(row_id=source_id)])
    _patch_sessionmaker(monkeypatch, session)

    summary = await creator.create_paddleocr_annotation_tasks_from_improvement_candidates(
        improvement_manifest=manifest,
        owner_subject_hash="a" * 64,
    )

    assert summary["created_count"] == 0
    assert summary["skip_reason_counts"] == {"unsafe_candidate_payload": 1}
    serialized_summary = json.dumps(summary, ensure_ascii=False)
    assert "Vitamin C" not in serialized_summary
    assert "raw_ocr_text" not in serialized_summary


def test_cli_failure_summary_is_redacted(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI parameter failures do not print private labels or refs."""
    manifest = tmp_path / "candidates.jsonl"
    source_id = uuid4()
    _write_manifest(manifest, [_candidate_row(source_ref=f"learning_image:{source_id}")])

    with pytest.raises(SystemExit) as exc_info:
        creator.main(
            [
                "--improvement-manifest",
                str(manifest),
                "--owner-subject-hash",
                "not-a-hash",
            ]
        )

    stdout = capsys.readouterr().out
    assert exc_info.value.code == 1
    assert "ValueError" in stdout
    assert "Vitamin C" not in stdout
    assert "learning_image:" not in stdout
    assert source_id.hex not in stdout
    assert "owner_subject_hash_printed" in stdout
