"""Integration: Stage-2 owner isolation for the ambient-tx Step 6 analysis_results write path.

Authority: outputs/todo-list/2026-06-14/2026-06-14-ambient-transaction-refactor-plan.md
           outputs/todo-list/2026-06-14/2026-06-14-step6-design.md

ambient-tx Step 6 migrated ``analysis_results._persist_result`` from
``async with session.begin()`` to ``persist_scope`` (the route swap lands with the 6b
privacy batch, since the analysis_results DELETE route depends on privacy:683). This proves
the *actual migrated service code* persists under the FORCE RLS Stage-2 posture, connected
as the non-superuser ``lemon_app`` role inside a request-managed transaction:

  * the participate-mode INSERT into the plaintext-owner ``analysis_results`` table
    (0023b Type A, keyed to ``app.current_subject``) succeeds and isolates,
  * a different subject sees no row (USING isolation), and
  * the row persists once the request transaction commits.

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
from src.models.schemas.algorithm import ActivityScoreRequest
from src.models.schemas.user import UserProfile
from src.security.auth import AuthenticatedUser
from src.security.privacy import hash_actor_subject
from src.security.subjects import build_owner_subject
from src.services.analysis_results import store_activity_score_result

ADMIN_URL = os.getenv("TEST_DATABASE_URL")
APP_URL = os.getenv("TEST_RLS_APP_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    ADMIN_URL is None or APP_URL is None,
    reason=(
        "Set TEST_DATABASE_URL (admin) and TEST_RLS_APP_DATABASE_URL (lemon_app) "
        "to run the Stage-2 Step 6 analysis_results owner-isolation proof."
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


async def _count_by_id(session: AsyncSession, row_id: uuid.UUID) -> int:
    """Count analysis_results rows visible to the current GUC subject for ``id``."""
    return (
        await session.execute(
            text("SELECT count(*) FROM analysis_results WHERE id = :rid"),
            {"rid": str(row_id)},
        )
    ).scalar_one()


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(subject=f"alice-{uuid.uuid4()}", issuer="test-issuer")


def _activity_request() -> ActivityScoreRequest:
    return ActivityScoreRequest(
        profile=UserProfile(
            age=50,
            sex="female",
            height_cm=160,
            weight_kg=68,
            chronic_diseases=["diabetes"],
        ),
        daily_steps=7000,
        target_hr_minutes=20,
    )


async def test_stage2_analysis_result_is_owner_isolated_and_persists() -> None:
    """Plaintext-owner analysis_results policy accepts the participate-mode INSERT."""
    settings = get_settings()
    user = _user()
    owner = build_owner_subject(user)
    owner_hash = hash_actor_subject(user, settings)
    result_id: uuid.UUID | None = None
    async with _stage2_engines() as (admin, app):
        try:
            app_sessionmaker = async_sessionmaker(app, expire_on_commit=False)
            async with app_sessionmaker() as session:
                transaction = await session.begin()
                await set_request_rls_context(session, subject=owner, subject_hash=owner_hash)
                session.info[REQUEST_MANAGED_TX] = True
                await _assert_request_role_enforces_rls(session)

                record = await store_activity_score_result(session, user, _activity_request())
                result_id = record.id

                # Owner sees the row...
                assert await _count_by_id(session, result_id) == 1
                # ...a different subject does not (plaintext USING isolation).
                await set_request_rls_context(
                    session, subject="iss::someone-else", subject_hash="0" * 64
                )
                assert await _count_by_id(session, result_id) == 0

                await transaction.commit()

            async with admin.connect() as conn:
                persisted = (
                    await conn.execute(
                        text("SELECT count(*) FROM analysis_results WHERE id = :rid"),
                        {"rid": str(result_id)},
                    )
                ).scalar_one()
                assert persisted == 1
        finally:
            if result_id is not None:
                async with admin.begin() as conn:
                    await conn.execute(
                        text("DELETE FROM analysis_results WHERE id = :rid"),
                        {"rid": str(result_id)},
                    )
