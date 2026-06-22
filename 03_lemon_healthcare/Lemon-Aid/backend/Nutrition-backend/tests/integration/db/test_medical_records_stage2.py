"""Integration: Stage-2 owner isolation for the ambient-tx Step 5 medical write paths.

Authority: outputs/todo-list/2026-06-14/2026-06-14-ambient-transaction-refactor-plan.md

ambient-tx Step 5 migrated ``create_medical_record`` / ``confirm_medical_record`` /
``create_patient_status_snapshot`` to ``persist_scope`` and the medical-records
routes to ``get_rls_context_session`` (dropping the consent-read closer). This proves
the *actual migrated service code* works under the FORCE RLS Stage-2 posture, connected
as the non-superuser ``lemon_app`` role inside a request-managed transaction with the
owner GUCs set:

  * the participate-mode multi-row write (collection + FK child condition, flush only)
    succeeds against both the hashed ``owner_subject_hash`` parent policy (0023b Type B,
    ``medical_record_collections`` / ``patient_status_snapshots``) and the FK-child join
    policy (0023b Type C, ``patient_conditions`` → parent collection), keyed to
    ``app.current_subject_hash``,
  * a different subject sees neither the parent nor the child row (USING isolation), and
  * both rows persist once the request transaction commits.

Run gate (skip unless both set):
  TEST_DATABASE_URL          — admin/privileged conn (verify + cleanup)
  TEST_RLS_APP_DATABASE_URL  — lemon_app (NOSUPERUSER, NOBYPASSRLS) request conn
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from src.config import get_settings
from src.db.rls_context import set_request_rls_context
from src.db.tx import REQUEST_MANAGED_TX
from src.models.schemas.medical import (
    MedicalRecordCreateRequest,
    PatientConditionInput,
    PatientStatusSnapshotCreate,
)
from src.security.auth import AuthenticatedUser
from src.security.privacy import hash_actor_subject
from src.security.subjects import build_owner_subject
from src.services.medical_records import create_medical_record, create_patient_status_snapshot

ADMIN_URL = os.getenv("TEST_DATABASE_URL")
APP_URL = os.getenv("TEST_RLS_APP_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    ADMIN_URL is None or APP_URL is None,
    reason=(
        "Set TEST_DATABASE_URL (admin) and TEST_RLS_APP_DATABASE_URL (lemon_app) "
        "to run the Stage-2 Step 5 medical-records owner-isolation proofs."
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


async def _count_by_id(session: AsyncSession, table: str, row_id: uuid.UUID) -> int:
    """Count rows visible to the current GUC subject for ``id`` (``table`` is a constant).

    The ``WHERE id`` filter matches the row without RLS, so 0 under a *different*
    subject proves the USING policy hid it (it would be 1 if RLS were bypassed).
    """
    return (
        await session.execute(
            text(f"SELECT count(*) FROM {table} WHERE id = :rid"),
            {"rid": str(row_id)},
        )
    ).scalar_one()


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(subject=f"alice-{uuid.uuid4()}", issuer="test-issuer")


async def test_stage2_medical_record_collection_and_child_are_owner_isolated_and_persist() -> None:
    """Hashed parent policy + FK-child join policy accept the participate-mode write."""
    settings = get_settings()
    user = _user()
    owner = build_owner_subject(user)
    owner_hash = hash_actor_subject(user, settings)
    collection_id: uuid.UUID | None = None
    async with _stage2_engines() as (admin, app):
        try:
            app_sessionmaker = async_sessionmaker(app, expire_on_commit=False)
            async with app_sessionmaker() as session:
                transaction = await session.begin()
                await set_request_rls_context(session, subject=owner, subject_hash=owner_hash)
                session.info[REQUEST_MANAGED_TX] = True
                await _assert_request_role_enforces_rls(session)

                collection, conditions, _medications = await create_medical_record(
                    session,
                    user,
                    settings,
                    MedicalRecordCreateRequest(
                        record_type="condition",
                        condition=PatientConditionInput(
                            condition_text="사용자 확인 질환명",
                            clinical_status="active",
                        ),
                        user_confirmed=True,
                    ),
                )
                collection_id = collection.id
                condition_id = conditions[0].id

                # Owner sees both the parent collection and its FK child condition...
                assert await _count_by_id(session, "medical_record_collections", collection_id) == 1
                assert await _count_by_id(session, "patient_conditions", condition_id) == 1
                # ...a different subject sees neither (parent USING + child join isolation).
                await set_request_rls_context(
                    session, subject="iss::someone-else", subject_hash="0" * 64
                )
                assert await _count_by_id(session, "medical_record_collections", collection_id) == 0
                assert await _count_by_id(session, "patient_conditions", condition_id) == 0

                await transaction.commit()

            async with admin.connect() as conn:
                parent = (
                    await conn.execute(
                        text("SELECT count(*) FROM medical_record_collections WHERE id = :rid"),
                        {"rid": str(collection_id)},
                    )
                ).scalar_one()
                child = (
                    await conn.execute(
                        text("SELECT count(*) FROM patient_conditions WHERE id = :rid"),
                        {"rid": str(condition_id)},
                    )
                ).scalar_one()
                assert parent == 1
                assert child == 1
        finally:
            if collection_id is not None:
                async with admin.begin() as conn:
                    await conn.execute(
                        text("DELETE FROM patient_conditions WHERE medical_collection_id = :cid"),
                        {"cid": str(collection_id)},
                    )
                    await conn.execute(
                        text("DELETE FROM medical_record_collections WHERE id = :cid"),
                        {"cid": str(collection_id)},
                    )


async def test_stage2_patient_status_snapshot_is_owner_isolated_and_persists() -> None:
    """Hashed owner_subject_hash policy (0023b) accepts the participate-mode write."""
    settings = get_settings()
    user = _user()
    owner = build_owner_subject(user)
    owner_hash = hash_actor_subject(user, settings)
    snapshot_id: uuid.UUID | None = None
    async with _stage2_engines() as (admin, app):
        try:
            app_sessionmaker = async_sessionmaker(app, expire_on_commit=False)
            async with app_sessionmaker() as session:
                transaction = await session.begin()
                await set_request_rls_context(session, subject=owner, subject_hash=owner_hash)
                session.info[REQUEST_MANAGED_TX] = True
                await _assert_request_role_enforces_rls(session)

                snapshot = await create_patient_status_snapshot(
                    session, user, settings, PatientStatusSnapshotCreate()
                )
                snapshot_id = snapshot.id

                assert await _count_by_id(session, "patient_status_snapshots", snapshot_id) == 1
                await set_request_rls_context(
                    session, subject="iss::someone-else", subject_hash="0" * 64
                )
                assert await _count_by_id(session, "patient_status_snapshots", snapshot_id) == 0

                await transaction.commit()

            async with admin.connect() as conn:
                persisted = (
                    await conn.execute(
                        text("SELECT count(*) FROM patient_status_snapshots WHERE id = :rid"),
                        {"rid": str(snapshot_id)},
                    )
                ).scalar_one()
                assert persisted == 1
        finally:
            if snapshot_id is not None:
                async with admin.begin() as conn:
                    await conn.execute(
                        text("DELETE FROM patient_status_snapshots WHERE id = :rid"),
                        {"rid": str(snapshot_id)},
                    )
