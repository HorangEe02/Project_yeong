"""Integration: Stage-2 owner isolation + out-of-band audit survival for ambient-tx Step 6b.

Authority: outputs/todo-list/2026-06-14/2026-06-14-ambient-transaction-refactor-plan.md
           outputs/todo-list/2026-06-14/2026-06-14-step6-design.md

ambient-tx Step 6b migrated ``grant_consent`` / ``revoke_consent`` /
``delete_analysis_result_for_user`` to ``persist_scope`` and decoupled their audit from
the request transaction: the inline ``_build_audit_log`` + ``session.add`` was removed and
the audit now flows through the ambient-aware ``record_audit_event`` (out-of-band via the
privileged audit engine under a request-managed session). The consent/privacy routes adopted
``get_rls_context_session``.

This proves the *actual migrated service code* under the FORCE RLS Stage-2 posture, connected
as the non-superuser ``lemon_app`` role inside a request-managed transaction:

  * the participate-mode ``grant_consent`` INSERT into the plaintext-owner ``consent_records``
    table (0023b Type A, keyed to ``app.current_subject``) succeeds, isolates from other
    subjects, and persists once the request transaction commits, and
  * THE LOAD-BEARING Option-A proof: when the request transaction is force-rolled-back, the
    consent row is discarded but the audit row SURVIVES, because ``record_audit_event`` wrote
    it out-of-band through the privileged audit engine (independent commit) — never riding the
    request transaction that ``lemon_app`` cannot write ``audit_logs`` from anyway.

Run gate (skip unless both set):
  TEST_DATABASE_URL          — admin/privileged conn (verify + cleanup + out-of-band audit)
  TEST_RLS_APP_DATABASE_URL  — lemon_app (NOSUPERUSER, NOBYPASSRLS) request conn
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from src.config import get_settings
from src.db.rls_context import set_request_rls_context
from src.db.session import dispose_engine
from src.db.tx import REQUEST_MANAGED_TX
from src.models.schemas.privacy import ConsentType
from src.security.auth import AuthenticatedUser
from src.security.privacy import hash_actor_subject
from src.security.subjects import build_owner_subject
from src.services.privacy import delete_analysis_result_for_user, grant_consent

ADMIN_URL = os.getenv("TEST_DATABASE_URL")
APP_URL = os.getenv("TEST_RLS_APP_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    ADMIN_URL is None or APP_URL is None,
    reason=(
        "Set TEST_DATABASE_URL (admin) and TEST_RLS_APP_DATABASE_URL (lemon_app) "
        "to run the Stage-2 Step 6b consent owner-isolation + audit-survival proofs."
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
        # The out-of-band audit writer reuses the module-level engine (audit_database_url
        # unset → falls back to the main sessionmaker); dispose it so the next async test
        # does not reuse a pool bound to this test's now-closed event loop.
        await dispose_engine()


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


async def _count_owner(session: AsyncSession, table: str, owner_subject: str) -> int:
    """Count rows visible to the current GUC subject for ``owner_subject``."""
    return (
        await session.execute(
            text(f"SELECT count(*) FROM {table} WHERE owner_subject = :o"),
            {"o": owner_subject},
        )
    ).scalar_one()


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(subject=f"alice-{uuid.uuid4()}", issuer="test-issuer")


def _request() -> Request:
    """Return a minimal auditable Starlette request."""
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/me/privacy/consents/sensitive_health_analysis",
            "headers": [(b"user-agent", b"stage2-agent"), (b"x-request-id", b"req-stage2")],
            "client": ("203.0.113.10", 12345),
        }
    )


async def test_stage2_grant_consent_is_owner_isolated_and_persists() -> None:
    """Plaintext-owner consent_records policy accepts the participate-mode grant + isolates."""
    settings = get_settings()
    user = _user()
    owner = build_owner_subject(user)
    owner_hash = hash_actor_subject(user, settings)
    async with _stage2_engines() as (admin, app):
        try:
            app_sessionmaker = async_sessionmaker(app, expire_on_commit=False)
            async with app_sessionmaker() as session:
                transaction = await session.begin()
                await set_request_rls_context(session, subject=owner, subject_hash=owner_hash)
                session.info[REQUEST_MANAGED_TX] = True
                await _assert_request_role_enforces_rls(session)

                await grant_consent(
                    session, user, ConsentType.SENSITIVE_HEALTH_ANALYSIS, _request(), settings
                )

                # Owner sees the (flushed) consent row...
                assert await _count_owner(session, "consent_records", owner) == 1
                # ...a different subject does not (plaintext USING isolation).
                await set_request_rls_context(
                    session, subject="iss::someone-else", subject_hash="0" * 64
                )
                assert await _count_owner(session, "consent_records", owner) == 0

                await transaction.commit()

            async with admin.connect() as conn:
                persisted = (
                    await conn.execute(
                        text("SELECT count(*) FROM consent_records WHERE owner_subject = :o"),
                        {"o": owner},
                    )
                ).scalar_one()
                assert persisted == 1
        finally:
            async with admin.begin() as conn:
                await conn.execute(
                    text("DELETE FROM audit_logs WHERE actor_subject_hash = :h"),
                    {"h": owner_hash},
                )
                await conn.execute(
                    text("DELETE FROM consent_records WHERE owner_subject = :o"),
                    {"o": owner},
                )


async def test_stage2_grant_consent_audit_survives_forced_request_rollback() -> None:
    """Option-A proof: a force-rolled-back request keeps the out-of-band audit, drops the row."""
    settings = get_settings()
    user = _user()
    owner = build_owner_subject(user)
    owner_hash = hash_actor_subject(user, settings)
    async with _stage2_engines() as (admin, app):
        try:
            app_sessionmaker = async_sessionmaker(app, expire_on_commit=False)
            async with app_sessionmaker() as session:
                transaction = await session.begin()
                await set_request_rls_context(session, subject=owner, subject_hash=owner_hash)
                session.info[REQUEST_MANAGED_TX] = True
                await _assert_request_role_enforces_rls(session)

                await grant_consent(
                    session, user, ConsentType.SENSITIVE_HEALTH_ANALYSIS, _request(), settings
                )
                # The consent row is flushed (visible within the request tx)...
                assert await _count_owner(session, "consent_records", owner) == 1

                # ...but we force the request transaction to roll back (simulating a later
                # dependency-exit failure). The owner-data write must vanish.
                await transaction.rollback()

            async with admin.connect() as conn:
                consent_n = (
                    await conn.execute(
                        text("SELECT count(*) FROM consent_records WHERE owner_subject = :o"),
                        {"o": owner},
                    )
                ).scalar_one()
                assert consent_n == 0, "consent row must roll back with the request transaction"

                # The audit, written out-of-band via the privileged audit engine, SURVIVES —
                # and carries the success outcome/action (not merely some stray row).
                audit_n = (
                    await conn.execute(
                        text(
                            "SELECT count(*) FROM audit_logs "
                            "WHERE actor_subject_hash = :h AND action = 'consent_granted' "
                            "AND outcome = 'success'"
                        ),
                        {"h": owner_hash},
                    )
                ).scalar_one()
                assert audit_n == 1, "out-of-band audit must survive the request rollback"
        finally:
            async with admin.begin() as conn:
                await conn.execute(
                    text("DELETE FROM audit_logs WHERE actor_subject_hash = :h"),
                    {"h": owner_hash},
                )
                await conn.execute(
                    text("DELETE FROM consent_records WHERE owner_subject = :o"),
                    {"o": owner},
                )


async def test_stage2_delete_analysis_audit_survives_forced_request_rollback() -> None:
    """Option-A proof for the DELETE path: a force-rolled-back delete keeps the audit out-of-band.

    delete_analysis_result_for_user runs under participate mode (flush-only delete + out-of-band
    audit). Forcing the request transaction to roll back undoes the delete (the owner row
    reappears) but the audit, committed independently by the privileged audit engine, survives.
    """
    settings = get_settings()
    user = _user()
    owner = build_owner_subject(user)
    owner_hash = hash_actor_subject(user, settings)
    result_id = uuid.uuid4()
    async with _stage2_engines() as (admin, app):
        try:
            # Pre-create an owned analysis result (committed) for the delete to target.
            async with admin.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO analysis_results "
                        "(id, owner_subject, analysis_type, algorithm_version, "
                        " input_snapshot, result_snapshot, created_at, updated_at) "
                        "VALUES (:id, :owner, 'activity_score', 'activity-v1.0.0', "
                        " '{}'::jsonb, '{}'::jsonb, now(), now())"
                    ),
                    {"id": str(result_id), "owner": owner},
                )

            app_sessionmaker = async_sessionmaker(app, expire_on_commit=False)
            async with app_sessionmaker() as session:
                transaction = await session.begin()
                await set_request_rls_context(session, subject=owner, subject_hash=owner_hash)
                session.info[REQUEST_MANAGED_TX] = True
                await _assert_request_role_enforces_rls(session)

                deleted = await delete_analysis_result_for_user(
                    session, user, result_id, _request(), settings
                )
                assert deleted is True  # owner-scoped row was found and the delete issued

                # Force the request tx to roll back → the delete is undone, the row survives.
                await transaction.rollback()

            async with admin.connect() as conn:
                row_n = (
                    await conn.execute(
                        text("SELECT count(*) FROM analysis_results WHERE id = :id"),
                        {"id": str(result_id)},
                    )
                ).scalar_one()
                assert row_n == 1, "the deleted row must reappear after the request rollback"

                audit_n = (
                    await conn.execute(
                        text(
                            "SELECT count(*) FROM audit_logs "
                            "WHERE actor_subject_hash = :h AND action = 'analysis_result_deleted' "
                            "AND outcome = 'success'"
                        ),
                        {"h": owner_hash},
                    )
                ).scalar_one()
                assert audit_n == 1, "out-of-band delete audit must survive the request rollback"
        finally:
            async with admin.begin() as conn:
                await conn.execute(
                    text("DELETE FROM audit_logs WHERE actor_subject_hash = :h"),
                    {"h": owner_hash},
                )
                await conn.execute(
                    text("DELETE FROM analysis_results WHERE id = :id"),
                    {"id": str(result_id)},
                )
