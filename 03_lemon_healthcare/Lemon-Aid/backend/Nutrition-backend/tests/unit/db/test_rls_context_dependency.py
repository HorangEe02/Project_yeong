"""Unit tests for the RLS-context request session dependency (Stage-1 seam)."""

from __future__ import annotations

from typing import Any

import pytest
from src.config import Settings
from src.db import dependencies as deps
from src.db.dependencies import (
    get_rls_context_session,
    rls_request_transaction,
    rls_request_transaction_allow_inner_commit,
)
from src.db.rls_context import SUBJECT_GUC, SUBJECT_HASH_GUC
from src.db.tx import REQUEST_MANAGED_TX
from src.security.auth import AuthenticatedUser


class _FakeTransaction:
    """Fake async transaction context manager."""

    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeTransaction:
        self._session.begun = True
        return self

    async def __aexit__(self, *exc: object) -> bool:
        if exc and exc[0] is not None:
            self._session.rolled_back = True
        else:
            self._session.committed = True
        return False


class _FakeSession:
    """Fake async session recording set_config executions."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.begun = False
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self.info: dict[str, Any] = {}

    async def execute(self, statement: object, params: dict[str, Any]) -> None:
        """Record an executed statement and its bind params."""
        self.calls.append((str(statement), params))

    def begin(self) -> _FakeTransaction:
        """Return a fake transaction context manager."""
        return _FakeTransaction(self)

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        self.closed = True
        return False


def _fake_sessionmaker(session: _FakeSession) -> Any:
    """Return a callable yielding the given fake session."""

    def _maker() -> _FakeSession:
        return session

    return _maker


@pytest.mark.asyncio
async def test_get_rls_context_session_sets_owner_gucs(monkeypatch: pytest.MonkeyPatch) -> None:
    """The dependency opens a transaction and sets both owner GUCs from the user."""
    session = _FakeSession()
    monkeypatch.setattr(deps, "get_sessionmaker", lambda: _fake_sessionmaker(session))
    user = AuthenticatedUser(subject="user-1", issuer="https://issuer.example/")
    settings = Settings(_env_file=None)

    agen = get_rls_context_session(user, settings)
    yielded = await agen.__anext__()

    assert yielded is session
    assert session.begun is True  # GUCs are set inside a transaction
    # Subject GUC is set before the hash GUC (set_request_rls_context order).
    names = [params["name"] for _sql, params in session.calls]
    assert names == ["app.current_subject", "app.current_subject_hash"]
    values = {params["name"]: params["value"] for _sql, params in session.calls}
    assert values["app.current_subject"] == "https://issuer.example/::user-1"
    assert values["app.current_subject_hash"]  # non-empty HMAC
    assert values["app.current_subject_hash"] != values["app.current_subject"]

    with pytest.raises(StopAsyncIteration):
        await agen.__anext__()
    assert session.committed is True
    assert session.closed is True


@pytest.mark.asyncio
async def test_get_rls_context_session_rejects_empty_subject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An invalid (empty) subject fails closed before any session work."""
    session = _FakeSession()
    monkeypatch.setattr(deps, "get_sessionmaker", lambda: _fake_sessionmaker(session))
    user = AuthenticatedUser(subject="", issuer="https://issuer.example/")
    settings = Settings(_env_file=None)

    agen = get_rls_context_session(user, settings)
    with pytest.raises(ValueError, match="owner subject"):
        await agen.__anext__()
    assert session.calls == []  # no GUCs set when the subject is invalid


@pytest.mark.asyncio
async def test_rls_request_transaction_sets_gucs_marks_and_commits() -> None:
    """The route-owned helper opens a tx, sets owner GUCs, marks request-managed."""
    session = _FakeSession()
    user = AuthenticatedUser(subject="user-1", issuer="https://issuer.example/")
    settings = Settings(_env_file=None)

    async with rls_request_transaction(session, user, settings) as yielded:  # type: ignore[arg-type]
        assert yielded is session
        assert session.begun is True
        # Owner-scoped writes participate (flush only) while inside the block.
        assert session.info.get(REQUEST_MANAGED_TX) is True
        names = [params["name"] for _sql, params in session.calls]
        assert names == ["app.current_subject", "app.current_subject_hash"]
        values = {params["name"]: params["value"] for _sql, params in session.calls}
        assert values["app.current_subject"] == "https://issuer.example/::user-1"
        assert values["app.current_subject_hash"]

    # Commit happens at block exit (before the route returns); marker cleared.
    assert session.committed is True
    assert REQUEST_MANAGED_TX not in session.info


@pytest.mark.asyncio
async def test_rls_request_transaction_clears_marker_on_error() -> None:
    """An error inside the block propagates and still clears the request marker."""
    session = _FakeSession()
    user = AuthenticatedUser(subject="user-1", issuer="https://issuer.example/")
    settings = Settings(_env_file=None)

    with pytest.raises(RuntimeError, match="boom"):
        async with rls_request_transaction(session, user, settings):  # type: ignore[arg-type]
            assert session.info.get(REQUEST_MANAGED_TX) is True
            raise RuntimeError("boom")

    assert REQUEST_MANAGED_TX not in session.info
    assert session.rolled_back is True  # the request transaction rolls back on error
    assert session.committed is False


class _FakeConnection:
    """Fake sync Core connection recording set_config executions in after_begin."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute(self, statement: object, params: dict[str, Any]) -> None:
        """Record an executed statement and its bind params (sync, like Core)."""
        self.calls.append((str(statement), params))


class _AllowInnerCommitSession:
    """Fake AsyncSession for the inner-commit-tolerant CM.

    Mirrors the surface the CM touches: ``sync_session`` (event target),
    ``info`` (marker), ``in_transaction()``, and async ``commit``/``rollback``.
    """

    def __init__(self, *, in_transaction: bool = True) -> None:
        self.sync_session = object()
        self.info: dict[str, Any] = {}
        self.committed = False
        self.rolled_back = False
        self._in_transaction = in_transaction

    def in_transaction(self) -> bool:
        """Report whether a transaction is open at CM exit."""
        return self._in_transaction

    async def commit(self) -> None:
        """Record a commit and close the transaction."""
        self.committed = True
        self._in_transaction = False

    async def rollback(self) -> None:
        """Record a rollback and close the transaction."""
        self.rolled_back = True
        self._in_transaction = False


def _capture_events(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Replace deps.event.listen/remove with capturing fakes.

    The after_begin listener can only be registered on a real SQLAlchemy
    Session, so unit tests capture the registered handler instead and invoke it
    directly; the real event wiring is proven by the Stage-2 integration test.
    """
    captured: dict[str, Any] = {"listen": [], "remove": []}

    def _listen(target: object, identifier: str, fn: Any) -> None:
        captured["listen"].append((target, identifier, fn))

    def _remove(target: object, identifier: str, fn: Any) -> None:
        captured["remove"].append((target, identifier, fn))

    monkeypatch.setattr(deps.event, "listen", _listen)
    monkeypatch.setattr(deps.event, "remove", _remove)
    return captured


@pytest.mark.asyncio
async def test_allow_inner_commit_marks_registers_listener_and_commits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CM marks request-managed, registers after_begin, and commits at exit."""
    captured = _capture_events(monkeypatch)
    session = _AllowInnerCommitSession(in_transaction=True)
    user = AuthenticatedUser(subject="user-1", issuer="https://issuer.example/")
    settings = Settings(_env_file=None)

    async with rls_request_transaction_allow_inner_commit(session, user, settings) as yielded:  # type: ignore[arg-type]
        assert yielded is session
        assert session.info.get(REQUEST_MANAGED_TX) is True
        # Listener registered on the sync session for the after_begin lifecycle.
        assert len(captured["listen"]) == 1
        target, identifier, _fn = captured["listen"][0]
        assert target is session.sync_session
        assert identifier == "after_begin"

    # Open transaction at exit -> committed; marker cleared; listener removed.
    assert session.committed is True
    assert session.rolled_back is False
    assert REQUEST_MANAGED_TX not in session.info
    assert len(captured["remove"]) == 1
    assert captured["remove"][0] == captured["listen"][0]


@pytest.mark.asyncio
async def test_allow_inner_commit_listener_reapplies_gucs_via_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The registered after_begin handler sets both is_local GUCs on the connection."""
    captured = _capture_events(monkeypatch)
    session = _AllowInnerCommitSession(in_transaction=True)
    user = AuthenticatedUser(subject="user-1", issuer="https://issuer.example/")
    settings = Settings(_env_file=None)

    async with rls_request_transaction_allow_inner_commit(session, user, settings):  # type: ignore[arg-type]
        _target, _id, handler = captured["listen"][0]
        connection = _FakeConnection()
        # Simulate a transaction begin/autobegin firing the listener.
        handler(session.sync_session, object(), connection)

    names = [params["name"] for _sql, params in connection.calls]
    assert names == [SUBJECT_GUC, SUBJECT_HASH_GUC]
    values = {params["name"]: params["value"] for _sql, params in connection.calls}
    assert values[SUBJECT_GUC] == "https://issuer.example/::user-1"
    assert values[SUBJECT_HASH_GUC]  # non-empty HMAC
    assert values[SUBJECT_HASH_GUC] != values[SUBJECT_GUC]
    # is_local GUC: third set_config arg is the literal ``true`` (no pool leak).
    assert all("true" in sql for sql, _params in connection.calls)


@pytest.mark.asyncio
async def test_allow_inner_commit_rolls_back_and_removes_listener_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An error rolls back the open transaction, clears the marker, removes listener."""
    captured = _capture_events(monkeypatch)
    session = _AllowInnerCommitSession(in_transaction=True)
    user = AuthenticatedUser(subject="user-1", issuer="https://issuer.example/")
    settings = Settings(_env_file=None)

    with pytest.raises(RuntimeError, match="boom"):
        async with rls_request_transaction_allow_inner_commit(session, user, settings):  # type: ignore[arg-type]
            assert session.info.get(REQUEST_MANAGED_TX) is True
            raise RuntimeError("boom")

    assert session.rolled_back is True
    assert session.committed is False
    assert REQUEST_MANAGED_TX not in session.info
    assert len(captured["remove"]) == 1


@pytest.mark.asyncio
async def test_allow_inner_commit_skips_commit_without_open_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the inner commit already closed the tx, exit must not double-commit."""
    captured = _capture_events(monkeypatch)
    session = _AllowInnerCommitSession(in_transaction=False)
    user = AuthenticatedUser(subject="user-1", issuer="https://issuer.example/")
    settings = Settings(_env_file=None)

    async with rls_request_transaction_allow_inner_commit(session, user, settings):  # type: ignore[arg-type]
        pass

    assert session.committed is False  # no open transaction -> nothing to commit
    assert session.rolled_back is False
    assert REQUEST_MANAGED_TX not in session.info
    assert len(captured["remove"]) == 1
