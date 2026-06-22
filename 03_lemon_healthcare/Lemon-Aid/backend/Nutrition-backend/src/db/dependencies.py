"""FastAPI database dependency providers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings, get_settings
from src.db.rls_context import SUBJECT_GUC, SUBJECT_HASH_GUC, set_request_rls_context
from src.db.session import get_sessionmaker
from src.db.tx import REQUEST_MANAGED_TX
from src.security.auth import AuthenticatedUser, require_current_user
from src.security.privacy import hash_actor_subject
from src.security.subjects import build_owner_subject


async def get_async_session() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped async database session.

    This dependency does not auto-commit. Write operations must use an
    explicit service-level transaction such as ``async with session.begin()``.

    Yields:
        SQLAlchemy AsyncSession bound to the configured async engine.
    """
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        yield session


async def get_rls_context_session(
    current_user: Annotated[AuthenticatedUser, Depends(require_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped session inside a transaction with RLS GUCs set.

    This is the FORCE RLS rollout's Stage-1 request seam
    (docs/2026-05-31-force-rls-rollout-design.md): it opens a single
    request-scoped transaction and sets the owner-subject GUCs that the
    migration 0023b owner policies read. While the app still connects as the
    superuser ``lemon`` the GUCs are ignored (superuser bypasses RLS), so
    adopting this dependency is safe before Stage-2 flips ``DATABASE_URL`` to the
    non-superuser ``lemon_app`` role.

    Adoption contract: a route using this session relies on the request-scoped
    transaction opened here and must NOT call ``session.begin()`` or
    ``session.commit()`` itself — committing mid-request releases the
    transaction-local GUCs. Routes that manage their own transactions keep using
    ``get_async_session`` until they are migrated as part of the staged rollout.

    Args:
        current_user: Authenticated principal resolved before the route runs.
        settings: Runtime settings supplying the privacy hash secret.

    Yields:
        AsyncSession with ``app.current_subject`` / ``app.current_subject_hash``
        set for the owner-scoped RLS policies. A missing subject is impossible
        here because auth has already validated it; the policies still fail
        closed (empty GUC matches no row) as a defensive default.
    """
    owner_subject = build_owner_subject(current_user)
    subject_hash = hash_actor_subject(current_user, settings)
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session, session.begin():
        await set_request_rls_context(
            session,
            subject=owner_subject,
            subject_hash=subject_hash,
        )
        # Mark this request as owning the transaction so write/audit services
        # participate (flush only) instead of committing — committing mid-request
        # would drop the transaction-local RLS GUCs set above. See src/db/tx.py.
        session.info[REQUEST_MANAGED_TX] = True
        yield session


@asynccontextmanager
async def rls_request_transaction(
    session: AsyncSession,
    current_user: AuthenticatedUser,
    settings: Settings,
) -> AsyncIterator[AsyncSession]:
    """Open a route-owned RLS transaction that commits before the route returns.

    Same owner-scoped, single-transaction semantics as
    :func:`get_rls_context_session`, but the request transaction is opened and
    committed *inside the route body* rather than at dependency teardown. This
    is required for routes that schedule post-commit work via FastAPI
    ``BackgroundTasks``: Starlette runs background tasks **before** the
    yield-dependency teardown, so a ``get_rls_context_session`` route (which
    commits at teardown) would run the background task before its writes are
    durable. Committing in the route body — which happens before the response is
    sent and therefore before the background task runs — keeps the deferred
    fresh-session work (e.g. learning image storage) safely post-commit.

    Use with ``get_async_session`` (which opens no transaction). The wrapped
    block must perform all owner-scoped reads/writes via ``persist_scope`` and
    must not call ``session.commit()``/``session.begin()`` itself; the context
    manager owns begin + commit (rollback on error), and clears the
    request-managed marker on exit so any later use of the session reverts to
    legacy ownership.

    Args:
        session: Request-scoped async session from ``get_async_session``.
        current_user: Authenticated principal whose owner subject scopes the RLS GUCs.
        settings: Runtime settings supplying the privacy hash secret.

    Yields:
        The same session, inside an open transaction with owner-subject GUCs set.
    """
    owner_subject = build_owner_subject(current_user)
    subject_hash = hash_actor_subject(current_user, settings)
    async with session.begin():
        await set_request_rls_context(
            session,
            subject=owner_subject,
            subject_hash=subject_hash,
        )
        session.info[REQUEST_MANAGED_TX] = True
        try:
            yield session
        finally:
            session.info.pop(REQUEST_MANAGED_TX, None)


@asynccontextmanager
async def rls_request_transaction_allow_inner_commit(
    session: AsyncSession,
    current_user: AuthenticatedUser,
    settings: Settings,
) -> AsyncIterator[AsyncSession]:
    """Route-owned RLS transaction that tolerates a callee's mid-request commit.

    Same goal as :func:`rls_request_transaction` — owner-subject GUCs set so the
    0023b owner policies admit reads/writes once ``DATABASE_URL`` flips to the
    non-superuser ``lemon_app`` role — but it survives a DO-NOT-TOUCH callee that
    commits *and then refreshes* on the request session
    (``store_app_health_analysis_result``, app_health_analysis.py: ``add → commit
    → refresh``). Two problems that ``rls_request_transaction`` cannot handle:

    * ``async with session.begin()`` is unusable: the callee's inner ``commit()``
      closes that transaction, so the begin-block's exit raises ``Can't operate
      on closed transaction inside context manager``.
    * The GUCs are transaction-local (``set_config(..., is_local=true)``), so the
      inner commit releases them; the callee's subsequent ``refresh()`` autobegins
      a *new* transaction whose RLS read then matches 0 rows and raises
      ``Could not refresh instance`` under FORCE RLS.

    The fix keeps the leak-free is_local GUC but re-applies it on **every**
    transaction begin via an ``after_begin`` listener — so the request's first
    autobegun transaction, the callee's refresh transaction, and any later
    autobegin all carry the subject. Transactions are managed manually (no
    begin-block): the block commits at exit only when a transaction is still open
    (rolls back on error), which covers both the non-analysis path (one
    transaction spanning reads + the unknown-backlog insert) and the analysis
    path (the callee committed its own row; the trailing read-only refresh
    transaction is committed harmlessly).

    Use with ``get_async_session`` (which opens no transaction). The listener is
    scoped to this session and removed on exit, and is_local guarantees nothing
    survives onto the pooled connection.

    Args:
        session: Request-scoped async session from ``get_async_session``.
        current_user: Authenticated principal whose owner subject scopes the GUCs.
        settings: Runtime settings supplying the privacy hash secret.

    Yields:
        The same session, with owner-subject GUCs re-applied on every begin.
    """
    owner_subject = build_owner_subject(current_user)
    subject_hash = hash_actor_subject(current_user, settings)

    def _reapply_rls_guc(_session: object, _transaction: object, connection: Connection) -> None:
        # Fires on every (auto)begin. Use the passed sync connection — never the
        # AsyncSession — per the after_begin contract. is_local=true keeps the
        # GUC scoped to this transaction (released at its end; no pool leak).
        connection.execute(
            text("SELECT set_config(:name, :value, true)"),
            {"name": SUBJECT_GUC, "value": owner_subject or ""},
        )
        connection.execute(
            text("SELECT set_config(:name, :value, true)"),
            {"name": SUBJECT_HASH_GUC, "value": subject_hash or ""},
        )

    sync_session = session.sync_session
    event.listen(sync_session, "after_begin", _reapply_rls_guc)
    session.info[REQUEST_MANAGED_TX] = True
    try:
        yield session
    except BaseException:
        if session.in_transaction():
            await session.rollback()
        raise
    else:
        if session.in_transaction():
            await session.commit()
    finally:
        session.info.pop(REQUEST_MANAGED_TX, None)
        event.remove(sync_session, "after_begin", _reapply_rls_guc)
