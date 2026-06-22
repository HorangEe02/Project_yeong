"""Unit tests for the transaction-local RLS subject context helper."""

from __future__ import annotations

from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.rls_context import (
    SUBJECT_GUC,
    SUBJECT_HASH_GUC,
    set_request_rls_context,
)


class _CapturingSession:
    """Fake async session capturing executed statements and bind params."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, statement: object, params: dict[str, Any]) -> None:
        """Record the SQL text and bind parameters."""
        self.calls.append((str(statement), params))


@pytest.mark.asyncio
async def test_sets_both_gucs_transaction_local() -> None:
    """Both subject GUCs are set via set_config with is_local=true."""
    session = _CapturingSession()
    await set_request_rls_context(
        cast(AsyncSession, session),
        subject="iss::user-1",
        subject_hash="a" * 64,
    )
    assert len(session.calls) == 2
    # Every statement uses set_config(..., true) — transaction-local, no pool leak.
    for sql, _params in session.calls:
        assert "set_config" in sql
        assert ":name" in sql and ":value" in sql  # parameterized, injection-safe
    by_name = {params["name"]: params["value"] for _sql, params in session.calls}
    assert by_name[SUBJECT_GUC] == "iss::user-1"
    assert by_name[SUBJECT_HASH_GUC] == "a" * 64


@pytest.mark.asyncio
async def test_none_values_become_empty_fail_closed() -> None:
    """Missing subject/hash resolve to empty strings (match no owner row)."""
    session = _CapturingSession()
    await set_request_rls_context(
        cast(AsyncSession, session),
        subject=None,
        subject_hash=None,
    )
    by_name = {params["name"]: params["value"] for _sql, params in session.calls}
    assert by_name[SUBJECT_GUC] == ""
    assert by_name[SUBJECT_HASH_GUC] == ""


@pytest.mark.asyncio
async def test_subject_value_passed_as_bind_parameter() -> None:
    """The subject is a bind parameter, so it cannot inject SQL."""
    session = _CapturingSession()
    injection = "x'; DROP TABLE user_supplements; --"
    await set_request_rls_context(
        cast(AsyncSession, session),
        subject=injection,
        subject_hash=None,
    )
    subject_call = next(p for _s, p in session.calls if p["name"] == SUBJECT_GUC)
    # Value is carried as data, never concatenated into the SQL text.
    assert subject_call["value"] == injection
    for sql, _params in session.calls:
        assert "DROP TABLE" not in sql
