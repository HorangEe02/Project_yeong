"""Integration: Stage-2 ambient-transaction end-to-end proof under lemon_app.

Authority: outputs/todo-list/2026-06-14/2026-06-14-ambient-transaction-refactor-plan.md

Proves the FORCE RLS Stage-2 posture works with the ambient-transaction seam:
under a request-managed (``request_managed_tx``) session connected as the
non-superuser ``lemon_app`` role,

  * an owner-scoped WRITE succeeds and is isolated (RLS WITH CHECK + USING),
  * ``record_audit_event`` writes the audit via the PRIVILEGED audit engine
    (lemon_app holds only SELECT on audit_logs), not the request session, and
  * the audit survives a rollback of the request transaction (out-of-band),
    while the request's owner-table write is rolled back.

This is the load-bearing validation that audit/write persistence + isolation
hold once a route adopts get_rls_context_session and DATABASE_URL flips to
lemon_app (Option A: privileged out-of-band audit writer).

Run gate (skip unless both set):
  TEST_DATABASE_URL          — admin/privileged conn (seed, audit engine, verify)
  TEST_RLS_APP_DATABASE_URL  — lemon_app (NOSUPERUSER, NOBYPASSRLS) request conn

Local run example (after setting a local lemon_app password):
  TEST_DATABASE_URL=postgresql+asyncpg://postgres:***@127.0.0.1:56322/postgres \
  TEST_RLS_APP_DATABASE_URL=postgresql+asyncpg://lemon_app:***@127.0.0.1:56322/postgres \
  .venv/bin/python -m pytest \
    Nutrition-backend/tests/integration/db/test_ambient_audit_stage2.py -q
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from src.config import get_settings
from src.db.rls_context import set_request_rls_context
from src.db.tx import REQUEST_MANAGED_TX
from src.security.auth import AuthenticatedUser
from src.security.privacy import hash_actor_subject
from src.security.subjects import build_owner_subject
from src.services import privacy
from starlette.requests import Request

ADMIN_URL = os.getenv("TEST_DATABASE_URL")
APP_URL = os.getenv("TEST_RLS_APP_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    ADMIN_URL is None or APP_URL is None,
    reason=(
        "Set TEST_DATABASE_URL (admin) and TEST_RLS_APP_DATABASE_URL (lemon_app) "
        "to run the Stage-2 ambient-transaction proof."
    ),
)

_OWNER_TABLE = "analysis_results"
_INSERT_OWNER_ROW = text(
    f"INSERT INTO {_OWNER_TABLE} "
    "(id, owner_subject, analysis_type, algorithm_version, input_snapshot, result_snapshot) "
    "VALUES (gen_random_uuid(), :owner, 'nutrition_analysis', :alg, '{}'::jsonb, '{}'::jsonb)"
)


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [],
            "query_string": b"",
            "client": ("127.0.0.1", 0),
        }
    )


async def test_stage2_audit_survives_rollback_and_owner_write_is_isolated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: owner write isolated, audit out-of-band survives rollback."""
    assert ADMIN_URL is not None and APP_URL is not None
    settings = get_settings()
    alg = f"ambient-stage2-{uuid.uuid4()}"
    audit_action = f"ambient-stage2-audit-{uuid.uuid4()}"
    user = AuthenticatedUser(subject=f"alice-{uuid.uuid4()}", issuer="test-issuer")
    owner = build_owner_subject(user)

    admin = create_async_engine(ADMIN_URL, pool_pre_ping=True)
    app = create_async_engine(APP_URL, pool_pre_ping=True)
    # The privileged audit engine: lemon_app cannot write audit_logs, so audits
    # route here. Inject it so record_audit_event's out-of-band write is verifiable.
    audit_sessionmaker = async_sessionmaker(admin, expire_on_commit=False)
    monkeypatch.setattr(privacy, "get_audit_sessionmaker", lambda: audit_sessionmaker)

    try:
        app_sessionmaker = async_sessionmaker(app, expire_on_commit=False)
        async with app_sessionmaker() as session:
            transaction = await session.begin()
            # Reproduce get_rls_context_session's setup on the lemon_app session.
            await set_request_rls_context(
                session,
                subject=owner,
                subject_hash=hash_actor_subject(user, settings),
            )
            session.info[REQUEST_MANAGED_TX] = True

            # Owner-scoped WRITE under RLS (lemon_app has CRUD + owner policy).
            await session.execute(_INSERT_OWNER_ROW, {"owner": owner, "alg": alg})

            # Isolation: the owner sees its own just-written row...
            seen_own = (
                await session.execute(
                    text(f"SELECT count(*) FROM {_OWNER_TABLE} " "WHERE algorithm_version = :alg"),
                    {"alg": alg},
                )
            ).scalar_one()
            assert seen_own == 1
            # ...and a different subject sees none of it.
            await set_request_rls_context(
                session, subject="iss::someone-else", subject_hash="0" * 64
            )
            seen_other = (
                await session.execute(
                    text(f"SELECT count(*) FROM {_OWNER_TABLE} " "WHERE algorithm_version = :alg"),
                    {"alg": alg},
                )
            ).scalar_one()
            assert seen_other == 0

            # Audit via the privileged out-of-band engine (NOT the lemon_app session).
            audit = await privacy.record_audit_event(
                session=session,
                user=user,
                action=audit_action,
                resource_type="analysis_result",
                resource_id=None,
                outcome="success",
                request=_request(),
                settings=settings,
            )
            # id is assigned client-side (uuid4); actual persistence is proven
            # below by the admin re-query after the request rollback.
            assert audit.id is not None

            # Roll back the request transaction: the owner-table write is discarded.
            await transaction.rollback()

        # The audit (committed out-of-band) survived the request rollback...
        async with admin.connect() as conn:
            audit_count = (
                await conn.execute(
                    text("SELECT count(*) FROM audit_logs WHERE action = :a"),
                    {"a": audit_action},
                )
            ).scalar_one()
            assert audit_count == 1
            # ...while the rolled-back owner-table write left nothing behind.
            row_count = (
                await conn.execute(
                    text(f"SELECT count(*) FROM {_OWNER_TABLE} " "WHERE algorithm_version = :alg"),
                    {"alg": alg},
                )
            ).scalar_one()
            assert row_count == 0
    finally:
        async with admin.begin() as conn:
            await conn.execute(
                text("DELETE FROM audit_logs WHERE action = :a"), {"a": audit_action}
            )
            await conn.execute(
                text(f"DELETE FROM {_OWNER_TABLE} WHERE algorithm_version = :alg"),
                {"alg": alg},
            )
        await app.dispose()
        await admin.dispose()
