"""Unit tests for ambient-transaction-aware audit writing (services/privacy.py).

Verifies record_audit_event's two branches without a DB/Request: legacy
own-commit (marker absent) and request-managed out-of-band (marker present →
privileged audit engine). _build_audit_log / _write_audit_out_of_band are
monkeypatched so the control flow is asserted in isolation.
"""

from __future__ import annotations

import pytest
from src.db.tx import REQUEST_MANAGED_TX
from src.services import privacy


class _FakeSession:
    def __init__(self, *, request_managed: bool = False) -> None:
        self.info: dict[str, object] = {REQUEST_MANAGED_TX: True} if request_managed else {}
        self.calls: list[str] = []

    def add(self, _obj: object) -> None:
        self.calls.append("add")

    async def flush(self) -> None:
        self.calls.append("flush")

    async def commit(self) -> None:
        self.calls.append("commit")


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch) -> tuple[object, list[object]]:
    sentinel = object()
    monkeypatch.setattr(privacy, "_build_audit_log", lambda **_kw: sentinel)
    out_of_band: list[object] = []

    async def _fake_out_of_band(audit_log: object) -> object:
        out_of_band.append(audit_log)
        return audit_log

    monkeypatch.setattr(privacy, "_write_audit_out_of_band", _fake_out_of_band)
    return sentinel, out_of_band


async def _record(session: _FakeSession) -> object:
    return await privacy.record_audit_event(
        session=session,  # type: ignore[arg-type]
        user=object(),  # type: ignore[arg-type]
        action="action",
        resource_type="resource",
        resource_id=None,
        outcome="success",
        request=object(),  # type: ignore[arg-type]
        settings=object(),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_legacy_session_adds_then_commits(
    patched: tuple[object, list[object]],
) -> None:
    sentinel, out_of_band = patched
    session = _FakeSession()
    result = await _record(session)
    assert result is sentinel
    assert session.calls == ["add", "commit"]
    assert out_of_band == []


@pytest.mark.asyncio
async def test_request_managed_writes_audit_out_of_band(
    patched: tuple[object, list[object]],
) -> None:
    sentinel, out_of_band = patched
    session = _FakeSession(request_managed=True)
    result = await _record(session)
    assert result is sentinel
    # The audit rides the privileged out-of-band engine; the request (lemon_app)
    # session — which cannot write audit_logs — is never touched.
    assert out_of_band == [sentinel]
    assert session.calls == []
