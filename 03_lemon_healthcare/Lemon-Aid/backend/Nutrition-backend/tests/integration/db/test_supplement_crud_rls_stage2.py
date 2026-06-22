"""Integration: Stage-2 owner isolation for the supplement CRUD RLS migration.

The flip-exposed fix migrated four supplement owner routes to the RLS seam
(``list_user_supplements`` / ``get_user_supplement`` →
``get_rls_context_session``; ``delete_user_supplement`` → service ``persist_scope``
+ dep swap). This proves the *migrated service code* behaves correctly connected
as the non-superuser ``lemon_app`` role under FORCE RLS:

  * ``list_user_supplement_records`` / ``get_user_supplement_record`` return the
    owner's row with the per-request GUC, and a different subject sees nothing
    (0023b Type A ``owner_subject`` USING isolation),
  * ``soft_delete_user_supplement`` participates in the request transaction
    (persist_scope: flush only, no mid-service commit), so the soft delete
    persists once the request transaction commits and the GUC survives, and
  * a different subject cannot soft-delete another owner's row (RLS hides it).

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
from src.db.rls_context import set_request_rls_context
from src.db.tx import REQUEST_MANAGED_TX
from src.models.db.supplement import UserSupplement
from src.security.auth import AuthenticatedUser
from src.security.subjects import build_owner_subject
from src.services.supplement_registration import (
    get_user_supplement_record,
    list_user_supplement_records,
    soft_delete_user_supplement,
)

ADMIN_URL = os.getenv("TEST_DATABASE_URL")
APP_URL = os.getenv("TEST_RLS_APP_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    ADMIN_URL is None or APP_URL is None,
    reason=(
        "Set TEST_DATABASE_URL (admin) and TEST_RLS_APP_DATABASE_URL (lemon_app) "
        "to run the Stage-2 supplement CRUD owner-isolation proof."
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


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(subject=f"alice-{uuid.uuid4()}", issuer="test-issuer")


async def _seed_supplement(admin: AsyncEngine, owner_subject: str) -> uuid.UUID:
    """Insert one active supplement for ``owner_subject`` via the admin engine."""
    supplement = UserSupplement(
        owner_subject=owner_subject,
        display_name="Vitamin D 1000 IU",
        serving_snapshot={"amount": 1, "unit": "capsule", "daily_servings": 1},
        intake_schedule={"frequency": "daily", "time_of_day": ["morning"]},
    )
    admin_sessionmaker = async_sessionmaker(admin, expire_on_commit=False)
    async with admin_sessionmaker() as session, session.begin():
        session.add(supplement)
    return supplement.id


async def test_stage2_supplement_crud_is_owner_isolated_and_soft_delete_persists() -> None:
    """Reads isolate by owner GUC; soft delete participates and persists."""
    owner = _user()
    other = _user()
    owner_subject = build_owner_subject(owner)
    supplement_id: uuid.UUID | None = None
    async with _stage2_engines() as (admin, app):
        try:
            supplement_id = await _seed_supplement(admin, owner_subject)
            app_sessionmaker = async_sessionmaker(app, expire_on_commit=False)

            # --- Reads: owner sees the row; a different subject does not. ---
            async with app_sessionmaker() as session:
                transaction = await session.begin()
                await set_request_rls_context(
                    session,
                    subject=owner_subject,
                    subject_hash=build_owner_subject(owner),
                )
                session.info[REQUEST_MANAGED_TX] = True
                await _assert_request_role_enforces_rls(session)

                listed = await list_user_supplement_records(session, owner, limit=20, offset=0)
                assert [r.id for r in listed.results] == [supplement_id]
                fetched = await get_user_supplement_record(session, owner, supplement_id)
                assert fetched is not None

                # A different owner subject sees no rows (USING isolation).
                await set_request_rls_context(
                    session,
                    subject=build_owner_subject(other),
                    subject_hash=build_owner_subject(other),
                )
                empty = await list_user_supplement_records(session, other, limit=20, offset=0)
                assert empty.results == []
                assert await get_user_supplement_record(session, other, supplement_id) is None
                await transaction.commit()

            # --- Cross-subject soft delete is denied (RLS hides the row). ---
            async with app_sessionmaker() as session:
                transaction = await session.begin()
                await set_request_rls_context(
                    session,
                    subject=build_owner_subject(other),
                    subject_hash=build_owner_subject(other),
                )
                session.info[REQUEST_MANAGED_TX] = True
                assert await soft_delete_user_supplement(session, other, supplement_id) is False
                await transaction.commit()

            async with admin.connect() as conn:
                still_active = (
                    await conn.execute(
                        text("SELECT deleted_at IS NULL FROM user_supplements WHERE id = :sid"),
                        {"sid": str(supplement_id)},
                    )
                ).scalar_one()
                assert still_active is True  # the other subject could not delete it

            # --- Owner soft delete participates (flush only) and persists at commit. ---
            async with app_sessionmaker() as session:
                transaction = await session.begin()
                await set_request_rls_context(
                    session,
                    subject=owner_subject,
                    subject_hash=owner_subject,
                )
                session.info[REQUEST_MANAGED_TX] = True
                assert await soft_delete_user_supplement(session, owner, supplement_id) is True
                await transaction.commit()  # the request transaction owns the commit

            async with admin.connect() as conn:
                deleted = (
                    await conn.execute(
                        text("SELECT deleted_at IS NOT NULL FROM user_supplements WHERE id = :sid"),
                        {"sid": str(supplement_id)},
                    )
                ).scalar_one()
                assert deleted is True  # soft delete persisted after the request commit
        finally:
            if supplement_id is not None:
                async with admin.begin() as conn:
                    await conn.execute(
                        text("DELETE FROM user_supplements WHERE id = :sid"),
                        {"sid": str(supplement_id)},
                    )
