"""Transaction-local RLS subject context for the request role.

Building block for the FORCE RLS rollout
(docs/2026-05-31-force-rls-rollout-design.md §3.2). When the request path connects
as the non-superuser ``lemon_app`` role, the owner-scoped policies created in
migration 0023b read the current subject from transaction-local GUCs. This module
sets those GUCs.

Inert until wired: nothing calls this yet, and while the app still connects as the
superuser ``lemon`` the GUCs are simply ignored (superuser bypasses RLS). The
approved staging step will call :func:`set_request_rls_context` at the start of
each request transaction, then flip ``DATABASE_URL`` to ``lemon_app``.

Safety:
- Uses ``set_config(name, value, is_local=true)`` so the setting is scoped to the
  current transaction and released on commit/rollback — no connection-pool leak.
- ``set_config`` takes the value as a bind parameter, so the subject string cannot
  inject SQL even though GUC names cannot be parameterized.
- Must be called *inside* a transaction (``async with session.begin()``); outside
  one, ``set_config(..., true)`` has no lasting effect.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# GUC names referenced by the 0023b policies. Keep in sync with that migration.
SUBJECT_GUC = "app.current_subject"
SUBJECT_HASH_GUC = "app.current_subject_hash"


async def set_request_rls_context(
    session: AsyncSession,
    *,
    subject: str | None,
    subject_hash: str | None,
) -> None:
    """Set transaction-local RLS subject GUCs for the current request.

    Args:
        session: Active async session, already inside a transaction.
        subject: Issuer-qualified plaintext owner subject, or ``None``.
        subject_hash: HMAC owner-subject hash, or ``None``.

    Notes:
        ``None``/missing values resolve to empty strings. With the owner policies,
        an empty subject matches no row → fail-closed (0 rows), never a leak.
    """
    await session.execute(
        text("SELECT set_config(:name, :value, true)"),
        {"name": SUBJECT_GUC, "value": subject or ""},
    )
    await session.execute(
        text("SELECT set_config(:name, :value, true)"),
        {"name": SUBJECT_HASH_GUC, "value": subject_hash or ""},
    )
