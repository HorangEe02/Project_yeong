"""Tests for importing benchmark fixture images as MediaObject rows."""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from src.models.db.media import MediaObject

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

importer = importlib.import_module("scripts.import_supplement_benchmark_fixtures_as_media_objects")


class _FakeSession:
    """Fake async session for media import tests."""

    def __init__(self, *, existing_media: MediaObject | None = None) -> None:
        """Initialize fake DB state.

        Args:
            existing_media: Optional existing MediaObject returned by lookup.
        """
        self.existing_media = existing_media
        self.added: list[MediaObject] = []
        self.commit_count = 0
        self.scalar_count = 0

    async def scalar(self, _statement: object) -> MediaObject | None:
        """Return a configured existing media row."""
        self.scalar_count += 1
        return self.existing_media

    def add(self, media_object: MediaObject) -> None:
        """Record a MediaObject insert.

        Args:
            media_object: Media object to persist.
        """
        self.added.append(media_object)

    async def commit(self) -> None:
        """Record a fake commit."""
        self.commit_count += 1


class _FakeSessionContext:
    """Fake async session context manager."""

    def __init__(self, session: _FakeSession) -> None:
        """Initialize context.

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
        """Exit fake context."""
        _ = (exc_type, exc, traceback)


def _patch_sessionmaker(monkeypatch: pytest.MonkeyPatch, session: _FakeSession) -> None:
    """Patch importer DB session factory.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        session: Fake session.
    """
    monkeypatch.setattr(importer, "get_sessionmaker", lambda: lambda: _FakeSessionContext(session))


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL rows.

    Args:
        path: Destination path.
        rows: JSON object rows.
    """
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _benchmark_row(*, image_path: str, image_bytes: bytes) -> dict[str, object]:
    """Return a safe benchmark row.

    Args:
        image_path: Relative image path.
        image_bytes: Fixture image bytes.

    Returns:
        Benchmark manifest row.
    """
    image_sha256 = hashlib.sha256(image_bytes).hexdigest()
    return {
        "schema_version": "supplement-ocr-provider-benchmark-fixture-v1",
        "source_run_id": "benchmark-test",
        "fixture_id": "fixture-001",
        "source_ref": "crawling-image:" + ("a" * 32),
        "image_ref_hash": "b" * 64,
        "image_sha256": image_sha256,
        "image_size_bytes": len(image_bytes),
        "image_mime_type": "image/jpeg",
        "category_key": "vitamin",
        "source_kind": "review",
        "expected": {
            "verification_status": "human_reviewed",
            "product_name": "Sensitive Expected Product",
            "manufacturer": "Expected Brand",
            "ingredients": [{"display_name": "Vitamin C", "amount": 100, "unit": "mg"}],
            "intake_method": {"text": "Take once daily."},
            "precautions": [{"text": "Do not exceed recommended dose."}],
            "functional_claims": [],
            "label_sections": [{"section_type": "supplement_facts"}],
        },
        "benchmark_providers": ["clova_ocr", "google_vision_document", "paddleocr_local"],
        "teacher_providers": ["clova_ocr", "google_vision_document"],
        "target_provider": "paddleocr_local",
        "metric_plan": {"text_metrics": ["cer", "wer"]},
        "image_materialization_required": False,
        "image_materialization_policy": "private_hashed_fixture_copy_materialized",
        "paddleocr_training_candidate": True,
        "requires_human_review": False,
        "contains_personal_data": False,
        "pii_screening_status": "operator_cleared_no_personal_data",
        "external_transfer_allowed": True,
        "teacher_ocr_allowed": True,
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "image_path": image_path,
    }


def _media_object(*, row_id: UUID, owner_hash: str, image_sha256: str) -> MediaObject:
    """Build an existing MediaObject fixture.

    Args:
        row_id: Media object id.
        owner_hash: Source owner hash.
        image_sha256: Image content hash.

    Returns:
        Existing media object fixture.
    """
    return MediaObject(
        id=row_id,
        owner_subject_hash=owner_hash,
        domain="supplement_label",
        source_run_id=uuid4(),
        object_storage_provider="local",
        object_ref="supplement/ocr-benchmark/existing/object.jpg",
        object_version_id=None,
        image_sha256=image_sha256,
        image_mime_type="image/jpeg",
        image_size_bytes=128,
        width_px=None,
        height_px=None,
        exif_stripped=False,
        retained_until=datetime(2026, 7, 3, tzinfo=UTC) + timedelta(days=1),
        status="retained",
        consent_snapshot={"consent_type": "image_learning_dataset"},
        deleted_at=None,
    )


@pytest.mark.asyncio
async def test_dry_run_validates_fixture_without_writes(tmp_path: Path) -> None:
    """Verify dry-run scans fixture rows without DB writes or output manifest."""
    image_bytes = b"jpeg-like-content"
    image_root = tmp_path / "fixtures"
    image_path = image_root / "fixture-001.jpg"
    image_root.mkdir()
    image_path.write_bytes(image_bytes)
    manifest = tmp_path / "benchmark.jsonl"
    output_manifest = tmp_path / "rewritten.jsonl"
    _write_jsonl(manifest, [_benchmark_row(image_path="fixture-001.jpg", image_bytes=image_bytes)])

    summary = await importer.import_benchmark_fixtures_as_media_objects(
        benchmark_manifest=manifest,
        image_root=image_root,
        local_media_root=tmp_path / "media",
        output_manifest=output_manifest,
        owner_subject_hash="a" * 64,
        apply=False,
    )

    assert summary["status"] == "ok"
    assert summary["validated_fixture_count"] == 1
    assert summary["rewritten_count"] == 0
    assert summary["media_object_write_performed"] is False
    assert summary["local_copy_performed"] is False
    assert output_manifest.exists() is False


@pytest.mark.asyncio
async def test_apply_creates_media_object_and_rewrites_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify apply imports a fixture and rewrites source_ref to media UUID."""
    image_bytes = b"jpeg-like-content"
    image_root = tmp_path / "fixtures"
    image_path = image_root / "fixture-001.jpg"
    image_root.mkdir()
    image_path.write_bytes(image_bytes)
    row = _benchmark_row(image_path="fixture-001.jpg", image_bytes=image_bytes)
    manifest = tmp_path / "benchmark.jsonl"
    output_manifest = tmp_path / "rewritten.jsonl"
    local_media_root = tmp_path / "private-media"
    _write_jsonl(manifest, [row])
    session = _FakeSession()
    _patch_sessionmaker(monkeypatch, session)

    summary = await importer.import_benchmark_fixtures_as_media_objects(
        benchmark_manifest=manifest,
        image_root=image_root,
        local_media_root=local_media_root,
        output_manifest=output_manifest,
        owner_subject_hash="a" * 64,
        source_run_id=str(uuid4()),
        apply=True,
    )

    assert summary["created_media_count"] == 1
    assert summary["rewritten_count"] == 1
    assert summary["copied_object_count"] == 1
    assert session.commit_count == 1
    assert len(session.added) == 1
    media_object = session.added[0]
    assert media_object.owner_subject_hash == "a" * 64
    assert media_object.domain == "supplement_label"
    assert media_object.status == "retained"
    assert media_object.object_ref.startswith("supplement/ocr-benchmark/")
    assert (local_media_root / media_object.object_ref).read_bytes() == image_bytes

    rewritten = [
        json.loads(line) for line in output_manifest.read_text(encoding="utf-8").splitlines()
    ]
    assert rewritten[0]["source_ref"] == f"media:{media_object.id}"
    assert rewritten[0]["source_ref_kind"] == "media_object"
    assert rewritten[0]["media_object_registered"] is True
    assert media_object.object_ref not in json.dumps(rewritten, ensure_ascii=False)


@pytest.mark.asyncio
async def test_apply_reuses_existing_media_object_without_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify existing retained media rows are reused instead of duplicated."""
    image_bytes = b"jpeg-like-content"
    image_root = tmp_path / "fixtures"
    image_path = image_root / "fixture-001.jpg"
    image_root.mkdir()
    image_path.write_bytes(image_bytes)
    row = _benchmark_row(image_path="fixture-001.jpg", image_bytes=image_bytes)
    manifest = tmp_path / "benchmark.jsonl"
    output_manifest = tmp_path / "rewritten.jsonl"
    _write_jsonl(manifest, [row])
    existing_id = uuid4()
    session = _FakeSession(
        existing_media=_media_object(
            row_id=existing_id,
            owner_hash="a" * 64,
            image_sha256=str(row["image_sha256"]),
        )
    )
    _patch_sessionmaker(monkeypatch, session)

    summary = await importer.import_benchmark_fixtures_as_media_objects(
        benchmark_manifest=manifest,
        image_root=image_root,
        local_media_root=tmp_path / "private-media",
        output_manifest=output_manifest,
        owner_subject_hash="a" * 64,
        apply=True,
    )

    assert summary["created_media_count"] == 0
    assert summary["reused_media_count"] == 1
    assert summary["copied_object_count"] == 0
    assert session.added == []
    rewritten = [
        json.loads(line) for line in output_manifest.read_text(encoding="utf-8").splitlines()
    ]
    assert rewritten[0]["source_ref"] == f"media:{existing_id}"


@pytest.mark.asyncio
async def test_hash_mismatch_is_skipped_without_output(tmp_path: Path) -> None:
    """Verify hash mismatch fails closed for the affected row."""
    image_bytes = b"jpeg-like-content"
    image_root = tmp_path / "fixtures"
    image_path = image_root / "fixture-001.jpg"
    image_root.mkdir()
    image_path.write_bytes(b"different-bytes")
    manifest = tmp_path / "benchmark.jsonl"
    output_manifest = tmp_path / "rewritten.jsonl"
    _write_jsonl(manifest, [_benchmark_row(image_path="fixture-001.jpg", image_bytes=image_bytes)])

    summary = await importer.import_benchmark_fixtures_as_media_objects(
        benchmark_manifest=manifest,
        image_root=image_root,
        local_media_root=tmp_path / "media",
        output_manifest=output_manifest,
        owner_subject_hash="a" * 64,
        apply=False,
    )

    assert summary["validated_fixture_count"] == 0
    assert summary["skip_reason_counts"] == {"image_sha256_mismatch": 1}
    assert output_manifest.exists() is False


@pytest.mark.asyncio
async def test_unsafe_absolute_image_path_is_skipped(tmp_path: Path) -> None:
    """Verify absolute local image paths are rejected."""
    image_bytes = b"jpeg-like-content"
    image_root = tmp_path / "fixtures"
    image_root.mkdir()
    manifest = tmp_path / "benchmark.jsonl"
    output_manifest = tmp_path / "rewritten.jsonl"
    row = _benchmark_row(image_path="/private/tmp/leaked.jpg", image_bytes=image_bytes)
    _write_jsonl(manifest, [row])

    summary = await importer.import_benchmark_fixtures_as_media_objects(
        benchmark_manifest=manifest,
        image_root=image_root,
        local_media_root=tmp_path / "media",
        output_manifest=output_manifest,
        owner_subject_hash="a" * 64,
        apply=False,
    )

    assert summary["validated_fixture_count"] == 0
    assert summary["skip_reason_counts"] == {"unsafe_image_path": 1}


@pytest.mark.asyncio
async def test_cli_failure_summary_is_redacted(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI failure output avoids sensitive values."""
    manifest = tmp_path / "missing.jsonl"
    exit_code = await importer.run_cli(
        [
            "--benchmark-manifest",
            str(manifest),
            "--local-media-root",
            str(tmp_path / "media"),
            "--output-manifest",
            str(tmp_path / "rewritten.jsonl"),
            "--owner-subject-hash",
            "a" * 64,
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "missing.jsonl" in output
    assert str(tmp_path) not in output
    assert "Sensitive Expected Product" not in output
    assert "crawling-image:" not in output
    assert "a" * 64 not in output
    assert '"raw_payload_printed": false' in output
