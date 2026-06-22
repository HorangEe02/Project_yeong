"""Tests for operator-only retraining manifest export."""

from __future__ import annotations

import importlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from src.learning.retraining import RetrainingSecurityError
from src.models.db.retraining import LearningDatasetItem, LearningDatasetVersion

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

manifest_exporter = importlib.import_module("scripts.export_training_manifest")


class _FakeScalarResult:
    """Fake SQLAlchemy scalar result."""

    def __init__(self, rows: list[LearningDatasetItem]) -> None:
        """Initialize result rows.

        Args:
            rows: Rows returned by ``all``.
        """
        self._rows = rows

    def all(self) -> list[LearningDatasetItem]:
        """Return all fake rows."""
        return self._rows


class _FakeSession:
    """Fake async session for manifest export tests."""

    def __init__(
        self,
        *,
        dataset_version: LearningDatasetVersion | None,
        rows: list[LearningDatasetItem],
    ) -> None:
        """Initialize fake query results.

        Args:
            dataset_version: Dataset version returned by ``get``.
            rows: Dataset item rows returned by ``scalars``.
        """
        self.dataset_version = dataset_version
        self.rows = rows

    async def get(self, _model: object, dataset_version_id: UUID) -> LearningDatasetVersion | None:
        """Return the fake dataset version when ids match.

        Args:
            _model: Ignored ORM model.
            dataset_version_id: Requested dataset version id.

        Returns:
            Dataset version or None.
        """
        if self.dataset_version is not None and self.dataset_version.id == dataset_version_id:
            return self.dataset_version
        return None

    async def scalars(self, _statement: object) -> _FakeScalarResult:
        """Return fake scalar rows."""
        return _FakeScalarResult(self.rows)


class _FakeSessionContext:
    """Fake async session context manager."""

    def __init__(
        self,
        *,
        dataset_version: LearningDatasetVersion | None,
        rows: list[LearningDatasetItem],
    ) -> None:
        """Initialize context rows.

        Args:
            dataset_version: Dataset version returned by the fake session.
            rows: Dataset item rows returned by the fake session.
        """
        self.session = _FakeSession(dataset_version=dataset_version, rows=rows)

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


def _dataset(
    *,
    dataset_id: UUID | None = None,
    status: str = "frozen",
    privacy_review_status: str = "approved",
) -> LearningDatasetVersion:
    """Build a dataset version fixture.

    Args:
        dataset_id: Optional fixed dataset id.
        status: Dataset lifecycle status.
        privacy_review_status: Dataset privacy review status.

    Returns:
        Learning dataset version fixture.
    """
    return LearningDatasetVersion(
        id=dataset_id or uuid4(),
        dataset_key="supplement_ocr_recognition",
        version="2026-05-27.2",
        status=status,
        train_count=1,
        val_count=0,
        test_count=0,
        privacy_review_status=privacy_review_status,
    )


def _dataset_item(
    *,
    dataset_version_id: UUID,
    task_type: str = "paddleocr_recognition",
    label_snapshot: dict[str, object] | None = None,
) -> LearningDatasetItem:
    """Build a dataset item fixture.

    Args:
        dataset_version_id: Parent dataset version id.
        task_type: Learning task type.
        label_snapshot: Sanitized label snapshot.

    Returns:
        Learning dataset item fixture.
    """
    return LearningDatasetItem(
        id=uuid4(),
        dataset_version_id=dataset_version_id,
        owner_subject_hash="a" * 64,
        media_object_id=uuid4(),
        source_domain="supplement",
        task_type=task_type,
        label_status="human_reviewed",
        split="train",
        label_snapshot=label_snapshot or {"text_label": "Confirmed OCR Label 100 mg"},
        label_hash="b" * 64,
        quality_score=None,
        consent_snapshot={"consent_type": "image_learning_dataset"},
        retained_until=datetime(2026, 6, 27, tzinfo=UTC) + timedelta(days=1),
    )


def _patch_sessionmaker(
    monkeypatch: pytest.MonkeyPatch,
    *,
    dataset_version: LearningDatasetVersion | None,
    rows: list[LearningDatasetItem],
) -> None:
    """Patch the script DB session factory.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        dataset_version: Fake dataset version row.
        rows: Fake dataset item rows.
    """
    monkeypatch.setattr(
        manifest_exporter,
        "get_sessionmaker",
        lambda: lambda: _FakeSessionContext(dataset_version=dataset_version, rows=rows),
    )


@pytest.mark.asyncio
async def test_export_training_manifest_returns_redacted_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify task exports write labels only to artifacts, not stdout summaries."""
    dataset = _dataset()
    item = _dataset_item(
        dataset_version_id=dataset.id,
        label_snapshot={
            "text_label": "Confirmed OCR Label 100 mg",
            "crop_box": {
                "x_center": 0.5,
                "y_center": 0.5,
                "width": 0.4,
                "height": 0.2,
            },
        },
    )
    _patch_sessionmaker(monkeypatch, dataset_version=dataset, rows=[item])

    artifact, summary = await manifest_exporter.export_training_manifest(
        dataset_version_id=dataset.id,
        export_kind="paddleocr_recognition",
    )

    assert artifact["schema_version"] == "learning-paddleocr-rec-export-v1"
    assert artifact["items"][0]["text_label"] == "Confirmed OCR Label 100 mg"
    assert artifact["items"][0]["recognition_source"] == "source_image_crop"
    assert artifact["items"][0]["crop_box"] == {
        "x_center": 0.5,
        "y_center": 0.5,
        "width": 0.4,
        "height": 0.2,
    }
    assert summary["item_count"] == 1
    serialized_summary = json.dumps(summary, ensure_ascii=False)
    assert "Confirmed OCR Label" not in serialized_summary
    assert "media:" not in serialized_summary
    assert "a" * 64 not in serialized_summary
    assert "unreviewed text" not in serialized_summary


@pytest.mark.asyncio
async def test_export_training_manifest_supports_supplement_section_yolo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify operator export can emit supplement section YOLO contracts."""
    dataset = _dataset()
    item = _dataset_item(
        dataset_version_id=dataset.id,
        task_type="yolo_detection",
        label_snapshot={
            "boxes": [
                {
                    "label": "supplement_facts",
                    "x_center": 0.5,
                    "y_center": 0.5,
                    "width": 0.6,
                    "height": 0.4,
                },
                {
                    "label": "warning",
                    "x_center": 0.5,
                    "y_center": 0.8,
                    "width": 0.6,
                    "height": 0.2,
                },
            ]
        },
    )
    _patch_sessionmaker(monkeypatch, dataset_version=dataset, rows=[item])

    artifact, summary = await manifest_exporter.export_training_manifest(
        dataset_version_id=dataset.id,
        export_kind="supplement_section_yolo_detection",
    )

    assert artifact["schema_version"] == "supplement-section-yolo-detect-export-v1"
    assert artifact["class_names"] == [
        "product_identity",
        "supplement_facts",
        "ingredient_amounts",
        "precautions",
        "allergen_warning",
        "intake_method",
        "other_ingredients",
        "functional_claims",
    ]
    assert artifact["items"][0]["labels"][1]["label"] == "precautions"
    assert summary["export_kind"] == "supplement_section_yolo_detection"
    serialized_summary = json.dumps(summary, ensure_ascii=False)
    assert "media:" not in serialized_summary
    assert "supplement_facts" not in serialized_summary
    assert "precautions" not in serialized_summary


def test_main_writes_manifest_and_summary_without_printing_private_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI output is redacted while the operator artifact is written."""
    dataset = _dataset()
    item = _dataset_item(dataset_version_id=dataset.id)
    output_path = tmp_path / "manifest.json"
    _patch_sessionmaker(monkeypatch, dataset_version=dataset, rows=[item])

    manifest_exporter.main(
        [
            "--dataset-version-id",
            str(dataset.id),
            "--export-kind",
            "paddleocr_recognition",
            "--output",
            str(output_path),
        ]
    )

    stdout = capsys.readouterr().out
    assert output_path.exists()
    assert output_path.with_suffix(".json.summary.json").exists()
    assert "Confirmed OCR Label" not in stdout
    assert "media:" not in stdout
    assert str(tmp_path) not in stdout
    assert "/private/" not in stdout
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["items"][0]["text_label"] == "Confirmed OCR Label 100 mg"
    assert written["items"][0]["recognition_source"] == "pre_cropped_image"


@pytest.mark.asyncio
async def test_export_training_manifest_rejects_raw_payload_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify raw OCR/provider/url fields cannot enter operator exports."""
    dataset = _dataset()
    item = _dataset_item(
        dataset_version_id=dataset.id,
        label_snapshot={
            "raw_ocr_text": "unreviewed text",
            "public_url": "https://example.com/object",
        },
    )
    _patch_sessionmaker(monkeypatch, dataset_version=dataset, rows=[item])

    with pytest.raises(RetrainingSecurityError, match="Forbidden label snapshot key"):
        await manifest_exporter.export_training_manifest(
            dataset_version_id=dataset.id,
            export_kind="dataset",
        )


def test_main_failure_summary_omits_private_output_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify failure output reveals only error class and a path hash."""
    dataset = _dataset(privacy_review_status="pending")
    item = _dataset_item(dataset_version_id=dataset.id)
    output_path = tmp_path / "manifest.json"
    _patch_sessionmaker(monkeypatch, dataset_version=dataset, rows=[item])

    with pytest.raises(SystemExit) as exc_info:
        manifest_exporter.main(
            [
                "--dataset-version-id",
                str(dataset.id),
                "--output",
                str(output_path),
            ]
        )

    stdout = capsys.readouterr().out
    assert exc_info.value.code == 1
    assert "DatasetFreezeError" in stdout
    assert str(tmp_path) not in stdout
    assert "output_path_hash" in stdout
