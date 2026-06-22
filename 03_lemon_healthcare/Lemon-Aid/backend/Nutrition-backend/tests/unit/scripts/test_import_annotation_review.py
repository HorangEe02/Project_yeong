"""Tests for operator annotation review import CLI."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from src.learning.retraining import RetrainingSecurityError
from src.models.db.retraining import AnnotationTask

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

review_importer = importlib.import_module("scripts.import_annotation_review")


class _FakeSession:
    """Fake async session for annotation review import tests."""

    def __init__(self, tasks: list[AnnotationTask]) -> None:
        """Initialize fake tasks.

        Args:
            tasks: Annotation tasks addressable by id.
        """
        self.tasks = {task.id: task for task in tasks}
        self.commit_count = 0

    async def get(self, model_type: object, row_id: UUID) -> object | None:
        """Return fake rows by ORM type and id.

        Args:
            model_type: ORM model class.
            row_id: Requested row id.

        Returns:
            Fake row or None.
        """
        if model_type is AnnotationTask:
            return self.tasks.get(row_id)
        return None

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


def _annotation_task(*, status: str = "pending") -> AnnotationTask:
    """Build an annotation task fixture.

    Args:
        status: Initial task status.

    Returns:
        Annotation task fixture.
    """
    return AnnotationTask(
        id=uuid4(),
        owner_subject_hash="a" * 64,
        media_object_id=uuid4(),
        task_type="ocr_textline_label",
        status=status,
        assignee_role="data_reviewer",
        label_snapshot={},
        review_notes_code=None,
        reviewer_hash=None,
        completed_at=None,
    )


def _patch_sessionmaker(monkeypatch: pytest.MonkeyPatch, session: _FakeSession) -> None:
    """Patch the script DB session factory.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        session: Fake session.
    """
    monkeypatch.setattr(
        review_importer,
        "get_sessionmaker",
        lambda: lambda: _FakeSessionContext(session),
    )


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    """Write JSONL records.

    Args:
        path: Output path.
        records: Records to write.
    """
    path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records
        ),
        encoding="utf-8",
    )


def test_load_annotation_review_decisions_validates_and_sanitizes_rejections(
    tmp_path: Path,
) -> None:
    """Verify JSONL records become sanitized decisions."""
    accepted_id = uuid4()
    rejected_id = uuid4()
    input_path = tmp_path / "reviews.jsonl"
    _write_jsonl(
        input_path,
        [
            {
                "annotation_task_id": str(accepted_id),
                "decision": "accept",
                "reviewer_hash": "b" * 64,
                "review_notes_code": "ok",
                "label_snapshot": {"text_label": "Confirmed Label 100 mg"},
            },
            {
                "annotation_task_id": str(rejected_id),
                "decision": "reject",
                "reviewer_hash": "c" * 64,
                "review_notes_code": "bad_crop",
                "label_snapshot": {"text_label": "Discarded Value"},
            },
        ],
    )

    decisions = review_importer.load_annotation_review_decisions(input_path)

    assert len(decisions) == 2
    assert decisions[0].annotation_task_id == accepted_id
    assert decisions[0].label_snapshot == {"text_label": "Confirmed Label 100 mg"}
    assert decisions[1].annotation_task_id == rejected_id
    assert decisions[1].label_snapshot == {}


@pytest.mark.asyncio
async def test_import_annotation_review_decisions_updates_tasks_in_one_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify accepted/rejected decisions update tasks with sanitized labels."""
    accepted_task = _annotation_task(status="pending")
    rejected_task = _annotation_task(status="in_review")
    session = _FakeSession([accepted_task, rejected_task])
    _patch_sessionmaker(monkeypatch, session)
    decisions = [
        review_importer.AnnotationReviewDecision(
            annotation_task_id=accepted_task.id,
            decision="accept",
            label_snapshot={"text_label": "Confirmed Label 100 mg"},
            review_notes_code="ok",
            reviewer_hash="d" * 64,
        ),
        review_importer.AnnotationReviewDecision(
            annotation_task_id=rejected_task.id,
            decision="reject",
            label_snapshot={},
            review_notes_code="bad_crop",
            reviewer_hash="e" * 64,
        ),
    ]

    summary = await review_importer.import_annotation_review_decisions(decisions)

    assert session.commit_count == 1
    assert accepted_task.status == "accepted"
    assert accepted_task.label_snapshot == {"text_label": "Confirmed Label 100 mg"}
    assert accepted_task.review_notes_code == "ok"
    assert accepted_task.reviewer_hash == "d" * 64
    assert accepted_task.completed_at is not None
    assert rejected_task.status == "rejected"
    assert rejected_task.label_snapshot == {}
    assert summary["accepted_count"] == 1
    assert summary["rejected_count"] == 1
    serialized = json.dumps(summary, ensure_ascii=False)
    assert "Confirmed Label" not in serialized
    assert "d" * 64 not in serialized


@pytest.mark.asyncio
async def test_import_annotation_review_decisions_rejects_non_updateable_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify cancelled tasks block the whole import before commit."""
    task = _annotation_task(status="cancelled")
    session = _FakeSession([task])
    _patch_sessionmaker(monkeypatch, session)
    decisions = [
        review_importer.AnnotationReviewDecision(
            annotation_task_id=task.id,
            decision="accept",
            label_snapshot={"text_label": "Confirmed Label 100 mg"},
            review_notes_code="ok",
            reviewer_hash="f" * 64,
        )
    ]

    with pytest.raises(ValueError, match="not updateable"):
        await review_importer.import_annotation_review_decisions(decisions)

    assert task.status == "cancelled"
    assert task.label_snapshot == {}
    assert session.commit_count == 0


def test_load_annotation_review_decisions_rejects_raw_payload_keys(tmp_path: Path) -> None:
    """Verify raw OCR/provider/url fields cannot enter reviewer labels."""
    input_path = tmp_path / "reviews.jsonl"
    _write_jsonl(
        input_path,
        [
            {
                "annotation_task_id": str(uuid4()),
                "decision": "accept",
                "reviewer_hash": "a" * 64,
                "label_snapshot": {"raw_ocr_text": "unreviewed"},
            }
        ],
    )

    with pytest.raises(RetrainingSecurityError, match="Forbidden label snapshot key"):
        review_importer.load_annotation_review_decisions(input_path)


@pytest.mark.asyncio
async def test_run_cli_outputs_redacted_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI stdout excludes labels, reviewer hash, and input path."""
    task = _annotation_task(status="pending")
    session = _FakeSession([task])
    input_path = tmp_path / "reviews.jsonl"
    _write_jsonl(
        input_path,
        [
            {
                "annotation_task_id": str(task.id),
                "decision": "accept",
                "reviewer_hash": "b" * 64,
                "label_snapshot": {"text_label": "Confirmed Label 100 mg"},
            }
        ],
    )
    _patch_sessionmaker(monkeypatch, session)

    exit_code = await review_importer.run_cli(["--input", str(input_path)])

    stdout = capsys.readouterr().out
    assert exit_code == 0
    assert "accepted_count" in stdout
    assert "Confirmed Label" not in stdout
    assert "b" * 64 not in stdout
    assert str(tmp_path) not in stdout
