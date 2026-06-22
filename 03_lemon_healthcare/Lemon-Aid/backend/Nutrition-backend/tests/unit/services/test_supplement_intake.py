"""Supplement image intake service tests."""

from __future__ import annotations

import hashlib
from base64 import b64decode
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Self, cast
from uuid import uuid4

import pytest
from fastapi import UploadFile
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import Settings
from src.models.db.supplement import SupplementAnalysisRun
from src.models.schemas.supplement import SupplementAnalysisStatus
from src.security.auth import AuthenticatedUser
from src.services.supplement_intake import (
    SUPPLEMENT_INTAKE_ALGORITHM_VERSION,
    SupplementImageValidationError,
    SupplementIntakeConflictError,
    ValidatedSupplementImage,
    create_supplement_analysis_intake,
    detect_image_mime,
    read_and_validate_supplement_image,
    supplement_analysis_run_to_preview,
)
from starlette.datastructures import Headers


class _TransactionContext:
    """Async context manager used by the fake session transaction."""

    async def __aenter__(self) -> Self:
        """Enter the fake transaction.

        Returns:
            Context manager instance.
        """
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Exit the fake transaction.

        Args:
            *_exc_info: Exception information ignored by the fake context.

        Returns:
            None.
        """


class _FakeStoreSession:
    """Fake async session for supplement intake write tests."""

    def __init__(self, existing: SupplementAnalysisRun | None = None) -> None:
        self.existing = existing
        self.added: SupplementAnalysisRun | None = None
        self.refreshed: SupplementAnalysisRun | None = None
        self.commits = 0
        # A real AsyncSession always exposes ``.info``; persist_scope reads it.
        self.info: dict[str, object] = {}

    async def flush(self) -> None:
        """No-op flush (persist_scope flushes pending writes)."""

    async def commit(self) -> None:
        """Count commits (persist_scope own-mode must commit exactly once)."""
        self.commits += 1

    async def rollback(self) -> None:
        """No-op rollback (persist_scope own-mode rolls back on exception)."""

    def begin(self) -> _TransactionContext:
        """Return a fake transaction context.

        Returns:
            Fake async transaction context.
        """
        return _TransactionContext()

    async def scalar(self, _statement: object) -> SupplementAnalysisRun | None:
        """Return a fake existing row for idempotency lookup.

        Args:
            _statement: SQLAlchemy select statement.

        Returns:
            Existing supplement analysis run or None.
        """
        return self.existing

    def add(self, record: object) -> None:
        """Capture the ORM record being added.

        Args:
            record: ORM object passed by the service.

        Returns:
            None.
        """
        self.added = cast(SupplementAnalysisRun, record)

    async def refresh(self, record: object) -> None:
        """Populate server-generated fields after fake persistence.

        Args:
            record: ORM object to refresh.

        Returns:
            None.
        """
        supplement_run = cast(SupplementAnalysisRun, record)
        supplement_run.id = uuid4()
        supplement_run.created_at = datetime.now(UTC)
        supplement_run.updated_at = datetime.now(UTC)
        self.refreshed = supplement_run


def _settings(
    *,
    supplement_image_max_bytes: int = 5 * 1024 * 1024,
    supplement_image_max_pixels: int = 12_000_000,
    supplement_preview_ttl_minutes: int = 30,
) -> Settings:
    """Return settings for supplement intake tests.

    Args:
        supplement_image_max_bytes: Maximum image byte size.
        supplement_image_max_pixels: Maximum decoded image pixels.
        supplement_preview_ttl_minutes: Preview TTL in minutes.

    Returns:
        Settings object.
    """
    return Settings(
        supplement_image_max_bytes=supplement_image_max_bytes,
        supplement_image_max_pixels=supplement_image_max_pixels,
        supplement_preview_ttl_minutes=supplement_preview_ttl_minutes,
    )


def _user() -> AuthenticatedUser:
    """Return an authenticated user fixture.

    Returns:
        Authenticated user model.
    """
    return AuthenticatedUser(
        subject="user_123",
        issuer="https://auth.example.com/",
        claims={"sub": "user_123"},
    )


def _png_bytes(size: tuple[int, int] = (3, 2)) -> bytes:
    """Return a tiny PNG image.

    Args:
        size: Image size.

    Returns:
        PNG image bytes.
    """
    buffer = BytesIO()
    Image.new("RGB", size, color=(255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def _upload(data: bytes, content_type: str = "image/png") -> UploadFile:
    """Build an UploadFile for service tests.

    Args:
        data: File bytes.
        content_type: Declared upload MIME type.

    Returns:
        UploadFile object.
    """
    return UploadFile(
        file=BytesIO(data),
        filename="raw-client-name.png",
        headers=Headers({"content-type": content_type}),
    )


def _image_metadata(sha256: str = "a" * 64) -> ValidatedSupplementImage:
    """Return validated image metadata fixture.

    Args:
        sha256: Image SHA-256 hex digest.

    Returns:
        Validated image metadata.
    """
    return ValidatedSupplementImage(
        sha256=sha256,
        mime_type="image/png",
        size_bytes=128,
        width=3,
        height=2,
    )


def _existing_run(image_sha256: str) -> SupplementAnalysisRun:
    """Return an existing supplement analysis run fixture.

    Args:
        image_sha256: Stored image hash.

    Returns:
        Existing supplement analysis run.
    """
    now = datetime.now(UTC)
    return SupplementAnalysisRun(
        id=uuid4(),
        owner_subject="https://auth.example.com/::user_123",
        client_request_id="client-1",
        status=SupplementAnalysisStatus.REQUIRES_CONFIRMATION.value,
        image_sha256=image_sha256,
        image_mime_type="image/png",
        image_size_bytes=128,
        ocr_provider="intake-only",
        parsed_snapshot={"parsed_product": {}, "ingredient_candidates": []},
        match_snapshot={"matched_product_candidates": []},
        warnings=[],
        algorithm_version=SUPPLEMENT_INTAKE_ALGORITHM_VERSION,
        expires_at=now + timedelta(minutes=30),
        created_at=now,
        updated_at=now,
    )


def test_detect_image_mime_supports_allowed_magic_bytes() -> None:
    """Verify image MIME detection uses magic bytes rather than filenames."""
    assert detect_image_mime(b"\xff\xd8\xff\xe0") == "image/jpeg"
    assert detect_image_mime(b"\x89PNG\r\n\x1a\nrest") == "image/png"
    assert detect_image_mime(b"RIFFxxxxWEBPrest") == "image/webp"
    assert detect_image_mime(b"not-an-image") is None


@pytest.mark.asyncio
async def test_read_and_validate_supplement_image_returns_hash_and_dimensions() -> None:
    """Verify valid PNG uploads return only bounded image metadata."""
    data = _png_bytes()

    result = await read_and_validate_supplement_image(_upload(data), _settings())

    assert result.sha256 == hashlib.sha256(data).hexdigest()
    assert result.mime_type == "image/png"
    assert result.size_bytes == len(data)
    assert (result.width, result.height) == (3, 2)


@pytest.mark.asyncio
async def test_read_and_validate_rejects_media_type_spoofing() -> None:
    """Verify declared MIME type must match image magic bytes."""
    with pytest.raises(SupplementImageValidationError) as exc_info:
        await read_and_validate_supplement_image(_upload(_png_bytes(), "image/jpeg"), _settings())

    assert exc_info.value.code == "unsupported_media_type"
    assert exc_info.value.status_code == 415


@pytest.mark.asyncio
async def test_read_and_validate_rejects_oversized_byte_payload() -> None:
    """Verify uploads are rejected before decoding when byte size exceeds the limit."""
    data = b"x" * 1025

    with pytest.raises(SupplementImageValidationError) as exc_info:
        await read_and_validate_supplement_image(
            _upload(data),
            _settings(supplement_image_max_bytes=1024),
        )

    assert exc_info.value.code == "payload_too_large"
    assert exc_info.value.status_code == 413


@pytest.mark.asyncio
async def test_read_and_validate_rejects_corrupt_supported_image() -> None:
    """Verify corrupt images with supported magic bytes are rejected as invalid images."""
    with pytest.raises(SupplementImageValidationError) as exc_info:
        await read_and_validate_supplement_image(
            _upload(b"\x89PNG\r\n\x1a\ncorrupt"),
            _settings(),
        )

    assert exc_info.value.code == "invalid_image"
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_read_and_validate_rejects_bad_png_checksum() -> None:
    """Verify PNG CRC failures are converted to validation errors, not 500s."""
    bad_png = b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )

    with pytest.raises(SupplementImageValidationError) as exc_info:
        await read_and_validate_supplement_image(_upload(bad_png), _settings())

    assert exc_info.value.code == "invalid_image"
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_read_and_validate_rejects_excessive_pixel_count() -> None:
    """Verify decoded image dimensions are bounded to reduce decompression risk."""
    with pytest.raises(SupplementImageValidationError) as exc_info:
        await read_and_validate_supplement_image(
            _upload(_png_bytes(size=(10, 10))),
            _settings(supplement_image_max_pixels=50),
        )

    assert exc_info.value.code == "payload_too_large"
    assert exc_info.value.status_code == 413


@pytest.mark.asyncio
async def test_create_supplement_analysis_intake_stores_sanitized_preview() -> None:
    """Verify intake persistence stores owner, hash, and sanitized snapshots only."""
    fake_session = _FakeStoreSession()

    result = await create_supplement_analysis_intake(
        cast(AsyncSession, fake_session),
        _user(),
        _image_metadata(),
        " client-1 ",
        _settings(),
    )

    assert result.reused_existing is False
    assert result.record is fake_session.added
    assert result.record is fake_session.refreshed
    assert result.record.owner_subject == "https://auth.example.com/::user_123"
    stored_idempotency_key = result.record.client_request_id
    assert stored_idempotency_key is not None
    prefix, sep, hint = stored_idempotency_key.partition(":")
    assert sep == ":"
    assert len(prefix) == 16
    assert all(char in "0123456789abcdef" for char in prefix)
    assert hint == "client-1"
    assert result.record.image_sha256 == "a" * 64
    assert result.record.ocr_text_hash is None
    assert result.record.parsed_snapshot["intake"] == {
        "mime_type": "image/png",
        "size_bytes": 128,
        "width": 3,
        "height": 2,
    }
    assert "filename" not in result.record.parsed_snapshot["intake"]


@pytest.mark.asyncio
async def test_create_supplement_analysis_intake_reuses_existing_same_hash() -> None:
    """Verify matching idempotency key and image hash return the existing row."""
    existing = _existing_run("a" * 64)
    fake_session = _FakeStoreSession(existing=existing)

    result = await create_supplement_analysis_intake(
        cast(AsyncSession, fake_session),
        _user(),
        _image_metadata(),
        "client-1",
        _settings(),
    )

    assert result.record is existing
    assert result.reused_existing is True
    assert fake_session.added is None
    assert fake_session.refreshed is None


@pytest.mark.asyncio
async def test_create_supplement_analysis_intake_rejects_idempotency_conflict() -> None:
    """Verify reused idempotency keys cannot point to different image bytes."""
    fake_session = _FakeStoreSession(existing=_existing_run("b" * 64))

    with pytest.raises(SupplementIntakeConflictError):
        await create_supplement_analysis_intake(
            cast(AsyncSession, fake_session),
            _user(),
            _image_metadata(),
            "client-1",
            _settings(),
        )


def test_supplement_analysis_run_to_preview_omits_intake_metadata() -> None:
    """Verify API preview omits stored image hash and intake metadata."""
    record = _existing_run("a" * 64)
    record.parsed_snapshot = {
        "parsed_product": {},
        "ingredient_candidates": [],
        "low_confidence_fields": ["label_text"],
        "intake": {"mime_type": "image/png", "size_bytes": 128},
    }

    preview = supplement_analysis_run_to_preview(record)
    body = preview.model_dump()

    assert body["analysis_id"] == record.id
    assert body["low_confidence_fields"] == ["label_text"]
    assert "image_sha256" not in body
    assert "intake" not in body
    assert preview.pipeline_metadata.image_count == 1
    assert preview.pipeline_metadata.image_role == "unknown"
    assert preview.pipeline_metadata.ocr_text_present is False
    assert preview.pipeline_metadata.ocr_confidence_bucket == "none"
    assert preview.pipeline_metadata.roi_count == 0
    assert preview.pipeline_metadata.section_count == 0
    assert preview.pipeline_metadata.missing_required_sections == [
        "product_name",
        "supplement_facts",
        "intake_method",
        "precautions",
    ]


def test_supplement_analysis_run_to_preview_suggests_categories_from_ingredients() -> None:
    """Verify the preview derives curated category suggestions from ingredient names."""
    record = _existing_run("b" * 64)
    record.parsed_snapshot = {
        "parsed_product": {},
        "ingredient_candidates": [
            {"display_name": "루테인", "confidence": 0.0, "source": "ollama_structured"},
            {"display_name": "지아잔틴", "confidence": 0.0, "source": "ollama_structured"},
            {
                "display_name": "헤마토코쿠스추출물",
                "confidence": 0.0,
                "source": "ollama_structured",
            },
        ],
    }

    preview = supplement_analysis_run_to_preview(record)

    assert "루테인_눈" in preview.suggested_category_keys


def test_supplement_analysis_run_to_preview_suggests_no_category_without_match() -> None:
    """Verify the suggestion list is empty when no ingredient maps to a category."""
    record = _existing_run("c" * 64)
    record.parsed_snapshot = {
        "parsed_product": {},
        "ingredient_candidates": [
            {"display_name": "qzx-filler-000", "confidence": 0.0, "source": "ollama_structured"},
        ],
    }

    preview = supplement_analysis_run_to_preview(record)

    assert preview.suggested_category_keys == []


def test_supplement_analysis_run_to_preview_surfaces_stored_raw_ocr_text() -> None:
    """When the gated snapshot carries raw_ocr_text, the preview exposes it and the
    diagnostic pipeline flag reflects the actual retention."""
    record = _existing_run("d" * 64)
    record.parsed_snapshot = {
        "parsed_product": {},
        "ingredient_candidates": [],
        "raw_ocr_text": "비타민 D 1000\n비타민 D 25μg",
        # A persisted pipeline_metadata that hardcodes the flag False must NOT clobber
        # the authoritative derive (regression guard for the metadata.update overwrite).
        "pipeline_metadata": {"raw_ocr_text_stored": False, "ocr_status": "success"},
    }

    preview = supplement_analysis_run_to_preview(record)

    assert preview.raw_ocr_text == "비타민 D 1000\n비타민 D 25μg"
    assert preview.pipeline_metadata.raw_ocr_text_stored is True


def test_supplement_analysis_run_to_preview_omits_absent_raw_ocr_text() -> None:
    """Default off (no snapshot key): the preview field is None and the flag False."""
    record = _existing_run("e" * 64)

    preview = supplement_analysis_run_to_preview(record)

    assert preview.raw_ocr_text is None
    assert preview.pipeline_metadata.raw_ocr_text_stored is False
