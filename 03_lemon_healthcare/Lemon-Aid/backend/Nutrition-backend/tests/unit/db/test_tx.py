"""Unit tests for the ambient-transaction seam (src/db/tx.py)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from src.db.tx import REQUEST_MANAGED_TX, persist_scope, request_manages_transaction


class _FakeSession:
    """Records flush/commit/rollback calls and carries an info dict."""

    def __init__(self, *, request_managed: bool = False) -> None:
        self.info: dict[str, object] = {REQUEST_MANAGED_TX: True} if request_managed else {}
        self.calls: list[str] = []

    async def flush(self) -> None:
        self.calls.append("flush")

    async def commit(self) -> None:
        self.calls.append("commit")

    async def rollback(self) -> None:
        self.calls.append("rollback")


def test_request_manages_transaction_reads_marker() -> None:
    assert request_manages_transaction(_FakeSession(request_managed=True)) is True
    assert request_manages_transaction(_FakeSession()) is False
    # Guard: a partial double without a dict ``.info`` reads as legacy
    # (not request-managed) rather than raising AttributeError.
    assert request_manages_transaction(object()) is False  # type: ignore[arg-type]
    assert request_manages_transaction(SimpleNamespace(info=None)) is False  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_participate_mode_flushes_and_never_commits() -> None:
    session = _FakeSession(request_managed=True)
    async with persist_scope(session) as scoped:
        assert scoped is session
        session.calls.append("work")
    assert session.calls == ["work", "flush"]
    assert "commit" not in session.calls
    assert "rollback" not in session.calls


@pytest.mark.asyncio
async def test_participate_mode_exception_leaves_rollback_to_dependency() -> None:
    session = _FakeSession(request_managed=True)
    with pytest.raises(ValueError, match="boom"):
        async with persist_scope(session):
            raise ValueError("boom")
    # The request dependency owns rollback; the scope must not touch the tx.
    assert session.calls == []


@pytest.mark.asyncio
async def test_own_mode_outermost_flushes_then_commits() -> None:
    session = _FakeSession()
    async with persist_scope(session):
        session.calls.append("work")
    assert session.calls == ["work", "flush", "commit"]


@pytest.mark.asyncio
async def test_own_mode_nested_commits_once_at_outermost() -> None:
    session = _FakeSession()
    async with persist_scope(session):
        session.calls.append("outer-start")
        async with persist_scope(session):
            session.calls.append("inner")
        session.calls.append("outer-end")
    assert session.calls == [
        "outer-start",
        "inner",
        "flush",  # inner scope: flush only, no commit
        "outer-end",
        "flush",  # outer scope
        "commit",  # single commit at the outermost own scope
    ]
    assert session.calls.count("commit") == 1


@pytest.mark.asyncio
async def test_own_mode_exception_rolls_back_and_reraises() -> None:
    session = _FakeSession()
    with pytest.raises(ValueError, match="boom"):
        async with persist_scope(session):
            raise ValueError("boom")
    assert session.calls == ["rollback"]
    assert "commit" not in session.calls


@pytest.mark.asyncio
async def test_own_mode_nested_exception_rolls_back_once() -> None:
    session = _FakeSession()
    with pytest.raises(ValueError, match="boom"):
        async with persist_scope(session):
            async with persist_scope(session):
                raise ValueError("boom")
    # Only the outermost own scope rolls back; inner re-raises without touching tx.
    assert session.calls == ["rollback"]
    assert session.calls.count("rollback") == 1
