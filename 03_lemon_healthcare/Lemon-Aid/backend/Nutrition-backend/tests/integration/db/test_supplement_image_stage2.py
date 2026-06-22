"""Integration: Stage-2 owner isolation for the ambient-tx Step 7 supplement paths.

Authority: outputs/todo-list/2026-06-14/2026-06-14-ambient-transaction-refactor-plan.md
           outputs/todo-list/2026-06-14/2026-06-14-step7-8-design.md
           outputs/todo-list/2026-06-15/2026-06-15-step7-phase2-handoff.md

ambient-tx Step 7 moved the supplement image orchestrator's owner-data writes onto
``persist_scope`` and the three orchestrator routes onto a route-owned RLS transaction
(``rls_request_transaction`` — committed in the route body so the post-commit learning
``BackgroundTask`` observes durable rows). Learning image storage + annotation enqueue
moved out of the request transaction into a fresh post-commit session.

This proves the *actual migrated code* under the FORCE RLS Stage-2 posture, connected as
the non-superuser ``lemon_app`` role inside a request-managed (participate) transaction
with the owner GUCs set:

  * the intake INSERT and the ``_annotate_multi_image_record`` UPDATE — two sequential
    ``persist_scope`` writes against the plaintext-owner ``supplement_analysis_runs`` table
    (0023b Type A, keyed to ``app.current_subject``) — both pass WITH CHECK in **one
    flush-only transaction**. If any write had committed mid-orchestration the
    transaction-local GUC would have dropped and the next WITH CHECK would have failed,
    so two successful sequential writes prove the GUC survives (no mid-commit), and
  * a different subject sees none of the rows (USING isolation), and
  * the row persists once the request transaction commits, and
  * the post-commit learning helper (fresh session, independent of the committed request
    transaction) stores a ``learning_image_objects`` row whose ``analysis_id`` foreign key
    resolves to the now-durable run — proving the deferral keeps the FK valid.

Note: the post-commit learning session runs on the admin (privileged) engine here, which
mirrors today's pre-flip reality where ``get_sessionmaker`` binds the superuser
``DATABASE_URL``. Under a Step-8 ``lemon_app`` flip the learning fresh session needs a
privileged/BYPASSRLS engine (``maybe_store_learning_image_object`` keeps its own commit +
a post-commit ``session.refresh`` that a transaction-local GUC cannot survive); that engine
choice is a Step-8 ops decision, consistent with how audit writes already run out-of-band.

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
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from src.api.v1.supplements import _annotate_multi_image_record
from src.config import Settings
from src.db.rls_context import set_request_rls_context
from src.db.tx import REQUEST_MANAGED_TX
from src.learning.object_storage import (
    LearningImageObjectInput,
    LearningImageObjectStore,
    StoredLearningImage,
)
from src.models.schemas.privacy import ConsentType
from src.security.auth import AuthenticatedUser
from src.security.privacy import hash_actor_subject
from src.security.subjects import build_owner_subject
from src.services.supplement_image_analysis import (
    SupplementLearningArtifactsInput,
    analyze_supplement_image,
    store_supplement_learning_artifacts,
)
from src.services.supplement_intake import ValidatedSupplementImage
from starlette.datastructures import Headers

ADMIN_URL = os.getenv("TEST_DATABASE_URL")
APP_URL = os.getenv("TEST_RLS_APP_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    ADMIN_URL is None or APP_URL is None,
    reason=(
        "Set TEST_DATABASE_URL (admin) and TEST_RLS_APP_DATABASE_URL (lemon_app) "
        "to run the Stage-2 Step 7 supplement owner-isolation proofs."
    ),
)


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
    """Count rows visible to the current GUC subject where ``column`` matches ``value``."""
    return (
        await session.execute(
            text(f"SELECT count(*) FROM {table} WHERE {column} = :val"),
            {"val": str(value)},
        )
    ).scalar_one()


def _stage2_settings() -> Settings:
    """Settings with image learning enabled (hermetic; ignores a local .env)."""
    return Settings(
        privacy_hash_secret=SecretStr("stage2-supplement-secret"),
        enable_image_learning_pipeline=True,
        enable_pgvector_storage=True,
        image_retention_days=30,
        _env_file=None,
    )


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(subject=f"alice-{uuid.uuid4()}", issuer="test-issuer")


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (3, 2), color=(255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def _upload() -> UploadFile:
    return UploadFile(
        file=BytesIO(_png_bytes()),
        filename="label.png",
        headers=Headers({"content-type": "image/png"}),
    )


class _FakeLearningImageObjectStore(LearningImageObjectStore):
    """In-memory learning object store (no filesystem/network IO)."""

    def __init__(self) -> None:
        self.put_payload: LearningImageObjectInput | None = None

    async def put_image(self, payload: LearningImageObjectInput) -> StoredLearningImage:
        self.put_payload = payload
        return StoredLearningImage(object_uri="local://stage2/image.png", provider="local")

    async def get_image(self, object_uri: str, version_id: str | None = None) -> bytes:
        _ = (object_uri, version_id)
        return b"image"

    async def delete_image(self, object_uri: str, version_id: str | None = None) -> None:
        _ = (object_uri, version_id)


async def test_stage2_supplement_owner_writes_single_tx_and_learning_post_commit() -> None:
    """Type-A run policy accepts the participate writes; learning store stays FK-valid."""
    settings = _stage2_settings()
    user = _user()
    owner = build_owner_subject(user)
    owner_hash = hash_actor_subject(user, settings)
    run_id: uuid.UUID | None = None
    learning_consents = (
        ConsentType.OCR_IMAGE_PROCESSING,
        ConsentType.DATA_RETENTION,
        ConsentType.IMAGE_LEARNING_DATASET,
    )
    async with _stage2_engines() as (admin, app):
        try:
            app_sessionmaker = async_sessionmaker(app, expire_on_commit=False)
            admin_sessionmaker = async_sessionmaker(admin, expire_on_commit=False)
            async with app_sessionmaker() as session:
                transaction = await session.begin()
                await set_request_rls_context(session, subject=owner, subject_hash=owner_hash)
                session.info[REQUEST_MANAGED_TX] = True
                await _assert_request_role_enforces_rls(session)

                # Write 1: intake INSERT (participate / flush only).
                result = await analyze_supplement_image(
                    session=session,
                    user=user,
                    image=_upload(),
                    client_request_id=None,
                    settings=settings,
                )
                run_id = result.record.id

                # Write 2: a second owner write in the SAME transaction. If write 1 had
                # committed mid-flow the GUC would be gone and this WITH CHECK would fail.
                await _annotate_multi_image_record(
                    session,
                    result.record,
                    image_role="front_label",
                    analysis_group_id="multi-stage2",
                    image_count=1,
                )

                assert await _count_where(session, "supplement_analysis_runs", "id", run_id) == 1

                # A different subject sees nothing (USING isolation).
                await set_request_rls_context(
                    session, subject="iss::someone-else", subject_hash="0" * 64
                )
                assert await _count_where(session, "supplement_analysis_runs", "id", run_id) == 0

                await transaction.commit()

            # The run persists after the request transaction commits.
            async with admin.connect() as conn:
                persisted = (
                    await conn.execute(
                        text("SELECT count(*) FROM supplement_analysis_runs WHERE id = :rid"),
                        {"rid": str(run_id)},
                    )
                ).scalar_one()
                assert persisted == 1
                role = (
                    await conn.execute(
                        text(
                            "SELECT parsed_snapshot->>'image_role' "
                            "FROM supplement_analysis_runs WHERE id = :rid"
                        ),
                        {"rid": str(run_id)},
                    )
                ).scalar_one()
                assert role == "front_label"  # _annotate write landed in the same tx

            # Post-commit learning: fresh session, independent of the committed request tx.
            # FK analysis_id resolves only because the run is already durable.
            store = _FakeLearningImageObjectStore()
            artifacts = SupplementLearningArtifactsInput(
                analysis_id=run_id,
                image_bytes=_png_bytes(),
                image_metadata=ValidatedSupplementImage(
                    sha256="b" * 64,
                    mime_type="image/png",
                    size_bytes=len(_png_bytes()),
                    width=3,
                    height=2,
                ),
                ocr_result=None,
                learning_consents=learning_consents,
            )
            await store_supplement_learning_artifacts(
                user=user,
                artifacts=artifacts,
                settings=settings,
                object_store=store,
                session_factory=admin_sessionmaker,
            )
            assert store.put_payload is not None

            async with admin.connect() as conn:
                learning_rows = (
                    await conn.execute(
                        text(
                            "SELECT count(*) FROM learning_image_objects WHERE analysis_id = :rid"
                        ),
                        {"rid": str(run_id)},
                    )
                ).scalar_one()
                assert learning_rows == 1  # stored post-commit with a valid FK to the run
        finally:
            if run_id is not None:
                async with admin.begin() as conn:
                    # FK-safe order: learning child before the parent run.
                    await conn.execute(
                        text("DELETE FROM learning_image_objects WHERE analysis_id = :rid"),
                        {"rid": str(run_id)},
                    )
                    await conn.execute(
                        text("DELETE FROM supplement_analysis_runs WHERE id = :rid"),
                        {"rid": str(run_id)},
                    )
