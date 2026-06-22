"""Ambient-transaction seam for the FORCE RLS rollout (Stage-2 enablement).

Authority: outputs/todo-list/2026-06-14/2026-06-14-ambient-transaction-refactor-plan.md

Background
----------
``get_async_session`` opens no transaction and never commits; write services
historically persist via their own ``session.add(...) + commit()`` or
``async with session.begin()``. ``get_rls_context_session`` instead opens one
request-scoped transaction and sets *transaction-local* RLS GUCs
(``app.current_subject*``, ``set_config(..., is_local=true)``) that the 0023b
owner policies read. Because those GUCs live only for that transaction, any
service that commits or opens its own transaction mid-request would drop them
(or raise, since ``begin()`` fails when a transaction is already open).

Design
------
A single marker decides the transaction ownership per request:

* ``get_rls_context_session`` stamps ``session.info[REQUEST_MANAGED_TX] = True``.
* :func:`persist_scope` then **participates** (flush only, never commit/begin)
  so the GUCs survive to the dependency's commit-on-exit.
* Without the marker (legacy ``get_async_session`` routes) :func:`persist_scope`
  **owns** the transaction, reproducing today's behavior byte-for-byte: the
  *outermost* own scope commits; nested own scopes only flush, so one logical
  unit stays a single transaction (re-entrancy safety).

This lets owner-scoped routes adopt ``get_rls_context_session`` incrementally
without touching un-migrated routes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

# Set by get_rls_context_session on the per-request session; read here and by
# the ambient-aware audit writer. Never set by get_async_session.
REQUEST_MANAGED_TX = "request_managed_tx"

# Internal own-mode nesting depth so only the outermost own scope commits.
_OWN_DEPTH = "_persist_scope_own_depth"


def request_manages_transaction(session: AsyncSession) -> bool:
    """Return whether the request dependency owns this session's transaction.

    Args:
        session: The per-request async session.

    Returns:
        True when ``get_rls_context_session`` opened the request transaction
        (so callees must participate, not commit); False for legacy
        ``get_async_session`` routes.

    Notes:
        A real ``AsyncSession`` always exposes ``.info`` (a dict), so the guard
        below never triggers in production; it only makes an unmarked session —
        including a partial test double without ``.info`` — read as legacy
        (not request-managed), which is the correct default.
    """
    info = getattr(session, "info", None)
    return bool(info.get(REQUEST_MANAGED_TX, False)) if isinstance(info, dict) else False


@asynccontextmanager
async def persist_scope(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """Run a write block under the correct transaction-ownership mode.

    * Request-managed (RLS) sessions: participate only — flush at scope exit and
      never commit/begin, so the transaction-local GUCs survive to the
      dependency's commit. Nesting is naturally safe (no commit ever happens).
    * Legacy sessions: own the transaction — the outermost scope flushes and
      commits (reproducing the historical ``add + commit`` / ``async with
      session.begin()`` behavior, including committing an autobegun read
      transaction); nested own scopes only flush so the unit stays atomic and
      no inner commit splits it.

    Args:
        session: The per-request async session.

    Yields:
        The same session, for ``session.add(...)`` / mutations inside the block.

    Notes:
        In participate mode there is no post-commit moment, so any
        ``session.refresh(...)`` for server defaults must run inside this scope
        after the flush (or be dropped, since ``expire_on_commit=False`` keeps
        Python-set attributes).
    """
    if request_manages_transaction(session):
        # PARTICIPATE: the request dependency owns begin + commit.
        yield session
        await session.flush()
        return

    # OWN (legacy): the outermost scope commits; nested scopes only flush.
    depth = session.info.get(_OWN_DEPTH, 0)
    session.info[_OWN_DEPTH] = depth + 1
    try:
        yield session
        await session.flush()
        if depth == 0:
            await session.commit()
    except Exception:
        if depth == 0:
            await session.rollback()
        raise
    finally:
        session.info[_OWN_DEPTH] = depth
