"""Integration: Stage-2 owner isolation for the ambient-tx Step 6a regulated write paths.

Authority: outputs/todo-list/2026-06-14/2026-06-14-ambient-transaction-refactor-plan.md
           outputs/todo-list/2026-06-14/2026-06-14-step6-design.md

ambient-tx Step 6a migrated ``_create_regulated_ocr_preview`` / ``confirm_regulated_document``
to ``persist_scope`` and the regulated-inputs routes to ``get_rls_context_session`` (audit
stays route-level via ``record_sensitive_audit_event``; the service writes owner data only).
This proves the *actual migrated service code* works under the FORCE RLS Stage-2 posture,
connected as the non-superuser ``lemon_app`` role inside a request-managed transaction with
the owner GUCs set:

  * the participate-mode preview INSERT into the hashed ``regulated_documents`` parent
    (0023b Type B, keyed to ``app.current_subject_hash``) succeeds and isolates,
  * the participate-mode confirm fan-out — ``regulated_documents`` UPDATE +
    ``prescription_items`` child INSERT (0023b Type C → ``regulated_documents``) +
    ``medical_record_collections`` parent INSERT (Type B) + ``patient_medications`` child
    INSERT (Type C → ``medical_record_collections``) — all pass USING + WITH CHECK in one
    flush-only transaction,
  * a different subject sees none of the four rows (USING isolation), and
  * every row persists once the request transaction commits.

Run gate (skip unless both set):
  TEST_DATABASE_URL          — admin/privileged conn (verify + cleanup)
  TEST_RLS_APP_DATABASE_URL  — lemon_app (NOSUPERUSER, NOBYPASSRLS) request conn
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from io import BytesIO

import pytest
from fastapi import UploadFile
from PIL import Image
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from src.config import Settings, get_settings
from src.db.rls_context import set_request_rls_context
from src.db.tx import REQUEST_MANAGED_TX
from src.models.schemas.regulated import (
    PrescriptionItemConfirm,
    RegulatedDocumentConfirmRequest,
    RegulatedDocumentType,
)
from src.ocr.base import OCRAdapter, OCRImageInput, OCRResult
from src.regulated.factory import RegulatedOCRAdapters
from src.regulated.ocr_intake import confirm_regulated_document, create_prescription_ocr_preview
from src.security.auth import AuthenticatedUser
from src.security.privacy import hash_actor_subject
from src.security.subjects import build_owner_subject
from starlette.datastructures import Headers

ADMIN_URL = os.getenv("TEST_DATABASE_URL")
APP_URL = os.getenv("TEST_RLS_APP_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    ADMIN_URL is None or APP_URL is None,
    reason=(
        "Set TEST_DATABASE_URL (admin) and TEST_RLS_APP_DATABASE_URL (lemon_app) "
        "to run the Stage-2 Step 6a regulated owner-isolation proofs."
    ),
)


class _FakeOCRAdapter(OCRAdapter):
    """Fake OCR adapter returning configured text (no network/model dependency)."""

    def __init__(self, text_value: str) -> None:
        self.text_value = text_value

    async def extract_text(self, _image: OCRImageInput) -> OCRResult:
        """Return fake OCR output for the supplied image.

        Args:
            _image: OCR image input (ignored by the fake).

        Returns:
            Fake OCR result.
        """
        return OCRResult(text=self.text_value, provider="fake_ocr", confidence=0.88)


@asynccontextmanager
async def _stage2_engines() -> AsyncIterator[tuple[AsyncEngine, AsyncEngine]]:
    """Yield (admin, lemon_app) engines and dispose both afterwards."""
    assert ADMIN_URL is not None and APP_URL is not None
    admin = create_async_engine(ADMIN_URL, pool_pre_ping=True)
    app = create_async_engine(APP_URL, pool_pre_ping=True)
    try:
        yield admin, app
    finally:
        await app.dispose()
        await admin.dispose()


async def _assert_request_role_enforces_rls(session: AsyncSession) -> None:
    """Fail fast if the request role bypasses RLS (would make isolation vacuous)."""
    rls_bypassed = (
        await session.execute(
            text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
        )
    ).scalar_one()
    assert rls_bypassed is False, (
        "TEST_RLS_APP_DATABASE_URL must connect as a NOSUPERUSER, NOBYPASSRLS role "
        "(e.g. lemon_app); otherwise RLS is bypassed and this proves nothing."
    )


async def _count_where(session: AsyncSession, table: str, column: str, value: uuid.UUID) -> int:
    """Count rows visible to the current GUC subject where ``column`` matches ``value``.

    ``table``/``column`` are test-controlled constants; the filter matches the row(s)
    without RLS, so 0 under a *different* subject proves the USING policy hid them.
    """
    return (
        await session.execute(
            text(f"SELECT count(*) FROM {table} WHERE {column} = :val"),
            {"val": str(value)},
        )
    ).scalar_one()


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(subject=f"alice-{uuid.uuid4()}", issuer="test-issuer")


def _settings() -> Settings:
    return get_settings()


def _upload() -> UploadFile:
    """Build a tiny in-memory PNG UploadFile for the preview path."""
    buffer = BytesIO()
    Image.new("RGB", (3, 2), color=(255, 255, 255)).save(buffer, format="PNG")
    return UploadFile(
        file=BytesIO(buffer.getvalue()),
        filename="document.png",
        headers=Headers({"content-type": "image/png"}),
    )


async def test_stage2_regulated_preview_is_owner_isolated_and_persists() -> None:
    """Hashed regulated_documents policy accepts the participate-mode preview INSERT."""
    settings = _settings()
    user = _user()
    owner = build_owner_subject(user)
    owner_hash = hash_actor_subject(user, settings)
    document_id: uuid.UUID | None = None
    async with _stage2_engines() as (admin, app):
        try:
            app_sessionmaker = async_sessionmaker(app, expire_on_commit=False)
            async with app_sessionmaker() as session:
                transaction = await session.begin()
                await set_request_rls_context(session, subject=owner, subject_hash=owner_hash)
                session.info[REQUEST_MANAGED_TX] = True
                await _assert_request_role_enforces_rls(session)

                preview = await create_prescription_ocr_preview(
                    session=session,
                    user=user,
                    image=_upload(),
                    settings=settings,
                    adapters=RegulatedOCRAdapters(
                        ocr=_FakeOCRAdapter("Amoxicillin 500mg 하루 2회 7일")
                    ),
                )
                document_id = preview.document_id

                # Owner sees the preview row...
                assert await _count_where(session, "regulated_documents", "id", document_id) == 1
                # ...a different subject does not (hashed USING isolation).
                await set_request_rls_context(
                    session, subject="iss::someone-else", subject_hash="0" * 64
                )
                assert await _count_where(session, "regulated_documents", "id", document_id) == 0

                await transaction.commit()

            async with admin.connect() as conn:
                persisted = (
                    await conn.execute(
                        text("SELECT count(*) FROM regulated_documents WHERE id = :rid"),
                        {"rid": str(document_id)},
                    )
                ).scalar_one()
                assert persisted == 1
        finally:
            if document_id is not None:
                async with admin.begin() as conn:
                    await conn.execute(
                        text("DELETE FROM regulated_documents WHERE id = :rid"),
                        {"rid": str(document_id)},
                    )


async def test_stage2_regulated_confirm_fanout_is_owner_isolated_and_persists() -> None:
    """Confirm's 4-table fan-out (parent + 3 children/collections) isolates and persists."""
    settings = _settings()
    user = _user()
    owner = build_owner_subject(user)
    owner_hash = hash_actor_subject(user, settings)
    document_id: uuid.UUID | None = None
    async with _stage2_engines() as (admin, app):
        try:
            app_sessionmaker = async_sessionmaker(app, expire_on_commit=False)
            async with app_sessionmaker() as session:
                transaction = await session.begin()
                await set_request_rls_context(session, subject=owner, subject_hash=owner_hash)
                session.info[REQUEST_MANAGED_TX] = True
                await _assert_request_role_enforces_rls(session)

                preview = await create_prescription_ocr_preview(
                    session=session,
                    user=user,
                    image=_upload(),
                    settings=settings,
                    adapters=RegulatedOCRAdapters(
                        ocr=_FakeOCRAdapter("Amoxicillin 500mg 하루 2회 7일")
                    ),
                )
                document_id = preview.document_id

                await confirm_regulated_document(
                    session=session,
                    user=user,
                    document_id=document_id,
                    request=RegulatedDocumentConfirmRequest(
                        document_type=RegulatedDocumentType.PRESCRIPTION,
                        prescription_items=[
                            PrescriptionItemConfirm(
                                medication_name_text="Amoxicillin",
                                dose_text="500mg",
                                frequency_text="하루 2회",
                                period_text="7일",
                            )
                        ],
                    ),
                    settings=settings,
                )

                # Owner sees the parent document plus all three confirm-time child rows.
                assert await _count_where(session, "regulated_documents", "id", document_id) == 1
                assert (
                    await _count_where(session, "prescription_items", "document_id", document_id)
                    == 1
                )
                assert (
                    await _count_where(
                        session, "medical_record_collections", "source_document_id", document_id
                    )
                    == 1
                )
                assert (
                    await _count_where(
                        session, "patient_medications", "source_document_id", document_id
                    )
                    == 1
                )

                # A different subject sees none of them (parent USING + child join isolation).
                await set_request_rls_context(
                    session, subject="iss::someone-else", subject_hash="0" * 64
                )
                assert await _count_where(session, "regulated_documents", "id", document_id) == 0
                assert (
                    await _count_where(session, "prescription_items", "document_id", document_id)
                    == 0
                )
                assert (
                    await _count_where(
                        session, "medical_record_collections", "source_document_id", document_id
                    )
                    == 0
                )
                assert (
                    await _count_where(
                        session, "patient_medications", "source_document_id", document_id
                    )
                    == 0
                )

                await transaction.commit()

            async with admin.connect() as conn:
                for table, column in (
                    ("regulated_documents", "id"),
                    ("prescription_items", "document_id"),
                    ("medical_record_collections", "source_document_id"),
                    ("patient_medications", "source_document_id"),
                ):
                    persisted = (
                        await conn.execute(
                            text(f"SELECT count(*) FROM {table} WHERE {column} = :rid"),
                            {"rid": str(document_id)},
                        )
                    ).scalar_one()
                    assert persisted == 1, f"{table} did not persist"
        finally:
            if document_id is not None:
                async with admin.begin() as conn:
                    # FK-safe order: children before their parents.
                    await conn.execute(
                        text("DELETE FROM patient_medications WHERE source_document_id = :rid"),
                        {"rid": str(document_id)},
                    )
                    await conn.execute(
                        text("DELETE FROM prescription_items WHERE document_id = :rid"),
                        {"rid": str(document_id)},
                    )
                    await conn.execute(
                        text(
                            "DELETE FROM medical_record_collections WHERE source_document_id = :rid"
                        ),
                        {"rid": str(document_id)},
                    )
                    await conn.execute(
                        text("DELETE FROM regulated_documents WHERE id = :rid"),
                        {"rid": str(document_id)},
                    )
