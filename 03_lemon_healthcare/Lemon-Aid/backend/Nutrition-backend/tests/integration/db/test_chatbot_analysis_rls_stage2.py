"""Integration: Stage-2 owner isolation for the run_chatbot RLS seam.

Authority: /Users/yeong/.claude/plans/robust-rolling-valiant.md (Phase C2)

ambient-tx Step 8 Phase C2 migrated ``run_chatbot`` (ai_agent.py) to the new
``rls_request_transaction_allow_inner_commit`` context manager. Unlike the other
RLS seams, run_chatbot's analysis path calls ``store_app_health_analysis_result``
(app_health_analysis.py: ``add -> commit -> refresh``), a DO-NOT-TOUCH service
whose inner ``commit`` releases the transaction-local RLS GUCs and whose
subsequent ``refresh`` autobegins a new transaction. With a plain is_local GUC
that refresh fails closed under FORCE RLS (``Could not refresh instance``). The
new CM re-applies the is_local GUCs on every transaction begin via an
``after_begin`` listener, so this proves — connected as the non-superuser
``lemon_app`` role — that:

  * the analysis-path INSERT into ``analysis_results`` (0023b Type A) succeeds and
    the DO-NOT-TOUCH ``commit + refresh`` does NOT fail closed (the listener
    re-applied the GUC on the refresh transaction),
  * the row persists once the request transaction commits,
  * no GUC leaks onto the pooled connection (is_local), and
  * the non-analysis ``record_unknown_knowledge_event`` insert (service policy,
    ownerless backlog) persists via the CM's exit commit.

The two ``async with`` blocks are intentionally nested (not combined): the
analysis test must observe ``session.in_transaction()`` *between* the CM exit and
the session close, which a single combined ``with`` cannot express.

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
from src.db.dependencies import rls_request_transaction_allow_inner_commit
from src.security.auth import AuthenticatedUser
from src.services.app_health_analysis import store_app_health_analysis_result
from src.services.chatbot_unknown_backlog import (
    build_unknown_knowledge_event,
    record_unknown_knowledge_event,
)

ADMIN_URL = os.getenv("TEST_DATABASE_URL")
APP_URL = os.getenv("TEST_RLS_APP_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    ADMIN_URL is None or APP_URL is None,
    reason=(
        "Set TEST_DATABASE_URL (admin) and TEST_RLS_APP_DATABASE_URL (lemon_app) "
        "to run the Stage-2 Phase C2 run_chatbot RLS-seam proof."
    ),
)


@asynccontextmanager
async def _stage2_engines() -> AsyncIterator[tuple[AsyncEngine, AsyncEngine]]:
    """Yield (admin, lemon_app) engines and dispose both afterwards."""
    assert ADMIN_URL is not None and APP_URL is not None
    admin = create_async_engine(ADMIN_URL, pool_pre_ping=True)
    # pool_size=1 so the leak guard re-checks the same physical connection.
    app = create_async_engine(APP_URL, pool_pre_ping=True, pool_size=1, max_overflow=0)
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


async def test_stage2_chatbot_cm_survives_store_inner_commit_refresh() -> None:
    """The analysis path persists despite store's DO-NOT-TOUCH commit+refresh.

    This is the case a plain is_local GUC fails: store's refresh autobegins a
    GUC-less transaction and raises ``Could not refresh instance`` under FORCE
    RLS. The CM's after_begin listener re-applies the GUC so the refresh sees the
    just-inserted row.
    """
    settings = get_settings()
    user = _user()
    result_id: uuid.UUID | None = None
    async with _stage2_engines() as (admin, app):
        try:
            app_sessionmaker = async_sessionmaker(app, expire_on_commit=False)
            async with app_sessionmaker() as session:
                async with rls_request_transaction_allow_inner_commit(session, user, settings):
                    # First read autobegins T1; the after_begin listener sets GUCs.
                    await _assert_request_role_enforces_rls(session)
                    # DO-NOT-TOUCH: add -> commit (releases T1 GUC) -> refresh (T2).
                    # Without the listener this refresh fails closed under FORCE RLS.
                    record = await store_app_health_analysis_result(
                        session,
                        user,
                        analysis_kind="today_analysis",
                        input_snapshot={"context_sections": [], "request_id": "req-stage2"},
                        result_snapshot={"summary": "ok"},
                        user_confirmed=True,
                    )
                    result_id = record.id
                    assert result_id is not None  # refresh succeeded
                # CM exit committed the trailing read-only refresh transaction.
                assert session.in_transaction() is False

            # The owner row is durable after the request transaction.
            async with admin.connect() as conn:
                persisted = (
                    await conn.execute(
                        text("SELECT count(*) FROM analysis_results WHERE id = :rid"),
                        {"rid": str(result_id)},
                    )
                ).scalar_one()
                assert persisted == 1

            # Pool-leak guard: the reused (pool_size=1) connection carries no GUC,
            # because the CM used is_local (released at each transaction's end).
            async with app_sessionmaker() as leak_session, leak_session.begin():
                leaked = (
                    await leak_session.execute(
                        text("SELECT current_setting('app.current_subject', true)")
                    )
                ).scalar_one()
                assert leaked in (None, "")
        finally:
            if result_id is not None:
                async with admin.begin() as conn:
                    await conn.execute(
                        text("DELETE FROM analysis_results WHERE id = :rid"),
                        {"rid": str(result_id)},
                    )


async def test_stage2_chatbot_cm_inner_committed_row_survives_later_error() -> None:
    """A store-committed row stays durable when the body later raises.

    store's inner ``commit`` makes the analysis row durable independently of the
    request transaction; a later in-body exception only rolls back the trailing
    (read-only) refresh transaction, so the row must remain. Confirms the
    DO-NOT-TOUCH inner-commit side effect is the intended, irreversible behavior.
    """
    settings = get_settings()
    user = _user()
    result_id: uuid.UUID | None = None
    async with _stage2_engines() as (admin, app):
        try:
            app_sessionmaker = async_sessionmaker(app, expire_on_commit=False)
            captured: dict[str, uuid.UUID] = {}
            with pytest.raises(RuntimeError, match="after store"):
                async with app_sessionmaker() as session:
                    async with rls_request_transaction_allow_inner_commit(session, user, settings):
                        await _assert_request_role_enforces_rls(session)
                        record = await store_app_health_analysis_result(
                            session,
                            user,
                            analysis_kind="today_analysis",
                            input_snapshot={"context_sections": [], "request_id": "req-exc"},
                            result_snapshot={"summary": "ok"},
                            user_confirmed=True,
                        )
                        captured["id"] = record.id
                        raise RuntimeError("after store")
            result_id = captured.get("id")
            assert result_id is not None

            async with admin.connect() as conn:
                persisted = (
                    await conn.execute(
                        text("SELECT count(*) FROM analysis_results WHERE id = :rid"),
                        {"rid": str(result_id)},
                    )
                ).scalar_one()
                assert persisted == 1  # store's own commit survived the later error
        finally:
            if result_id is not None:
                async with admin.begin() as conn:
                    await conn.execute(
                        text("DELETE FROM analysis_results WHERE id = :rid"),
                        {"rid": str(result_id)},
                    )


async def test_stage2_chatbot_cm_persists_unknown_knowledge_event() -> None:
    """The non-analysis path's ownerless backlog insert persists via exit commit.

    ``record_unknown_knowledge_event`` only ``add``s (no commit); under
    ``get_async_session`` today nothing committed it. The new CM commits at exit,
    and ``chatbot_unknown_knowledge_events`` is admitted by the 0041 service
    policy (USING/WITH CHECK true), so no GUC is required for the insert itself.
    """
    settings = get_settings()
    user = _user()
    marker = f"stage2-unknown-{uuid.uuid4()}"
    event_id: uuid.UUID | None = None
    async with _stage2_engines() as (admin, app):
        try:
            app_sessionmaker = async_sessionmaker(app, expire_on_commit=False)
            async with app_sessionmaker() as session:  # noqa: SIM117
                async with rls_request_transaction_allow_inner_commit(session, user, settings):
                    await _assert_request_role_enforces_rls(session)
                    event = build_unknown_knowledge_event(
                        message=marker,
                        answerability="unknown_no_reviewed_source",
                        retrieval_warnings=["no reviewed source"],
                    )
                    record_unknown_knowledge_event(session, event)
                    await session.flush()
                    event_id = event.id

            async with admin.connect() as conn:
                persisted = (
                    await conn.execute(
                        text(
                            "SELECT count(*) FROM chatbot_unknown_knowledge_events WHERE id = :eid"
                        ),
                        {"eid": str(event_id)},
                    )
                ).scalar_one()
                assert persisted == 1
        finally:
            if event_id is not None:
                async with admin.begin() as conn:
                    await conn.execute(
                        text("DELETE FROM chatbot_unknown_knowledge_events WHERE id = :eid"),
                        {"eid": str(event_id)},
                    )
